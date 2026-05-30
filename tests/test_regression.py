"""Regression tests over the saved email/ERP fixtures.

The .txt emails under tests/ are the regression source of truth: each is read
exactly as the web UI now feeds pasted text into the extractor, then compared
against its paired ERP JSON fixture.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from extractor import compare_fields, extract_erp_fields, extract_fields  # noqa: E402


def _load_pair(folder: str, email_name: str, erp_name: str):
    email_text = (TESTS_DIR / folder / email_name).read_text(encoding="utf-8")
    erp = json.loads((TESTS_DIR / folder / erp_name).read_text(encoding="utf-8"))
    return extract_fields(email_text), extract_erp_fields(erp)


def test_correct_pair_matches():
    email_fields, erp_fields = _load_pair("correct", "email_01.txt", "erp_01.json")

    assert email_fields == {
        "po_number": "MLA-2026-88X",
        "date": "2026-01-15",
        "amount": 24500.0,
        "currency": "EUR",
    }

    result = compare_fields(email_fields, erp_fields)
    assert result["status"] == "match"
    assert all(result["checks"].values())


def test_incorrect_pair_mismatches():
    email_fields, erp_fields = _load_pair("incorrect", "email_02.txt", "erp_02.json")

    result = compare_fields(email_fields, erp_fields)
    assert result["status"] == "mismatch"
    assert result["checks"]["date"] is False
    assert result["checks"]["amount"] is False
    # po_number and currency still agree between email and ERP.
    assert result["checks"]["po_number"] is True
    assert result["checks"]["currency"] is True
