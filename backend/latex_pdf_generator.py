"""
latex_pdf_generator.py — generates a resume PDF via LaTeX.
Takes the resume JSON dict (from the ATS optimizer prompt output)
and produces a PDF matching the exact LaTeX template structure.

Usage:
    from latex_pdf_generator import build_resume
    pdf_bytes = build_resume(data)   # returns raw PDF bytes

Requires: pdflatex (texlive) on PATH
"""

import io
import os
import re
import subprocess
import tempfile


# ── LaTeX escaping ────────────────────────────────────────────────
_LATEX_SPECIAL = {
    "&":  r"\&",
    "%":  r"\%",
    "$":  r"\$",
    "#":  r"\#",
    "_":  r"\_",
    "{":  r"\{",
    "}":  r"\}",
    "~":  r"\textasciitilde{}",
    "^":  r"\textasciicircum{}",
    "\\": r"\textbackslash{}",
    "\u2013": "--",    # en dash –
    "\u2014": "---",   # em dash —
    "\u2022": r"\textbullet{}",  # bullet •
}

def _esc(text: str) -> str:
    """Escape special LaTeX characters in plain text."""
    if not text:
        return ""
    result = []
    for ch in str(text):
        result.append(_LATEX_SPECIAL.get(ch, ch))
    return "".join(result)


def _esc_url(url: str) -> str:
    r"""URLs go inside \href — only escape % signs."""
    return str(url or "").replace("%", r"\%")


