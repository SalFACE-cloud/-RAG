import hashlib
import json
from datetime import datetime
from pathlib import Path


class FileTracker:
    def __init__(self, state_file: str = "configs/pipeline_state.json"):
        self.state_file = Path(state_file)
        self.state = self._load_state()

    def _load_state(self) -> dict:
        if self.state_file.exists():
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        return {}

    def _save_state(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(
            json.dumps(self.state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_hash(self, file_path: str) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def is_changed(self, file_path: str) -> bool:
        abs_path = str(Path(file_path).resolve())
        return self.get_hash(file_path) != self.state.get(abs_path, {}).get("hash")

    def mark_processed(self, file_path: str, status: str = "success"):
        abs_path = str(Path(file_path).resolve())
        self.state[abs_path] = {
            "hash": self.get_hash(file_path),
            "status": status,
            "processed_at": datetime.now().isoformat(),
        }
        self._save_state()

    SUPPORTED_EXTENSIONS = {".md", ".docx", ".doc", ".pdf"}

    def get_pending_files(self, directory: str) -> list[str]:
        pending = []
        for f in Path(directory).rglob("*"):
            if not f.is_file() or f.name.startswith("."):
                continue
            if f.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
                continue
            if "_converted" in f.parts:
                continue
            if "0_项目文档" in f.parts:
                continue
            if self.is_changed(str(f)):
                pending.append(str(f))
        return pending

    def get_pending_md_files(self, directory: str) -> list[str]:
        return [
            f for f in self.get_pending_files(directory)
            if Path(f).suffix.lower() == ".md"
        ]


def _cli_root() -> Path:
    import sys

    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def get_git_diff_files(vault_root: Path) -> list[str]:
    import subprocess

    vault_root = vault_root.resolve()
    candidates: list[str] = []
    for ref_pair in (["HEAD^", "HEAD"], ["HEAD~1", "HEAD"]):
        try:
            out = subprocess.check_output(
                ["git", "diff", "--name-only", ref_pair[0], ref_pair[1], "--", "vault/"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            candidates = [line.strip() for line in out.splitlines() if line.strip()]
            if candidates:
                break
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue

    if not candidates:
        try:
            out = subprocess.check_output(
                ["git", "ls-files", "vault/"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            candidates = [line.strip() for line in out.splitlines() if line.strip()]
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    resolved = []
    for rel in candidates:
        p = Path(rel)
        if not p.is_absolute():
            p = vault_root.parent / p if rel.startswith("vault") else vault_root / rel
        if p.exists() and p.is_file():
            resolved.append(str(p.resolve()))
    return resolved


def run_git_diff_scan(vault_path: Path, ignore_patterns: list[str]) -> list[str]:
    from services.pipeline.converters import FormatConverter
    from services.pipeline.vault_paths import append_pipeline_log, save_changed_files, should_ignore

    vault_path = vault_path.resolve()
    tracker = FileTracker()
    converter = FormatConverter()
    raw = get_git_diff_files(vault_path)
    append_pipeline_log(f"file_tracker git_diff raw_count={len(raw)}")

    changed: list[str] = []
    for fp in raw:
        path = Path(fp)
        if should_ignore(path, vault_path, ignore_patterns):
            continue
        ext = path.suffix.lower()
        if ext in {".docx", ".doc", ".pdf"}:
            conv = converter.convert(str(path))
            if conv.get("success"):
                changed.append(conv["output_path"])
                tracker.mark_processed(str(path), "converted")
                print(f"[CONVERT] {path.name} -> {conv['output_path']}")
            else:
                tracker.mark_processed(str(path), "convert_failed")
                print(f"[CONVERT FAIL] {path}: {conv.get('error')}")
        elif ext == ".md":
            changed.append(str(path.resolve()))
        else:
            changed.append(str(path.resolve()))

    if not changed:
        changed = tracker.get_pending_md_files(str(vault_path))
        append_pipeline_log(f"file_tracker fallback pending_count={len(changed)}")

    save_changed_files(changed, "git_diff")
    append_pipeline_log(f"file_tracker done changed_count={len(changed)}")
    for f in changed:
        print(f"[CHANGED] {f}")
    return changed


def main_cli() -> int:
    import argparse

    _cli_root()
    from services.pipeline.vault_paths import parse_ignore_patterns, write_pipeline_result

    parser = argparse.ArgumentParser(description="文件变更跟踪与格式转换")
    parser.add_argument("--scan-mode", choices=["git_diff", "pending"], default="git_diff")
    parser.add_argument("--vault-path", default="./vault")
    parser.add_argument("--ignore-path", default="0_项目文档/**")
    args = parser.parse_args()

    vault = Path(args.vault_path).resolve()
    ignore = parse_ignore_patterns(args.ignore_path)
    if args.scan_mode == "git_diff":
        files = run_git_diff_scan(vault, ignore)
    else:
        tracker = FileTracker()
        files = tracker.get_pending_md_files(str(vault))
        from services.pipeline.vault_paths import save_changed_files

        save_changed_files(files, "pending")

    write_pipeline_result("file_tracker", True, {"changed_count": len(files)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main_cli())
