# JobFlow Backend

The engine behind the JobFlow system. Two things run here:

1. **n8n Workflow** — runs every weekday night, scrapes Java job listings from JSearch, scores each one against the resume using GPT, and routes them into Google Sheets by fit category.
2. **FastAPI Server** — triggered manually from the JobFlow dashboard, takes a job's description, rewrites the resume to match it, generates a LaTeX PDF, uploads it to Google Drive, and writes the link back to Sheets.

---

## How the n8n Workflow works

**File:** `n8n-workflow.json` — import this into your n8n instance.

### Trigger
Runs automatically at **11:30 PM UTC (7:30 PM ET) on weekdays** via a cron schedule trigger.

### Step-by-step

```
Schedule Trigger
    │
    ▼
📋 Read Existing Job_IDs         ← pulls all Job_IDs from Google Sheet to avoid duplicates
    │
    ▼
📦 Collect Existing IDs          ← collapses all rows into a single Set for fast lookup
    │
    ▼
📥 Download Resume from Drive    ← downloads your resume PDF from Google Drive
    │
    ▼
📄 Extract Resume Text           ← converts PDF binary to plain text
    │
    ▼
GPT-4o-mini: Parse Resume        ← extracts structured skill profile (languages, frameworks,
    │                               cloud, messaging, etc.) — stored in workflow static data
    ▼
Code: Build Search Queries       ← generates 9 search queries across FL, GA, NY
    │                               ("Java Developer Jobs in Florida", etc.)
    ▼
Loop Over Items (queries)
    │
    ├── JSearch API (RapidAPI)   ← fetches up to 49 pages of job listings per query
    │       │                       filters out low-quality publishers (Jooble, Lensa, etc.)
    │       ▼
    │   Wait 45s                 ← rate limiting between API calls
    │
    ▼
Aggregate                        ← merges all jobs from all queries into one list
    │
    ▼
🔬 Filter + Dedupe               ← applies all rules (see below), skips duplicates
    │
    ▼
Has New Jobs?
    ├── NO  → stop
    └── YES ▼
        │
        ├── ✅ Append to Google Sheet (JobTracker tab)
        │
        └── Loop Over Items (one job at a time)
                │
                ▼
            GPT-5: Score Job Fit     ← evaluates job against resume with a detailed rubric
                │                       (see Scoring section below)
                ▼
            Parse ATS Response
                │
                ▼
            Switch on Decision
                ├── strong_match → StrongMatch sheet
                ├── maybe        → MayBe sheet
                ├── weak         → Weak sheet
                └── no           → No sheet
                        │
                        ▼
                    Send Email notification
```

---

### Filter Rules (🔬 Filter + Dedupe node)

Every job fetched from JSearch goes through these checks before it's processed:

| Rule | Detail |
|---|---|
| Must have Java | Job title, description, or required skills must contain "java" |
| Exclude senior titles | Rejects: Staff, Principal, Fellow, Director, VP, Vice President, Manager, Lead Engineer |
| Exclude clearance/GC | Rejects jobs mentioning: security clearance, TS/SCI, top secret, green card required, US citizenship required, polygraph, etc. |
| Experience cap | Minimum years stated in the job must be ≤ 6 (e.g. "1–6 yrs" ✅, "7+ yrs" ❌) |
| Duplicate check | Skips Job_IDs already in the Google Sheet or seen earlier in the same batch |

Rejected jobs are logged with a reason but not written to the sheet.

---

### Fit Scoring (GPT-5 node)

Each passing job is scored across 4 dimensions (total 0–100):

| Dimension | Max | What it measures |
|---|---|---|
| Backend Alignment | 40 | Is the role primarily Java/Spring Boot/microservices? |
| Core Requirements Match | 35 | % of explicitly required skills present in the resume |
| Seniority Alignment | 15 | Is it an IC role, or does it expect team lead/architect? |
| Bonus | 10 | AWS/GCP, Docker/K8s, CI/CD, observability tools |

**Decision thresholds:**
- ≥ 75, no flags → `strong_match`
- ≥ 75, with flags → `maybe`
- 60–74 → `maybe`
- 40–59 → `weak`
- < 40 → `no`

**Hard flags** (can cap or change decision):
- `clearance_or_citizenship_required` → caps fitScore at 40
- `senior_title` → title has Staff/Principal/Lead/Director/VP/Architect/Head
- `6plus_years` → explicitly requires 6+ years minimum

---

### Google Sheets structure

