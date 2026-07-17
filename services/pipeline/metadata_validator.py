import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]
    metadata: Optional[dict]
    content: str


class MetadataValidator:
    REQUIRED_FIELDS = ["subject", "type"]
    VALID_SUBJECTS = {
        "ENG-S", "MATH-S", "PHY-S", "CHE-S", "BIO-S",
        "CHN-S", "HIS-S", "GEO-S", "POL-S",
        "ENG-J", "MATH-J", "PHY-J", "CHE-J", "BIO-J",
        "CHN-J", "HIS-J", "GEO-J", "POL-J",
    }
    VALID_TYPES = {
        "textbook", "jiangyi", "exercise", "exam",
        "audio_exercise", "video", "diagram",
        "policy", "standard", "summary",
    }
    SUBJECT_BASE_MAP = {
        "MATH": "MATH", "ENG": "ENG", "PHY": "PHY",
        "CHEM": "CHE", "CHE": "CHE", "BIO": "BIO",
        "CHN": "CHN", "HIS": "HIS", "GEO": "GEO", "POL": "POL",
    }
    TYPE_ALIASES = {
        "textbook_example": "jiangyi",
        "textbook_knowledge": "textbook",
        "knowledge": "textbook",
    }

    def validate(self, file_path: str) -> ValidationResult:
        content = Path(file_path).read_text(encoding="utf-8")
        errors = []

        m = re.match(r"^---\n(.*?)\n---\n(.*)", content, re.DOTALL)
        if not m:
            return ValidationResult(False, ["缺少 YAML Front Matter"], None, content)

        try:
            metadata = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError as e:
            return ValidationResult(False, [f"YAML 解析错误: {e}"], None, content)

        body = m.group(2)
        if not isinstance(metadata, dict):
            errors.append("YAML 元数据必须是键值对")
            metadata = {}

        metadata = self._normalize_metadata(metadata, file_path)

        for field in self.REQUIRED_FIELDS:
            if field not in metadata:
                errors.append(f"缺少必填字段: {field}")

        if metadata.get("subject") not in self.VALID_SUBJECTS:
            errors.append(f"无效学科代码: {metadata.get('subject')}")

        if metadata.get("type") not in self.VALID_TYPES:
            errors.append(f"无效文档类型: {metadata.get('type')}")

        errors.extend(self._validate_graph_fields(metadata))

        return ValidationResult(len(errors) == 0, errors, metadata, body)

    def _normalize_metadata(self, metadata: dict, file_path: str) -> dict:
        """兼容教材库新 schema（doc_type / subject_code + 路径推断）。"""
        meta = dict(metadata)
        if not meta.get("type") and meta.get("doc_type"):
            meta["type"] = meta["doc_type"]
        alias = self.TYPE_ALIASES.get(meta.get("type"))
        if alias:
            meta["type"] = alias
        if not meta.get("subject"):
            inferred = self._infer_subject_code(meta, file_path)
            if inferred:
                meta["subject"] = inferred
        return meta

    def _infer_subject_code(self, metadata: dict, file_path: str) -> str | None:
        code = str(metadata.get("subject_code") or "")
        if "{{" in code or not code:
            code = ""
        else:
            code = code.split("-")[0].upper()

        path = file_path.replace("\\", "/")
        if not code:
            m = re.search(r"/(MATH|ENG|PHY|CHEM|CHE|BIO|CHN|HIS|GEO|POL)_", path)
            if m:
                code = m.group(1)

        base = self.SUBJECT_BASE_MAP.get(code)
        if not base:
            return None

        suffix = "S"
        if "/J_" in path:
            suffix = "J"
        elif "/G_" in path:
            suffix = "S"
        return f"{base}-{suffix}"

    def _validate_graph_fields(self, metadata: dict) -> list[str]:
        errors: list[str] = []

        for i, kp in enumerate(metadata.get("knowledge_points") or []):
            if not isinstance(kp, dict):
                errors.append(f"knowledge_points[{i}] 必须是对象")
                continue
            if not kp.get("id"):
                errors.append(f"knowledge_points[{i}] 缺少 id")
            for field in ("prerequisites", "related"):
                vals = kp.get(field) or []
                if not isinstance(vals, list):
                    errors.append(f"knowledge_points[{i}].{field} 必须是列表")

        for i, comp in enumerate(metadata.get("competencies") or []):
            if not isinstance(comp, dict):
                errors.append(f"competencies[{i}] 必须是对象")
                continue
            if not (comp.get("code") or comp.get("id")):
                errors.append(f"competencies[{i}] 缺少 code")

        for i, ex in enumerate(metadata.get("exercises") or []):
            if not isinstance(ex, dict):
                errors.append(f"exercises[{i}] 必须是对象")
                continue
            if not ex.get("id"):
                errors.append(f"exercises[{i}] 缺少 id")

        doc_type = metadata.get("type")
        if doc_type in {"exercise", "exam"}:
            has_exercises = bool(metadata.get("exercises"))
            has_kp = bool(metadata.get("knowledge_points"))
            if not has_exercises and not has_kp:
                errors.append(f"type={doc_type} 时需至少提供 exercises 或 knowledge_points")

        return errors


def _cli_root() -> Path:
    import sys

    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def validate_vault(vault_path: Path, ignore_patterns: list[str]) -> tuple[int, int]:
    from services.pipeline.vault_paths import should_ignore

    invalid = 0
    valid = 0
    validator = MetadataValidator()
    for md in sorted(vault_path.rglob("*.md")):
        if should_ignore(md, vault_path, ignore_patterns):
            continue
        result = validator.validate(str(md))
        if result.valid:
            valid += 1
            print(f"[OK] {md.relative_to(vault_path)}")
        else:
            invalid += 1
            print(f"[FAIL] {md.relative_to(vault_path)}: {result.errors}")
    return valid, invalid


def main_cli() -> int:
    import argparse

    _cli_root()
    from services.pipeline.vault_paths import (
        append_pipeline_log,
        parse_ignore_patterns,
        write_pipeline_result,
    )

    parser = argparse.ArgumentParser(description="校验 vault Markdown 元数据")
    parser.add_argument("--vault-path", default="./vault")
    parser.add_argument("--ignore-path", default="0_项目文档/**")
    args = parser.parse_args()

    vault = Path(args.vault_path).resolve()
    ignore = parse_ignore_patterns(args.ignore_path)
    append_pipeline_log(f"metadata_validator start vault={vault}")
    valid, invalid = validate_vault(vault, ignore)
    print(f"\nvalid={valid} invalid={invalid}")
    ok = invalid == 0
    write_pipeline_result("metadata_validator", ok, {"valid": valid, "invalid": invalid})
    append_pipeline_log(f"metadata_validator done valid={valid} invalid={invalid}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main_cli())
