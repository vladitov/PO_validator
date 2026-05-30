"""FastAPI web server for the PO Validator.

Provides a simple UI with two uploads:
  - Email purchase order confirmation (.txt): fields are extracted via regex and
    written to an intermediate JSON file in output/.
  - ERP JSON (.json): validated as JSON and stored in uploads/ (no comparison yet).
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from extractor import build_intermediate_record

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
UPLOADS_DIR = BASE_DIR / "uploads"
TEMPLATES_DIR = BASE_DIR / "templates"

OUTPUT_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)

app = FastAPI(title="PO Validator")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html", {"result": None})


@app.post("/upload-email", response_class=HTMLResponse)
async def upload_email(request: Request, file: UploadFile = File(...)) -> HTMLResponse:
    filename = file.filename or "email.txt"
    if not filename.lower().endswith(".txt"):
        return templates.TemplateResponse(
            request,
            "index.html",
            {"result": {"type": "error", "message": "Please upload a .txt email file."}},
        )

    raw = await file.read()
    text = raw.decode("utf-8", errors="replace")

    record = build_intermediate_record(filename, text)

    stem = Path(filename).stem
    out_path = OUTPUT_DIR / f"{stem}.extracted.json"
    out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "result": {
                "type": "email",
                "message": f"Extracted fields written to {out_path.name}",
                "record": record,
                "output_path": str(out_path),
            }
        },
    )


@app.post("/upload-erp", response_class=HTMLResponse)
async def upload_erp(request: Request, file: UploadFile = File(...)) -> HTMLResponse:
    filename = file.filename or "erp.json"
    if not filename.lower().endswith(".json"):
        return templates.TemplateResponse(
            request,
            "index.html",
            {"result": {"type": "error", "message": "Please upload a .json ERP file."}},
        )

    raw = await file.read()
    try:
        parsed = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"result": {"type": "error", "message": f"Invalid JSON: {exc}"}},
        )

    dest_path = UPLOADS_DIR / filename
    dest_path.write_text(json.dumps(parsed, indent=2), encoding="utf-8")

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "result": {
                "type": "erp",
                "message": f"ERP JSON stored as {dest_path.name}",
                "record": parsed,
                "output_path": str(dest_path),
            }
        },
    )
