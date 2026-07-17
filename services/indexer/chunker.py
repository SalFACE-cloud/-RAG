import hashlib
import re
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from configs.settings import CHUNK_MAX_CHARS, CHUNK_MIN_CHARS, CHUNK_OVERLAP_CHARS


@dataclass
class Chunk:
    chunk_id: str
    content: str
    metadata: dict
    source_file: str
    section_title: str
    breadcrumb: str
    char_count: int = 0
    token_count: int = 0


class EduDocumentChunker:
    """按 Markdown 标题分块，字符阈值统一，支持面包屑上下文。"""

    def __init__(
        self,
        min_chunk_size: int = CHUNK_MIN_CHARS,
        max_chunk_size: int = CHUNK_MAX_CHARS,
        overlap_size: int = CHUNK_OVERLAP_CHARS,
    ):
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.overlap_size = overlap_size

    def chunk(self, content: str, source_file: str, metadata: dict) -> list[Chunk]:
        sections = self._split_by_headers(content)
        chunks: list[Chunk] = []

        for section in sections:
            title = section["title"]
            text = section["content"]
            breadcrumb = section["breadcrumb"]

            if not text.strip():
                continue

            if len(text) <= self.max_chunk_size:
                chunks.append(self._make_chunk(text, source_file, metadata, title, breadcrumb))
            else:
                chunks.extend(
                    self._split_large_section(text, source_file, metadata, title, breadcrumb)
                )

        chunks = self._merge_short_chunks(chunks)
        return self._add_overlap(chunks)

    def _split_by_headers(self, content: str) -> list[dict]:
        lines = content.split("\n")
        sections = []
        stack: list[tuple[int, str]] = []
        current_title = "正文"
        current_content: list[str] = []

        def flush():
            if not current_content and current_title == "正文":
                return
            breadcrumb = " > ".join(t for _, t in stack) if stack else current_title
            sections.append({
                "title": current_title,
                "breadcrumb": breadcrumb,
                "content": "\n".join(current_content).strip(),
            })

        for line in lines:
            m = re.match(r"^(#{1,6})\s+(.+)", line)
            if m:
                flush()
                level = len(m.group(1))
                title = m.group(2).strip()
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, title))
                current_title = title
                current_content = []
            else:
                current_content.append(line)

        flush()
        return sections

    def _split_large_section(
        self,
        text: str,
        source_file: str,
        metadata: dict,
        section_title: str,
        breadcrumb: str,
    ) -> list[Chunk]:
        paragraphs = re.split(r"\n\n+", text)
        chunks: list[Chunk] = []
        buffer = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            candidate = f"{buffer}\n\n{para}".strip() if buffer else para
            if len(candidate) <= self.max_chunk_size:
                buffer = candidate
            else:
                if buffer:
                    chunks.append(
                        self._make_chunk(buffer, source_file, metadata, section_title, breadcrumb)
                    )
                buffer = para

        if buffer:
            chunks.append(
                self._make_chunk(buffer, source_file, metadata, section_title, breadcrumb)
            )
        return chunks

    def _merge_short_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        if len(chunks) <= 1:
            return chunks

        merged: list[Chunk] = []
        i = 0
        while i < len(chunks):
            current = chunks[i]
            while (
                current.char_count < self.min_chunk_size
                and i + 1 < len(chunks)
                and chunks[i + 1].section_title == current.section_title
            ):
                i += 1
                nxt = chunks[i]
                combined = f"{current.content}\n\n{nxt.content}"
                current = self._make_chunk(
                    combined,
                    current.source_file,
                    current.metadata,
                    current.section_title,
                    current.breadcrumb,
                )
            merged.append(current)
            i += 1
        return merged

    def _add_overlap(self, chunks: list[Chunk]) -> list[Chunk]:
        if self.overlap_size <= 0 or len(chunks) <= 1:
            return chunks

        result: list[Chunk] = []
        prev_tail = ""
        for chunk in chunks:
            body = chunk.content
            if prev_tail:
                body = f"{prev_tail}\n\n{body}"
            result.append(
                self._make_chunk(
                    body,
                    chunk.source_file,
                    chunk.metadata,
                    chunk.section_title,
                    chunk.breadcrumb,
                )
            )
            prev_tail = (
                chunk.content[-self.overlap_size :]
                if len(chunk.content) > self.overlap_size
                else chunk.content
            )
        return result

    def _make_chunk(
        self,
        content: str,
        source_file: str,
        metadata: dict,
        section_title: str,
        breadcrumb: str,
    ) -> Chunk:
        enriched = self._preprocess_for_embedding(content, breadcrumb)
        digest = hashlib.md5(
            f"{source_file}:{breadcrumb}:{content}".encode("utf-8")
        ).hexdigest()
        chunk_id = str(uuid.UUID(digest))
        char_count = len(content)
        token_count = int(char_count / 1.5)
        return Chunk(
            chunk_id=chunk_id,
            content=enriched,
            metadata={**metadata, "section": section_title, "breadcrumb": breadcrumb},
            source_file=source_file,
            section_title=section_title,
            breadcrumb=breadcrumb,
            char_count=char_count,
            token_count=token_count,
        )

    @staticmethod
    def _preprocess_for_embedding(content: str, breadcrumb: str) -> str:
        content = re.sub(
            r"\$\$(.+?)\$\$",
            r"[数学公式] \1 [/数学公式]",
            content,
            flags=re.DOTALL,
        )
        content = re.sub(r"\$(.+?)\$", r"[公式] \1 [/公式]", content)
        return f"[上下文] {breadcrumb}\n\n{content}"


