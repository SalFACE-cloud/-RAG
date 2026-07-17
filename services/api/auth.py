import logging
import time
from functools import wraps
from typing import Callable, Optional

import redis
from fastapi import HTTPException, Request
from jose import JWTError, jwt
from passlib.context import CryptContext

from configs.settings import (
    AUTH_ENABLED,
    DEV_TOKEN_ENABLED,
    JWT_EXPIRE_HOURS,
    JWT_SECRET_KEY,
    RATE_LIMIT_PER_MINUTE,
    REDIS_HOST,
    REDIS_PORT,
)
from services.common.db import get_user_by_username

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"

_redis_client: Optional[redis.Redis] = None


def _get_redis() -> Optional[redis.Redis]:
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                decode_responses=True,
                socket_connect_timeout=2,
            )
            _redis_client.ping()
        except Exception as exc:
            logger.warning("Redis 不可用，限流已降级: %s", exc)
            _redis_client = None
    return _redis_client


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def authenticate_user(username: str, password: str) -> Optional[dict]:
    user = get_user_by_username(username)
    if not user or not user.get("password_hash"):
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def create_token(sub: str, role: str = "student", extra: dict | None = None) -> str:
    if not JWT_SECRET_KEY:
        raise ValueError("JWT_SECRET_KEY 未配置")
    payload = {
        "sub": sub,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRE_HOURS * 3600,
        **(extra or {}),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    if not JWT_SECRET_KEY:
        raise HTTPException(status_code=500, detail="JWT_SECRET_KEY 未配置")
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="无效或已过期的 Token") from exc


def verify_token(request: Request) -> Optional[dict]:
    if not AUTH_ENABLED:
        return None

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少 Bearer Token")

    return decode_token(auth_header[7:])


def verify_ws_token(token: Optional[str]) -> Optional[dict]:
    if not AUTH_ENABLED:
        return None
    if not token:
        raise HTTPException(status_code=401, detail="缺少 token 查询参数")
    return decode_token(token)


def require_role(*roles: str):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            payload = verify_token(request)
            if AUTH_ENABLED and payload:
                role = payload.get("role", "student")
                if role not in roles:
                    raise HTTPException(status_code=403, detail="权限不足")
            return await func(request, *args, **kwargs)

        return wrapper

    return decorator


def ensure_dev_token_allowed() -> None:
    if not DEV_TOKEN_ENABLED:
        raise HTTPException(status_code=403, detail="开发 Token 端点已禁用，请使用 /auth/login")


def rate_limit(max_requests: int | None = None, window: int = 60):
    limit = max_requests if max_requests is not None else RATE_LIMIT_PER_MINUTE

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            client = _get_redis()
            if client is not None:
                client_ip = request.client.host if request.client else "unknown"
                key = f"rate:{client_ip}:{request.url.path}"
                try:
                    count = client.incr(key)
                    if count == 1:
                        client.expire(key, window)
                    if count > limit:
                        raise HTTPException(status_code=429, detail="请求过于频繁")
                except HTTPException:
                    raise
                except Exception as exc:
                    logger.warning("限流检查失败，已跳过: %s", exc)

            return await func(request, *args, **kwargs)

        return wrapper

    return decorator
