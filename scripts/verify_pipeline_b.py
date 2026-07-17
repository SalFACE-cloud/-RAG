"""方案 B 分步 CLI 流水线验收（metadata → tracker → chunker → embedder → meili）。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "eval" / "results" / "pipeline_b_verify_latest.json"


def run_step(name: str, cmd: list[str], env: dict | None = None) -> dict:
    print(f"\n========== {name} ==========")
    print(">>>", " ".join(cmd))
    import os

    merged = {**os.environ, **(env or {})}
    proc = subprocess.run(cmd, cwd=ROOT, env=merged, capture_output=True, text=True)
    if proc.stdout:
        print(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    ok = proc.returncode == 0
    return {
        "name": name,
        "ok": ok,
        "exit_code": proc.returncode,
        "cmd": cmd,
    }


def main() -> int:
    py = sys.executable
    vault = "./vault"
    ignore = "0_项目文档/**"
    steps: list[dict] = []

    steps.append(
        run_step(
            "validate",
            [py, "services/pipeline/metadata_validator.py", "--vault-path", vault, "--ignore-path", ignore],
        )
    )
    steps.append(
        run_step(
            "file_tracker",
            [
                py,
                "services/pipeline/file_tracker.py",
                "--scan-mode",
                "full",
                "--vault-path",
                vault,
                "--ignore-path",
                ignore,
            ],
        )
    )
    steps.append(
        run_step(
            "chunker",
            [
                py,
                "services/indexer/chunker.py",
                "--vault-path",
                vault,
                "--ignore-paths",
                ignore,
                "--chunk-size",
                "512",
                "--chunk-overlap",
                "64",
            ],
        )
    )
    steps.append(
        run_step(
            "embedder",
            [py, "services/indexer/embedder.py", "--vault-path", vault, "--mock-embeddings"],
        )
    )
    steps.append(run_step("meili", [py, "services/indexer/meili_indexer.py"]))

    manifest_path = ROOT / "vault" / "9_数据流水线" / "logs" / "chunks_manifest.json"
    chunk_count = 0
    if manifest_path.exists():
        chunk_count = len(json.loads(manifest_path.read_text(encoding="utf-8")).get("chunks", []))

    overall_ok = all(s["ok"] for s in steps) and chunk_count > 0
    report = {
        "pipeline": "B",
        "steps": steps,
        "chunk_count": chunk_count,
        "overall_ok": overall_ok,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"overall_ok": overall_ok, "chunk_count": chunk_count, "report": str(OUT)}, ensure_ascii=False))
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
