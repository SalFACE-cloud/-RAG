import logging
import time
from functools import wraps
from typing import Callable, Optional

import jwt
import redis
from fastapi import HTTPException, Request

from configs.settings import (
    AUTH_ENABLED,
    JWT_EXPIRE_HOURS,
    JWT_SECRET_KEY,
    RATE_LIMIT_PER_MINUTE,
    REDIS_HOST,
    REDIS_PORT,
)

logger = logging.getLogger(__name__)

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


def create_token(sub: str, extra: dict | None = None) -> str:
    if not JWT_SECRET_KEY:
        raise ValueError("JWT_SECRET_KEY 未配置")
    payload = {
        "sub": sub,
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRE_HOURS * 3600,
        **(extra or {}),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict:
    if not JWT_SECRET_KEY:
        raise HTTPException(status_code=500, detail="JWT_SECRET_KEY 未配置")
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token 已过期") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="无效 Token") from exc


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
