"""列出并重试 RQ 死信 / 失败任务。"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.pipeline.main import list_failed_jobs, retry_failed_jobs


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline 失败任务管理")
    parser.add_argument("--retry", action="store_true", help="批量重新入队")
    parser.add_argument("--job-id", default=None, help="仅重试指定 job_id")
    parser.add_argument("--dry-run", action="store_true", help="仅列出，不重试")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    jobs = list_failed_jobs(limit=args.limit)
    print(json.dumps(jobs, ensure_ascii=False, indent=2))
    print(f"Total failed entries: {len(jobs)}")

    if args.dry_run or not args.retry:
        return 0

    requeued = retry_failed_jobs(job_id=args.job_id)
    print(f"Requeued: {requeued}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
