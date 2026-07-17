from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from configs.settings import GRAPH_ENABLED
from services.api.auth import rate_limit, verify_token

router = APIRouter()


def get_graph_builder():
    from services.indexer.graph_builder import KnowledgeGraphBuilder

    return KnowledgeGraphBuilder()


@router.get("/knowledge/path/{knowledge_id}")
@rate_limit()
async def learning_path(request: Request, knowledge_id: str):
    verify_token(request)
    if not GRAPH_ENABLED:
        return {"knowledge_id": knowledge_id, "path": [], "graph_enabled": False}
    try:
        builder = get_graph_builder()
        path = builder.get_learning_path(knowledge_id)
        return {"knowledge_id": knowledge_id, "path": path, "graph_enabled": True}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"图谱服务不可用: {exc}") from exc


@router.get("/exercises/filter")
@rate_limit()
async def filter_exercises(
    request: Request,
    knowledge_id: Optional[str] = Query(None),
    difficulty_min: float = Query(0.0, ge=0.0, le=1.0),
    difficulty_max: float = Query(1.0, ge=0.0, le=1.0),
):
    verify_token(request)
    if not GRAPH_ENABLED or not knowledge_id:
        return {"knowledge_id": knowledge_id, "exercises": [], "graph_enabled": GRAPH_ENABLED}
    try:
        builder = get_graph_builder()
        exercises = builder.get_exercises_for_knowledge(
            knowledge_id,
            difficulty_range=(difficulty_min, difficulty_max),
        )
        return {"knowledge_id": knowledge_id, "exercises": exercises, "graph_enabled": True}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"图谱服务不可用: {exc}") from exc
