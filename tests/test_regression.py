"""Regression tests over the saved email/ERP fixtures.

Each tests/test_XX folder is a self-contained case:
  - email_XX.txt — the confirmation text (as pasted in the web UI)
  - expected.json — email ground-truth fields (po_number, date, amount, currency)
  - erp_XX.json — the ERP record to validate against

Extraction is scored against expected.json. Validation is scored by whether
the app's match/mismatch flag (extracted email vs ERP) agrees with the true
verdict (expected.json vs ERP).

test_06 and test_07 are written so the regex fallback cannot recover any
field; only the LLM path is expected to extract 4/4 and produce the correct
validation flag.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from extractor import compare_fields, extract_erp_fields, regex_extract_fields  # noqa: E402
from llm_extractor import llm_extract_fields  # noqa: E402

requires_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set; skipping LLM extraction tests.",
)

# Cases whose wording is outside the regex patterns (lowercase PO, prose date,
# EUR amount with no euro sign). Regex is expected to return all-null fields.
REGEX_CANNOT_EXTRACT = {"test_06", "test_07"}


def _case_dirs() -> list[Path]:
    return sorted(p for p in TESTS_DIR.glob("test_*") if p.is_dir())


def _load_case(case_dir: Path) -> tuple[str, dict, dict]:
    email_path = next(case_dir.glob("email_*.txt"))
    erp_path = next(case_dir.glob("erp_*.json"))
    expected_path = case_dir / "expected.json"

    email_text = email_path.read_text(encoding="utf-8")
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    erp_fields = extract_erp_fields(json.loads(erp_path.read_text(encoding="utf-8")))
    return email_text, expected, erp_fields


def _assert_extraction(extracted: dict | None, expected: dict) -> None:
    assert extracted is not None, "extraction returned no result"
    assert extracted.get("po_number") == expected["po_number"]
    assert extracted.get("date") == expected["date"]
    assert extracted.get("amount") is not None
    assert abs(float(extracted["amount"]) - float(expected["amount"])) < 0.005
    assert isinstance(extracted.get("currency"), str)
    assert extracted["currency"].upper() == expected["currency"].upper()


def _assert_validation(extracted: dict, expected: dict, erp_fields: dict) -> None:
    true_verdict = compare_fields(expected, erp_fields)["status"]
    app_verdict = compare_fields(extracted, erp_fields)["status"]
    assert app_verdict == true_verdict


@pytest.mark.parametrize("case_dir", _case_dirs(), ids=lambda p: p.name)
def test_regex_extraction_and_validation(case_dir: Path):
    email_text, expected, erp_fields = _load_case(case_dir)
    extracted = regex_extract_fields(email_text)
    if case_dir.name in REGEX_CANNOT_EXTRACT:
        assert extracted == {
            "po_number": None,
            "date": None,
            "amount": None,
            "currency": None,
        }
        return
    _assert_extraction(extracted, expected)
    _assert_validation(extracted, expected, erp_fields)


@requires_api_key
@pytest.mark.parametrize("case_dir", _case_dirs(), ids=lambda p: p.name)
def test_llm_extraction_and_validation(case_dir: Path):
    email_text, expected, erp_fields = _load_case(case_dir)
    extracted = llm_extract_fields(email_text)
    _assert_extraction(extracted, expected)
    _assert_validation(extracted, expected, erp_fields)
