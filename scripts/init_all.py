"""一键初始化：Phase 1 基础设施 → Phase 2 素材流水线（委托 run_pipeline）。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_pipeline import main as pipeline_main


def main() -> int:
    # 默认：全栈 Docker + 全量索引 + 图谱
    argv = []
    if "--skip-docker" in sys.argv:
        argv.append("--skip-docker")
    if "--skip-index" in sys.argv:
        argv.extend(["--phase1-only"])
    if "--skip-graph" in sys.argv:
        argv.append("--skip-graph")
    if "--full-stack" in sys.argv:
        argv.append("--full-stack")
    if "--use-queue" in sys.argv:
        argv.append("--use-queue")
    if not any(a in sys.argv for a in ("--phase1-only", "--skip-index")):
        argv.append("--force")
    return pipeline_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
