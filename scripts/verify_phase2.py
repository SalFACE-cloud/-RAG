"""Phase 2 acceptance: metadata validation + RQ + needs_review + dead letter."""
import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "eval" / "results" / "phase2_verify_latest.json"


def validate_vault(vault_dir: Path) -> dict:
    from services.pipeline.metadata_validator import validate_vault as _validate_vault
    from services.pipeline.vault_paths import parse_ignore_patterns

    return _validate_vault(vault_dir.resolve(), parse_ignore_patterns("0_项目文档/**"))


def check_rq() -> dict:
    try:
        from redis import Redis
        from rq import Queue

        from configs.settings import REDIS_HOST, REDIS_PORT

        conn = Redis(host=REDIS_HOST, port=REDIS_PORT, socket_connect_timeout=3)
        conn.ping()
        pipeline_q = Queue("pipeline", connection=conn)
        failed_q = Queue("failed", connection=conn)
        return {
            "ok": True,
            "pipeline_queue": pipeline_q.name,
            "pipeline_count": pipeline_q.count,
            "failed_queue": failed_q.name,
            "failed_count": failed_q.count,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def check_needs_review() -> dict:
    """无 YAML 头文件应 needs_review 且 chunk_count > 0。"""
    from services.pipeline.main import process_file

    with tempfile.TemporaryDirectory() as tmp:
        bad_md = Path(tmp) / "bad_no_yaml.md"
        bad_md.write_text("# 无元数据测试\n\n内容段落。", encoding="utf-8")
        result = process_file(str(bad_md))
        return {
            "ok": result.get("stage") == "needs_review" and result.get("chunk_count", 0) > 0,
            "stage": result.get("stage"),
            "chunk_count": result.get("chunk_count"),
        }


def check_retry_failed_dry_run() -> dict:
    try:
        from services.pipeline.main import list_failed_jobs

        jobs = list_failed_jobs(limit=5)
        return {"ok": True, "listed": len(jobs)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 2 pipeline verification")
    parser.add_argument("--skip-rq", action="store_true")
    parser.add_argument("--skip-needs-review", action="store_true")
    args = parser.parse_args()

    vault = ROOT / "vault"
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "vault_validation": validate_vault(vault),
        "rq": {"skipped": True} if args.skip_rq else check_rq(),
        "needs_review": {"skipped": True} if args.skip_needs_review else check_needs_review(),
        "retry_failed_dry_run": check_retry_failed_dry_run(),
    }
    rq_ok = report["rq"].get("skipped") or report["rq"].get("ok")
    needs_ok = report["needs_review"].get("skipped") or report["needs_review"].get("ok")
    retry_ok = report["retry_failed_dry_run"].get("ok")
    report["overall"] = {
        "metadata_pass": report["vault_validation"]["pass"],
        "rq_pass": bool(rq_ok),
        "needs_review_pass": bool(needs_ok),
        "retry_failed_pass": bool(retry_ok),
        "phase2_pass": (
            report["vault_validation"]["pass"] and bool(rq_ok) and bool(needs_ok) and bool(retry_ok)
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["overall"], ensure_ascii=False, indent=2))
    print(f"Report: {OUT}")
    return 0 if report["overall"]["phase2_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
