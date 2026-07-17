from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from services.api.auth import rate_limit, verify_token

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    subject: Optional[str] = None
    doc_type: Optional[str] = None
    difficulty_max: Optional[float] = None
    top_k: int = 20
    top_n: int = 5


def get_retriever():
    from services.api.app import retriever

    return retriever


@router.post("/knowledge/search")
@rate_limit()
async def knowledge_search(request: Request, req: SearchRequest):
    verify_token(request)
    results = get_retriever().hybrid_search(
        query=req.query,
        subject=req.subject,
        doc_type=req.doc_type,
        difficulty_max=req.difficulty_max,
        top_k=req.top_k,
        top_n=req.top_n,
    )
    return {"query": req.query, "total": len(results), "results": results}
