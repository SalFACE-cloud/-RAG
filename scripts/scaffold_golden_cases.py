"""根据 sources_manifest.json 为每个 chunk 输出 golden case JSONL 模板。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MANIFEST = ROOT / "eval" / "sources_manifest.json"
OUT = ROOT / "eval" / "golden_set_scaffold.jsonl"


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    lines = []
    for i, chunk in enumerate(manifest["chunks"], start=1):
        meta = chunk.get("metadata", {})
        subject = meta.get("subject", "ENG-S")
        kp = (meta.get("knowledge_points") or [{}])[0]
        case = {
            "id": f"SCaffold-{i:03d}",
            "split": "dev",
            "subject": subject,
            "grade_band": "高中",
            "doc_type": "jiangyi",
            "difficulty": meta.get("difficulty", 0.5),
            "question_type": "concept",
            "query": "TODO_query",
            "query_variants": [],
            "metadata_filters": {"subject": subject, "doc_type": None, "difficulty_max": 0.9},
            "expected_sources": [{
                "source_file": chunk["source_file"],
                "section_title": chunk["section_title"],
                "knowledge_point_id": kp.get("id", ""),
            }],
            "relevant_chunk_ids": [chunk["chunk_id"]],
            "ground_truth_answer": "TODO_answer",
            "must_include_points": ["TODO_point"],
            "forbidden_points": [],
            "answer_format": "definition",
            "eval_notes": f"scaffold for {chunk['section_title']}",
        }
        lines.append(json.dumps(case, ensure_ascii=False))

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已生成 {len(lines)} 条模板 -> {OUT}")


if __name__ == "__main__":
    main()
