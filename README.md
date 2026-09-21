# PO Validator

A FastAPI web app for processing purchase order (PO) confirmations.

**Live demo:** https://po-validator-151848188685.europe-west1.run.app

It provides a simple web UI with two inputs:

1. **Email confirmation** — paste the PO confirmation email text directly into
   the textarea. The server extracts the **PO number**, **date**, and
   **amount** (LLM-first, regex fallback — see [Extraction](#extraction)), then
   writes an intermediate JSON file to `output/`.
2. **ERP JSON (`.json`)** — the file created by the ERP system after the PO was
   manually entered, uploaded and validated as JSON, then stored in `uploads/`.

## Extracted fields

Tuned to the sample email in `tests/test_00/email_00.txt`:

| Field       | Source in email                              | Example         |
| ----------- | -------------------------------------------- | --------------- |
| `po_number` | Master Lease Agreement reference             | `MLA-2026-88X`  |
| `date`      | Activation date ("scheduled for ...")        | `2026-01-15`    |
| `amount`    | Euro amount                                  | `24500.0` (EUR) |

The intermediate JSON looks like:

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

`extraction_method` records which path produced the fields (`llm` or `regex`).

## Extraction

Extraction is **LLM-first with an automatic regex fallback**:

1. If `ANTHROPIC_API_KEY` is set, the email is sent to the Anthropic API
   (`llm_extractor.py`), which returns the structured fields.
2. If the key is missing, the call fails, or the LLM result is incomplete (any
   of the four fields is null), the app falls back to the regex extractor in
   `extractor.py`.

### Configuration

Set these environment variables (a local `.env` file is loaded automatically
via `python-dotenv`):

| Variable            | Required | Default            | Purpose                         |
| ------------------- | -------- | ------------------ | ------------------------------- |
| `ANTHROPIC_API_KEY` | No       | —                  | Enables the LLM path when set.  |
| `ANTHROPIC_MODEL`   | No       | `claude-opus-5`    | Override the model used.        |

Example `.env`:

```bash
ANTHROPIC_API_KEY=sk-ant-...
# ANTHROPIC_MODEL=claude-sonnet-4-6
```

Without a key the app still works end-to-end using regex extraction only.

## Validation

Once both an email and an ERP JSON are provided, the app compares the
extracted fields (`po_number`, `date`, `amount`, `currency`) and shows a
green (match) / red (mismatch) / gray (not enough data) indicator. The PO
reference is compared on its core identifier, so the email's `MLA-` prefix and
the ERP's `PO-` prefix for the same order are treated as equal.

The ERP JSON is accepted in three shapes:

- **nested** — fields under a `manual_entries` object with `fulfillment_date`
  and an explicit `currency`;
- **flat** — fields at the top level with an `expected_fulfillment_date`;
- **list-wrapped** — a single-element array containing either of the above
  (the ERP exports one record per file as a JSON array).

## Setup

This project uses [uv](https://docs.astral.sh/uv/). Create the virtual
environment and install the locked dependencies (Python 3.14 is pinned via
`.python-version`):

```bash
uv sync
```

This reads `pyproject.toml` / `uv.lock` and provisions `.venv`. Use
`uv sync --no-dev` to skip the dev dependencies (e.g. `pytest`).

## Run

```bash
uv run uvicorn main:app --reload
```

Then open http://127.0.0.1:8000 in your browser.

## Tests

Each `tests/test_XX/` case has an email, an `expected.json` with the true
fields from that email, and the paired ERP JSON. Extraction is scored against
the email ground truth. Validation is scored by whether the app correctly
flags **match** or **mismatch** (extracted email vs ERP, compared to
`expected.json` vs ERP).

```bash
uv run pytest
```

Regex extraction tests always run. LLM tests (`claude-opus-5`) require
`ANTHROPIC_API_KEY` and are skipped automatically when the key is not set.

### Extraction and validation

LLM extraction (`claude-opus-5`) vs regex fallback, scored against
`expected.json`. Validation is the LLM-first app path (match/mismatch vs ERP).

`test_06` and `test_07` use lowercase PO syntax, a prose go-live date, and
`EUR` with no euro sign, so regex returns no fields while the LLM still
extracts 4/4.

| Case    | LLM extraction | Regex extraction | Validation verdict |
| ------- | -------------- | ---------------- | ------------------ |
| test_00 | 4/4            | 4/4              | match ✓            |
| test_01 | 4/4            | 4/4              | mismatch ✓         |
| test_02 | 4/4            | 4/4              | match ✓            |
| test_03 | 4/4            | 4/4              | match ✓            |
| test_04 | 4/4            | 4/4              | mismatch ✓         |
| test_05 | 4/4            | 4/4              | mismatch ✓         |
| test_06 | 4/4            | 0/4              | match ✓            |
| test_07 | 4/4            | 0/4              | mismatch ✓         |
| **Total** | **32/32**    | **24/32**        | **8/8 correct**    |

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

## Notes

- Extraction is LLM-first; the regex fallback in `extractor.py` is tuned to the
  sample email formats, so unusual wording handled only by regex may require
  updating the patterns.
- Only EUR amounts are handled today; currency defaults to EUR when an amount
  is present but no currency is given.
