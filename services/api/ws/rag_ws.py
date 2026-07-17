import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

from services.api.auth import verify_ws_token
from services.rag.answer_generator import RAGAnswerGenerator

logger = logging.getLogger(__name__)


async def rag_websocket_handler(
    websocket: WebSocket,
    generator: RAGAnswerGenerator,
    token: str | None = None,
):
    verify_ws_token(token)
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        req = json.loads(raw)
        question = req.get("question", "").strip()
        if not question:
            await websocket.send_json({"type": "error", "message": "question 不能为空"})
            return

        subject = req.get("subject")
        student_level = req.get("student_level")

        context_results, context_text = generator.retrieve_context(
            question, subject=subject
        )
        system_prompt, user_prompt = generator.build_prompts(
            question,
            context_text,
            subject=subject,
            student_level=student_level,
        )

        await websocket.send_json(
            {"type": "context", "sources": len(context_results)}
        )

        async for event in generator.stream_llm_events(system_prompt, user_prompt):
            await websocket.send_json(event)

        await websocket.send_json(
            {
                "type": "sources",
                "references": [
                    {"file": r["source_file"], "section": r["section_title"]}
                    for r in context_results
                ],
            }
        )
        await websocket.send_json({"type": "done"})
    except WebSocketDisconnect:
        logger.debug("WebSocket 客户端断开")
    except json.JSONDecodeError:
        await websocket.send_json({"type": "error", "message": "无效的 JSON 请求"})
    except Exception as exc:
        logger.warning("RAG WebSocket 错误: %s", exc)
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
