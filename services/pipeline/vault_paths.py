"""Vault 路径扫描与 ignore 规则（流水线 CLI 共用）。"""
from __future__ import annotations

import fnmatch
import json
from datetime import datetime
from pathlib import Path

PIPELINE_LOG_DIR = Path("vault/9_数据流水线/logs")
CHANGED_FILES_JSON = PIPELINE_LOG_DIR / "changed_files.json"
CHUNKS_MANIFEST_JSON = PIPELINE_LOG_DIR / "chunks_manifest.json"
PIPELINE_LOG = PIPELINE_LOG_DIR / "pipeline.log"
PIPELINE_RESULT_JSON = PIPELINE_LOG_DIR / "pipeline_result.json"

DEFAULT_IGNORE = ["0_项目文档/**", "_converted/**", "**/.gitkeep"]


def parse_ignore_patterns(raw: str | None) -> list[str]:
    if not raw:
        return list(DEFAULT_IGNORE)
    parts = [p.strip() for p in raw.replace(",", ";").split(";") if p.strip()]
    return parts or list(DEFAULT_IGNORE)


def _rel_posix(path: Path, vault_root: Path) -> str:
    try:
        return path.relative_to(vault_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def should_ignore(path: Path, vault_root: Path, ignore_patterns: list[str]) -> bool:
    rel = _rel_posix(path.resolve(), vault_root.resolve())
    name = path.name
    if name.startswith("."):
        return True
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(name, pattern):
            return True
        # 目录前缀：0_项目文档
        prefix = pattern.rstrip("*").rstrip("/")
        if prefix and rel.startswith(prefix):
            return True
    return False


def iter_vault_files(
    vault_root: Path,
    ignore_patterns: list[str],
    extensions: set[str] | None = None,
) -> list[Path]:
    vault_root = vault_root.resolve()
    files: list[Path] = []
    if not vault_root.exists():
        return files
    for f in sorted(vault_root.rglob("*")):
        if not f.is_file():
            continue
        if should_ignore(f, vault_root, ignore_patterns):
            continue
        if extensions and f.suffix.lower() not in extensions:
            continue
        files.append(f)
    return files


def load_changed_files(vault_root: Path) -> list[str] | None:
    if not CHANGED_FILES_JSON.exists():
        return None
    data = json.loads(CHANGED_FILES_JSON.read_text(encoding="utf-8"))
    files = data.get("files") or []
    resolved = [str(f) for f in files if Path(f).exists()]
    return resolved if resolved else None


def save_changed_files(files: list[str], scan_mode: str) -> Path:
    PIPELINE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "scan_mode": scan_mode,
        "timestamp": datetime.now().isoformat(),
        "files": [str(Path(f).resolve()) for f in files],
    }
    CHANGED_FILES_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return CHANGED_FILES_JSON


def append_pipeline_log(message: str) -> None:
    PIPELINE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now().isoformat()}] {message}\n"
    with PIPELINE_LOG.open("a", encoding="utf-8") as fh:
        fh.write(line)


def write_pipeline_result(step: str, ok: bool, detail: dict | None = None) -> None:
    PIPELINE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "step": step,
        "ok": ok,
        "timestamp": datetime.now().isoformat(),
        "detail": detail or {},
    }
    if PIPELINE_RESULT_JSON.exists():
        existing = json.loads(PIPELINE_RESULT_JSON.read_text(encoding="utf-8"))
        if not isinstance(existing, list):
            existing = [existing]
    else:
        existing = []
    existing.append(payload)
    PIPELINE_RESULT_JSON.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
