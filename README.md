# PO Validator

A local FastAPI web app for processing purchase order (PO) confirmations.

It provides a simple web UI with two inputs:

1. **Email confirmation** — paste the PO confirmation email text directly into
   the textarea. The server regex-extracts the **PO number**, **date**, and
   **amount**, then writes an intermediate JSON file to `output/`.
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
  "extracted_at": "2026-05-30T10:24:00+00:00"
}
```

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

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn main:app --reload
```

Then open http://127.0.0.1:8000 in your browser.

## Tests

Regression tests run the saved emails under `tests/` through the extractor and
compare them against their paired ERP JSON fixtures:

```bash
pytest
```

## Project structure

```
main.py            FastAPI app and routes
extractor.py       Regex field extraction + normalization
templates/         HTML UI (Jinja2)
output/            Generated intermediate JSON files (gitignored)
uploads/           Stored ERP JSON files (gitignored)
tests/             Per-case fixtures (test_XX/) + regression tests
```

## Notes

- Extraction is regex-based and tuned to the sample email format; different
  wording may require updating the patterns in `extractor.py`.
- Only EUR amounts are handled today; currency defaults to EUR when an amount
  is present but no currency is given.
