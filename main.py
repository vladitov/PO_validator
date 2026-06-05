"""FastAPI web server for the PO Validator.

Provides a simple UI with two inputs:
  - Email purchase order confirmation: pasted as text; fields are extracted via
    regex and written to an intermediate JSON file in output/.
  - ERP JSON (.json): validated as JSON and stored in uploads/.

When both an email and an ERP file have been uploaded, the extracted email
fields are compared against the ERP fields and a green/red/gray indicator is
shown (gray = not enough data yet).
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from extractor import build_intermediate_record, compare_fields, extract_erp_fields

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
UPLOADS_DIR = BASE_DIR / "uploads"
TEMPLATES_DIR = BASE_DIR / "templates"

OUTPUT_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)

app = FastAPI(title="PO Validator")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# In-memory state for the most recent uploads (single-user localhost tool).
STATE: dict[str, dict | None] = {"email": None, "erp": None}

COMPARE_FIELDS = ("po_number", "date", "amount", "currency")


def _build_context(message: dict | None = None) -> dict:
    """Assemble the template context including the comparison indicator."""
    email = STATE["email"]
    erp = STATE["erp"]

    indicator = "gray"
    comparison = None
    rows = None

    if email and erp:
        comparison = compare_fields(email["fields"], erp["fields"])
        indicator = "green" if comparison["status"] == "match" else "red"
        rows = [
            {
                "field": field,
                "email": email["fields"].get(field),
                "erp": erp["fields"].get(field),
                "match": comparison["checks"][field],
            }
            for field in COMPARE_FIELDS
        ]

    return {
        "message": message,
        "email": email,
        "erp": erp,
        "indicator": indicator,
        "comparison": comparison,
        "rows": rows,
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html", _build_context())


@app.post("/upload-email", response_class=HTMLResponse)
async def upload_email(request: Request, email_text: str = Form(...)) -> HTMLResponse:
    text = email_text.strip()
    if not text:
        return templates.TemplateResponse(
            request,
            "index.html",
            _build_context({"type": "error", "text": "Please paste the email text."}),
        )

    source_name = "pasted-email"
    record = build_intermediate_record(source_name, text)

    out_path = OUTPUT_DIR / "pasted-email.extracted.json"
    out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    method = record.get("extraction_method", "regex")
    STATE["email"] = {
        "source_file": source_name,
        "fields": {k: record[k] for k in COMPARE_FIELDS},
        "record": record,
        "output_path": out_path.name,
        "method": method,
    }

    method_label = "LLM" if method == "llm" else "regex"
    return templates.TemplateResponse(
        request,
        "index.html",
        _build_context(
            {
                "type": "ok",
                "text": f"Email extracted via {method_label} -> {out_path.name}",
            }
        ),
    )


@app.post("/upload-erp", response_class=HTMLResponse)
async def upload_erp(request: Request, file: UploadFile = File(...)) -> HTMLResponse:
    filename = file.filename or "erp.json"
    if not filename.lower().endswith(".json"):
        return templates.TemplateResponse(
            request,
            "index.html",
            _build_context({"type": "error", "text": "Please upload a .json ERP file."}),
        )

    raw = await file.read()
    try:
        parsed = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        return templates.TemplateResponse(
            request,
            "index.html",
            _build_context({"type": "error", "text": f"Invalid JSON: {exc}"}),
        )

    dest_path = UPLOADS_DIR / filename
    dest_path.write_text(json.dumps(parsed, indent=2), encoding="utf-8")

    STATE["erp"] = {
        "source_file": filename,
        "fields": extract_erp_fields(parsed),
        "raw": parsed,
    }

    return templates.TemplateResponse(
        request,
        "index.html",
        _build_context({"type": "ok", "text": f"ERP JSON stored -> {dest_path.name}"}),
    )


@app.get("/reset")
async def reset() -> RedirectResponse:
    STATE["email"] = None
    STATE["erp"] = None
    return RedirectResponse(url="/", status_code=303)
