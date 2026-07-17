import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from configs.settings import CONVERTED_DIR

logger = logging.getLogger(__name__)

STRATEGIES = {
    ".md": "direct",
    ".docx": "pandoc_doc",
    ".doc": "pandoc_doc",
    ".pdf": "pandoc_pdf",
    ".pptx": "pandoc_ppt",
    ".mp3": "whisper",
    ".wav": "whisper",
    ".m4a": "whisper",
    ".mp4": "ffmpeg_whisper",
    ".mov": "ffmpeg_whisper",
    ".png": "paddle_ocr",
    ".jpg": "paddle_ocr",
    ".jpeg": "paddle_ocr",
    ".webp": "paddle_ocr",
}


class FormatConverter:
    """多格式素材统一转换为 Markdown。"""

    def __init__(self, output_dir: str | None = None):
        self.output_dir = Path(output_dir or CONVERTED_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._media_dir = self.output_dir / "media"
        self._media_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _pandoc_available() -> bool:
        return shutil.which("pandoc") is not None

    @staticmethod
    def _ffmpeg_available() -> bool:
        return shutil.which("ffmpeg") is not None

    def convert(self, source_path: str) -> dict:
        src = Path(source_path)
        ext = src.suffix.lower()
        strategy = STRATEGIES.get(ext)

        if strategy is None:
            return {"success": False, "error": f"不支持的文件类型: {ext}"}

        handler = getattr(self, f"_convert_{strategy}", None)
        if handler is None:
            return {"success": False, "error": f"无转换处理器: {strategy}"}

        result = handler(str(src))
        if result.get("success") and "output_path" not in result and "output" in result:
            result["output_path"] = result["output"]
        return result

    def _convert_direct(self, file_path: str) -> dict:
        content = Path(file_path).read_text(encoding="utf-8")
        out_path = self.output_dir / f"{Path(file_path).stem}.md"
        out_path.write_text(content, encoding="utf-8")
        return {
            "success": True,
            "output_path": str(out_path.resolve()),
            "output": str(out_path.resolve()),
            "converter": "direct",
        }

    def _convert_pandoc_doc(self, file_path: str) -> dict:
        return self._run_pandoc(file_path, input_fmt="docx", converter="pandoc_doc")

    def _convert_pandoc_pdf(self, file_path: str) -> dict:
        return self._run_pandoc(file_path, input_fmt="pdf", converter="pandoc_pdf")

    def _convert_pandoc_ppt(self, file_path: str) -> dict:
        return self._run_pandoc(file_path, input_fmt="pptx", converter="pandoc_ppt")

    def _run_pandoc(self, file_path: str, input_fmt: str, converter: str) -> dict:
        if not self._pandoc_available():
            return {
                "success": False,
                "error": "未检测到 pandoc，请安装: https://pandoc.org/installing.html",
            }
        out_path = self.output_dir / f"{Path(file_path).stem}.md"
        try:
            subprocess.run(
                [
                    "pandoc",
                    file_path,
                    "-f",
                    input_fmt,
                    "-t",
                    "gfm",
                    "-o",
                    str(out_path),
                    "--wrap=none",
                    "--extract-media",
                    str(self._media_dir),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            logger.error("Pandoc 转换失败: %s", exc.stderr)
            return {"success": False, "error": exc.stderr or str(exc)}

        return {
            "success": True,
            "output_path": str(out_path.resolve()),
            "output": str(out_path.resolve()),
            "converter": converter,
        }

    def _convert_whisper(self, file_path: str) -> dict:
        try:
            import whisper
        except ImportError:
            return {"success": False, "error": "依赖未安装: openai-whisper"}

        try:
            model = whisper.load_model("base")
            result = model.transcribe(file_path, language="zh", word_timestamps=True)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        stem = Path(file_path).stem
        md_file = self.output_dir / f"{stem}_文字稿.md"
        md_content = "# 听力原文\n\n"
        for seg in result.get("segments", []):
            start = self._format_time(seg["start"])
            end = self._format_time(seg["end"])
            md_content += f"> {start} - {end}\n\n{seg['text']}\n\n---\n\n"
        md_file.write_text(md_content, encoding="utf-8")

        srt_file = self.output_dir / f"{stem}.srt"
        with open(srt_file, "w", encoding="utf-8") as f:
            for i, seg in enumerate(result.get("segments", []), 1):
                f.write(f"{i}\n")
                f.write(
                    f"{self._format_srt_time(seg['start'])} --> "
                    f"{self._format_srt_time(seg['end'])}\n"
                )
                f.write(f"{seg['text']}\n\n")

        return {
            "success": True,
            "output_path": str(md_file.resolve()),
            "output": str(md_file.resolve()),
            "srt": str(srt_file.resolve()),
            "converter": "whisper",
        }

    def _convert_ffmpeg_whisper(self, file_path: str) -> dict:
        if not self._ffmpeg_available():
            return {"success": False, "error": "未检测到 ffmpeg，请安装: https://ffmpeg.org/download.html"}

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            audio_path = tmp.name

        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", file_path, "-vn", "-acodec", "pcm_s16le", audio_path],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            Path(audio_path).unlink(missing_ok=True)
            return {"success": False, "error": exc.stderr or str(exc)}

        try:
            result = self._convert_whisper(audio_path)
            if result.get("success"):
                result["converter"] = "ffmpeg_whisper"
            return result
        finally:
            Path(audio_path).unlink(missing_ok=True)

    def _convert_paddle_ocr(self, file_path: str) -> dict:
        try:
            from paddleocr import PaddleOCR
        except ImportError:
            return {"success": False, "error": "依赖未安装: paddleocr / paddlepaddle"}

        try:
            ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
            ocr_result = ocr.ocr(file_path, cls=True)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        md_file = self.output_dir / f"{Path(file_path).stem}_OCR.md"
        md_content = f"# {Path(file_path).stem} OCR 结果\n\n"
        lines = ocr_result[0] if ocr_result else []
        for line in lines or []:
            text = line[1][0]
            confidence = line[1][1]
            md_content += f"- {text} (置信度: {confidence:.2f})\n"

        md_file.write_text(md_content, encoding="utf-8")
        return {
            "success": True,
            "output_path": str(md_file.resolve()),
            "output": str(md_file.resolve()),
            "converter": "paddle_ocr",
        }

    @staticmethod
    def _format_time(seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        return f"{h:d}:{m:02d}:{s:02d}"

    @staticmethod
    def _format_srt_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


CONVERT_ONLY_EXTENSIONS = {
    ".docx",
    ".doc",
    ".pdf",
    ".pptx",
    ".mp3",
    ".wav",
    ".m4a",
    ".mp4",
    ".mov",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}
