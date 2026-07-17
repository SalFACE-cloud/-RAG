import logging
from typing import Optional

from configs.settings import RERANKER_MODEL, USE_FP16, USE_RERANK
from services.indexer.qdrant_indexer import QdrantIndexer
from services.indexer.meili_indexer import MeiliIndexer

logger = logging.getLogger(__name__)


class HybridRetriever:
    def __init__(self):
        self.qdrant = QdrantIndexer()
        self.meili = MeiliIndexer()
        self._reranker = None

    @property
    def reranker(self):
        if self._reranker is None:
            from FlagEmbedding import FlagReranker

            self._reranker = FlagReranker(RERANKER_MODEL, use_fp16=USE_FP16)
        return self._reranker

    def _try_rerank(self, query: str, candidates: list[dict], top_n: int) -> list[dict]:
        try:
            return self.rerank(query, candidates, top_n=top_n)
        except Exception as exc:
            logger.warning("Reranker 不可用，回退到 RRF 结果: %s", exc)
            return candidates[:top_n]

    def reciprocal_rank_fusion(
        self,
        vector_results: list[dict],
        keyword_results: list[dict],
        k: int = 60,
    ) -> list[dict]:
        scores: dict[str, float] = {}
        store: dict[str, dict] = {}

        for rank, item in enumerate(vector_results):
            cid = item["chunk_id"]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
            store.setdefault(cid, item)

        for rank, item in enumerate(keyword_results):
            cid = item["chunk_id"]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
            store.setdefault(cid, item)

        merged = []
        for cid, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
            row = dict(store[cid])
            row["rrf_score"] = score
            merged.append(row)
        return merged

    def rerank(self, query: str, candidates: list[dict], top_n: int = 5) -> list[dict]:
        if not candidates:
            return []
        pairs = [[query, c["content"]] for c in candidates]
        scores = self.reranker.compute_score(pairs, normalize=True)
        if isinstance(scores, float):
            scores = [scores]
        for cand, score in zip(candidates, scores):
            cand["rerank_score"] = float(score)
        candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
        return candidates[:top_n]

    def hybrid_search(
        self,
        query: str,
        subject: Optional[str] = None,
        doc_type: Optional[str] = None,
        difficulty_max: Optional[float] = None,
        top_k: int = 20,
        top_n: int = 5,
        use_rerank: bool | None = None,
    ) -> list[dict]:
        vector_results = self.qdrant.search(
            query,
            subject=subject,
            doc_type=doc_type,
            difficulty_max=difficulty_max,
            top_k=top_k,
        )
        keyword_results = self.meili.search(query, subject=subject, limit=top_k)
        merged = self.reciprocal_rank_fusion(vector_results, keyword_results)
        should_rerank = USE_RERANK if use_rerank is None else use_rerank
        if should_rerank:
            return self._try_rerank(query, merged[:top_k], top_n=top_n)
        return merged[:top_n]
