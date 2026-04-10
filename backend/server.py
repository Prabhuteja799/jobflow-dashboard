"""
server.py — FastAPI server that the website calls to generate a single resume.
Run: python server.py
Listens on http://localhost:8000

Endpoint:
  POST /generate-resume
  Body: { job_id, company, position, job_desc }
  Returns: { resume_url }
"""

import logging
import re

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config          import OUTPUT_FOLDER_ID
from drive           import upload_pdf
from jd_analysis     import analyze_jd
from optimizer       import optimize_resume
from pdf_client      import generate_pdf
from sheets          import write_resume_link, get_filtered_jobs
from config          import SPREADSHEET_ID, SHEET_NAME

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

app = FastAPI(title="ATS Resume Pipeline")

# Allow the local HTML file to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    job_id:   str
    company:  str
    position: str
    job_desc: str


class GenerateResponse(BaseModel):
    resume_url: str
    file_name:  str


_FILLER_WORDS = {
    "and", "the", "of", "for", "a", "an", "in", "at", "by",
    "inc", "llc", "ltd", "corp", "co", "group", "holdings",
    "technology", "technologies", "tech", "solutions", "services",
    "systems", "staffing", "consulting", "global", "international",
}

def short_name(name: str, max_words: int = 2) -> str:
    """Return a short, clean filename segment from a company or position name."""
    clean = re.sub(r"[^a-zA-Z0-9 ]", "", name)
    words = [w for w in clean.split() if w.lower() not in _FILLER_WORDS]
    slug  = "_".join(words[:max_words])
    return slug or re.sub(r"\s+", "_", clean)[:20]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate-resume", response_model=GenerateResponse)
async def generate_resume(req: GenerateRequest):
    log.info("Generating resume for %s — %s", req.company, req.position)

    try:
        # Fetch the resume text from Drive (cached in memory after first call)
        resume_text = _get_resume_text()

        # Call 1 — JD analysis
        log.info("  [1/4] Analyzing JD...")
        jd_analysis = analyze_jd(req.job_desc, req.company, req.position)

        # Call 2 — Surgical resume optimization
        log.info("  [2/4] Optimizing resume...")
        resume_data = optimize_resume(resume_text, jd_analysis, req.company, req.position)

        # Generate PDF
        log.info("  [3/4] Generating PDF...")
        file_name = f"{short_name(req.company)}_{short_name(req.position, max_words=3)}.pdf"
        pdf_bytes = generate_pdf(resume_data, file_name)

        # Upload to Google Drive
        log.info("  [4/4] Uploading to Drive...")
        drive_link = upload_pdf(pdf_bytes, file_name, OUTPUT_FOLDER_ID)

        # Write link back to Google Sheet
        if req.job_id:
            write_resume_link(SPREADSHEET_ID, SHEET_NAME, req.job_id, drive_link)

        log.info("  ✅ Done: %s", drive_link)
        return GenerateResponse(resume_url=drive_link, file_name=file_name)

    except Exception as e:
        log.error("  ❌ Failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Resume text cache — fetched once per server session ──────────
_resume_text_cache: str | None = None

def _get_resume_text() -> str:
    global _resume_text_cache
    if _resume_text_cache is None:
        from drive import fetch_resume_text
        from config import RESUME_FILE_ID
        log.info("Fetching resume from Drive (first call)...")
        _resume_text_cache = fetch_resume_text(RESUME_FILE_ID)
        log.info("Resume cached — %d chars", len(_resume_text_cache))
    return _resume_text_cache


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)