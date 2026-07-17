"""一键初始化：Docker 基础设施 → 全量索引 → 知识图谱（可选）。"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from configs.settings import GRAPH_ENABLED


def run_cmd(cmd: list[str], cwd: Path | None = None) -> int:
    print(f"\n>>> {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=cwd or ROOT)


def wait_http(name: str, url: str, timeout: float = 120.0, interval: float = 2.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = httpx.get(url, timeout=3.0)
            if resp.status_code < 500:
                print(f"[OK] {name}: {url}")
                return True
        except Exception:
            pass
        time.sleep(interval)
    print(f"[WARN] {name} 未在 {timeout}s 内就绪: {url}")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="初始化所有服务并重建索引")
    parser.add_argument("--skip-docker", action="store_true", help="跳过 docker compose up")
    parser.add_argument("--skip-index", action="store_true", help="跳过全量索引")
    parser.add_argument("--skip-graph", action="store_true", help="跳过知识图谱重建")
    args = parser.parse_args()

    if not args.skip_docker:
        code = run_cmd(["docker", "compose", "up", "-d"])
        if code != 0:
            return code
        wait_http("Qdrant", "http://127.0.0.1:6333/healthz")
        wait_http("Meilisearch", "http://127.0.0.1:7700/health")
        wait_http("Neo4j Browser", "http://127.0.0.1:7474")
        wait_http("MinIO Console", "http://127.0.0.1:9001", timeout=60)

    if not args.skip_index:
        code = run_cmd([sys.executable, "scripts/rebuild_index.py"])
        if code != 0:
            return code

    if not args.skip_graph and GRAPH_ENABLED:
        code = run_cmd([sys.executable, "main.py", "graph"])
        if code != 0:
            return code
    elif not GRAPH_ENABLED:
        print("\n[INFO] GRAPH_ENABLED=false，跳过图谱重建")

    print("\n初始化完成。")
    print("  API:    python main.py api")
    print("  评估:   python scripts/eval_rag.py --retrieval-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
