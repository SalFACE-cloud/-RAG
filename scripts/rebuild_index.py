"""全量重建索引（对齐指南 rebuild_index.py）。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.pipeline.main import run_batch


def main() -> int:
    results = run_batch(force=True)
    failed = [r for r in results if not r.get("success")]
    print(f"完成: 共 {len(results)} 个文件, 失败 {len(failed)} 个")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