def chunk_to_dict(chunk: Chunk) -> dict:
    return {
        "chunk_id": chunk.chunk_id,
        "content": chunk.content,
        "metadata": chunk.metadata,
        "source_file": chunk.source_file,
        "section_title": chunk.section_title,
        "breadcrumb": chunk.breadcrumb,
        "char_count": chunk.char_count,
        "token_count": chunk.token_count,
    }


def chunk_from_dict(data: dict) -> Chunk:
    return Chunk(
        chunk_id=data["chunk_id"],
        content=data["content"],
        metadata=data.get("metadata") or {},
        source_file=data["source_file"],
        section_title=data.get("section_title", ""),
        breadcrumb=data.get("breadcrumb", ""),
        char_count=int(data.get("char_count") or 0),
        token_count=int(data.get("token_count") or 0),
    )


def _cli_root() -> Path:
    import sys

    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def run_chunk_vault(
    vault_path: Path,
    ignore_patterns: list[str],
    chunk_size: int,
    chunk_overlap: int,
) -> dict:
    import json
    from datetime import datetime

    from services.pipeline.metadata_validator import MetadataValidator
    from services.pipeline.vault_paths import (
        CHUNKS_MANIFEST_JSON,
        append_pipeline_log,
        load_changed_files,
        should_ignore,
    )

    _cli_root()
    vault_path = vault_path.resolve()
    min_size = max(50, chunk_size // 4)
    chunker = EduDocumentChunker(
        min_chunk_size=min_size,
        max_chunk_size=chunk_size,
        overlap_size=chunk_overlap,
    )
    validator = MetadataValidator()

    targets = load_changed_files(vault_path)
    if targets is None:
        from services.pipeline.vault_paths import iter_vault_files

        targets = [str(p.resolve()) for p in iter_vault_files(vault_path, ignore_patterns, {".md"})]

    all_chunks: list[dict] = []
    file_stats: list[dict] = []
    errors: list[dict] = []

    for fp in targets:
        path = Path(fp)
        if not path.exists() or path.suffix.lower() != ".md":
            continue
        if should_ignore(path, vault_path, ignore_patterns):
            continue
        validation = validator.validate(str(path))
        if not validation.valid:
            errors.append({"file": fp, "errors": validation.errors})
            print(f"[SKIP] {path.name}: {validation.errors}")
            continue
        source = str(path.resolve()).replace("\\", "/")
        chunks = chunker.chunk(validation.content, source, validation.metadata or {})
        serialized = [chunk_to_dict(c) for c in chunks]
        all_chunks.extend(serialized)
        file_stats.append({"source_file": source, "chunk_count": len(serialized)})
        print(f"[CHUNK] {path.name} -> {len(serialized)} chunks")

    manifest = {
        "timestamp": datetime.now().isoformat(),
        "vault_path": str(vault_path),
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "files": file_stats,
        "chunks": all_chunks,
        "errors": errors,
    }
    CHUNKS_MANIFEST_JSON.parent.mkdir(parents=True, exist_ok=True)
    CHUNKS_MANIFEST_JSON.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    append_pipeline_log(f"chunker files={len(file_stats)} chunks={len(all_chunks)} errors={len(errors)}")
    return manifest


def main_cli() -> int:
    import argparse

    _cli_root()
    from services.pipeline.vault_paths import parse_ignore_patterns, should_ignore, write_pipeline_result

    parser = argparse.ArgumentParser(description="Vault 文档分块")
    parser.add_argument("--vault-path", default="./vault")
    parser.add_argument("--ignore-paths", default="0_项目文档/**")
    parser.add_argument("--chunk-size", type=int, default=800)
    parser.add_argument("--chunk-overlap", type=int, default=80)
    args = parser.parse_args()

    manifest = run_chunk_vault(
        Path(args.vault_path),
        parse_ignore_patterns(args.ignore_paths),
        args.chunk_size,
        args.chunk_overlap,
    )
    ok = len(manifest.get("chunks", [])) > 0 or len(manifest.get("errors", [])) == 0
    write_pipeline_result(
        "chunker",
        ok,
        {"files": len(manifest.get("files", [])), "chunks": len(manifest.get("chunks", []))},
    )
    print(f"files={len(manifest.get('files', []))} chunks={len(manifest.get('chunks', []))}")
    from services.pipeline.vault_paths import CHUNKS_MANIFEST_JSON

    print(f"Wrote {CHUNKS_MANIFEST_JSON}")
    return 0 if manifest.get("chunks") else 1


if __name__ == "__main__":
    raise SystemExit(main_cli())
