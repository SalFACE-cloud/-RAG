"""Phase 2 acceptance: metadata validation + optional RQ smoke test."""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "eval" / "results" / "phase2_verify_latest.json"


def validate_vault(vault_dir: Path) -> dict:
    from services.pipeline.metadata_validator import MetadataValidator

    validator = MetadataValidator()
    ok = err = 0
    errors = []
    for md in sorted(vault_dir.rglob("*.md")):
        if "_converted" in md.parts or md.name.startswith("."):
            continue
        if "0_项目文档" in md.parts:
            continue
        result = validator.validate(str(md))
        if result.valid:
            ok += 1
        else:
            err += 1
            errors.append({"file": str(md.relative_to(ROOT)), "errors": result.errors})
    return {"valid": ok, "invalid": err, "errors": errors, "pass": err == 0 and ok > 0}


def check_rq() -> dict:
    try:
        from redis import Redis
        from rq import Queue

        from configs.settings import REDIS_HOST, REDIS_PORT

        conn = Redis(host=REDIS_HOST, port=REDIS_PORT, socket_connect_timeout=3)
        conn.ping()
        q = Queue("pipeline", connection=conn)
        return {"ok": True, "queue": q.name, "count": q.count}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 2 pipeline verification")
    parser.add_argument("--skip-rq", action="store_true")
    args = parser.parse_args()

    vault = ROOT / "vault"
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "vault_validation": validate_vault(vault),
        "rq": {"skipped": True} if args.skip_rq else check_rq(),
    }
    rq_ok = report["rq"].get("skipped") or report["rq"].get("ok")
    report["overall"] = {
        "metadata_pass": report["vault_validation"]["pass"],
        "rq_pass": bool(rq_ok),
        "phase2_pass": report["vault_validation"]["pass"] and bool(rq_ok),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["overall"], ensure_ascii=False, indent=2))
    print(f"Report: {OUT}")
    return 0 if report["overall"]["phase2_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
