import logging
import re
from pathlib import Path
from typing import Optional

from configs.settings import GRAPH_ENABLED, NEO4J_PASSWORD, NEO4J_URI

logger = logging.getLogger(__name__)

OBSIDIAN_LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]")


class KnowledgeGraphBuilder:
    def __init__(self):
        self._driver = None

    @property
    def driver(self):
        if self._driver is None:
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(NEO4J_URI, auth=("neo4j", NEO4J_PASSWORD))
        return self._driver

    def close(self):
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def init_constraints(self):
        with self.driver.session() as session:
            session.run(
                "CREATE CONSTRAINT knowledge_id IF NOT EXISTS "
                "FOR (k:Knowledge) REQUIRE k.id IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT competency_code IF NOT EXISTS "
                "FOR (c:Competency) REQUIRE c.code IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT exercise_id IF NOT EXISTS "
                "FOR (e:Exercise) REQUIRE e.id IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT document_path IF NOT EXISTS "
                "FOR (d:Document) REQUIRE d.path IS UNIQUE"
            )

    @staticmethod
    def _normalize_path(file_path: str) -> str:
        return str(Path(file_path).resolve()).replace("\\", "/")

    def import_from_metadata(self, file_path: str, metadata: dict):
        path = self._normalize_path(file_path)
        subject = metadata.get("subject", "")
        doc_type = metadata.get("type", "")
        difficulty = metadata.get("difficulty")

        with self.driver.session() as session:
            session.run(
                """
                MERGE (d:Document {path: $path})
                SET d.subject = $subject,
                    d.type = $doc_type,
                    d.title = $title,
                    d.difficulty = $difficulty
                """,
                path=path,
                subject=subject,
                doc_type=doc_type,
                title=Path(file_path).stem,
                difficulty=difficulty,
            )

            knowledge_points = metadata.get("knowledge_points") or []
            for kp in knowledge_points:
                if not isinstance(kp, dict):
                    continue
                kp_id = kp.get("id")
                if not kp_id:
                    continue
                session.run(
                    """
                    MERGE (k:Knowledge {id: $id})
                    SET k.name = $name, k.subject = $subject
                    WITH k
                    MATCH (d:Document {path: $path})
                    MERGE (d)-[:COVERS]->(k)
                    """,
                    id=kp_id,
                    name=kp.get("name", ""),
                    subject=subject,
                    path=path,
                )

                for prereq_id in kp.get("prerequisites") or []:
                    session.run(
                        """
                        MATCH (k:Knowledge {id: $kid})
                        MERGE (pre:Knowledge {id: $pre_id})
                        MERGE (pre)-[:PREREQUISITE]->(k)
                        """,
                        kid=kp_id,
                        pre_id=prereq_id,
                    )

                for related_id in kp.get("related") or []:
                    session.run(
                        """
                        MATCH (k:Knowledge {id: $kid})
                        MERGE (other:Knowledge {id: $other_id})
                        MERGE (k)-[:RELATED_TO]->(other)
                        """,
                        kid=kp_id,
                        other_id=related_id,
                    )

            competencies = list(metadata.get("competencies") or [])
            legacy = metadata.get("competency")
            if legacy and isinstance(legacy, dict):
                code = legacy.get("code") or legacy.get("id")
                if code:
                    competencies.append({
                        "code": code,
                        "name": legacy.get("name", ""),
                        "level": legacy.get("level", ""),
                    })

            for comp in competencies:
                if not isinstance(comp, dict):
                    continue
                code = comp.get("code") or comp.get("id")
                if not code:
                    continue
                session.run(
                    """
                    MERGE (c:Competency {code: $code})
                    SET c.name = $name, c.level = $level
                    """,
                    code=code,
                    name=comp.get("name", ""),
                    level=comp.get("level", ""),
                )
                for kp in knowledge_points:
                    if not isinstance(kp, dict) or not kp.get("id"):
                        continue
                    session.run(
                        """
                        MATCH (k:Knowledge {id: $kid})
                        MATCH (c:Competency {code: $code})
                        MERGE (k)-[:BELONGS_TO]->(c)
                        """,
                        kid=kp["id"],
                        code=code,
                    )

            exercises = metadata.get("exercises") or []
            if doc_type in {"exercise", "exam"} and not exercises:
                ex_id = metadata.get("exercise_id") or f"DOC-EX-{Path(file_path).stem}"
                exercises = [{
                    "id": ex_id,
                    "content": metadata.get("title") or Path(file_path).stem,
                    "difficulty": difficulty or 0.5,
                    "type": doc_type,
                    "tests": [kp.get("id") for kp in knowledge_points if isinstance(kp, dict) and kp.get("id")],
                    "assesses": [c.get("code") or c.get("id") for c in competencies if isinstance(c, dict)],
                }]

            for ex in exercises:
                if not isinstance(ex, dict) or not ex.get("id"):
                    continue
                session.run(
                    """
                    MERGE (e:Exercise {id: $id})
                    SET e.content = $content,
                        e.difficulty = $difficulty,
                        e.type = $type,
                        e.subject = $subject
                    WITH e
                    MATCH (d:Document {path: $path})
                    MERGE (d)-[:CONTAINS]->(e)
                    """,
                    id=ex["id"],
                    content=ex.get("content", ""),
                    difficulty=ex.get("difficulty", difficulty or 0.5),
                    type=ex.get("type", doc_type or "exercise"),
                    subject=subject,
                    path=path,
                )
                for kid in ex.get("tests") or []:
                    session.run(
                        """
                        MATCH (e:Exercise {id: $eid})
                        MERGE (k:Knowledge {id: $kid})
                        MERGE (e)-[:TESTS]->(k)
                        """,
                        eid=ex["id"],
                        kid=kid,
                    )
                for code in ex.get("assesses") or []:
                    session.run(
                        """
                        MATCH (e:Exercise {id: $eid})
                        MERGE (c:Competency {code: $code})
                        MERGE (e)-[:ASSESSES]->(c)
                        """,
                        eid=ex["id"],
                        code=code,
                    )

    def import_obsidian_links(self, file_path: str, content: str):
        path = self._normalize_path(file_path)
        links = OBSIDIAN_LINK.findall(content)
        if not links:
            return

        with self.driver.session() as session:
            for raw_title, _alias in links:
                link_title = raw_title.strip()
                if not link_title:
                    continue
                session.run(
                    """
                    MATCH (src:Document {path: $path})
                    MERGE (tgt:Document {title: $title})
                    MERGE (src)-[:LINKS_TO]->(tgt)
                    """,
                    path=path,
                    title=link_title,
                )
                session.run(
                    """
                    MATCH (src:Document {path: $path})-[:COVERS]->(k1:Knowledge)
                    MATCH (tgt:Document {title: $title})-[:COVERS]->(k2:Knowledge)
                    MERGE (k1)-[:RELATED_TO]->(k2)
                    """,
                    path=path,
                    title=link_title,
                )

    def get_learning_path(self, knowledge_id: str) -> list[dict]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (k:Knowledge {id: $id})
                OPTIONAL MATCH path = (pre:Knowledge)-[:PREREQUISITE*1..5]->(k)
                WITH k, path
                ORDER BY length(path) DESC
                LIMIT 1
                RETURN k.id AS id,
                       k.name AS name,
                       k.subject AS subject,
                       CASE WHEN path IS NULL THEN []
                            ELSE [n IN nodes(path)[0..-1] | {id: n.id, name: n.name}]
                       END AS prerequisites
                """,
                id=knowledge_id,
            )
            record = result.single()
            if not record:
                return []
            return [{
                "id": record["id"],
                "name": record["name"],
                "subject": record["subject"],
                "prerequisites": record["prerequisites"] or [],
            }]

    def get_exercises_for_knowledge(
        self,
        knowledge_id: Optional[str],
        difficulty_range: tuple[float, float] = (0.0, 1.0),
    ) -> list[dict]:
        if not knowledge_id:
            return []
        min_d, max_d = difficulty_range
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (e:Exercise)-[:TESTS]->(k:Knowledge {id: $id})
                WHERE e.difficulty >= $min_d AND e.difficulty <= $max_d
                RETURN e.id AS id,
                       e.content AS content,
                       e.difficulty AS difficulty,
                       e.type AS type,
                       e.subject AS subject
                ORDER BY e.difficulty
                """,
                id=knowledge_id,
                min_d=min_d,
                max_d=max_d,
            )
            return [dict(r) for r in result]

    def graph_stats(self) -> dict:
        with self.driver.session() as session:
            result = session.run(
                """
                OPTIONAL MATCH (k:Knowledge) WITH count(k) AS knowledge
                OPTIONAL MATCH (c:Competency) WITH knowledge, count(c) AS competency
                OPTIONAL MATCH (e:Exercise) WITH knowledge, competency, count(e) AS exercise
                OPTIONAL MATCH ()-[r]->() WITH knowledge, competency, exercise, count(r) AS rels
                RETURN knowledge, competency, exercise, rels
                """
            )
            row = result.single()
            return dict(row) if row else {}


def get_graph_builder() -> Optional[KnowledgeGraphBuilder]:
    if not GRAPH_ENABLED:
        return None
    try:
        builder = KnowledgeGraphBuilder()
        builder.init_constraints()
        return builder
    except Exception as exc:
        logger.warning("Neo4j 不可用，跳过图谱写入: %s", exc)
        return None