# ── Template builder ──────────────────────────────────────────────
def _build_latex(data: dict) -> str:
    lines = []

    def w(s=""):
        lines.append(s)

    # ── Preamble ──────────────────────────────────────────────────
    w(r"\documentclass[11pt]{article}")
    w()
    w(r"\usepackage[margin=0.65in]{geometry}")
    w(r"\usepackage[T1]{fontenc}")
    w(r"\usepackage{lmodern}")
    w(r"\usepackage[utf8]{inputenc}")
    w()
    w(r"\usepackage{xcolor}")
    w(r"\usepackage{hyperref}")
    w()
    w(r"\hypersetup{")
    w(r"    colorlinks=true,")
    w(r"    urlcolor=blue")
    w(r"}")
    w()
    w(r"\usepackage{enumitem}")
    w(r"\usepackage{tabularx}")
    w(r"\usepackage{titlesec}")
    w(r"\usepackage{ragged2e}")
    w()
    w(r"\newcommand{\job}[2]{")
    w(r"\noindent")
    w(r"\makebox[\textwidth]{")
    w(r"\textbf{#1} \hfill \textbf{#2}")
    w(r"}")
    w(r"\vspace{-4pt}")
    w(r"}")
    w()
    w(r"\pagenumbering{gobble}")
    w(r"\setlength{\parindent}{0pt}")
    w(r"\setlength{\parskip}{0pt}")
    w()
    w(r"\titleformat{\section}{\bfseries\uppercase}{ }{0pt}{}[\vspace{2pt}\titlerule]")
    w(r"\titlespacing*{\section}{0pt}{10pt}{6pt}")
    w()
    w(r"\setlist[itemize]{leftmargin=14pt, itemsep=3pt, topsep=2pt, parsep=0pt, partopsep=0pt}")
    w()
    w(r"% Disable automatic hyphenation — prevents soft-hyphen artifacts in ATS text extraction")
    w(r"\hyphenpenalty=10000")
    w(r"\exhyphenpenalty=10000")
    w()
    w(r"\begin{document}")
    w()

    # ── Header ────────────────────────────────────────────────────
    name = _esc(data.get("name", ""))
    c = data.get("contact", {})
    email    = c.get("email", "")
    phone    = _esc(c.get("phone", ""))
    location = _esc(c.get("location", ""))
    linkedin = c.get("linkedin", "")
    github   = c.get("github", "")

    # Display versions (strip https:// and trailing slash for cleanliness)
    def _display_url(url):
        return re.sub(r"^https?://", "", str(url or "")).rstrip("/")

    w(r"\begin{center}")
    w(r"{\LARGE \textbf{" + name + r"}}\\[4pt]")

    # Line 1: email | phone | location
    contact_line1_parts = []
    if email:
        contact_line1_parts.append(
            r"\href{mailto:" + _esc_url(email) + r"}{" + _esc(email) + r"}"
        )
    if phone:
        contact_line1_parts.append(phone)
    if location:
        contact_line1_parts.append(location)
    w(r" \;|\; ".join(contact_line1_parts) + r"\\[2pt]")

    # Line 2: LinkedIn | GitHub
    contact_line2_parts = []
    if linkedin:
        contact_line2_parts.append(
            r"\href{" + _esc_url(linkedin) + r"}{" + _esc(_display_url(linkedin)) + r"}"
        )
    if github:
        contact_line2_parts.append(
            r"\href{" + _esc_url(github) + r"}{" + _esc(_display_url(github)) + r"}"
        )
    if contact_line2_parts:
        w(r" \;|\; ".join(contact_line2_parts))
    w(r"\end{center}")
    w()

    # ── Professional Summary ──────────────────────────────────────
    w(r"\section{Professional Summary}")
    w(r"\justifying")

    summary = data.get("summary", {})
    if isinstance(summary, dict):
        paragraph = summary.get("paragraph", "")
        metrics   = summary.get("metrics", [])
    else:
        paragraph = str(summary)
        metrics   = []

    # Also check top-level fallbacks
    if not paragraph:
        paragraph = data.get("summary_paragraph", "")
    if not metrics:
        metrics = data.get("summary_metrics", [])

    if paragraph:
        w(_esc(paragraph.strip()))
    w()

    if metrics:
        w(r"\begin{itemize}")
        for m in metrics:
            if m and str(m).strip():
                w(r"\item " + _esc(str(m).strip()))
        w(r"\end{itemize}")
    w()

    # ── Technical Skills ──────────────────────────────────────────
    skills = data.get("skills", {})
    if skills:
        w(r"\section{Technical Skills}")
        w()
        w(r"\begin{itemize}")
        for cat, val in skills.items():
            cat_esc = _esc(str(cat))
            val_esc = _esc(str(val))
            w(r"\item \textbf{" + cat_esc + r":} " + val_esc)
        w(r"\end{itemize}")
        w()

    # ── Professional Experience ───────────────────────────────────
    experience = data.get("experience", [])
    if experience:
        w(r"\section{Professional Experience}")
        w()
        for i, job in enumerate(experience):
            company = _esc(str(job.get("company", "")))
            role    = _esc(str(job.get("role", "")))
            dates   = _esc(str(job.get("dates", "")).replace("–", "--").replace("—", "--"))

            # \job{Company | Role}{Dates}
            w(r"\job{" + company + r" | " + role + r"}{" + dates + r"}")
            w()
            w(r"\begin{itemize}")
            for bullet in job.get("bullets", []):
                if bullet and str(bullet).strip():
                    w(r"\item " + _esc(str(bullet).strip()))
            w(r"\end{itemize}")

            if i < len(experience) - 1:
                w()
                w(r"\vspace{4pt}")
            w()

    # ── Education ─────────────────────────────────────────────────
    education = data.get("education", [])
    if education:
        w(r"\section{Education}")
        w()
        for i, edu in enumerate(education):
            institution = _esc(str(edu.get("institution", "")))
            loc         = _esc(str(edu.get("location", "")))
            degree      = _esc(str(edu.get("degree", "")))
            gpa         = _esc(str(edu.get("gpa", "")))
            dates       = _esc(str(edu.get("dates", "")).replace("–", "--").replace("—", "--"))

            inst_line = r"\noindent\textbf{" + institution
            if loc and loc not in institution:
                inst_line += ", " + loc
            inst_line += r"}\\"
            w(inst_line)

            # Degree \hfill GPA: X.X \hfill Dates
            degree_line = r"\noindent " + degree
            if gpa:
                degree_line += r" \hfill GPA: " + gpa
            if dates:
                degree_line += r" \hfill " + dates
            degree_line += r"\\"
            w(degree_line)

            if i < len(education) - 1:
                w(r"\vspace{4pt}")
            w()

    w(r"\end{document}")

    return "\n".join(lines)


