# PO Validator

A FastAPI web app that extracts purchase-order confirmation fields from an
email and validates them against an ERP JSON record.

**Live demo:** https://po-validator-151848188685.europe-west1.run.app

The UI has two inputs:

1. **Email confirmation** — paste the confirmation text. The server extracts
   `po_number`, `date`, `amount`, and `currency` (LLM-first, regex fallback)
   and writes an intermediate JSON file to `output/`.
2. **ERP JSON (`.json`)** — the record created after the PO was entered in
   the ERP. The file is validated as JSON and stored in `uploads/`.

When both are present, the app compares those four fields and shows match
(green), mismatch (red), or awaiting data (gray).

## Extracted fields

Example from `tests/test_00/email_00.txt`:

| Field       | Source in the email                  | Example        |
| ----------- | ------------------------------------ | -------------- |
| `po_number` | Master Lease Agreement reference     | `MLA-2026-88X` |
| `date`      | Activation date, normalized to ISO   | `2026-01-15`   |
| `amount`    | Net amount (excl. VAT)               | `24500.0`      |
| `currency`  | ISO code; defaults to EUR            | `EUR`          |

Intermediate JSON:

```json
{
  "source_file": "pasted-email",
  "po_number": "MLA-2026-88X",
  "date": "2026-01-15",
  "amount": 24500.0,
  "currency": "EUR",
  "extraction_method": "llm",
  "extracted_at": "2026-05-30T10:24:00+00:00"
}
```

`extraction_method` is `llm` or `regex`.

## Extraction

LLM-first with automatic regex fallback:

1. If `ANTHROPIC_API_KEY` is set, `llm_extractor.py` calls the Anthropic API.
2. If the key is missing, the call fails, or any of the four fields is null,
   the app uses the regex extractor in `extractor.py`.

The regex path is tuned to hyphenated POs (`MLA-2026-88X`), ISO /
`DD-MM-YYYY` / `scheduled for <Month DD, YYYY>` dates, and `€` amounts.
Other wording needs the LLM (see `test_06` and `test_07`). Only EUR is
handled today.

### Configuration

A local `.env` is loaded via `python-dotenv`:

| Variable            | Required | Default         | Purpose                        |
| ------------------- | -------- | --------------- | ------------------------------ |
| `ANTHROPIC_API_KEY` | No       | —               | Enables the LLM path when set. |
| `ANTHROPIC_MODEL`   | No       | `claude-opus-5` | Override the model used.       |

```bash
ANTHROPIC_API_KEY=sk-ant-...
# ANTHROPIC_MODEL=claude-sonnet-5
```

## Validation

PO references are compared on the core identifier, so `MLA-2026-88X` and
`PO-2026-88X` count as the same order.

ERP JSON is accepted in three shapes:

- **nested** — fields under `manual_entries`, with `fulfillment_date` and
  an explicit `currency`
- **flat** — top-level fields, date key `expected_fulfillment_date`
- **list-wrapped** — a one-element array of either shape

## Setup

This project uses [uv](https://docs.astral.sh/uv/). Python 3.14 is pinned in
`.python-version`:

```bash
uv sync
```

Use `uv sync --no-dev` to skip pytest.

## Run

```bash
uv run uvicorn main:app --reload
```

Then open http://127.0.0.1:8000.

## Tests

Each `tests/test_XX/` case has an email, `expected.json` (ground-truth fields
from that email), and an ERP JSON. Extraction is scored against
`expected.json`. Validation is scored by whether match/mismatch vs ERP
agrees with that ground truth.

```bash
uv run pytest
```

Regex tests always run. LLM tests use `claude-opus-5` and skip if
`ANTHROPIC_API_KEY` is unset.

`test_06` and `test_07` use lowercase PO syntax, a prose date, and `EUR`
with no euro sign, so regex returns no fields while the LLM extracts 4/4.

| Case      | LLM extraction | Regex extraction | Validation verdict |
| --------- | -------------- | ---------------- | ------------------ |
| test_00   | 4/4            | 4/4              | match ✓            |
| test_01   | 4/4            | 4/4              | mismatch ✓         |
| test_02   | 4/4            | 4/4              | match ✓            |
| test_03   | 4/4            | 4/4              | match ✓            |
| test_04   | 4/4            | 4/4              | mismatch ✓         |
| test_05   | 4/4            | 4/4              | mismatch ✓         |
| test_06   | 4/4            | 0/4              | match ✓            |
| test_07   | 4/4            | 0/4              | mismatch ✓         |
| **Total** | **32/32**      | **24/32**        | **8/8 correct**    |

## Project structure

```
main.py            FastAPI app and routes
extractor.py       Extraction orchestrator (LLM-first) + regex fallback + comparison
llm_extractor.py   Anthropic LLM field extraction
templates/         HTML UI (Jinja2)
output/            Generated intermediate JSON files (gitignored)
uploads/           Stored ERP JSON files (gitignored)
tests/             Per-case fixtures (test_XX/) + regression tests
```
