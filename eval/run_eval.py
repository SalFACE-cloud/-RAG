import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.indexer.evaluator import RAGEvaluator

DEFAULT_GOLDEN = ROOT / "eval" / "golden_set_v2.jsonl"
OUT = ROOT / "eval" / "results" / "eval_latest.json"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="运行黄金评估集")
    parser.add_argument("--retrieval-only", action="store_true", help="跳过 LLM 生成评估")
    parser.add_argument("--split", choices=["dev", "test"], default=None, help="只跑指定 split")
    parser.add_argument("--golden", type=str, default=str(DEFAULT_GOLDEN), help="golden set 路径")
    parser.add_argument("--output", type=str, default=str(OUT), help="结果输出路径")
    parser.add_argument("--limit", type=int, default=None, help="最多运行 N 条（调试用）")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    summary = RAGEvaluator().run_golden_set(
        golden_path=args.golden,
        output_path=args.output,
        run_generation=not args.retrieval_only,
        split=args.split,
        limit=args.limit,
    )
    if summary.get("error"):
        print(summary["error"])
        return 1

    overall = summary["overall"]
    print(json.dumps({
        "total": overall["total"],
        "positive_cases": overall.get("positive_cases"),
        "negative_cases": overall.get("negative_cases"),
        "recall@5_rate": round(overall["recall@5_rate"], 3),
        "mrr_avg": round(overall["mrr_avg"], 3),
        "negative_pass_rate": round(overall.get("negative_pass_rate", 0), 3),
        "generation": overall.get("generation"),
        "by_split": {
            k: {
                "total": v["total"],
                "recall@5_rate": round(v["recall@5_rate"], 3),
                "mrr_avg": round(v["mrr_avg"], 3),
            }
            for k, v in summary.get("by_split", {}).items()
        },
        "run_generation": summary.get("run_generation"),
        "output": args.output,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
