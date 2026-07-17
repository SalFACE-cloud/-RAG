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

        for field in self.REQUIRED_FIELDS:
            if field not in metadata:
                errors.append(f"缺少必填字段: {field}")

        if metadata.get("subject") not in self.VALID_SUBJECTS:
            errors.append(f"无效学科代码: {metadata.get('subject')}")

        if metadata.get("type") not in self.VALID_TYPES:
            errors.append(f"无效文档类型: {metadata.get('type')}")

        errors.extend(self._validate_graph_fields(metadata))

        return ValidationResult(len(errors) == 0, errors, metadata, body)

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
