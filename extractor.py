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


_PO_PREFIX_PATTERN = re.compile(r"^[A-Z]+-")


def normalize_po(value) -> str | None:
    """Normalize a PO/MLA reference for comparison.

    Email uses an 'MLA-' prefix while the ERP uses a 'PO-' prefix for the same
    order, so we strip the leading alphabetic prefix and compare the core
    identifier (e.g. both 'MLA-2026-88X' and 'PO-2026-88X' -> '2026-88X').
    """
    if value is None:
        return None
    core = _PO_PREFIX_PATTERN.sub("", str(value).strip().upper())
    return core or None


def extract_erp_fields(erp: dict) -> dict:
    """Map the ERP JSON's manual_entries onto the comparable field set."""
    entries = erp.get("manual_entries", {}) if isinstance(erp, dict) else {}

    raw_amount = entries.get("net_amount")
    try:
        amount = float(raw_amount) if raw_amount is not None else None
    except (TypeError, ValueError):
        amount = None

    currency = entries.get("currency")
    return {
        "po_number": entries.get("po_number"),
        "date": entries.get("fulfillment_date"),
        "amount": amount,
        "currency": currency.upper() if isinstance(currency, str) else currency,
    }


def _amounts_match(a, b) -> bool:
    if a is None or b is None:
        return False
    try:
        return abs(float(a) - float(b)) < 0.005
    except (TypeError, ValueError):
        return False


def compare_fields(email_fields: dict, erp_fields: dict) -> dict:
    """Compare the email-extracted fields against the ERP fields.

    Returns per-field match booleans and an overall status of 'match' or
    'mismatch'.
    """
    email_po = normalize_po(email_fields.get("po_number"))
    erp_po = normalize_po(erp_fields.get("po_number"))

    email_cur = email_fields.get("currency")
    erp_cur = erp_fields.get("currency")

    checks = {
        "po_number": email_po is not None and email_po == erp_po,
        "date": email_fields.get("date") is not None
        and email_fields.get("date") == erp_fields.get("date"),
        "amount": _amounts_match(email_fields.get("amount"), erp_fields.get("amount")),
        "currency": isinstance(email_cur, str)
        and isinstance(erp_cur, str)
        and email_cur.upper() == erp_cur.upper(),
    }

    overall = all(checks.values())
    return {"checks": checks, "status": "match" if overall else "mismatch"}
