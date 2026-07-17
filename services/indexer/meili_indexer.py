import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import requests

from configs.settings import MEILI_INDEX, MEILI_MASTER_KEY, MEILI_URL

logger = logging.getLogger(__name__)


class MeiliIndexer:
    def __init__(self):
        self.base = MEILI_URL.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {MEILI_MASTER_KEY}",
            "Content-Type": "application/json",
        }
        self.proxies = {"http": None, "https": None}

    def _request(self, method: str, path: str, **kwargs):
        resp = requests.request(
            method,
            f"{self.base}{path}",
            headers=self.headers,
            proxies=self.proxies,
            timeout=kwargs.pop("timeout", 30),
            **kwargs,
        )
        return resp

    def _wait_task(self, task_uid: int, timeout: int = 60):
        import time

        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = self._request("GET", f"/tasks/{task_uid}")
            resp.raise_for_status()
            task = resp.json()
            status = task.get("status")
            if status == "succeeded":
                return task
            if status in {"failed", "canceled"}:
                error = task.get("error", {})
                raise RuntimeError(
                    f"Meilisearch task {task_uid} {status}: {error.get('message', task)}"
                )
            time.sleep(0.2)
        raise TimeoutError(f"Meilisearch task {task_uid} timed out")

    def init_index(self):
        resp = self._request("GET", f"/indexes/{MEILI_INDEX}")
        if resp.status_code == 404:
            create = self._request(
                "POST",
                "/indexes",
                json={"uid": MEILI_INDEX, "primaryKey": "chunk_id"},
            )
            create.raise_for_status()
        else:
            resp.raise_for_status()
            primary_key = resp.json().get("primaryKey")
            if primary_key != "chunk_id":
                logger.warning(
                    "Meilisearch index %s primaryKey=%s, recreating with chunk_id",
                    MEILI_INDEX,
                    primary_key,
                )
                delete = self._request("DELETE", f"/indexes/{MEILI_INDEX}")
                delete.raise_for_status()
                self._wait_task(delete.json()["taskUid"])
                create = self._request(
                    "POST",
                    "/indexes",
                    json={"uid": MEILI_INDEX, "primaryKey": "chunk_id"},
                )
                create.raise_for_status()

        settings = self._request(
            "PATCH",
            f"/indexes/{MEILI_INDEX}/settings",
            json={
                "searchableAttributes": [
                    "content",
                    "section_title",
                    "breadcrumb",
                    "source_file",
                ],
                "filterableAttributes": ["subject", "doc_type", "source_file", "chunk_id"],
            },
        )
        settings.raise_for_status()

    def delete_by_source_file(self, source_file: str):
        resp = self._request(
            "POST",
            f"/indexes/{MEILI_INDEX}/documents/delete",
            json={"filter": f'source_file = "{source_file}"'},
        )
        if resp.status_code == 202:
            self._wait_task(resp.json()["taskUid"])

    def upsert_chunks(self, chunks: list) -> int:
        docs = []
        for c in chunks:
            docs.append({
                "chunk_id": c.chunk_id,
                "content": c.content,
                "source_file": c.source_file,
                "section_title": c.section_title,
                "breadcrumb": c.breadcrumb,
                "subject": c.metadata.get("subject"),
                "doc_type": c.metadata.get("type"),
                "metadata": c.metadata,
            })
        resp = self._request(
            "POST",
            f"/indexes/{MEILI_INDEX}/documents",
            json=docs,
            timeout=60,
        )
        resp.raise_for_status()
        if resp.status_code == 202:
            self._wait_task(resp.json()["taskUid"])
        return len(docs)

    def search(self, query: str, subject: str | None = None, limit: int = 20) -> list[dict]:
        payload: dict = {"q": query, "limit": limit}
        if subject:
            payload["filter"] = f'subject = "{subject}"'
        resp = self._request(
            "POST",
            f"/indexes/{MEILI_INDEX}/search",
            json=payload,
        )
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
        return [
            {
                "chunk_id": h.get("chunk_id"),
                "score": float(h.get("_rankingScore", 0.0)),
                "content": h.get("content"),
                "source_file": h.get("source_file"),
                "section_title": h.get("section_title"),
                "metadata": h.get("metadata", {}),
            }
            for h in hits
        ]


def _cli_root() -> Path:
    import sys

    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def run_sync_meili_from_manifest() -> dict:
    import json

    from services.indexer.chunker import chunk_from_dict
    from services.pipeline.vault_paths import CHUNKS_MANIFEST_JSON, append_pipeline_log

    _cli_root()
    if not CHUNKS_MANIFEST_JSON.exists():
        raise FileNotFoundError(f"缺少分块清单: {CHUNKS_MANIFEST_JSON}")

    manifest = json.loads(CHUNKS_MANIFEST_JSON.read_text(encoding="utf-8"))
    chunks = [chunk_from_dict(c) for c in manifest.get("chunks", [])]
    meili = MeiliIndexer()
    meili.init_index()

    source_files = sorted({c.source_file for c in chunks})
    for sf in source_files:
        meili.delete_by_source_file(sf)

    count = meili.upsert_chunks(chunks) if chunks else 0
    append_pipeline_log(f"meili_indexer upserted={count} sources={len(source_files)}")
    print(f"[MEILI] upserted={count} from {len(source_files)} files")
    return {"upserted": count, "source_files": len(source_files)}


def main_cli() -> int:
    _cli_root()
    from services.pipeline.vault_paths import write_pipeline_result

    try:
        result = run_sync_meili_from_manifest()
    except FileNotFoundError as exc:
        print(exc)
        write_pipeline_result("meili_indexer", False, {"error": str(exc)})
        return 1

    ok = result["upserted"] > 0
    write_pipeline_result("meili_indexer", ok, result)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main_cli())
