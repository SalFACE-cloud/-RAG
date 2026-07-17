"""Simple load test: python scripts/load_test.py --url http://127.0.0.1:8000/api/v1/health --qps 100 --duration 10"""
import argparse
import asyncio
import time

import httpx


async def run(url: str, qps: int, duration: int, token: str | None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    ok = 0
    err = 0

    async with httpx.AsyncClient() as client:
        deadline = time.perf_counter() + duration
        while time.perf_counter() < deadline:
            tasks = []
            for _ in range(qps):
                tasks.append(_one(client, url, headers))
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if r is True:
                    ok += 1
                else:
                    err += 1
            await asyncio.sleep(1)

    total = ok + err
    err_rate = err / total if total else 0.0
    print(f"url={url}")
    print(f"total={total} ok={ok} err={err} err_rate={err_rate:.2%}")
    return 0 if err_rate < 0.01 else 1


async def _one(client: httpx.AsyncClient, url: str, headers: dict) -> bool:
    try:
        resp = await client.get(url, headers=headers, timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="HTTP 并发压测")
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/v1/health")
    parser.add_argument("--qps", type=int, default=100)
    parser.add_argument("--duration", type=int, default=10)
    parser.add_argument("--token", default=None)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.url, args.qps, args.duration, args.token)))


if __name__ == "__main__":
    main()
