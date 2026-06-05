"""LLM-based extraction of PO confirmation fields via the Anthropic API.

This is the primary extractor used by the app when an ``ANTHROPIC_API_KEY`` is
configured. It asks Claude to pull the same fields the regex extractor in
``extractor.py`` handles, returning structured JSON:

  - po_number: the order reference (e.g. MLA-2026-88X, PO-2026-99Z)
  - date:      the fulfillment/activation date, normalized to ISO (YYYY-MM-DD)
  - amount:    the net monetary amount as a number
  - currency:  the ISO currency code (e.g. EUR)

The function returns ``None`` when no key is configured or when the call fails
for any reason, so the caller can fall back to regex extraction.
"""

from __future__ import annotations

import json
import logging
import os

try:  # python-dotenv is optional; load a local .env if present.
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is a convenience only
    pass

logger = logging.getLogger(__name__)

# Default to the latest Opus model; override with ANTHROPIC_MODEL if desired.
DEFAULT_MODEL = "claude-opus-4-8"

_SYSTEM_PROMPT = (
    "You extract structured purchase-order fields from a confirmation email. "
    "Return only the requested fields.\n"
    "Rules:\n"
    "- po_number: the order/lease reference, including its alphabetic prefix "
    "(e.g. 'MLA-2026-88X', 'PO-2026-77A'). Strip a leading '#'.\n"
    "- date: the fulfillment/activation/go-live date for the order, NOT the "
    "email header date and NOT an invoice/billing date. Normalize to ISO "
    "format YYYY-MM-DD.\n"
    "- amount: the net (excl. VAT) / subtotal amount as a plain number, "
    "preferring a value explicitly labelled net/subtotal over a gross or "
    "grand total or individual line items. Use '.' as the decimal separator "
    "and no thousands separators.\n"
    "- currency: the ISO 4217 currency code (e.g. EUR, USD).\n"
    "If a field is genuinely absent, use null for that field."
)

# JSON schema the model must conform to via structured outputs.
_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "po_number": {"type": ["string", "null"]},
        "date": {"type": ["string", "null"]},
        "amount": {"type": ["number", "null"]},
        "currency": {"type": ["string", "null"]},
    },
    "required": ["po_number", "date", "amount", "currency"],
    "additionalProperties": False,
}


def _coerce_amount(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_json_text(message) -> str | None:
    """Concatenate the text content blocks of an Anthropic message."""
    parts: list[str] = []
    for block in getattr(message, "content", []) or []:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    joined = "".join(parts).strip()
    return joined or None


def llm_extract_fields(text: str) -> dict | None:
    """Extract po_number, date, amount, currency from email text via the LLM.

    Returns a dict with those four keys, or ``None`` if no API key is set or the
    call fails for any reason (so the caller can fall back to regex).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    model = os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)

    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)
        message = client.messages.create(
            model=model,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Extract the purchase-order fields from this email:\n\n"
                        f"{text}"
                    ),
                }
            ],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": _OUTPUT_SCHEMA,
                }
            },
        )

        raw = _extract_json_text(message)
        if not raw:
            logger.warning("LLM extraction returned no text content.")
            return None

        data = json.loads(raw)
    except Exception as exc:  # noqa: BLE001 - any failure -> regex fallback
        logger.warning("LLM extraction failed, falling back to regex: %s", exc)
        return None

    if not isinstance(data, dict):
        return None

    po_number = data.get("po_number")
    date = data.get("date")
    currency = data.get("currency")

    return {
        "po_number": po_number.strip() if isinstance(po_number, str) else po_number,
        "date": date.strip() if isinstance(date, str) else date,
        "amount": _coerce_amount(data.get("amount")),
        "currency": currency.strip().upper() if isinstance(currency, str) else currency,
    }
