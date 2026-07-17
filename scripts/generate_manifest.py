"""根据 Qdrant 中的数据生成 chunk manifest，供黄金评估集标注 chunk_id。"""
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qdrant_client import QdrantClient

from configs.settings import COLLECTION_NAME, QDRANT_URL


def main():
    client = QdrantClient(url=QDRANT_URL)
    manifest = {
        "version": "v1",
        "generated_at": datetime.now().isoformat(),
        "chunks": [],
    }

    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=100,
            offset=offset,
            with_payload=True,
        )
        if not points:
            break
        for p in points:
            payload = p.payload or {}
            manifest["chunks"].append({
                "chunk_id": str(p.id),
                "source_file": payload.get("source_file"),
                "section_title": payload.get("section_title"),
                "breadcrumb": payload.get("breadcrumb"),
                "metadata": payload.get("metadata", {}),
            })
        if offset is None:
            break

    out = ROOT / "eval" / "sources_manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已生成 {len(manifest['chunks'])} 条 chunk 记录 -> {out}")


if __name__ == "__main__":
    main()