# ── PDF compilation ───────────────────────────────────────────────
def build_resume(data: dict) -> bytes:
    """
    Build a PDF from the resume data dict using pdflatex.
    Returns raw PDF bytes.
    Raises RuntimeError if pdflatex fails.
    """
    latex_source = _build_latex(data)

    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, "resume.tex")
        pdf_path = os.path.join(tmpdir, "resume.pdf")

        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(latex_source)

        # Run pdflatex twice (for proper layout resolution)
        for _ in range(2):
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-output-directory", tmpdir, tex_path],
                capture_output=True,
                text=True,
            )

        if not os.path.exists(pdf_path):
            raise RuntimeError(
                f"pdflatex failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )

        with open(pdf_path, "rb") as f:
            return f.read()


def build_resume_latex(data: dict) -> str:
    """
    Return the raw LaTeX source string (useful for debugging or Overleaf upload).
    """
    return _build_latex(data)


# ── CLI test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import json, sys

    sample = {
        "name": "Prabhuteja Chintala",
        "contact": {
            "email": "prabhuteja.dev1@gmail.com",
            "linkedin": "https://www.linkedin.com/in/prabhu-teja-ch",
            "github": "https://github.com/prabhuteja799",
            "phone": "(561) 975-9501",
            "location": "Boca Raton, FL"
        },
        "summary_heading": "PROFESSIONAL SUMMARY",
        "summary": {
            "paragraph": (
                "Software Engineer with 5 years of experience designing scalable microservices "
                "and distributed systems for FinTech and enterprise platforms. Specialized in Java, "
                "Spring Boot, REST APIs, and event-driven architectures with strong experience in "
                "performance optimization, database design, and cloud infrastructure (AWS/Azure). "
                "Proven track record improving system reliability, reducing latency, and building "
                "production systems supporting 10,000+ users and high-volume transaction workloads."
            ),
            "metrics": [
                "Improved database performance by 18% by optimizing Spring MVC controllers and Spring Data JPA queries during peak transaction windows, resulting in faster purchase order processing.",
                "Achieved 99.99% system uptime by optimizing AWS ECS infrastructure and monitoring, reducing cloud operational costs by 20%.",
                "Reduced frontend load times by 40% by implementing React code splitting and lazy loading strategies, improving procurement portal responsiveness.",
                "Scaled analytics platform to 10,000+ monthly active users by developing Spring Boot REST services integrating PostgreSQL and MongoDB.",
                "Reduced release cycles by 25% by automating CI/CD pipelines using GitHub Actions and GitLab CI, improving deployment consistency.",
            ]
        },
        "skills": {
            "Programming": "Java (8-17), Python",
            "Backend Frameworks": "Spring Boot, Spring MVC, Spring Data JPA, Hibernate, Spring Security",
            "Architecture & System Design": "Microservices architecture, distributed systems, REST API design, GraphQL API design, caching strategies, asynchronous processing",
            "Cloud & DevOps": "AWS (ECS, Application Load Balancer, CloudWatch), Microsoft Azure, CI/CD (GitHub Actions, GitLab CI, Jenkins), Git, Tomcat",
            "Databases": "PostgreSQL, MySQL, Oracle, MongoDB",
            "Messaging & Streaming": "Apache Kafka",
            "Security": "Role-based access control (RBAC), OAuth 2.0, JWT authentication",
            "Observability & Performance": "ELK Stack, Redis caching, performance tuning, database optimization, latency reduction"
        },
        "experience": [
            {
                "company": "Principal Financial, USA",
                "role": "Software Engineer",
                "dates": "February 2025 – Present",
                "bullets": [
                    "Improved reliability of procurement and invoicing services by designing Spring Boot microservices aligned with strict financial audit requirements, resulting in more stable enterprise workflows.",
                    "Increased database query performance by 18% by optimizing Spring MVC controllers and Spring Data JPA queries under peak transaction loads, accelerating purchase order processing.",
                    "Improved audit event throughput by publishing compliance and transaction events to Kafka topics consumed by downstream reporting services, decoupling financial workflows and enabling Redis-cached aggregation for real-time budget dashboards.",
                    "Strengthened application security by implementing RBAC authorization with OAuth2 and JWT authentication flows, enabling SOX-compliant access controls.",
                    "Improved system observability by integrating centralized ELK logging infrastructure, enabling faster debugging and regulatory audit traceability.",
                    "Reduced procurement portal load time by 40% by optimizing React UI delivery using lazy loading and code splitting, improving user experience.",
                    "Reduced release cycles by 25% by implementing CI/CD pipelines using GitHub Actions and GitLab CI, improving deployment reliability.",
                    "Achieved 99.99% service uptime by optimizing AWS ECS infrastructure and monitoring configurations, reducing cloud operational costs by 20%.",
                ]
            },
            {
                "company": "NCR Corporation, India",
                "role": "Software Engineer",
                "dates": "April 2021 – August 2023",
                "bullets": [
                    "Improved product lifecycle management workflows by building Java-backed REST APIs using Spring Boot, enabling consistent tracking of product components and releases.",
                    "Reduced service latency by 25% by deploying microservices using Spring Data JPA and Hibernate across MySQL and Oracle environments, improving structured data retrieval by 30%.",
                    "Increased system responsiveness by implementing Kafka-based event-driven architecture with consumer groups and dead-letter queue handling to manage distributed service failures, ensuring reliable message delivery and Redis-backed state recovery across systems.",
                    "Increased API responsiveness for approval workflows by introducing Redis caching for frequently accessed product metadata and session data, reducing repeated database reads by 40% across Kafka-consumed event pipelines.",
                    "Improved frontend maintainability by developing reusable React hooks, reducing code duplication by 30% across enterprise modules.",
                    "Reduced manual workflow effort by implementing Python-based NLP automation using spaCy for text classification and entity extraction from unstructured product data, improving processing efficiency.",
                    "Improved deployment stability by collaborating with DevOps to implement Jenkins-based CI/CD pipelines, reducing production downtime.",
                ]
            },
            {
                "company": "Rlogical Techsoft, India",
                "role": "Software Engineer",
                "dates": "October 2020 – March 2021",
                "bullets": [
                    "Improved UI consistency across enterprise applications by developing Angular and TypeScript components, accelerating feature delivery across multiple client modules.",
                    "Reduced backend API response times by 25% by optimizing Spring MVC workflows for high-volume transactions, improving application scalability.",
                    "Reduced data over-fetching by implementing GraphQL APIs for client applications, cutting average query payload size by 40%.",
                    "Scaled analytics platform to 10,000+ users by developing Spring Boot REST services integrating PostgreSQL and MongoDB.",
                    "Reduced partner onboarding time by 20% by integrating REST APIs with Azure services and payment gateways, streamlining third-party integrations.",
                ]
            }
        ],
        "education": [
            {
                "institution": "Florida Atlantic University",
                "location": "Florida, USA",
                "degree": "Master of Science, Computer Science",
                "gpa": "3.8",
                "dates": "August 2023 – May 2025"
            },
            {
                "institution": "Lovely Professional University",
                "location": "India",
                "degree": "B.Tech, Computer Science and Engineering",
                "gpa": "7.8",
                "dates": "August 2017 – May 2021"
            }
        ]
    }

    # Print LaTeX source
    latex = build_resume_latex(sample)
    print(latex)

    # Build PDF
    try:
        pdf_bytes = build_resume(sample)
        out_path = "resume_test.pdf"
        with open(out_path, "wb") as f:
            f.write(pdf_bytes)
        print(f"\nPDF written to {out_path} ({len(pdf_bytes)} bytes)")
    except RuntimeError as e:
        print(f"\nPDF generation failed:\n{e}", file=sys.stderr)