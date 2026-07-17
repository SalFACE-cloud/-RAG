import json
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from configs.settings import AUDIO_SEED_PATH
from services.api.auth import rate_limit, verify_token

router = APIRouter()


def _load_seed() -> dict:
    path = Path(AUDIO_SEED_PATH)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _get_audio(audio_id: str) -> dict:
    data = _load_seed()
    if audio_id not in data:
        raise HTTPException(status_code=404, detail=f"音频不存在: {audio_id}")
    return data[audio_id]


@router.get("/audio/play/{audio_id}")
@rate_limit()
async def get_audio(request: Request, audio_id: str):
    verify_token(request)
    item = _get_audio(audio_id)
    return {
        "audio_id": audio_id,
        "audio_url": item.get("audio_url"),
        "transcript_url": f"/api/v1/audio/transcript/{audio_id}",
        "title": item.get("title"),
        "subject": item.get("subject"),
        "segments": item.get("segments", []),
        "questions": item.get("questions", []),
        "knowledge_ids": item.get("knowledge_ids", []),
    }


@router.get("/audio/transcript/{audio_id}")
@rate_limit()
async def get_transcript(request: Request, audio_id: str):
    verify_token(request)
    item = _get_audio(audio_id)
    return {
        "audio_id": audio_id,
        "title": item.get("title"),
        "segments": item.get("segments", []),
    }


class TrainingSubmit(BaseModel):
    audio_id: str
    answers: list[dict] = []
    score: Optional[float] = None


@router.post("/audio/training/submit")
@rate_limit()
async def submit_training(request: Request, body: TrainingSubmit):
    verify_token(request)
    _get_audio(body.audio_id)
    return {
        "status": "received",
        "training_id": str(uuid.uuid4()),
        "audio_id": body.audio_id,
    }
