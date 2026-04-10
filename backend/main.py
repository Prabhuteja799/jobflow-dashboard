"""
ATS Resume Optimization Pipeline
Replacement for the n8n workflow — same logic, full Python control.
Run: python main.py
"""

import logging
import re
import sys

from config         import RESUME_FILE_ID, OUTPUT_FOLDER_ID, SPREADSHEET_ID, SHEET_NAME
from sheets         import get_filtered_jobs, write_resume_link
from drive          import fetch_resume_text, upload_pdf
from jd_analysis    import analyze_jd
from optimizer      import optimize_resume
from pdf_client     import generate_pdf
from email_sender   import send_summary_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


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


def main():
    log.info("── ATS Pipeline starting ──────────────────────────────")

    # ── Step 1: Fetch resume once ────────────────────────────────
    log.info("Fetching resume PDF from Google Drive...")
    try:
        resume_text = fetch_resume_text(RESUME_FILE_ID)
        log.info("Resume fetched — %d characters", len(resume_text))
    except Exception as e:
        log.error("Failed to fetch resume: %s", e)
        sys.exit(1)

    # ── Step 2: Fetch & filter jobs from Google Sheet ────────────
    log.info("Fetching jobs from Google Sheets...")
    try:
        jobs = get_filtered_jobs(SPREADSHEET_ID, SHEET_NAME)
        log.info("Found %d jobs to process", len(jobs))
    except Exception as e:
        log.error("Failed to fetch jobs: %s", e)
        sys.exit(1)

    if not jobs:
        log.info("No jobs to process. Exiting.")
        return

    # ── Step 3: Process each job ─────────────────────────────────
    summary = []

    for job in jobs:
        company  = job.get("Company",  "")
        position = job.get("Position", "")
        job_desc = job.get("Job_Desc", "")
        job_id   = job.get("Job_ID",   "")
        job_url  = job.get("Job_URL",  "")

        log.info("Processing: %s — %s", company, position)

        try:
            # Call 1 — JD keyword analysis (gpt-4o-mini, cheap & fast)
            log.info("  [1/5] Analyzing JD...")
            jd_analysis = analyze_jd(job_desc, company, position)

            # Call 2 — Surgical resume optimization (o4-mini)
            log.info("  [2/5] Optimizing resume...")
            resume_data = optimize_resume(resume_text, jd_analysis, company, position)

            # Call pdf-service to generate PDF
            log.info("  [3/5] Generating PDF...")
            file_name = f"{short_name(company)}_{short_name(position, max_words=3)}.pdf"
            pdf_bytes = generate_pdf(resume_data, file_name)

            # Upload to Google Drive (replace if exists)
            log.info("  [4/5] Uploading to Google Drive...")
            drive_link = upload_pdf(pdf_bytes, file_name, OUTPUT_FOLDER_ID)

            # Write Drive link back to Google Sheet
            log.info("  [5/5] Writing link to Google Sheet...")
            write_resume_link(SPREADSHEET_ID, SHEET_NAME, job_id, drive_link)

            log.info("  ✅ Done: %s", drive_link)
            summary.append({
                "company":    company,
                "position":   position,
                "job_url":    job_url,
                "resume_url": drive_link,
                "status":     "✅ Success",
            })

        except Exception as e:
            log.error("  ❌ Failed: %s", e)
            summary.append({
                "company":  company,
                "position": position,
                "job_url":  job_url,
                "status":   f"❌ Failed: {e}",
            })

    # ── Step 4: Send summary email ───────────────────────────────
    log.info("Sending summary email...")
    try:
        send_summary_email(summary)
        log.info("Email sent.")
    except Exception as e:
        log.error("Failed to send email: %s", e)

    log.info("── Pipeline complete: %d processed ────────────────────", len(summary))


if __name__ == "__main__":
    main()
