import json
import logging
from pathlib import Path
from typing import Optional

from services.indexer.eval_text_utils import (
    forbidden_hit_rate as calc_forbidden_hit_rate,
    point_coverage as calc_point_coverage,
)
from services.indexer.hybrid_retriever import HybridRetriever
from services.rag.answer_generator import RAGAnswerGenerator

logger = logging.getLogger(__name__)


class RAGEvaluator:
    def __init__(
        self,
        retriever: Optional[HybridRetriever] = None,
        generator: Optional[RAGAnswerGenerator] = None,
    ):
        self.retriever = retriever or HybridRetriever()
        self.generator = generator or RAGAnswerGenerator(self.retriever)

    @staticmethod
    def evaluate_retrieval(
        retrieved_ids: list[str],
        relevant_ids: list[str],
        negative_case: bool = False,
    ) -> dict:
        if negative_case or not relevant_ids:
            topk_has_any = len(retrieved_ids) > 0
            return {
                "negative_case": True,
                "recall@1": 0.0 if topk_has_any else 1.0,
                "recall@5": 0.0 if len(retrieved_ids[:5]) > 0 else 1.0,
                "mrr": 0.0,
                "retrieved_any": topk_has_any,
            }

        metrics: dict = {"negative_case": False}
        rel = set(relevant_ids)
        for k in [1, 3, 5, 10]:
            topk = retrieved_ids[:k]
            metrics[f"recall@{k}"] = len(set(topk) & rel) / len(rel) if rel else 0.0
        metrics["mrr"] = 0.0
        for i, cid in enumerate(retrieved_ids, start=1):
            if cid in rel:
                metrics["mrr"] = 1.0 / i
                break
        return metrics

    @staticmethod
    def point_coverage(answer: str, must_points: list[str]) -> float:
        return calc_point_coverage(answer, must_points)

    @staticmethod
    def forbidden_hit_rate(answer: str, forbidden_points: list[str]) -> float:
        return calc_forbidden_hit_rate(answer, forbidden_points)

    def evaluate_generation(
        self,
        answer: str,
        must_include_points: Optional[list[str]] = None,
        forbidden_points: Optional[list[str]] = None,
    ) -> dict:
        must = must_include_points or []
        forbidden = forbidden_points or []
        return {
            "point_coverage": self.point_coverage(answer, must),
            "forbidden_hit_rate": self.forbidden_hit_rate(answer, forbidden),
        }

    def _summarize_rows(self, rows: list[dict]) -> dict:
        if not rows:
            return {
                "total": 0,
                "recall@5_rate": 0.0,
                "mrr_avg": 0.0,
                "generation": {
                    "point_coverage_avg": 0.0,
                    "forbidden_hit_rate_avg": 0.0,
                    "success_rate": 0.0,
                },
            }

        pos_rows = [r for r in rows if not r.get("negative_case")]
        recall5_hits = sum(
            1 for r in pos_rows if r.get("retrieval", {}).get("recall@5", 0) > 0
        )
        mrr_sum = sum(r.get("retrieval", {}).get("mrr", 0) for r in pos_rows)

        gen_rows = [
            r for r in rows
            if r.get("generation", {}).get("point_coverage") is not None
        ]
        pc_avg = 0.0
        fb_avg = 0.0
        success = 0.0
        if gen_rows:
            pc_avg = sum(r["generation"]["point_coverage"] for r in gen_rows) / len(gen_rows)
            fb_avg = sum(r["generation"]["forbidden_hit_rate"] for r in gen_rows) / len(gen_rows)
            success = sum(1 for r in gen_rows if r["generation"].get("llm_ok")) / len(gen_rows)

        neg_rows = [r for r in rows if r.get("negative_case")]
        neg_pass = 0
        for r in neg_rows:
            retrieval_ok = not r.get("retrieval", {}).get("retrieved_any", True)
            pc = r.get("generation", {}).get("point_coverage")
            gen_ok = pc is not None and pc > 0
            if retrieval_ok or gen_ok:
                neg_pass += 1

        return {
            "total": len(rows),
            "positive_cases": len(pos_rows),
            "negative_cases": len(neg_rows),
            "recall@5_rate": recall5_hits / len(pos_rows) if pos_rows else 0.0,
            "mrr_avg": mrr_sum / len(pos_rows) if pos_rows else 0.0,
            "negative_pass_rate": neg_pass / len(neg_rows) if neg_rows else 0.0,
            "generation": {
                "point_coverage_avg": pc_avg,
                "forbidden_hit_rate_avg": fb_avg,
                "success_rate": success,
                "evaluated_cases": len(gen_rows),
            },
        }

    def run_golden_set(
        self,
        golden_path: Path | str,
        output_path: Path | str,
        run_generation: bool = True,
        split: str | None = None,
        limit: int | None = None,
    ) -> dict:
        golden_path = Path(golden_path)
        output_path = Path(output_path)

        cases = self._load_cases(golden_path)
        if split:
            cases = [c for c in cases if c.get("split") == split]

        runnable = [
            c
            for c in cases
            if c.get("relevant_chunk_ids") is not None
            and (
                not c.get("relevant_chunk_ids")
                or not str(c["relevant_chunk_ids"][0]).startswith("TODO_")
            )
        ]
        if limit is not None:
            runnable = runnable[:limit]

        if not runnable:
            msg = "没有可运行的 golden case"
            logger.warning(msg)
            return {"error": msg, "total": 0}

        llm_available = RAGAnswerGenerator.is_llm_configured()
        if run_generation and not llm_available:
            logger.warning("LLM 未配置，跳过生成评估")

        rows = []
        for i, case in enumerate(runnable, start=1):
            logger.info("[%s/%s] %s", i, len(runnable), case["id"])
            filters = case.get("metadata_filters", {})
            negative_case = case.get("negative_case", False) or not case.get("relevant_chunk_ids")

            results = self.retriever.hybrid_search(
                query=case["query"],
                subject=filters.get("subject"),
                doc_type=filters.get("doc_type"),
                difficulty_max=filters.get("difficulty_max"),
                top_k=20,
                top_n=10,
            )
            ids = [r["chunk_id"] for r in results]
            retrieval = self.evaluate_retrieval(
                ids,
                case.get("relevant_chunk_ids", []),
                negative_case=negative_case,
            )

            row = {
                "id": case["id"],
                "split": case.get("split", "dev"),
                "subject": case["subject"],
                "negative_case": negative_case,
                "retrieval": retrieval,
                "retrieved_top5": ids[:5],
                "expected": case.get("relevant_chunk_ids", []),
                "ground_truth_answer": case.get("ground_truth_answer", ""),
            }

            if run_generation and llm_available:
                gen_result = self.generator.generate_answer_sync(
                    question=case["query"],
                    subject=filters.get("subject"),
                )
                answer = gen_result["answer"]
                generation = self.evaluate_generation(
                    answer,
                    case.get("must_include_points", []),
                    case.get("forbidden_points", []) if not negative_case else [],
                )
                generation["llm_ok"] = gen_result["llm_ok"]
                generation["generation_skipped"] = gen_result.get("generation_skipped", False)
                row["generated_answer"] = answer
                row["generation"] = generation
            else:
                row["generated_answer"] = None
                row["generation"] = {
                    "point_coverage": None,
                    "forbidden_hit_rate": None,
                    "llm_ok": None,
                    "generation_skipped": True,
                }

            rows.append(row)
            logger.info("%s retrieval=%s", case["id"], retrieval)

        by_split: dict[str, list] = {}
        for row in rows:
            by_split.setdefault(row["split"], []).append(row)

        summary = {
            "golden_path": str(golden_path),
            "run_generation": run_generation and llm_available,
            "overall": self._summarize_rows(rows),
            "by_split": {k: self._summarize_rows(v) for k, v in by_split.items()},
            "cases": rows,
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return summary

    @staticmethod
    def _load_cases(golden_path: Path) -> list[dict]:
        if not golden_path.exists():
            return []
        return [
            json.loads(line)
            for line in golden_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