| Sheet | Contents |
|---|---|
| `JobTracker` | All passing jobs with raw fields (Job_ID, Company, Position, URL, Location, etc.) |
| `StrongMatch` | Jobs scored ≥ 75 with no hard flags |
| `MayBe` | Jobs scored 60–74, or ≥ 75 with flags |
| `Weak` | Jobs scored 40–59 |
| `No` | Jobs scored < 40 |

Each scored sheet also stores: `FitScore`, `Confidence`, `Decision`, `Strengths`, `Missings`, `Hard_Flags`, `ScoreJustification`, `SeniorityMismatch`, `CoverLetter`.

---

## How the FastAPI Server works

**File:** `server.py` — run locally when you want to generate a tailored resume for a specific job.

```
POST /generate-resume
Body: { job_id, company, position, job_desc }
```

### Pipeline

```
job_desc
    │
    ▼
jd_analysis.py          ← GPT extracts required skills, seniority, key themes from JD
    │
    ▼
optimizer.py            ← GPT rewrites resume sections (summary, bullets) to mirror JD keywords
    │                      Uses ATS rules: no buzzwords, full degree names, keyword placement
    ▼
latex_pdf_generator.py  ← builds a .tex file and compiles it with pdflatex
    │                      Handles: ligatures, hyphenation, education alignment, bullet encoding
    ▼
drive.py                ← uploads the compiled PDF to Google Drive (OUTPUT_FOLDER_ID)
    │
    ▼
sheets.py               ← writes the Drive URL back to the ATS_Resume column in Google Sheets
    │
    ▼
Response: { resume_url, file_name }
```

The generated PDF filename is `CompanyName_Position.pdf` (e.g. `Google_Software_Engineer.pdf`).

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/Prabhuteja799/jobflow-backend.git
cd jobflow-backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Install BasicTeX (required for PDF generation):
```bash
brew install --cask basictex
sudo tlmgr update --self && sudo tlmgr install lmodern
```

### 2. Configure environment

```bash
cp .env.example .env
# Fill in all values in .env
```

Required values:

| Variable | Where to get it |
|---|---|
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com/api-keys) |
| `GITHUB_TOKEN` | [github.com/settings/tokens](https://github.com/settings/tokens) |
| `GIST_ID` | The ID from your GitHub Gist URL |
| `RESUME_FILE_ID` | Google Drive file ID of your resume PDF |
| `OUTPUT_FOLDER_ID` | Google Drive folder ID for generated resumes |
| `SPREADSHEET_ID` | Google Sheets ID from the URL |
| `GMAIL_APP_PASSWORD` | [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) |

### 3. Google OAuth (one-time)

Place your `service_account.json` (Google Cloud service account) and `oauth_credentials.json` (OAuth2 Desktop credentials) in the project root. These are never committed.

### 4. Run the server

```bash
PATH="$PATH:/Library/TeX/texbin" python server.py
# Listening on http://localhost:8000
```

### 5. Import n8n workflow

1. Open your n8n instance
2. Go to **Workflows → Import**
3. Upload `n8n-workflow.json`
4. Re-link credentials (Google Sheets, Google Drive, Gmail, OpenAI)
5. Replace the RapidAPI key in the JSearch HTTP node with your own from [rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch)
6. Activate the workflow

---

## Tech stack

| Layer | Tech |
|---|---|
| Job scraping | JSearch API (RapidAPI) |
| Automation | n8n (self-hosted) |
| AI scoring | OpenAI GPT-5 / GPT-4o-mini |
| Resume optimization | OpenAI GPT-4o-mini |
| PDF generation | LaTeX (`pdflatex`, `lmodern`) |
| Storage | Google Drive, Google Sheets |
| Notifications | Gmail |
| API server | FastAPI + Uvicorn |

---

## Repository layout

```
jobflow-backend/
├── server.py                  # FastAPI entry point
├── optimizer.py               # Resume rewriter (OpenAI)
├── jd_analysis.py             # Job description analyzer
├── latex_pdf_generator.py     # LaTeX PDF builder
├── pdf_client.py              # PDF service client
├── drive.py                   # Google Drive upload
├── sheets.py                  # Google Sheets read/write
├── email_sender.py            # Gmail notification sender
├── seed_gist.py               # One-time Gist seeder (Sheets → GitHub Gist)
├── config.py                  # Env var loader
├── prompts/
│   ├── optimizer_system.txt   # ATS rewrite system prompt
│   ├── optimizer_user.txt     # ATS rewrite user prompt
│   ├── jd_analysis_system.txt
│   └── jd_analysis_user.txt
├── n8n-workflow.json          # Full n8n automation workflow
├── requirements.txt
├── .env.example               # Template — copy to .env and fill in
└── .gitignore
```
