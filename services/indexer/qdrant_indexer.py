from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from configs.settings import COLLECTION_NAME, QDRANT_URL, VECTOR_SIZE
from services.indexer.embedder import embed_texts


class QdrantIndexer:
    def __init__(self):
        self.client = QdrantClient(url=QDRANT_URL)

    def init_collection(self):
        names = [c.name for c in self.client.get_collections().collections]
        if COLLECTION_NAME not in names:
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
            for field in ["metadata.subject", "metadata.type", "source_file"]:
                self.client.create_payload_index(
                    collection_name=COLLECTION_NAME,
                    field_name=field,
                    field_schema="keyword",
                )
            self.client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name="metadata.difficulty",
                field_schema="float",
            )

    def delete_by_source_file(self, source_file: str):
        self.client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(
                must=[FieldCondition(key="source_file", match=MatchValue(value=source_file))]
            ),
        )

    def upsert_chunks(self, chunks: list) -> int:
        if not chunks:
            return 0
        texts = [c.content for c in chunks]
        vectors = embed_texts(texts)
        points = [
            PointStruct(
                id=c.chunk_id,
                vector=vector,
                payload={
                    "content": c.content,
                    "source_file": c.source_file,
                    "section_title": c.section_title,
                    "breadcrumb": c.breadcrumb,
                    "metadata": c.metadata,
                    "char_count": c.char_count,
                    "token_count": c.token_count,
                },
            )
            for c, vector in zip(chunks, vectors)
        ]
        self.client.upsert(collection_name=COLLECTION_NAME, points=points)
        return len(points)

    def search(
        self,
        query: str,
        subject: Optional[str] = None,
        doc_type: Optional[str] = None,
        difficulty_max: Optional[float] = None,
        top_k: int = 20,
    ) -> list[dict]:
        conditions = []
        if subject:
            conditions.append(
                FieldCondition(key="metadata.subject", match=MatchValue(value=subject))
            )
        if doc_type:
            conditions.append(
                FieldCondition(key="metadata.type", match=MatchValue(value=doc_type))
            )
        if difficulty_max is not None:
            conditions.append(
                FieldCondition(key="metadata.difficulty", range={"lte": difficulty_max})
            )

        query_filter = Filter(must=conditions) if conditions else None
        query_vector = embed_texts([query])[0]
        response = self.client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )
        return [
            {
                "chunk_id": str(r.id),
                "score": float(r.score),
                "content": r.payload["content"],
                "source_file": r.payload["source_file"],
                "section_title": r.payload["section_title"],
                "metadata": r.payload.get("metadata", {}),
            }
            for r in response.points
        ]
