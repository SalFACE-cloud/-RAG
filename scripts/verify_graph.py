"""Verify Phase 4 knowledge graph acceptance queries."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from configs.settings import GRAPH_ENABLED
from services.indexer.graph_builder import get_graph_builder


def main():
    if not GRAPH_ENABLED:
        print("GRAPH_ENABLED=false")
        return 1

    builder = get_graph_builder()
    if builder is None:
        print("Neo4j unavailable")
        return 1

    stats = builder.graph_stats()
    path = builder.get_learning_path("MATH-KP-03-01")
    exercises = builder.get_exercises_for_knowledge("MATH-KP-03-01", (0.0, 1.0))

    with builder.driver.session() as session:
        links = session.run(
            "MATCH (d1:Document)-[:LINKS_TO]->(d2:Document) "
            "RETURN d1.title AS src, d2.title AS tgt LIMIT 10"
        ).data()
        belongs = session.run(
            "MATCH (k:Knowledge)-[:BELONGS_TO]->(c:Competency) "
            "RETURN k.id AS kid, c.code AS code LIMIT 5"
        ).data()
        prereq = session.run(
            "MATCH (pre:Knowledge)-[:PREREQUISITE]->(k:Knowledge) "
            "RETURN pre.id AS pre, k.id AS kid LIMIT 5"
        ).data()

    report = {
        "stats": stats,
        "learning_path_MATH-KP-03-01": path,
        "exercises_MATH-KP-03-01": exercises,
        "sample_links": links,
        "sample_belongs_to": belongs,
        "sample_prerequisite": prereq,
        "checks": {
            "has_knowledge": stats.get("knowledge", 0) > 0,
            "has_competency": stats.get("competency", 0) > 0,
            "has_exercise": stats.get("exercise", 0) > 0,
            "has_prerequisite": len(prereq) > 0,
            "has_links": len(links) > 0,
            "learning_path_ok": bool(path and path[0].get("prerequisites")),
            "exercises_ok": len(exercises) > 0,
        },
    }
    out = ROOT / "eval" / "results" / "graph_verify_latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Output: {out}")
    return 0 if all(report["checks"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
