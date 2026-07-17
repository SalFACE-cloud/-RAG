from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from services.api.auth import (
    authenticate_user,
    create_token,
    ensure_dev_token_allowed,
    rate_limit,
)

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenRequest(BaseModel):
    user_id: str
    role: str = "student"


@router.post("/auth/login")
@rate_limit(max_requests=30)
async def login(request: Request, req: LoginRequest):
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_token(user["username"], role=user.get("role") or "student")
    return {
        "access_token": token,
        "token_type": "Bearer",
        "username": user["username"],
        "role": user.get("role") or "student",
    }


@router.post("/auth/token")
@rate_limit(max_requests=30)
async def issue_token(request: Request, req: TokenRequest):
    ensure_dev_token_allowed()
    try:
        token = create_token(req.user_id, role=req.role)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "access_token": token,
        "token_type": "Bearer",
        "user_id": req.user_id,
        "role": req.role,
    }
