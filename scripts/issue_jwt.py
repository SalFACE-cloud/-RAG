"""Issue a JWT for API testing (login or dev token)."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from configs.settings import DEV_TOKEN_ENABLED


def main():
    parser = argparse.ArgumentParser(description="生成 JWT 测试令牌")
    parser.add_argument("--username", default="admin", help="登录用户名")
    parser.add_argument("--password", default="edu_dev_2026", help="登录密码")
    parser.add_argument("--user", default=None, help="DEV token sub（需 DEV_TOKEN_ENABLED=true）")
    parser.add_argument("--role", default="admin")
    args = parser.parse_args()

    if args.user:
        if not DEV_TOKEN_ENABLED:
            print("DEV_TOKEN_ENABLED=false，请使用 --username/--password 登录", file=sys.stderr)
            return 1
        from services.api.auth import create_token

        print(create_token(args.user, role=args.role))
        return 0

    from services.api.auth import authenticate_user, create_token

    user = authenticate_user(args.username, args.password)
    if not user:
        print("登录失败：用户名或密码错误（请先运行 scripts/seed_dev_user.py）", file=sys.stderr)
        return 1
    print(create_token(user["username"], role=user.get("role") or "student"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
