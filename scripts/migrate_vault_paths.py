"""Migrate vault paths and purge stale index/graph entries."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OLD_PREFIX = "vault/4_题库/"
NEW_PREFIX = "vault/4_题库与试卷/结构化题库/高中/"

MIGRATIONS = [
    (
        ROOT / "vault/4_题库/高中数学/数列/等比数列练习.md",
        ROOT / "vault/4_题库与试卷/结构化题库/高中/数学/数列/等比数列练习.md",
    ),
]


def purge_source_file(source_file: str) -> None:
    from configs.settings import GRAPH_ENABLED
    from services.indexer.meili_indexer import MeiliIndexer
    from services.indexer.qdrant_indexer import QdrantIndexer

    normalized = str(Path(source_file).resolve()).replace("\\", "/")
    print(f"清理索引: {normalized}")
    QdrantIndexer().delete_by_source_file(normalized)
    MeiliIndexer().delete_by_source_file(normalized)

    if GRAPH_ENABLED:
        from services.indexer.graph_builder import get_graph_builder

        builder = get_graph_builder()
        if builder:
            path = builder._normalize_path(normalized)
            with builder.driver.session() as session:
                session.run(
                    "MATCH (d:Document {path: $path}) DETACH DELETE d",
                    path=path,
                )
            builder.close()


def migrate_files(dry_run: bool = False) -> list[tuple[str, str]]:
    moved = []
    for src, dst in MIGRATIONS:
        if not src.exists():
            print(f"[SKIP] 源文件不存在: {src}")
            continue
        old_abs = str(src.resolve()).replace("\\", "/")
        if dry_run:
            print(f"[DRY] {src} -> {dst}")
            moved.append((old_abs, str(dst)))
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        print(f"[MOVE] {src} -> {dst}")
        moved.append((old_abs, str(dst.resolve()).replace("\\", "/")))
    return moved


def cleanup_empty_dirs(base: Path) -> None:
    if not base.exists():
        return
    for directory in sorted(base.rglob("*"), reverse=True):
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
            print(f"[RMDIR] {directory}")


def reset_pipeline_state() -> None:
    state = ROOT / "configs" / "pipeline_state.json"
    if state.exists():
        state.unlink()
        print(f"[DEL] {state}")


def main() -> int:
    parser = argparse.ArgumentParser(description="迁移 vault 路径并清理旧索引")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-purge", action="store_true")
    args = parser.parse_args()

    moved = migrate_files(dry_run=args.dry_run)
    if args.dry_run:
        return 0

    if not args.skip_purge:
        for old_abs, _new in moved:
            purge_source_file(old_abs)

    reset_pipeline_state()
    cleanup_empty_dirs(ROOT / "vault/4_题库")
    print("迁移完成。请运行: python main.py index --force && python main.py graph")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
