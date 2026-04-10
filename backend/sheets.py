"""
sheets.py — read jobs from Google Sheet, write resume Drive link back.
Uses OAuth2 (your personal Google account) — same as n8n.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from config import OAUTH_CREDENTIALS_FILE, SHEETS_TOKEN_FILE

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _get_client() -> gspread.Client:
    creds = None

    if Path(SHEETS_TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(SHEETS_TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow  = InstalledAppFlow.from_client_secrets_file(
                OAUTH_CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)
        Path(SHEETS_TOKEN_FILE).write_text(creds.to_json())

    return gspread.authorize(creds)


def get_filtered_jobs(spreadsheet_id: str, sheet_name: str) -> List[Dict[str, Any]]:
    """
    Return rows where:
      - Status != 'Applied'  (case-insensitive)
      - Job_Desc is not empty
    """
    client     = _get_client()
    sheet      = client.open_by_key(spreadsheet_id).worksheet(sheet_name)
    all_values = sheet.get_all_values()
    if not all_values:
        return []

    # Build header map — skip empty or duplicate columns
    raw_headers = all_values[0]
    seen        = set()
    headers     = []
    for h in raw_headers:
        h = h.strip()
        if h and h not in seen:
            seen.add(h)
            headers.append(h)
        else:
            headers.append(None)

    # Build list of dicts using only valid headers
    rows = []
    for raw_row in all_values[1:]:
        row = {}
        for i, val in enumerate(raw_row):
            if i < len(headers) and headers[i]:
                row[headers[i]] = val
        rows.append(row)

    filtered = [
        row for row in rows
        if str(row.get("Job_Desc", "")).strip()
        and str(row.get("Status",   "")).strip().lower() != "applied"
    ]
    log.info("Sheet has %d total rows, %d pass filter", len(rows), len(filtered))
    return filtered


def write_resume_link(spreadsheet_id: str, sheet_name: str,
                      job_id: str, drive_link: str) -> None:
    """
    Write the Drive link to the ATS_Resume column, matched by Job_ID.
    """
    client     = _get_client()
    sheet      = client.open_by_key(spreadsheet_id).worksheet(sheet_name)
    all_values = sheet.get_all_values()
    if not all_values:
        log.warning("Sheet is empty — link not written")
        return

    headers = all_values[0]

    if "ATS_Resume" not in headers:
        log.warning("ATS_Resume column not found in sheet headers")
        return
    if "Job_ID" not in headers:
        log.warning("Job_ID column not found in sheet headers")
        return

    job_id_col = headers.index("Job_ID")     + 1
    resume_col = headers.index("ATS_Resume") + 1

    for i, raw_row in enumerate(all_values[1:], start=2):
        cell_val = raw_row[job_id_col - 1] if len(raw_row) >= job_id_col else ""
        if cell_val.strip() == str(job_id).strip():
            sheet.update_cell(i, resume_col, drive_link)
            log.info("    Wrote Drive link to row %d (Job_ID=%s)", i, job_id)
            return

    log.warning("Job_ID %s not found in sheet — link not written", job_id)