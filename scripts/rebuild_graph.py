"""Rebuild Neo4j knowledge graph from all vault markdown files."""
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from configs.settings import GRAPH_ENABLED, VAULT_DIR
from services.indexer.graph_builder import KnowledgeGraphBuilder, get_graph_builder
from services.pipeline.metadata_validator import MetadataValidator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def rebuild_graph(vault_dir: str | None = None) -> dict:
    if not GRAPH_ENABLED:
        raise SystemExit("GRAPH_ENABLED=false，请在 .env 中设置为 true")

    builder = get_graph_builder()
    if builder is None:
        raise SystemExit("Neo4j 连接失败，请确认 docker compose up -d neo4j")

    validator = MetadataValidator()
    vault = Path(vault_dir or VAULT_DIR)
    files = sorted(
        f for f in vault.rglob("*.md")
        if f.is_file() and "_converted" not in f.parts and not f.name.startswith(".")
        and "0_项目文档" not in f.parts
    )

    imported = 0
    errors: list[str] = []
    for md in files:
        result = validator.validate(str(md))
        if not result.valid:
            errors.append(f"{md}: {result.errors}")
            continue
        try:
            builder.import_from_metadata(str(md), result.metadata or {})
            builder.import_obsidian_links(str(md), result.content)
            imported += 1
            logger.info("导入图谱: %s", md)
        except Exception as exc:
            errors.append(f"{md}: {exc}")
            logger.warning("导入失败 %s: %s", md, exc)

    stats = builder.graph_stats()
    return {"imported_files": imported, "errors": errors, "stats": stats}


def main():
    summary = rebuild_graph()
    print(summary)
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
