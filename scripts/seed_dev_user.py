"""创建/更新开发环境管理员账号。"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from passlib.context import CryptContext

from services.common.db import ensure_schema, get_connection

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def seed_user(username: str, password: str, role: str = "admin") -> int:
    ensure_schema()
    password_hash = pwd_context.hash(password)
    external_id = username
    sql = """
        INSERT INTO users (username, password_hash, role, external_id, nickname)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (username) DO UPDATE SET
            password_hash = EXCLUDED.password_hash,
            role = EXCLUDED.role,
            updated_at = NOW()
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (username, password_hash, role, external_id, username))
    print(f"Seeded user: {username} (role={role})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed development admin user")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="edu_dev_2026")
    parser.add_argument("--role", default="admin")
    args = parser.parse_args()
    try:
        return seed_user(args.username, args.password, args.role)
    except Exception as exc:
        print(f"Seed failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
