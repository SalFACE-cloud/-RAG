from typing import Optional

from fastapi import APIRouter, Query, Request, WebSocket
from pydantic import BaseModel

from services.api.auth import rate_limit, verify_token
from services.api.ws.rag_ws import rag_websocket_handler
from services.rag.answer_generator import RAGAnswerGenerator

router = APIRouter()
_generator = RAGAnswerGenerator()


class RAGRequest(BaseModel):
    question: str
    subject: Optional[str] = None
    student_level: Optional[str] = None


def get_generator() -> RAGAnswerGenerator:
    from services.api.app import retriever

    if _generator.retriever is not retriever:
        _generator.retriever = retriever
    return _generator


@router.websocket("/rag/ws")
async def rag_ws(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    await rag_websocket_handler(websocket, get_generator(), token=token)


@router.post("/rag/ask/sync")
@rate_limit()
async def rag_ask_sync(request: Request, req: RAGRequest):
    verify_token(request)
    result = await get_generator().generate_answer(
        question=req.question,
        subject=req.subject,
        student_level=req.student_level,
    )
    return {
        "answer": result["answer"],
        "sources": [
            {"file": r["source_file"], "section": r["section_title"]}
            for r in result["chunks"]
        ],
        "chunks": result["chunks"],
    }
