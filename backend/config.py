"""
config.py — all credentials and pipeline constants.
Copy .env.example to .env and fill in your values.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── OpenAI ───────────────────────────────────────────────────────
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "")
JD_MODEL         = os.getenv("JD_MODEL",        "gpt-4.1-mini-2025-04-14")   # Call 1 — cheap extraction
OPTIMIZER_MODEL  = os.getenv("OPTIMIZER_MODEL", "gpt-4.1-2025-04-14")       # Call 2 — surgical rewrite

# ── Google Drive ─────────────────────────────────────────────────
RESUME_FILE_ID   = os.getenv("RESUME_FILE_ID",   "12T7ATJkfnajmlZ0mVpO_6un3i7PXUYSJ")
OUTPUT_FOLDER_ID = os.getenv("OUTPUT_FOLDER_ID",  "1Q17UTwelBtnm2_KrQZuhxGToUfUkDfCV")

# ── Google Sheets ────────────────────────────────────────────────
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "1NndDIHb3k3ebG8ijiDxQ6ZlgnFtpyZaqveEi0dJb3xo")
SHEET_NAME     = os.getenv("SHEET_NAME",     "Meta2")

# ── Gmail ────────────────────────────────────────────────────────
GMAIL_SENDER       = os.getenv("GMAIL_SENDER",       "prabhuteja.dev1@gmail.com")
GMAIL_RECIPIENT    = os.getenv("GMAIL_RECIPIENT",     "prabhuteja.dev1@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD",  "")

# ── Google OAuth2 ────────────────────────────────────────────────
# Download from: Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client IDs → Download JSON
OAUTH_CREDENTIALS_FILE = os.getenv("OAUTH_CREDENTIALS_FILE", "oauth_credentials.json")
# Token files — created automatically after first browser login. Do NOT commit these.
DRIVE_TOKEN_FILE  = os.getenv("DRIVE_TOKEN_FILE",  "token_drive.json")
SHEETS_TOKEN_FILE = os.getenv("SHEETS_TOKEN_FILE", "token_sheets.json")

# ── Fixed summary metrics — always injected, never AI-generated ──
FIXED_METRICS = [
    "Optimized Spring MVC and Spring Data JPA queries during peak windows, improving database query performance by 18%.",
    "Achieved 99.99% uptime and cut cloud operational costs by 20% through AWS ECS infrastructure optimization.",
    "Reduced procurement portal load time by 40% via React code splitting and lazy loading optimizations.",
    "Scaled analytics platform to 10,000+ MAU integrating Spring Boot REST services with PostgreSQL and MongoDB.",
    "Shortened release cycles by 25% automating CI/CD pipelines with GitHub Actions and GitLab CI.",
]









