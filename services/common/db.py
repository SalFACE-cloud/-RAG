"""轻量 PostgreSQL 访问层（documents / users）。"""
import json
import logging
from contextlib import contextmanager
from typing import Any, Optional

import psycopg2
import psycopg2.extras

from configs.settings import (
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
)

logger = logging.getLogger(__name__)


@contextmanager
def get_connection():
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        connect_timeout=5,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def upsert_document(
    file_path: str,
    *,
    subject: Optional[str] = None,
    doc_type: Optional[str] = None,
    status: str = "pending",
    review_errors: Optional[list[str]] = None,
) -> None:
    """写入或更新 documents 表记录。"""
    review_json = json.dumps(review_errors, ensure_ascii=False) if review_errors else None
    sql = """
        INSERT INTO documents (file_path, subject, doc_type, status, review_errors, updated_at)
        VALUES (%s, %s, %s, %s, %s::jsonb, NOW())
        ON CONFLICT (file_path) DO UPDATE SET
            subject = EXCLUDED.subject,
            doc_type = EXCLUDED.doc_type,
            status = EXCLUDED.status,
            review_errors = EXCLUDED.review_errors,
            updated_at = NOW()
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (file_path, subject, doc_type, status, review_json))
    except Exception as exc:
        logger.warning("documents 表写入失败（PG 可能未启动）: %s", exc)


def get_user_by_username(username: str) -> Optional[dict[str, Any]]:
    """按 username 查询用户（含 password_hash、role）。"""
    sql = """
        SELECT id, username, password_hash, role, external_id, nickname
        FROM users
        WHERE username = %s
        LIMIT 1
    """
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (username,))
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception as exc:
        logger.warning("users 表查询失败: %s", exc)
        return None


def ensure_schema() -> bool:
    """确保 documents / users 鉴权列存在（兼容已有 PG 数据卷）。"""
    statements = [
        """
        CREATE TABLE IF NOT EXISTS documents (
            id SERIAL PRIMARY KEY,
            file_path VARCHAR(512) UNIQUE NOT NULL,
            subject VARCHAR(20),
            doc_type VARCHAR(30),
            status VARCHAR(20) DEFAULT 'pending',
            review_errors JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(50) UNIQUE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'student'",
        "ALTER TABLE users ALTER COLUMN external_id DROP NOT NULL",
    ]
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                for stmt in statements:
                    cur.execute(stmt)
        return True
    except Exception as exc:
        logger.warning("ensure_schema 失败: %s", exc)
        return False


def table_exists(table_name: str) -> bool:
    sql = """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        )
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (table_name,))
                return bool(cur.fetchone()[0])
    except Exception:
        return False
