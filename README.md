# JobFlow

A personal job intelligence system that automatically scrapes Java job listings every weekday, scores each one against your resume using GPT, routes them into Google Sheets by fit category, and lets you generate a tailored ATS-optimized PDF resume for any job with one click — all from a self-hosted dashboard.

**Live dashboard:** [prabhuteja799.github.io/jobflow](https://prabhuteja799.github.io/jobflow/)

---

## What the system does

```
Every weekday night (automated)
────────────────────────────────
n8n Workflow
  └─ Scrapes Java jobs from JSearch (FL, GA, NY)
  └─ Filters: Java required, no clearance, no senior titles, exp ≤ 6 yrs
  └─ Scores each job against resume using GPT (0–100 fit score)
  └─ Routes to StrongMatch / MayBe / Weak / No in Google Sheets
  └─ Sends email notification when done

On demand (from dashboard)
────────────────────────────
Click "Generate Resume" on any job card
  └─ FastAPI server analyzes the job description
  └─ GPT rewrites resume to mirror JD keywords (ATS-optimized)
  └─ LaTeX compiles a clean PDF
  └─ PDF uploaded to Google Drive
  └─ Drive link written back to Google Sheets
  └─ Dashboard shows the download link instantly
```

---

## Repository layout

```
jobflow/
├── index.html              ← Dashboard frontend (GitHub Pages)
├── .gitignore
├── README.md
│
└── backend/                ← Python server + n8n automation
    ├── server.py               FastAPI entry point (POST /generate-resume)
    ├── optimizer.py            GPT resume rewriter
    ├── jd_analysis.py          Job description analyzer
    ├── latex_pdf_generator.py  LaTeX PDF builder
    ├── pdf_client.py           PDF microservice client
    ├── drive.py                Google Drive upload
    ├── sheets.py               Google Sheets read/write
    ├── email_sender.py         Gmail notification sender
    ├── seed_gist.py            Syncs Sheets data → GitHub Gist (feeds dashboard)
    ├── config.py               Env var loader
    ├── prompts/
    │   ├── optimizer_system.txt    ATS rewrite instructions
    │   ├── optimizer_user.txt
    │   ├── jd_analysis_system.txt
    │   └── jd_analysis_user.txt
    ├── n8n-workflow.json       Full n8n automation (import into n8n)
    ├── requirements.txt
    └── .env.example            Copy to .env and fill in your keys
```

---

## Part 1 — Dashboard (index.html)

The frontend is a single HTML file served via GitHub Pages. It reads job data from a GitHub Gist (populated by `seed_gist.py`) and renders a filterable job board.

**Features:**
- View all scored jobs grouped by category (StrongMatch / MayBe / Weak)
- Filter by state, score range, publisher, company
- See fit score, matched strengths, missing skills, score justification
- Click **Generate Resume** to trigger the backend and get a tailored PDF
- Click **Apply** to open the job posting

The dashboard talks to the backend at `http://localhost:8000`. It must be running locally for resume generation to work.

---

## Part 2 — n8n Workflow (backend/n8n-workflow.json)

Runs every weekday at **11:30 PM UTC (7:30 PM ET)** automatically.

### Full flow

```
Schedule Trigger (weekdays 23:30 UTC)
    │
    ▼
📋 Read Existing Job_IDs from Google Sheets   ← dedup check
    │
    ▼
📦 Collect Existing IDs                        ← collapse rows into a Set
    │
    ▼
📥 Download Resume PDF from Google Drive
    │
    ▼
📄 Extract Resume Text
    │
    ▼
GPT-4o-mini: Parse Resume into Skill Profile   ← stored in workflow static data
    │                                              (languages, frameworks, cloud, etc.)
    ▼
Build Search Queries
    │   "Software Engineer Jobs in Florida"
    │   "Java Developer Jobs in Florida"
    │   "Backend Engineer Jobs in Florida"
    │   "Software Engineer Jobs in Georgia"
    │   ... (9 queries total across FL, GA, NY)
    │
    ▼
Loop: for each query
    ├── JSearch API (RapidAPI) → up to 49 pages of listings
    └── Wait 45s  (rate limiting)
    │
    ▼
Aggregate all results
    │
    ▼
🔬 Filter + Dedupe
    │
    ▼
Has new jobs?
    ├── NO  → stop
    └── YES
        ├── Append all to JobTracker sheet
        └── Loop: for each job (one at a time)
                │
                ▼
            GPT-5: Score Job Fit (0–100)
                │
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
                    Gmail: send notification email
```

### Filter rules

| Rule | Logic |
|---|---|
| Must have Java | Title + description + skills must contain "java" |
| No senior titles | Rejects: Staff, Principal, Fellow, Director, VP, Vice President, Manager, Lead Engineer |
| No clearance / GC | Rejects: security clearance, TS/SCI, top secret, green card required, US citizenship required, polygraph, and 15+ variants |
| Experience cap | Minimum years stated in the JD must be ≤ 6 (e.g. "1–6 yrs" ✅, "7+ yrs" ❌) |
| No duplicates | Skips Job_IDs already in the sheet or seen in the same batch |

### Fit scoring rubric

| Dimension | Points | What it measures |
|---|---|---|
| Backend Alignment | 0–40 | Is the role primarily Java / Spring Boot / microservices? |
| Core Requirements Match | 0–35 | % of explicitly required skills present in the resume |
| Seniority Alignment | 0–15 | IC role vs. team lead / architect expectations |
| Bonus | 0–10 | AWS/GCP, Docker/K8s, CI/CD, observability tools |

**Decision thresholds:**

| Score | Flags | Decision |
|---|---|---|
| ≥ 75 | None | `strong_match` |
| ≥ 75 | Any | `maybe` |
| 60–74 | Any | `maybe` |
| 40–59 | Any | `weak` |
| < 40 | Any | `no` |

**Hard flags** (evaluated before scoring):
- `clearance_or_citizenship_required` → caps fitScore at 40
- `senior_title` → title contains Staff / Principal / Lead / Director / VP / Architect / Head
- `6plus_years` → JD explicitly states minimum ≥ 6 years

### Google Sheets structure

| Sheet | Contents |
|---|---|
| `JobTracker` | All passing jobs: Job_ID, Company, Position, URL, Location, Posted_At, Status |
| `StrongMatch` | Jobs scored ≥ 75, no flags — FitScore, Strengths, Missings, ScoreJustification, CoverLetter |
| `MayBe` | Jobs scored 60–74, or ≥ 75 with flags |
| `Weak` | Jobs scored 40–59 |
| `No` | Jobs scored < 40 |

---

## Part 3 — FastAPI Resume Generator (backend/server.py)

Triggered from the dashboard when you click **Generate Resume** on a job card.

**Endpoint:** `POST /generate-resume`

```json
{
  "job_id": "abc123",
  "company": "Google",
  "position": "Software Engineer",
  "job_desc": "We are looking for..."
}
```

### Pipeline

```
Job Description
    │
    ▼
jd_analysis.py          GPT extracts: required skills, seniority level,
    │                   key themes, tech stack, preferred tools
    ▼
optimizer.py            GPT rewrites resume sections to mirror JD keywords:
    │                   - Summary rewritten to match role's language
    │                   - Bullet points strengthened with matching terms
    │                   - Skills section prioritized by JD requirements
    │                   ATS rules enforced: no buzzwords, full degree names,
    │                   keyword placement in summary + most recent role
    ▼
latex_pdf_generator.py  Builds .tex source and compiles with pdflatex:
    │                   - lmodern for fi/fl ligature rendering
    │                   - \hyphenpenalty=10000 prevents ATS hyphenation artifacts
    │                   - Education section: institution + location on one line,
    │                     degree + GPA + dates aligned with \hfill
    ▼
drive.py                Uploads compiled PDF to Google Drive (OUTPUT_FOLDER_ID)
    │
    ▼
sheets.py               Writes Drive URL back to ATS_Resume column in Google Sheets
    │
    ▼
Response: { resume_url, file_name }
```

The PDF filename is auto-generated as `Company_Position.pdf` — long names are cleaned and truncated (e.g. `Google_Software_Engineer.pdf`).

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+ (for n8n)
- BasicTeX (for PDF generation)
- A self-hosted [n8n](https://n8n.io) instance
- Google Cloud project with Drive, Sheets, and Gmail APIs enabled
- OpenAI API key
- RapidAPI key with JSearch access

### 1. Clone

```bash
git clone https://github.com/Prabhuteja799/jobflow.git
cd jobflow
```

### 2. Backend setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Install LaTeX:
```bash
brew install --cask basictex
sudo tlmgr update --self && sudo tlmgr install lmodern
```

### 3. Environment variables

```bash
cp backend/.env.example backend/.env
```

| Variable | Source |
|---|---|
| `OPENAI_API_KEY` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `GITHUB_TOKEN` | [github.com/settings/tokens](https://github.com/settings/tokens) |
| `GIST_ID` | ID from your GitHub Gist URL |
| `RESUME_FILE_ID` | Google Drive file ID of your base resume PDF |
| `OUTPUT_FOLDER_ID` | Google Drive folder ID for generated resumes |
| `SPREADSHEET_ID` | Google Sheets ID from the URL |
| `SHEET_NAME` | Sheet tab name (default: `Meta2`) |
| `GMAIL_SENDER` | Your Gmail address |
| `GMAIL_RECIPIENT` | Where to send notifications |
| `GMAIL_APP_PASSWORD` | [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) |

### 4. Google credentials

Place these in `backend/` (never committed):
- `service_account.json` — Google Cloud service account
- `oauth_credentials.json` — OAuth2 Desktop App credentials

### 5. Run the backend server

```bash
cd backend
PATH="$PATH:/Library/TeX/texbin" python server.py
# Running on http://localhost:8000
```

### 6. Import n8n workflow

1. Open your n8n instance → **Workflows → Import**
2. Upload `backend/n8n-workflow.json`
3. Re-link credentials: Google Sheets, Google Drive, Gmail, OpenAI
4. In the **JSearch HTTP node**, replace `x-rapidapi-key` with your own key from [RapidAPI](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch)
5. Activate the workflow

### 7. Seed the dashboard

After jobs are scored and written to Sheets, run once to push data to the GitHub Gist that powers the dashboard:

```bash
cd backend
python seed_gist.py
```

The dashboard at `index.html` (or GitHub Pages) reads from this Gist automatically.

---

## Tech stack

| Layer | Tech |
|---|---|
| Dashboard | Vanilla HTML/CSS/JS, GitHub Pages |
| Job scraping | JSearch API (RapidAPI) |
| Workflow automation | n8n (self-hosted) |
| AI scoring | OpenAI GPT-5 |
| Resume parsing | OpenAI GPT-4o-mini |
| Resume optimization | OpenAI GPT-4o-mini |
| PDF generation | LaTeX (`pdflatex`, `lmodern`) |
| Storage | Google Drive + Google Sheets |
| Notifications | Gmail |
| API server | FastAPI + Uvicorn |
