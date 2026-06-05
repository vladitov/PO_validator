"""Extraction of PO confirmation fields from email text.

Extraction is LLM-first (via ``llm_extractor.llm_extract_fields``) with the
regex extractor in this module as an automatic backup. The regex path handles
the assorted sample email formats under tests/test_*/ . Both paths pull the
same fields:
  - po_number: an order reference with an uppercase prefix (e.g. MLA-2026-88X,
    PO-2026-99Z)
  - date:      the fulfillment/activation date, normalized to ISO (YYYY-MM-DD),
    parsed from ISO, DD-MM-YYYY, or 'scheduled for <Month DD, YYYY>' phrasings
  - amount:    the monetary amount as a float (preferring a net-labelled value),
    plus its currency
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from llm_extractor import llm_extract_fields

# PO/order reference: any uppercase alphabetic prefix (MLA-, PO-, ...) followed
# by a year and an alphanumeric tail.
PO_PATTERN = re.compile(r"#?\b([A-Z]{2,}-\d{4}-[A-Z0-9]+)\b")

# Date formats seen across the sample emails, tried in priority order so that
# the relevant fulfillment date wins over the header/email date.
ISO_DATE_PATTERN = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
NUMERIC_DATE_PATTERN = re.compile(r"\b(\d{2}-\d{2}-\d{4})\b")
ACTIVATION_DATE_PATTERN = re.compile(
    r"scheduled for\s+([A-Z][a-z]+\s+\d{1,2},\s*\d{4})"
)

# Prefer an amount explicitly labelled as net/subtotal-net over the first euro
# value (which may be a line item or gross total).
NET_AMOUNT_PATTERN = re.compile(r"(?i)net[^€\n]*?€\s*([\d.,]+)")
AMOUNT_PATTERN = re.compile(r"€\s*([\d.,]+)")

_MONTH_DAY_YEAR_FORMAT = "%B %d, %Y"


def _normalize_date(raw_date: str) -> str | None:
    """Convert a date like 'January 15, 2026' into ISO '2026-01-15'."""
    cleaned = re.sub(r"\s+", " ", raw_date).strip()
    try:
        return datetime.strptime(cleaned, _MONTH_DAY_YEAR_FORMAT).date().isoformat()
    except ValueError:
        return None


def _parse_strict(raw_date: str, fmt: str) -> str | None:
    try:
        return datetime.strptime(raw_date, fmt).date().isoformat()
    except ValueError:
        return None


def _extract_date(text: str) -> str | None:
    """Find the fulfillment/activation date across the supported formats.

    Priority: ISO (YYYY-MM-DD) -> numeric DD-MM-YYYY -> the 'scheduled for
    <Month DD, YYYY>' phrasing. The phrasing anchor avoids grabbing the email
    header date in the long-form emails.
    """
    iso = ISO_DATE_PATTERN.search(text)
    if iso:
        parsed = _parse_strict(iso.group(1), "%Y-%m-%d")
        if parsed:
            return parsed

    numeric = NUMERIC_DATE_PATTERN.search(text)
    if numeric:
        parsed = _parse_strict(numeric.group(1), "%d-%m-%Y")
        if parsed:
            return parsed

    activation = ACTIVATION_DATE_PATTERN.search(text)
    if activation:
        return _normalize_date(activation.group(1))

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


_REQUIRED_FIELDS = ("po_number", "date", "amount", "currency")


def regex_extract_fields(text: str) -> dict:
    """Extract po_number, date, and amount from raw email text using regex.

    Returns a dict with normalized values. Fields that cannot be found are set
    to None so the caller can detect partial extractions.
    """
    po_match = PO_PATTERN.search(text)
    po_number = po_match.group(1) if po_match else None

    date_iso = _extract_date(text)

    amount_match = NET_AMOUNT_PATTERN.search(text) or AMOUNT_PATTERN.search(text)
    amount = _normalize_amount(amount_match.group(1)) if amount_match else None
    currency = "EUR" if amount_match else None

    return {
        "po_number": po_number,
        "date": date_iso,
        "amount": amount,
        "currency": currency,
    }


def _is_complete(fields: dict | None) -> bool:
    return isinstance(fields, dict) and all(
        fields.get(key) is not None for key in _REQUIRED_FIELDS
    )


def extract_fields_with_method(text: str) -> tuple[dict, str]:
    """Extract fields, preferring the LLM and falling back to regex.

    Returns a ``(fields, method)`` tuple where ``method`` is "llm" when the LLM
    produced a complete result, otherwise "regex". The LLM is skipped entirely
    when no API key is configured (``llm_extract_fields`` returns None).
    """
    llm_fields = llm_extract_fields(text)
    if _is_complete(llm_fields):
        return {key: llm_fields[key] for key in _REQUIRED_FIELDS}, "llm"

    return regex_extract_fields(text), "regex"


def extract_fields(text: str) -> dict:
    """Extract po_number, date, amount, and currency from raw email text.

    LLM-first with an automatic regex fallback. See
    ``extract_fields_with_method`` for the method used.
    """
    fields, _method = extract_fields_with_method(text)
    return fields


def build_intermediate_record(source_file: str, text: str) -> dict:
    """Build the full intermediate JSON record for an email file."""
    fields, method = extract_fields_with_method(text)
    return {
        "source_file": source_file,
        "po_number": fields["po_number"],
        "date": fields["date"],
        "amount": fields["amount"],
        "currency": fields["currency"],
        "extraction_method": method,
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


def extract_erp_fields(erp) -> dict:
    """Map the ERP JSON onto the comparable field set.

    Supports these shapes:
      - nested: fields live under a ``manual_entries`` object with a
        ``fulfillment_date`` and explicit ``currency``;
      - flat: fields sit at the top level, the date key is
        ``expected_fulfillment_date``, and ``currency`` may be absent;
      - list-wrapped: a single-element array containing either of the above
        (the ERP exports one record per file as a JSON array).

    When currency is not provided but an amount is, it defaults to EUR (the
    only currency this tool handles today).
    """
    if isinstance(erp, list):
        erp = next((item for item in erp if isinstance(item, dict)), None)

    if not isinstance(erp, dict):
        entries: dict = {}
    else:
        nested = erp.get("manual_entries")
        entries = nested if isinstance(nested, dict) else erp

    raw_amount = entries.get("net_amount")
    try:
        amount = float(raw_amount) if raw_amount is not None else None
    except (TypeError, ValueError):
        amount = None

    date = entries.get("fulfillment_date") or entries.get("expected_fulfillment_date")

    currency = entries.get("currency")
    if currency is None and amount is not None:
        currency = "EUR"

    return {
        "po_number": entries.get("po_number"),
        "date": date,
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
