"""Regex-based extraction of PO confirmation fields from email text.

Tuned to the sample email format in tests/correct/email_01.txt. The extractor
pulls three fields:
  - po_number: the Master Lease Agreement reference (e.g. MLA-2026-88X)
  - date:      the activation/deployment date, normalized to ISO (YYYY-MM-DD)
  - amount:    the monetary amount as a float, plus its currency
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

PO_PATTERN = re.compile(r"#?\b(MLA-\d{4}-[A-Z0-9]+)\b")

ACTIVATION_DATE_PATTERN = re.compile(
    r"scheduled for\s+([A-Z][a-z]+\s+\d{1,2},\s*\d{4})"
)

AMOUNT_PATTERN = re.compile(r"€\s*([\d.,]+)")

_DATE_INPUT_FORMAT = "%B %d, %Y"


def _normalize_date(raw_date: str) -> str | None:
    """Convert a date like 'January 15, 2026' into ISO '2026-01-15'."""
    cleaned = re.sub(r"\s+", " ", raw_date).strip()
    try:
        return datetime.strptime(cleaned, _DATE_INPUT_FORMAT).date().isoformat()
    except ValueError:
        return None


def _normalize_amount(raw_amount: str) -> float | None:
    """Convert a European-formatted amount like '24,500.00' into 24500.0.

    Handles the sample format where ',' is a thousands separator and '.' is the
    decimal separator.
    """
    cleaned = raw_amount.strip().replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_fields(text: str) -> dict:
    """Extract po_number, date, and amount from raw email text.

    Returns a dict with normalized values. Fields that cannot be found are set
    to None so the caller can detect partial extractions.
    """
    po_match = PO_PATTERN.search(text)
    date_match = ACTIVATION_DATE_PATTERN.search(text)
    amount_match = AMOUNT_PATTERN.search(text)

    po_number = po_match.group(1) if po_match else None

    date_iso = _normalize_date(date_match.group(1)) if date_match else None

    amount = _normalize_amount(amount_match.group(1)) if amount_match else None
    currency = "EUR" if amount_match else None

    return {
        "po_number": po_number,
        "date": date_iso,
        "amount": amount,
        "currency": currency,
    }


def build_intermediate_record(source_file: str, text: str) -> dict:
    """Build the full intermediate JSON record for an email file."""
    fields = extract_fields(text)
    return {
        "source_file": source_file,
        "po_number": fields["po_number"],
        "date": fields["date"],
        "amount": fields["amount"],
        "currency": fields["currency"],
        "extracted_at": datetime.now(timezone.utc).isoformat(),
    }
