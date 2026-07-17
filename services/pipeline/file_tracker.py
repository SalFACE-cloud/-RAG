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
