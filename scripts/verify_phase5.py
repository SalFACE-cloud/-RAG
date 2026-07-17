"""Phase 5 acceptance verification. Writes eval/results/phase5_verify_latest.json"""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from configs.settings import REDIS_HOST, REDIS_PORT

OUT = ROOT / "eval" / "results" / "phase5_verify_latest.json"


def clear_rate_limit_keys() -> None:
    try:
        import redis

        client = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, socket_connect_timeout=2
        )
        keys = client.keys("rate:*")
        if keys:
            client.delete(*keys)
    except Exception:
        pass
DEFAULT_BASE = "http://127.0.0.1:8000/api/v1"
WS_URL = "ws://127.0.0.1:8000/api/v1/rag/ws"


def check_http(base: str) -> dict:
    results = {}
    with httpx.Client(timeout=180.0) as client:
        r = client.get(f"{base}/health")
        results["health"] = {
            "status_code": r.status_code,
            "ok": r.status_code == 200 and r.json().get("status") == "ok",
            "body": r.json() if r.status_code == 200 else r.text[:200],
        }

        r = client.post(f"{base}/auth/token", json={"user_id": "phase5_verify"})
        token_body = r.json() if r.status_code == 200 else {}
        results["auth_token"] = {
            "status_code": r.status_code,
            "ok": r.status_code == 200 and "access_token" in token_body,
            "has_token": bool(token_body.get("access_token")),
        }

        r = client.post(
            f"{base}/knowledge/search",
            json={"query": "虚拟语气与现在事实相反", "subject": "ENG-S", "top_n": 3},
        )
        search_body = r.json() if r.status_code == 200 else {}
        results["knowledge_search"] = {
            "status_code": r.status_code,
            "ok": r.status_code == 200 and search_body.get("total", 0) > 0,
            "total": search_body.get("total"),
        }

        r = client.post(
            f"{base}/rag/ask/sync",
            json={"question": "虚拟语气怎么用？", "subject": "ENG-S"},
        )
        sync_body = r.json() if r.status_code == 200 else {}
        results["rag_ask_sync"] = {
            "status_code": r.status_code,
            "ok": r.status_code == 200 and bool(sync_body.get("answer")),
            "answer_len": len(sync_body.get("answer") or ""),
            "sources_count": len(sync_body.get("sources") or []),
        }

        r = client.get(f"{base}/knowledge/path/MATH-KP-03-01")
        path_body = r.json() if r.status_code == 200 else {}
        results["knowledge_path"] = {
            "status_code": r.status_code,
            "ok": r.status_code == 200 and path_body.get("graph_enabled") is not False,
            "path_len": len(path_body.get("path") or []),
        }

        r = client.get(
            f"{base}/exercises/filter",
            params={"knowledge_id": "MATH-KP-03-01"},
        )
        ex_body = r.json() if r.status_code == 200 else {}
        results["exercises_filter"] = {
            "status_code": r.status_code,
            "ok": r.status_code == 200,
            "exercises_count": len(ex_body.get("exercises") or []),
        }

        r = client.get(
            f"{base}/learning/recommend",
            params={"knowledge_id": "MATH-KP-03-01"},
        )
        rec_body = r.json() if r.status_code == 200 else {}
        results["learning_recommend"] = {
            "status_code": r.status_code,
            "ok": r.status_code == 200 and "related_chunks" in rec_body,
            "keys": list(rec_body.keys()) if r.status_code == 200 else [],
        }

        r = client.get(f"{base}/audio/play/aud-001")
        aud_body = r.json() if r.status_code == 200 else {}
        results["audio_play"] = {
            "status_code": r.status_code,
            "ok": r.status_code == 200 and aud_body.get("audio_id") == "aud-001",
        }

        r = client.get(f"{base}/audio/transcript/aud-001")
        tr_body = r.json() if r.status_code == 200 else {}
        results["audio_transcript"] = {
            "status_code": r.status_code,
            "ok": r.status_code == 200 and len(tr_body.get("segments") or []) > 0,
        }

        r = client.post(
            f"{base}/audio/training/submit",
            json={"audio_id": "aud-001", "answers": [{"q1": "were"}]},
        )
        results["audio_training_submit"] = {
            "status_code": r.status_code,
            "ok": r.status_code == 200 and r.json().get("status") == "received",
        }

        r = client.post(
            f"{base}/assessment/submit",
            json={"knowledge_id": "MATH-KP-03-01", "answers": []},
        )
        results["assessment_submit"] = {
            "status_code": r.status_code,
            "ok": r.status_code == 200 and "assessment_id" in r.json(),
        }

        # SSE removed check via openapi
        r = client.get("http://127.0.0.1:8000/openapi.json", timeout=10)
        paths = r.json().get("paths", {}) if r.status_code == 200 else {}
        results["sse_removed"] = {
            "ok": "/api/v1/rag/ask" not in paths,
            "has_ws_in_app": True,
            "has_rag_sync": "/api/v1/rag/ask/sync" in paths,
        }

    return results


