"""Compare retrieval modes: vector-only, keyword-only, RRF (no rerank)."""
import argparse
import json
import sys
from pathlib import Path
from typing import Callable, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.indexer.evaluator import RAGEvaluator
from services.indexer.hybrid_retriever import HybridRetriever
from services.indexer.meili_indexer import MeiliIndexer
from services.indexer.qdrant_indexer import QdrantIndexer

DEFAULT_GOLDEN = ROOT / "eval" / "golden_set_v2.jsonl"
DEFAULT_OUT = ROOT / "eval" / "results" / "retrieval_compare_latest.json"


def load_cases(golden_path: Path, split: Optional[str]) -> list[dict]:
    cases = [
        json.loads(line)
        for line in golden_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    runnable = [
        c
        for c in cases
        if c.get("relevant_chunk_ids") is not None
        and (
            not c.get("relevant_chunk_ids")
            or not str(c["relevant_chunk_ids"][0]).startswith("TODO_")
        )
    ]
    if split:
        runnable = [c for c in runnable if c.get("split") == split]
    return runnable


def summarize(rows: list[dict]) -> dict:
    pos = [r for r in rows if not r.get("negative_case")]
    recall5_hits = sum(1 for r in pos if r["metrics"].get("recall@5", 0) > 0)
    mrr_sum = sum(r["metrics"].get("mrr", 0) for r in pos)
    return {
        "total": len(rows),
        "positive_cases": len(pos),
        "recall@5_rate": recall5_hits / len(pos) if pos else 0.0,
        "mrr_avg": mrr_sum / len(pos) if pos else 0.0,
    }


def run_mode(
    mode: str,
    cases: list[dict],
    retriever: HybridRetriever,
    qdrant: QdrantIndexer,
    meili: MeiliIndexer,
) -> dict:
    search_fn: Callable[..., list[dict]]

    if mode == "vector_only":
        def search_fn(query, subject=None, doc_type=None, difficulty_max=None, **_):
            return qdrant.search(
                query,
                subject=subject,
                doc_type=doc_type,
                difficulty_max=difficulty_max,
                top_k=20,
            )
    elif mode == "keyword_only":
        def search_fn(query, subject=None, **_):
            return meili.search(query, subject=subject, limit=20)
    elif mode == "rrf":
        def search_fn(query, subject=None, doc_type=None, difficulty_max=None, **_):
            vector_results = qdrant.search(
                query,
                subject=subject,
                doc_type=doc_type,
                difficulty_max=difficulty_max,
                top_k=20,
            )
            keyword_results = meili.search(query, subject=subject, limit=20)
            return retriever.reciprocal_rank_fusion(vector_results, keyword_results)[:10]
    elif mode == "hybrid":
        def search_fn(query, subject=None, doc_type=None, difficulty_max=None, **_):
            return retriever.hybrid_search(
                query,
                subject=subject,
                doc_type=doc_type,
                difficulty_max=difficulty_max,
                top_k=20,
                top_n=10,
                use_rerank=False,
            )
    else:
        raise ValueError(f"Unknown mode: {mode}")

    rows = []
    for case in cases:
        filters = case.get("metadata_filters", {})
        negative_case = case.get("negative_case", False) or not case.get("relevant_chunk_ids")
        results = search_fn(
            case["query"],
            subject=filters.get("subject"),
            doc_type=filters.get("doc_type"),
            difficulty_max=filters.get("difficulty_max"),
        )
        ids = [r["chunk_id"] for r in results]
        metrics = RAGEvaluator.evaluate_retrieval(
            ids,
            case.get("relevant_chunk_ids", []),
            negative_case=negative_case,
        )
        rows.append(
            {
                "id": case["id"],
                "negative_case": negative_case,
                "metrics": metrics,
                "retrieved_top5": ids[:5],
            }
        )

    return {"mode": mode, "summary": summarize(rows), "cases": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare retrieval modes on golden set")
    parser.add_argument("--golden", type=str, default=str(DEFAULT_GOLDEN))
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUT))
    parser.add_argument("--split", choices=["dev", "test"], default=None)
    parser.add_argument(
        "--modes",
        nargs="+",
        default=["vector_only", "keyword_only", "rrf", "hybrid"],
        choices=["vector_only", "keyword_only", "rrf", "hybrid"],
    )
    args = parser.parse_args(argv)

    cases = load_cases(Path(args.golden), args.split)
    if not cases:
        print("No runnable golden cases found")
        return 1

    retriever = HybridRetriever()
    qdrant = QdrantIndexer()
    meili = MeiliIndexer()

    report = {
        "golden_path": args.golden,
        "split": args.split,
        "modes": {},
    }
    for mode in args.modes:
        print(f"Running mode: {mode} ({len(cases)} cases)...")
        report["modes"][mode] = run_mode(mode, cases, retriever, qdrant, meili)

    summaries = {m: report["modes"][m]["summary"] for m in args.modes}
    rrf = summaries.get("rrf", {})
    vector = summaries.get("vector_only", {})
    keyword = summaries.get("keyword_only", {})
    report["checks"] = {
        "rrf_beats_vector": rrf.get("recall@5_rate", 0) >= vector.get("recall@5_rate", 0),
        "rrf_beats_keyword": rrf.get("recall@5_rate", 0) >= keyword.get("recall@5_rate", 0),
        "hybrid_beats_vector": summaries.get("hybrid", {}).get("recall@5_rate", 0)
        >= vector.get("recall@5_rate", 0),
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nMode comparison (recall@5_rate / mrr_avg):")
    for mode, summary in summaries.items():
        print(
            f"  {mode:14s}  recall@5={summary['recall@5_rate']:.3f}  "
            f"mrr={summary['mrr_avg']:.3f}"
        )
    print(f"\nChecks: {report['checks']}")
    print(f"Output: {out_path}")

    all_pass = all(report["checks"].values())
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
