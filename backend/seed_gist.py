"""
JobFlow — One-time Gist Seeder (Google Sheets via OAuth)
=========================================================
Usage:
  1. pip install requests google-auth google-auth-oauthlib google-api-python-client
  2. Go to Google Cloud Console → Create OAuth 2.0 credentials → Download as credentials.json
  3. Paste your GitHub token and Spreadsheet ID below
  4. Run: python seed_gist.py
     (browser will open once to authorize — token saved as token.json for reuse)
"""

import json, re, requests
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os

# ── CONFIG ─────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()
GITHUB_TOKEN    = os.environ['GITHUB_TOKEN']
GIST_ID         = os.environ.get('GIST_ID', '')
SPREADSHEET_ID  = os.environ.get('SPREADSHEET_ID', '')
CREDENTIALS_FILE = 'oauth_credentials.json'   # downloaded from Google Cloud Console
TOKEN_FILE       = 'token.json'         # auto-created after first auth
# ──────────────────────────────────────────────────────────────

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

def get_sheets_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())
    return build('sheets', 'v4', credentials=creds)

def read_sheet(service, sheet_name, category):
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f'{sheet_name}!A1:ZZ'
        ).execute()

        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f'{sheet_name}!A1:ZZ',
            valueRenderOption='FORMULA'          # ← returns =HYPERLINK("url","text") as-is
        ).execute()
        
    except Exception as e:
        print(f'  ⚠️  Sheet "{sheet_name}" error: {e}')
        return []

    rows = result.get('values', [])
    if not rows:
        print(f'  ⚠️  Sheet "{sheet_name}" is empty')
        return []

    headers = rows[0]
    jobs = []

    for row in rows[1:]:
        # Pad row to header length
        row = row + [''] * (len(headers) - len(row))
        obj = {headers[i]: row[i] for i in range(len(headers))}

        job_id = str(obj.get('Job_ID', '') or '').strip()
        if not job_id:
            continue

        strengths    = str(obj.get('Strengths', '') or '')
        missings     = str(obj.get('Missings',  '') or '')
        tags         = [s.strip() for s in re.split(r'[|,]', strengths) if s.strip() and len(s.strip()) > 1][:6]
        missing_tags = [s.strip() for s in re.split(r'[|,]', missings)  if s.strip() and len(s.strip()) > 1][:4]
        ats_resume   = str(obj.get('ATS_Resume', '') or '').strip()

        jobs.append({
            'id':            job_id,
            'category':      category,
            'company':       str(obj.get('Company',  '') or '').strip(),
            'position':      str(obj.get('Position', '') or '').strip(),
            'location':      str(obj.get('Location', '') or '').strip(),
            'state':         get_state(obj.get('Location', '')),
            'url':           extract_url(str(obj.get('Job_URL', '') or '')),
            'job_desc':      str( obj.get('Description', '') or '') ,                        #String(job.Job_Desc   || ''),
            'score':         float(obj.get('FitScore', 0) or 0),
            'tags':          tags,
            'missing_tags':  missing_tags,
            'flags':         parse_flags(obj.get('Hard_Flags', '')),
            'justification': str(obj.get('ScoreJustification', '') or '')[:300],
            'cover':         str(obj.get('CoverLetter', '') or '')[:500],
            'posted_dt':     parse_date(obj.get('Posted At')),
            'last_checked': parse_date(obj.get('Last_Checked')),
            'publisher':     str(obj.get('Publisher', '') or '').strip(),
            'ats_resume':    ats_resume,
        })

    return jobs


# ── Helpers (unchanged from original) ─────────────────────────
def parse_flags(raw):
    if not raw or str(raw).strip() in ('', 'None'): return []
    flags = []
    for part in re.split(r'[,|]', str(raw)):
        f = part.strip()
        if not f: continue
        if f == 'senior_title':    flags.append('Senior Title')
        elif '6plus' in f:         flags.append('6+ Years Required')
        elif 'clearance' in f:     flags.append('Clearance / Citizenship')
        else:                      flags.append(f)
    return flags

def get_state(loc):
    if not loc: return ''
    loc = str(loc).strip()
    if re.search(r'\bRemote\b', loc, re.I) and ',' not in loc: return 'Remote'
    m = re.search(r',\s*([A-Za-z][A-Za-z\s]{1,18})(?:\s*\(|$)', loc)
    return m.group(1).strip() if m else ''

def extract_url(raw):
    if not raw: return ''
    m = re.search(r'https?://[^\s"]+', str(raw))
    return m.group(0) if m else ''


def parse_date(val):
    if val is None: return None
    if isinstance(val, datetime): return val.isoformat()
    s = str(val).strip()

    # Excel/Sheets serial number (e.g. 45983.75)
    try:
        n = float(s)
        if 40000 < n < 60000:  # sanity check — valid date range
            from datetime import timedelta
            d = datetime(1899, 12, 30) + timedelta(days=n)
            return d.isoformat()
    except: pass

    # Handle "MM/DD/YYYY, H:MM AM/PM" — Google Sheets locale format
    for fmt in ('%m/%d/%Y, %I:%M %p', '%m/%d/%Y, %I:%M%p', '%m/%d/%Y'):
        try: return datetime.strptime(s, fmt).isoformat()
        except: pass

    # Fallback — ISO strings
    try: return datetime.fromisoformat(s.replace('Z', '')).isoformat()
    except: return None
# def parse_date(val):
#     if val is None: return None
#     if isinstance(val, datetime): return val.isoformat()
#     s = str(val).strip()
#     # Handle "MM/DD/YYYY, H:MM AM/PM" — Google Sheets locale format
#     for fmt in ('%m/%d/%Y, %I:%M %p', '%m/%d/%Y, %I:%M%p', '%m/%d/%Y'):
#         try: return datetime.strptime(s, fmt).isoformat()
#         except: pass
#     # Fallback — ISO strings
#     try: return datetime.fromisoformat(s.replace('Z', '')).isoformat()
#     except: return None
# ──────────────────────────────────────────────────────────────


def main():
    print('🔑  Authenticating with Google Sheets...')
    service = get_sheets_service()
    print('  ✓  Authenticated')

    jobs = []
    for sheet, category in [('StrongMatch', 'strong'), ('MayBe', 'maybe'), ('Weak', 'weak')]:
        batch = read_sheet(service, sheet, category)
        print(f'  ✓  {sheet}: {len(batch)} jobs')
        jobs += batch

    print(f'\n📦  Total: {len(jobs)} jobs')
    content = json.dumps(jobs, separators=(',', ':'))
    print(f'📏  Size: {len(content)/1024:.1f} KB')

    print(f'\n📤  Pushing to Gist {GIST_ID}...')
    res = requests.patch(
        f'https://api.github.com/gists/{GIST_ID}',
        headers={
            'Authorization': f'token {GITHUB_TOKEN}',
            'Content-Type': 'application/json',
        },
        json={'files': {'jobs.json': {'content': content}}}
    )

    if res.status_code == 200:
        print(f'✅  Done! Gist updated with {len(jobs)} jobs.')
    else:
        print(f'❌  Failed: {res.status_code}')
        print(res.text[:500])

if __name__ == '__main__':
    main()