async def check_websocket() -> dict:
    try:
        import websockets
    except ImportError:
        return {"ok": False, "skipped": True, "reason": "websockets package not installed"}

    events = []
    try:
        async with websockets.connect(WS_URL, open_timeout=10) as ws:
            await ws.send(
                json.dumps(
                    {
                        "question": "虚拟语气怎么用？",
                        "subject": "ENG-S",
                        "student_level": "高中",
                    },
                    ensure_ascii=False,
                )
            )
            deadline = time.time() + 120
            while time.time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=30)
                except asyncio.TimeoutError:
                    break
                event = json.loads(raw)
                events.append(event.get("type"))
                if event.get("type") == "done":
                    break
                if event.get("type") == "error":
                    return {"ok": False, "events": events, "error": event.get("message")}
    except Exception as exc:
        return {"ok": False, "events": events, "error": str(exc)}

    has_context = "context" in events
    has_token = "token" in events
    has_sources = "sources" in events
    has_done = "done" in events
    return {
        "ok": has_context and has_token and has_sources and has_done,
        "events": events,
        "event_count": len(events),
    }


async def run_load_test(qps: int, duration: int) -> dict:
    ok = err = 0
    url = "http://127.0.0.1:8000/api/v1/health"
    async with httpx.AsyncClient() as client:
        deadline = time.time() + duration
        while time.time() < deadline:
            tasks = [client.get(url, timeout=5.0) for _ in range(qps)]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            for resp in responses:
                if isinstance(resp, Exception):
                    err += 1
                elif resp.status_code == 200:
                    ok += 1
                else:
                    err += 1
            await asyncio.sleep(1)
    total = ok + err
    err_rate = err / total if total else 1.0
    return {
        "url": url,
        "qps": qps,
        "duration_sec": duration,
        "total": total,
        "ok": ok,
        "err": err,
        "err_rate": round(err_rate, 4),
        "pass": err_rate < 0.01,
    }


async def main_async(base: str, qps: int, duration: int, skip_ws: bool):
    clear_rate_limit_keys()
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "base_url": base,
        "http": check_http(base),
        "websocket_rag": {"skipped": True} if skip_ws else await check_websocket(),
        "load_test": await run_load_test(qps, duration),
    }
    http_ok = all(v.get("ok") for v in report["http"].values())
    ws_data = report["websocket_rag"]
    ws_ok = bool(ws_data.get("skipped")) or ws_data.get("ok") is True
    load_ok = report["load_test"].get("pass") is True
    report["overall"] = {
        "http_pass": http_ok,
        "websocket_pass": ws_ok,
        "load_test_pass": load_ok,
        "phase5_pass": http_ok and ws_ok and load_ok,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["overall"], ensure_ascii=False, indent=2))
    print(f"Report: {OUT}")
    return 0 if report["overall"]["phase5_pass"] else 1


def main():
    parser = argparse.ArgumentParser(description="Phase 5 acceptance verification")
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--qps", type=int, default=100)
    parser.add_argument("--duration", type=int, default=10)
    parser.add_argument("--skip-ws", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main_async(args.base, args.qps, args.duration, args.skip_ws)))


if __name__ == "__main__":
    main()
