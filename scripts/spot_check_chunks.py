"""Spot-check chunk sizes and section boundaries for Phase 3 acceptance."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from configs.settings import CHUNK_MAX_CHARS, CHUNK_MIN_CHARS, VAULT_DIR
from services.indexer.chunker import EduDocumentChunker


def main(argv=None):
    parser = argparse.ArgumentParser(description="Spot-check document chunking")
    parser.add_argument("--file", type=str, default=None, help="Specific markdown file")
    args = parser.parse_args(argv)

    chunker = EduDocumentChunker()
    vault = Path(VAULT_DIR)
    files = [Path(args.file)] if args.file else sorted(vault.rglob("*.md"))

    total_chunks = 0
    out_of_range = 0

    for md in files:
        if "_converted" in md.parts or md.name.startswith("."):
            continue
        raw = md.read_text(encoding="utf-8")
        body = raw.split("---", 2)[-1] if raw.startswith("---") else raw
        chunks = chunker.chunk(body, str(md.resolve()).replace("\\", "/"), {})
        if not chunks:
            continue

        print(f"\n=== {md.name} ({len(chunks)} chunks) ===")
        for i, ch in enumerate(chunks):
            total_chunks += 1
            in_range = CHUNK_MIN_CHARS <= ch.char_count <= CHUNK_MAX_CHARS
            if not in_range:
                out_of_range += 1
            flag = "OK" if in_range else "OUT_OF_RANGE"
            print(
                f"  [{i}] {flag} chars={ch.char_count:4d}  "
                f"section={ch.section_title!r}  breadcrumb={ch.breadcrumb!r}"
            )

    print(f"\nTotal chunks: {total_chunks}")
    print(f"Out of range ({CHUNK_MIN_CHARS}-{CHUNK_MAX_CHARS} chars): {out_of_range}")
    print(f"In range: {total_chunks - out_of_range}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
