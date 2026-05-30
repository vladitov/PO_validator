"""Regression tests over the saved email/ERP fixtures.

Each tests/test_XX folder is a self-contained case:
  - an email .txt (the regression source of truth, read exactly as the web UI
    now feeds pasted text into the extractor),
  - an ERP .json,
  - po_validator_output.json with the expected {"result": "correct"|"incorrect"}.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from extractor import compare_fields, extract_erp_fields, extract_fields  # noqa: E402

EXPECTED_STATUS = {"correct": "match", "incorrect": "mismatch"}


def _case_dirs() -> list[Path]:
    return sorted(p for p in TESTS_DIR.glob("test_*") if p.is_dir())


@pytest.mark.parametrize("case_dir", _case_dirs(), ids=lambda p: p.name)
def test_case(case_dir: Path):
    email_path = next(case_dir.glob("*.txt"))
    erp_path = next(
        p for p in case_dir.glob("*.json") if p.name != "po_validator_output.json"
    )
    expected = json.loads(
        (case_dir / "po_validator_output.json").read_text(encoding="utf-8")
    )["result"]

    email_fields = extract_fields(email_path.read_text(encoding="utf-8"))
    erp_fields = extract_erp_fields(json.loads(erp_path.read_text(encoding="utf-8")))

    result = compare_fields(email_fields, erp_fields)
    assert result["status"] == EXPECTED_STATUS[expected]
