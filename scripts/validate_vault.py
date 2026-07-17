"""Validate all vault markdown YAML front matter (CI-friendly, no embedding)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from configs.settings import VAULT_DIR
from services.pipeline.metadata_validator import MetadataValidator


def main() -> int:
    validator = MetadataValidator()
    vault = Path(VAULT_DIR)
    if not vault.is_absolute():
        vault = ROOT / vault

    invalid = 0
    valid = 0
    for md in sorted(vault.rglob("*.md")):
        if "_converted" in md.parts or md.name.startswith("."):
            continue
        if "0_项目文档" in md.parts:
            continue
        result = validator.validate(str(md))
        if result.valid:
            valid += 1
            print(f"[OK] {md.relative_to(ROOT)}")
        else:
            invalid += 1
            print(f"[FAIL] {md.relative_to(ROOT)}: {result.errors}")

    print(f"\nvalid={valid} invalid={invalid}")
    return 1 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
