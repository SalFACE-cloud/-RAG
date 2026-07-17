from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from configs.settings import GRAPH_ENABLED
from services.api.auth import rate_limit, verify_token

router = APIRouter()


@router.get("/learning/recommend")
@rate_limit()
async def learning_recommend(
    request: Request,
    knowledge_id: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    limit: int = Query(5, ge=1, le=20),
):
    verify_token(request)
    from services.api.app import retriever

    result: dict = {
        "knowledge_id": knowledge_id,
        "subject": subject,
        "graph_enabled": GRAPH_ENABLED,
        "learning_path": [],
        "exercises": [],
        "related_chunks": [],
    }

    if knowledge_id and GRAPH_ENABLED:
        try:
            from services.indexer.graph_builder import KnowledgeGraphBuilder

            builder = KnowledgeGraphBuilder()
            result["learning_path"] = builder.get_learning_path(knowledge_id)
            result["exercises"] = builder.get_exercises_for_knowledge(knowledge_id)
            path = result["learning_path"]
            if path and path[0].get("name"):
                result["related_chunks"] = retriever.hybrid_search(
                    path[0]["name"],
                    subject=subject or path[0].get("subject"),
                    top_n=limit,
                    use_rerank=False,
                )
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"图谱服务不可用: {exc}") from exc
    elif subject:
        result["related_chunks"] = retriever.hybrid_search(
            subject, subject=subject, top_n=limit, use_rerank=False
        )
    else:
        raise HTTPException(status_code=400, detail="需提供 knowledge_id 或 subject")

    return result
