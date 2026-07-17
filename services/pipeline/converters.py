import logging
import shutil
import subprocess
from pathlib import Path

from configs.settings import CONVERTED_DIR

logger = logging.getLogger(__name__)

STRATEGIES = {
    ".md": "direct",
    ".docx": "pandoc",
    ".doc": "pandoc",
    ".pdf": "pandoc",
    ".pptx": "not_implemented",
    ".mp3": "not_implemented",
    ".wav": "not_implemented",
    ".png": "not_implemented",
    ".jpg": "not_implemented",
    ".jpeg": "not_implemented",
}


class FormatConverter:
    def __init__(self, output_dir: str | None = None):
        self.output_dir = Path(output_dir or CONVERTED_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _pandoc_available() -> bool:
        return shutil.which("pandoc") is not None

    def convert(self, source_path: str) -> dict:
        src = Path(source_path)
        ext = src.suffix.lower()
        strategy = STRATEGIES.get(ext)

        if strategy is None:
            return {"success": False, "error": f"不支持的文件类型: {ext}"}

        if strategy == "not_implemented":
            return {
                "success": False,
                "error": f"{ext} 转换尚未实现（预留接口: {strategy}）",
            }

        rel_stem = src.stem
        out_path = self.output_dir / f"{rel_stem}.md"

        if strategy == "direct":
            content = src.read_text(encoding="utf-8")
            out_path.write_text(content, encoding="utf-8")
            return {"success": True, "output_path": str(out_path.resolve())}

        if strategy == "pandoc":
            if not self._pandoc_available():
                return {
                    "success": False,
                    "error": "未检测到 pandoc，请安装: https://pandoc.org/installing.html",
                }
            try:
                subprocess.run(
                    [
                        "pandoc",
                        str(src),
                        "-f",
                        "docx" if ext in {".docx", ".doc"} else "pdf",
                        "-t",
                        "gfm",
                        "-o",
                        str(out_path),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError as exc:
                logger.error("Pandoc 转换失败: %s", exc.stderr)
                return {"success": False, "error": exc.stderr or str(exc)}

            return {"success": True, "output_path": str(out_path.resolve())}

        return {"success": False, "error": f"未知策略: {strategy}"}
