"""Phase 1 基础设施验收（检查已运行的 Docker 服务）。"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "eval" / "results" / "phase1_verify_latest.json"


def main() -> int:
    from scripts.run_pipeline import PHASE1_HTTP_CHECKS, check_redis, wait_http

    checks = {}
    for name, url in PHASE1_HTTP_CHECKS:
        if name in ("MinIO Console", "RQ Dashboard"):
            continue
        checks[name] = wait_http(name, url, timeout=10, interval=1)
    checks["Redis"] = check_redis()

    core_ok = checks.get("Qdrant") and checks.get("Meilisearch") and checks.get("Redis")
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "checks": checks,
        "overall": {"phase1_pass": bool(core_ok)},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["overall"], ensure_ascii=False, indent=2))
    print(f"Report: {OUT}")
    return 0 if core_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
