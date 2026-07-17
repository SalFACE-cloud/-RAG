import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.settings import REDIS_HOST, REDIS_PORT, RQ_MAX_RETRIES, VAULT_DIR
from services.common.db import upsert_document
from services.indexer.indexer_service import IndexerService
from services.pipeline.converters import CONVERT_ONLY_EXTENSIONS, FormatConverter
from services.pipeline.file_tracker import FileTracker
from services.pipeline.metadata_validator import MetadataValidator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

INDEXABLE_EXTENSIONS = {".md"}
JOB_TIMEOUT = int(os.getenv("RQ_JOB_TIMEOUT", "600"))
FAILED_JOBS_KEY = "pipeline:failed_jobs"


def _get_redis():
    from redis import Redis

    return Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)


def _get_queue(name: str = "pipeline"):
    from rq import Queue

    return Queue(name, connection=_get_redis())


def _record_failed_job(job, connection, type, value, traceback_str):
    """RQ on_failure 回调：写入审计 list 并 enqueue 到 failed 队列。"""
    from rq import Queue

    file_path = job.args[0] if job.args else None
    payload = {
        "job_id": job.id,
        "file_path": file_path,
        "error": str(value),
        "traceback": traceback_str,
        "failed_at": datetime.now().isoformat(),
    }
    try:
        connection.lpush(FAILED_JOBS_KEY, json.dumps(payload, ensure_ascii=False))
        failed_queue = Queue("failed", connection=connection)
        failed_queue.enqueue(store_failed_job, payload, job_timeout=60)
        logger.error("任务进入死信队列: job=%s file=%s error=%s", job.id, file_path, value)
    except Exception as exc:
        logger.error("记录死信任务失败: %s", exc)


def store_failed_job(payload: dict) -> dict:
    """failed 队列占位任务，便于 RQ Dashboard 查看。"""
    return {"stored": True, **payload}


def _sync_document_status(
    file_path: str,
    status: str,
    *,
    subject: str | None = None,
    doc_type: str | None = None,
    review_errors: list[str] | None = None,
) -> None:
    normalized = str(Path(file_path).resolve()).replace("\\", "/")
    upsert_document(
        normalized,
        subject=subject,
        doc_type=doc_type,
        status=status,
        review_errors=review_errors,
    )


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
            _sync_document_status(str(path), "convert_failed")
            return {"success": False, "stage": "convert", "error": conv.get("error"), "source_file": str(path)}
        md_path = conv["output_path"]
        logger.info("转换完成: %s -> %s", path, md_path)

    validation = validator.validate(md_path)
    svc = indexer or IndexerService()
    if indexer is None:
        svc.init_all()

    meta = validation.metadata or {}

    if not validation.valid:
        result = svc.index_markdown_file(md_path, review_status="needs_review")
        if result["success"]:
            tracker.mark_processed(str(path), "needs_review")
            return {
                "success": True,
                "stage": "needs_review",
                "warnings": validation.errors,
                "md_file": md_path,
                "source_file": str(path),
                "chunk_count": result.get("chunk_count"),
            }
        tracker.mark_processed(str(path), "index_failed")
        _sync_document_status(
            md_path,
            "index_failed",
            subject=meta.get("subject"),
            doc_type=meta.get("type"),
            review_errors=validation.errors,
        )
        return {"success": False, "stage": "index", "error": result.get("error"), "source_file": str(path)}

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
    _sync_document_status(
        md_path,
        "index_failed",
        subject=meta.get("subject"),
        doc_type=meta.get("type"),
    )
    return {"success": False, "stage": "index", "error": result.get("error"), "source_file": str(path)}


def enqueue_file(file_path: str) -> str:
    from rq import Retry

    queue = _get_queue("pipeline")
    job = queue.enqueue(
        process_file,
        file_path,
        job_timeout=JOB_TIMEOUT,
        retry=Retry(max=RQ_MAX_RETRIES, interval=[30, 60, 120]),
        on_failure=_record_failed_job,
    )
    logger.info("入队: %s -> job %s", file_path, job.id)
    return job.id


def enqueue_changed_files(vault_dir: str | None = None, changed_files: list[str] | None = None) -> list[str]:
    vault = vault_dir or VAULT_DIR
    tracker = FileTracker()
    if changed_files:
        pending = [str(Path(f)) for f in changed_files if Path(f).exists()]
    elif os.getenv("CHANGED_FILES"):
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
        and f.suffix.lower() in CONVERT_ONLY_EXTENSIONS
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


def list_failed_jobs(limit: int = 100) -> list[dict]:
    """从 FailedJobRegistry 与 Redis 审计 list 读取失败任务。"""
    from rq.registry import FailedJobRegistry

    conn = _get_redis()
    jobs: list[dict] = []
    registry = FailedJobRegistry(queue=_get_queue("pipeline"))
    for job_id in registry.get_job_ids(0, limit - 1):
        try:
            from rq.job import Job

            job = Job.fetch(job_id, connection=conn)
            jobs.append(
                {
                    "job_id": job.id,
                    "file_path": job.args[0] if job.args else None,
                    "error": job.exc_info or "",
                    "source": "registry",
                }
            )
        except Exception as exc:
            jobs.append({"job_id": job_id, "error": str(exc), "source": "registry"})

    raw = conn.lrange(FAILED_JOBS_KEY, 0, limit - 1)
    for item in raw:
        try:
            payload = json.loads(item)
            payload["source"] = "audit_log"
            jobs.append(payload)
        except json.JSONDecodeError:
            continue
    return jobs


def retry_failed_jobs(job_id: str | None = None) -> list[str]:
    """重新入队失败任务。"""
    from rq.job import Job
    from rq.registry import FailedJobRegistry

    conn = _get_redis()
    requeued: list[str] = []

    if job_id:
        job = Job.fetch(job_id, connection=conn)
        registry = FailedJobRegistry(queue=_get_queue("pipeline"))
        registry.requeue(job)
        requeued.append(job_id)
        return requeued

    registry = FailedJobRegistry(queue=_get_queue("pipeline"))
    for jid in registry.get_job_ids():
        try:
            registry.requeue(Job.fetch(jid, connection=conn))
            requeued.append(jid)
        except Exception as exc:
            logger.warning("重试 job %s 失败: %s", jid, exc)
    return requeued


if __name__ == "__main__":
    force = "--force" in sys.argv
    if "--worker" in sys.argv:
        run_worker(burst="--burst" in sys.argv)
    elif "--enqueue" in sys.argv:
        enqueue_changed_files()
    else:
        run_batch(force=force)
