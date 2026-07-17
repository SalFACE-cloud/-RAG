"""RAG 评估入口（对齐指南 eval_rag.py，封装 eval/run_eval.py）。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.run_eval import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
