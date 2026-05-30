# PO Validator

A local FastAPI web app for processing purchase order (PO) confirmations.

It provides a simple web UI with two uploads:

1. **Email confirmation (`.txt`)** — the PO confirmation email. The server
   regex-extracts the **PO number**, **date**, and **amount**, then writes an
   intermediate JSON file to `output/`.
2. **ERP JSON (`.json`)** — the file created by the ERP system after the PO was
   manually entered. For now it is validated as JSON and stored in `uploads/`
   (no comparison/validation against the email yet).

## Extracted fields

Tuned to the sample email in `tests/correct/email_01.txt`:

| Field       | Source in email                              | Example         |
| ----------- | -------------------------------------------- | --------------- |
| `po_number` | Master Lease Agreement reference             | `MLA-2026-88X`  |
| `date`      | Activation date ("scheduled for ...")        | `2026-01-15`    |
| `amount`    | Euro amount                                  | `24500.0` (EUR) |

The intermediate JSON looks like:

```json
{
  "source_file": "email_01.txt",
  "po_number": "MLA-2026-88X",
  "date": "2026-01-15",
  "amount": 24500.0,
  "currency": "EUR",
  "extracted_at": "2026-05-30T10:24:00+00:00"
}
```

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

## Project structure

```
main.py            FastAPI app and routes
extractor.py       Regex field extraction + normalization
templates/         HTML UI (Jinja2)
output/            Generated intermediate JSON files (gitignored)
uploads/           Stored ERP JSON files (gitignored)
tests/             Sample emails
```

## Notes

- Extraction is regex-based and tuned to the sample email format; different
  wording may require updating the patterns in `extractor.py`.
- Validation of the ERP JSON against the extracted email data is planned for a
  future step.
