import time

from fastapi import APIRouter, Request

from services.api.auth import verify_token

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    verify_token(request)
    return {"status": "ok", "timestamp": time.time()}
