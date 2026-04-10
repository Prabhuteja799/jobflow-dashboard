"""
drive.py — fetch resume PDF text, upload/replace optimized PDF on Google Drive.
Uses OAuth2 (your personal Google account) — same as n8n.
First run opens a browser to authenticate. Token saved to token_drive.json for reuse.
"""

import io
import logging
from pathlib import Path

import pdfplumber
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from config import OAUTH_CREDENTIALS_FILE, DRIVE_TOKEN_FILE

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]


def _get_service():
    creds = None

    # Load saved token if it exists
    if Path(DRIVE_TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(DRIVE_TOKEN_FILE, SCOPES)

    # Refresh or re-authenticate if needed
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow  = InstalledAppFlow.from_client_secrets_file(
                OAUTH_CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)
        Path(DRIVE_TOKEN_FILE).write_text(creds.to_json())

    return build("drive", "v3", credentials=creds)


def fetch_resume_text(file_id: str) -> str:
    """
    Download resume PDF from Google Drive and extract plain text.
    """
    service = _get_service()
    request = service.files().get_media(fileId=file_id)
    buf     = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    buf.seek(0)

    with pdfplumber.open(buf) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    text = "\n".join(pages).strip()
    log.info("Extracted %d characters from resume PDF", len(text))
    return text


def upload_pdf(pdf_bytes: bytes, file_name: str, folder_id: str) -> str:
    """
    Upload PDF to Google Drive folder.
    If a file with the same name already exists, REPLACE it (same file ID).
    Returns the public view URL.
    """
    service = _get_service()

    query   = (
        f"name='{file_name}' "
        f"and '{folder_id}' in parents "
        f"and trashed=false"
    )
    results  = service.files().list(q=query, fields="files(id)").execute()
    existing = results.get("files", [])

    buf   = io.BytesIO(pdf_bytes)
    media = MediaIoBaseUpload(buf, mimetype="application/pdf", resumable=True)

    if existing:
        file_id = existing[0]["id"]
        service.files().update(fileId=file_id, media_body=media).execute()
        log.info("Replaced existing Drive file: %s", file_id)
    else:
        meta    = {"name": file_name, "parents": [folder_id]}
        created = service.files().create(
            body=meta, media_body=media, fields="id"
        ).execute()
        file_id = created["id"]
        log.info("Uploaded new Drive file: %s", file_id)

    return f"https://drive.google.com/file/d/{file_id}/view"