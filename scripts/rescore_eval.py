"""用最新评估规则对已有 eval_latest.json 重新打分（无需重跑 LLM）。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.indexer.evaluator import RAGEvaluator

GOLDEN = ROOT / "eval" / "golden_set_v2.jsonl"
EVAL_IN = ROOT / "eval" / "results" / "eval_latest.json"
EVAL_OUT = EVAL_IN


def load_golden_map(path: Path) -> dict:
    cases = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            cases[row["id"]] = row
    return cases


def main():
    if not EVAL_IN.exists():
        print(f"未找到 {EVAL_IN}，请先运行 python main.py eval")
        return 1

    golden = load_golden_map(GOLDEN)
    data = json.loads(EVAL_IN.read_text(encoding="utf-8"))
    evaluator = RAGEvaluator()

    for case_row in data.get("cases", []):
        cid = case_row["id"]
        g = golden.get(cid, {})
        answer = case_row.get("generated_answer")
        if not answer:
            continue
        negative = case_row.get("negative_case", False)
        generation = evaluator.evaluate_generation(
            answer,
            g.get("must_include_points", []),
            [] if negative else g.get("forbidden_points", []),
        )
        generation["llm_ok"] = case_row.get("generation", {}).get("llm_ok")
        generation["generation_skipped"] = case_row.get("generation", {}).get(
            "generation_skipped", False
        )
        case_row["generation"] = generation

    data["rescored"] = True
    data["golden_path"] = str(GOLDEN)
    data["overall"] = evaluator._summarize_rows(data["cases"])
    by_split: dict[str, list] = {}
    for row in data["cases"]:
        by_split.setdefault(row["split"], []).append(row)
    data["by_split"] = {k: evaluator._summarize_rows(v) for k, v in by_split.items()}

    EVAL_OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    overall = data["overall"]
    print(json.dumps({
        "rescored": True,
        "total": overall["total"],
        "point_coverage_avg": round(overall["generation"]["point_coverage_avg"], 3),
        "forbidden_hit_rate_avg": round(overall["generation"]["forbidden_hit_rate_avg"], 3),
        "output": str(EVAL_OUT),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
