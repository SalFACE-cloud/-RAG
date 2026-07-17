from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from services.api.auth import create_token, rate_limit

router = APIRouter()


class TokenRequest(BaseModel):
    user_id: str


@router.post("/auth/token")
@rate_limit(max_requests=30)
async def issue_token(request: Request, req: TokenRequest):
    try:
        token = create_token(req.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"access_token": token, "token_type": "Bearer", "user_id": req.user_id}
