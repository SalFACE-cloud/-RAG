"""Issue a JWT for API testing."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.api.auth import create_token


def main():
    parser = argparse.ArgumentParser(description="生成 JWT 测试令牌")
    parser.add_argument("--user", default="dev_user", help="JWT sub 字段")
    args = parser.parse_args()
    print(create_token(args.user))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
