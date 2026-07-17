import logging

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
