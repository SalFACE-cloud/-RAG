import logging
from pathlib import Path

from configs.settings import GRAPH_ENABLED
from services.indexer.chunker import EduDocumentChunker
from services.indexer.graph_builder import get_graph_builder
from services.indexer.qdrant_indexer import QdrantIndexer
from services.indexer.meili_indexer import MeiliIndexer
from services.pipeline.metadata_validator import MetadataValidator

logger = logging.getLogger(__name__)


class IndexerService:
    def __init__(self):
        self.chunker = EduDocumentChunker()
        self.qdrant = QdrantIndexer()
        self.meili = MeiliIndexer()
        self.validator = MetadataValidator()
        self._graph = None

    def init_all(self):
        self.qdrant.init_collection()
        self.meili.init_index()
        if GRAPH_ENABLED:
            self._graph = get_graph_builder()

    def index_markdown_file(self, file_path: str) -> dict:
        path = Path(file_path)
        validation = self.validator.validate(str(path))
        if not validation.valid:
            return {"success": False, "error": validation.errors}

        source_file = str(path.resolve()).replace("\\", "/")
        chunks = self.chunker.chunk(
            validation.content,
            source_file,
            validation.metadata or {},
        )

        self.qdrant.delete_by_source_file(source_file)
        self.meili.delete_by_source_file(source_file)

        q_count = self.qdrant.upsert_chunks(chunks)
        m_count = self.meili.upsert_chunks(chunks)

        if GRAPH_ENABLED:
            graph = self._graph or get_graph_builder()
            if graph:
                try:
                    graph.import_from_metadata(source_file, validation.metadata or {})
                    graph.import_obsidian_links(source_file, validation.content)
                except Exception as exc:
                    logger.warning("图谱写入失败: %s", exc)

        return {
            "success": True,
            "source_file": source_file,
            "chunk_count": len(chunks),
            "qdrant_count": q_count,
            "meili_count": m_count,
            "chunk_ids": [c.chunk_id for c in chunks],
        }
