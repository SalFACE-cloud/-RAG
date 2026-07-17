import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.settings import REDIS_HOST, REDIS_PORT, VAULT_DIR
from services.indexer.indexer_service import IndexerService
from services.pipeline.converters import FormatConverter
from services.pipeline.file_tracker import FileTracker
from services.pipeline.metadata_validator import MetadataValidator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

INDEXABLE_EXTENSIONS = {".md"}
JOB_TIMEOUT = int(os.getenv("RQ_JOB_TIMEOUT", "600"))
MAX_RETRIES = int(os.getenv("RQ_MAX_RETRIES", "3"))


def _get_redis():
    from redis import Redis

    return Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)


def _get_queue():
    from rq import Queue

    return Queue("pipeline", connection=_get_redis())


def process_file(file_path: str, indexer: IndexerService | None = None) -> dict:
    """Phase 2 单文件流水线：格式转换 → 元数据校验 → 索引入库。"""
    tracker = FileTracker()
    converter = FormatConverter()
    validator = MetadataValidator()
    path = Path(file_path)

    ext = path.suffix.lower()
    if ext in INDEXABLE_EXTENSIONS:
        md_path = str(path.resolve())
    else:
        conv = converter.convert(str(path))
        if not conv.get("success"):
            tracker.mark_processed(str(path), "convert_failed")
            return {"success": False, "stage": "convert", "error": conv.get("error"), "source_file": str(path)}
        md_path = conv["output_path"]
        logger.info("转换完成: %s -> %s", path, md_path)

    validation = validator.validate(md_path)
    if not validation.valid:
        tracker.mark_processed(str(path), "metadata_warning")
        return {
            "success": True,
            "stage": "metadata_warning",
            "warnings": validation.errors,
            "md_file": md_path,
            "source_file": str(path),
        }

    svc = indexer or IndexerService()
    if indexer is None:
        svc.init_all()
    result = svc.index_markdown_file(md_path)
    if result["success"]:
        tracker.mark_processed(str(path), "indexed")
        return {
            "success": True,
            "stage": "indexed",
            "source_file": str(path),
            "md_file": md_path,
            "chunk_count": result.get("chunk_count"),
        }

    tracker.mark_processed(str(path), "index_failed")
    return {"success": False, "stage": "index", "error": result.get("error"), "source_file": str(path)}


def enqueue_file(file_path: str) -> str:
    from rq import Retry

    queue = _get_queue()
    job = queue.enqueue(
        process_file,
        file_path,
        job_timeout=JOB_TIMEOUT,
        retry=Retry(max=MAX_RETRIES, interval=[30, 60, 120]),
    )
    logger.info("入队: %s -> job %s", file_path, job.id)
    return job.id


def enqueue_changed_files(vault_dir: str | None = None, changed_files: list[str] | None = None) -> list[str]:
    vault = vault_dir or VAULT_DIR
    tracker = FileTracker()
    if changed_files:
        pending = [str(Path(f)) for f in changed_files if Path(f).exists()]
    elif os.getenv("CHANGED_FILES"):
        import json

        pending = [f for f in json.loads(os.getenv("CHANGED_FILES", "[]")) if Path(f).exists()]
    else:
        pending = tracker.get_pending_files(vault)

    job_ids = [enqueue_file(fp) for fp in pending]
    logger.info("已入队 %s 个文件", len(job_ids))
    return job_ids


def run_worker(burst: bool = False) -> None:
    conn = _get_redis()
    if sys.platform == "win32":
        from rq.worker import SimpleWorker

        worker = SimpleWorker(["pipeline"], connection=conn)
    else:
        from rq import Worker

        worker = Worker(["pipeline"], connection=conn)
    worker.work(burst=burst)


def run_batch(vault_dir: str | None = None, force: bool = False, use_queue: bool | None = None):
    use_rq = use_queue if use_queue is not None else os.getenv("PIPELINE_USE_RQ", "false").lower() == "true"
    vault = vault_dir or VAULT_DIR
    tracker = FileTracker()

    if force:
        pending = [
            str(f)
            for f in Path(vault).rglob("*")
            if f.is_file()
            and not f.name.startswith(".")
            and f.suffix.lower() in tracker.SUPPORTED_EXTENSIONS
            and "_converted" not in f.parts
            and "0_项目文档" not in f.parts
            and ".gitkeep" not in f.name
        ]
    else:
        pending = tracker.get_pending_files(vault)

    logger.info("待处理文件数: %s (use_queue=%s)", len(pending), use_rq)
    if use_rq:
        return [{"job_id": enqueue_file(fp), "source_file": fp} for fp in pending]

    indexer = IndexerService()
    indexer.init_all()
    results = []
    for fp in pending:
        logger.info("处理: %s", fp)
        result = process_file(fp, indexer=indexer)
        results.append(result)
        logger.info("结果: %s", result)
    return results


def run_convert_only(vault_dir: str | None = None):
    vault = vault_dir or VAULT_DIR
    converter = FormatConverter()
    tracker = FileTracker()
    pending = [
        str(f)
        for f in Path(vault).rglob("*")
        if f.is_file()
        and not f.name.startswith(".")
        and f.suffix.lower() in {".docx", ".doc", ".pdf"}
        and "_converted" not in f.parts
    ]
    results = []
    for fp in pending:
        conv = converter.convert(fp)
        if conv.get("success"):
            tracker.mark_processed(fp, "converted")
        else:
            tracker.mark_processed(fp, "convert_failed")
        results.append({"source": fp, **conv})
    return results


if __name__ == "__main__":
    force = "--force" in sys.argv
    if "--worker" in sys.argv:
        run_worker(burst="--burst" in sys.argv)
    elif "--enqueue" in sys.argv:
        enqueue_changed_files()
    else:
        run_batch(force=force)
