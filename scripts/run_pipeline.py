"""Phase 1 + Phase 2 统一流水线编排。

Phase 1: Docker 基础设施启动与健康检查
Phase 2: 素材处理（转换 → 校验 → 索引）→ 图谱 → 验收
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from configs.settings import GRAPH_ENABLED, REDIS_HOST, REDIS_PORT

# Phase 1 核心服务（索引/图谱/RQ 必需）
PHASE1_CORE_SERVICES = ["qdrant", "meilisearch", "redis", "neo4j"]
# Phase 1 完整栈（指南标准）
PHASE1_FULL_SERVICES = PHASE1_CORE_SERVICES + ["postgres", "minio", "rq-dashboard"]

PHASE1_HTTP_CHECKS = [
    ("Qdrant", "http://127.0.0.1:6333/healthz"),
    ("Meilisearch", "http://127.0.0.1:7700/health"),
    ("Neo4j Browser", "http://127.0.0.1:7474"),
    ("MinIO Console", "http://127.0.0.1:9001"),
    ("RQ Dashboard", "http://127.0.0.1:9181"),
]


def run_cmd(cmd: list[str], cwd: Path | None = None) -> int:
    print(f"\n>>> {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=cwd or ROOT)


def wait_http(name: str, url: str, timeout: float = 120.0, interval: float = 2.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = httpx.get(url, timeout=3.0)
            if resp.status_code < 500:
                print(f"[Phase1 OK] {name}: {url}")
                return True
        except Exception:
            pass
        time.sleep(interval)
    print(f"[Phase1 WARN] {name} 未就绪: {url}")
    return False


def check_redis() -> bool:
    try:
        import redis

        client = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, socket_connect_timeout=3, decode_responses=True
        )
        client.ping()
        print(f"[Phase1 OK] Redis: {REDIS_HOST}:{REDIS_PORT}")
        return True
    except Exception as exc:
        print(f"[Phase1 WARN] Redis 不可用: {exc}")
        return False


def run_phase1(*, skip_docker: bool = False, full_stack: bool = False) -> dict:
    """Phase 1: 启动 Docker 并等待服务就绪。"""
    print("\n========== Phase 1: 基础设施 ==========")
    services = PHASE1_FULL_SERVICES if full_stack else PHASE1_CORE_SERVICES
    result = {"services": services, "checks": {}}

    if not skip_docker:
        code = run_cmd(["docker", "compose", "up", "-d", *services])
        if code != 0:
            result["ok"] = False
            result["error"] = "docker compose up failed"
            return result

    for name, url in PHASE1_HTTP_CHECKS:
        if name == "MinIO Console" and "minio" not in services:
            continue
        if name == "RQ Dashboard" and "rq-dashboard" not in services:
            continue
        ok = wait_http(name, url, timeout=90 if name != "Neo4j Browser" else 120)
        result["checks"][name] = ok

    result["checks"]["Redis"] = check_redis()
    core_ok = (
        result["checks"].get("Qdrant", False)
        and result["checks"].get("Meilisearch", False)
        and result["checks"].get("Redis", False)
    )
    result["ok"] = core_ok
    return result


def run_phase2(
    *,
    force: bool = False,
    use_queue: bool = False,
    skip_graph: bool = False,
    skip_eval: bool = False,
    changed_files: list[str] | None = None,
) -> dict:
    """Phase 2: 素材处理流水线 + 图谱 + 验收。"""
    print("\n========== Phase 2: 素材处理流水线 ==========")
    from services.pipeline.main import enqueue_changed_files, process_file, run_batch, run_worker
    from services.indexer.indexer_service import IndexerService

    result: dict = {"indexed": [], "graph": None, "verify": None, "eval": None}

    if use_queue:
        job_ids = enqueue_changed_files(changed_files=changed_files)
        if force and not job_ids:
            # force 全量：直接同步处理
            batch = run_batch(force=True, use_queue=False)
            result["indexed"] = batch
        else:
            print(f"[Phase2] 已入队 {len(job_ids)} 个任务，启动 Worker 消费…")
            run_worker(burst=True)
            result["queued_jobs"] = job_ids
    else:
        if changed_files:
            indexer = IndexerService()
            indexer.init_all()
            batch = [process_file(fp, indexer=indexer) for fp in changed_files if Path(fp).exists()]
        else:
            batch = run_batch(force=force, use_queue=False)
        result["indexed"] = batch

    failed = [r for r in result.get("indexed", []) if isinstance(r, dict) and not r.get("success", True)]
    if failed and not use_queue:
        result["ok"] = False
        result["error"] = f"{len(failed)} 个文件处理失败"
        return result

    if not skip_graph and GRAPH_ENABLED:
        print("\n[Phase2] 重建知识图谱…")
        from scripts.rebuild_graph import rebuild_graph

        graph_summary = rebuild_graph()
        result["graph"] = graph_summary
        if graph_summary.get("errors"):
            print(f"[Phase2 WARN] 图谱部分文件校验失败: {len(graph_summary['errors'])}")

    print("\n[Phase2] 运行验收…")
    from scripts.verify_phase2 import validate_vault, check_rq
    from configs.settings import VAULT_DIR

    vault = ROOT / VAULT_DIR if not Path(VAULT_DIR).is_absolute() else Path(VAULT_DIR)
    result["verify"] = {
        "vault_validation": validate_vault(vault),
        "rq": check_rq(),
    }

    if not skip_eval:
        from eval.run_eval import main as eval_main

        print("\n[Phase2] 检索评估（无 LLM）…")
        eval_code = eval_main(["--retrieval-only"])
        eval_path = ROOT / "eval" / "results" / "eval_latest.json"
        result["eval"] = {"exit_code": eval_code, "output": str(eval_path)}
        if eval_path.exists():
            result["eval"]["summary"] = json.loads(eval_path.read_text(encoding="utf-8"))

    v_ok = result["verify"]["vault_validation"].get("pass", False)
    rq_ok = result["verify"]["rq"].get("ok", False)
    result["ok"] = v_ok and rq_ok
    return result


def run_pipeline(
    *,
    skip_docker: bool = False,
    full_stack: bool = False,
    phase1_only: bool = False,
    phase2_only: bool = False,
    force: bool = False,
    use_queue: bool = False,
    skip_graph: bool = False,
    skip_eval: bool = False,
    changed_files: list[str] | None = None,
) -> dict:
    report = {"phase1": None, "phase2": None, "ok": False}

    if not phase2_only:
        report["phase1"] = run_phase1(skip_docker=skip_docker, full_stack=full_stack)
        if not report["phase1"].get("ok"):
            report["ok"] = False
            return report
        if phase1_only:
            report["ok"] = True
            return report

    report["phase2"] = run_phase2(
        force=force,
        use_queue=use_queue,
        skip_graph=skip_graph,
        skip_eval=skip_eval,
        changed_files=changed_files,
    )
    report["ok"] = bool(report["phase2"].get("ok"))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 1+2 统一流水线")
    parser.add_argument("--phase1-only", action="store_true", help="仅 Phase 1 基础设施")
    parser.add_argument("--phase2-only", action="store_true", help="仅 Phase 2（需服务已启动）")
    parser.add_argument("--skip-docker", action="store_true", help="跳过 docker compose up")
    parser.add_argument("--full-stack", action="store_true", help="启动 postgres/minio/rq-dashboard")
    parser.add_argument("--force", action="store_true", help="全量重建索引")
    parser.add_argument("--use-queue", action="store_true", help="RQ 队列模式")
    parser.add_argument("--skip-graph", action="store_true")
    parser.add_argument("--skip-eval", action="store_true")
    parser.add_argument("--ci", action="store_true", help="CI 模式：跳过 docker，全量索引，同步处理")
    parser.add_argument("--changed-files", default=None, help="JSON 数组，指定变更文件")
    args = parser.parse_args(argv)

    changed = json.loads(args.changed_files) if args.changed_files else None
    if args.ci:
        args.skip_docker = True
        args.phase2_only = True
        args.force = True

    report = run_pipeline(
        skip_docker=args.skip_docker,
        full_stack=args.full_stack,
        phase1_only=args.phase1_only,
        phase2_only=args.phase2_only,
        force=args.force,
        use_queue=args.use_queue,
        skip_graph=args.skip_graph,
        skip_eval=args.skip_eval,
        changed_files=changed,
    )

    out = ROOT / "eval" / "results" / "pipeline_latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n流水线报告: {out}")
    print(json.dumps({"ok": report["ok"]}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
