import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from configs.settings import EMBEDDING_MODEL, USE_FP16

logger = logging.getLogger(__name__)

_shared_embedder = None


def get_shared_embedder():
    global _shared_embedder
    if _shared_embedder is None:
        from FlagEmbedding import BGEM3FlagModel

        _shared_embedder = BGEM3FlagModel(EMBEDDING_MODEL, use_fp16=USE_FP16)
    return _shared_embedder


def embed_texts(texts: list[str], *, mock: bool = False) -> list[list[float]]:
    if not texts:
        return []
    if mock:
        return mock_embed_texts(texts)
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


def mock_embed_texts(texts: list[str]) -> list[list[float]]:
    """CI 用确定性 mock 向量（不下载模型）。"""
    import hashlib
    import math

    from configs.settings import VECTOR_SIZE

    vectors: list[list[float]] = []
    for text in texts:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        raw = [(digest[i % len(digest)] / 255.0) for i in range(VECTOR_SIZE)]
        norm = math.sqrt(sum(v * v for v in raw)) or 1.0
        vectors.append([v / norm for v in raw])
    return vectors


def _cli_root() -> Path:
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def run_embed_vault(vault_path: Path, mock: bool = False) -> dict:
    import json

    from services.indexer.chunker import chunk_from_dict
    from services.indexer.qdrant_indexer import QdrantIndexer
    from services.pipeline.vault_paths import CHUNKS_MANIFEST_JSON, append_pipeline_log

    _cli_root()
    if not CHUNKS_MANIFEST_JSON.exists():
        raise FileNotFoundError(f"缺少分块清单: {CHUNKS_MANIFEST_JSON}，请先运行 chunker.py")

    manifest = json.loads(CHUNKS_MANIFEST_JSON.read_text(encoding="utf-8"))
    chunks = [chunk_from_dict(c) for c in manifest.get("chunks", [])]
    if not chunks:
        return {"upserted": 0, "mock": mock}

    qdrant = QdrantIndexer()
    qdrant.init_collection()

    source_files = sorted({c.source_file for c in chunks})
    for sf in source_files:
        qdrant.delete_by_source_file(sf)

    upserted = qdrant.upsert_chunks(chunks, mock=mock)
    append_pipeline_log(f"embedder mock={mock} upserted={upserted} sources={len(source_files)}")
    print(f"[EMBED] mock={mock} upserted={upserted} from {len(source_files)} files")
    return {"upserted": upserted, "mock": mock, "source_files": len(source_files)}


def main_cli() -> int:
    import argparse
    from pathlib import Path

    _cli_root()
    from services.pipeline.vault_paths import write_pipeline_result

    parser = argparse.ArgumentParser(description="Embedding 向量化并写入 Qdrant")
    parser.add_argument("--vault-path", default="./vault", help="与 chunker 一致（读取 manifest）")
    parser.add_argument("--mock-embeddings", action="store_true", help="CI mock 向量，不下载模型")
    args = parser.parse_args()

    del args.vault_path  # manifest 已含路径
    try:
        result = run_embed_vault(Path("."), mock=args.mock_embeddings)
    except FileNotFoundError as exc:
        print(exc)
        write_pipeline_result("embedder", False, {"error": str(exc)})
        return 1

    ok = result["upserted"] >= 0
    write_pipeline_result("embedder", ok, result)
    return 0 if result["upserted"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main_cli())
