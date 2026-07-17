"""Measure BGE-M3 embedding throughput. Phase 3 target: > 50 chunks/min."""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from configs.settings import VAULT_DIR
from services.indexer.chunker import EduDocumentChunker
from services.indexer.embedder import embed_texts


def collect_chunk_texts(min_count: int = 60) -> list[str]:
    chunker = EduDocumentChunker()
    texts: list[str] = []
    vault = Path(VAULT_DIR)

    for md in sorted(vault.rglob("*.md")):
        if "_converted" in md.parts or md.name.startswith("."):
            continue
        raw = md.read_text(encoding="utf-8")
        body = raw.split("---", 2)[-1] if raw.startswith("---") else raw
        for chunk in chunker.chunk(body, str(md.resolve()).replace("\\", "/"), {}):
            texts.append(chunk.content)

    if not texts:
        raise SystemExit(f"No chunks found under {vault}")

    while len(texts) < min_count:
        texts.extend(texts[: max(1, min_count - len(texts))])
    return texts[:min_count]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Benchmark BGE-M3 embedding speed")
    parser.add_argument("--min-chunks", type=int, default=60, help="Minimum chunks to embed")
    parser.add_argument("--target-cpm", type=float, default=50.0, help="Target chunks/min")
    args = parser.parse_args(argv)

    texts = collect_chunk_texts(min_count=args.min_chunks)
    print(f"Embedding {len(texts)} chunks...")

    t0 = time.perf_counter()
    embed_texts(texts)
    elapsed = time.perf_counter() - t0

    cpm = len(texts) / elapsed * 60 if elapsed > 0 else 0.0
    passed = cpm >= args.target_cpm

    print(f"chunks={len(texts)}")
    print(f"elapsed_sec={elapsed:.2f}")
    print(f"rate_chunks_per_min={cpm:.1f}")
    print(f"target={args.target_cpm}")
    print("PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
