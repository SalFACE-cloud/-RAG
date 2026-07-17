import logging

from configs.settings import EMBEDDING_MODEL, USE_FP16

logger = logging.getLogger(__name__)

_shared_embedder = None


def get_shared_embedder():
    global _shared_embedder
    if _shared_embedder is None:
        from FlagEmbedding import BGEM3FlagModel

        _shared_embedder = BGEM3FlagModel(EMBEDDING_MODEL, use_fp16=USE_FP16)
    return _shared_embedder


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    embedder = get_shared_embedder()
    result = embedder.encode(
        texts,
        batch_size=min(32, max(1, len(texts))),
        max_length=8192,
        return_dense=True,
        return_sparse=False,
        return_colbert_vecs=False,
    )
    return [v.tolist() for v in result["dense_vecs"]]
