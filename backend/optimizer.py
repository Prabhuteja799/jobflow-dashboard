"""
optimizer.py — Call 2: surgical resume rewrite using o4-mini (temperature=0).
Normalizes all possible summary structures.
Always injects FIXED_METRICS — AI always returns metrics: [].
"""

import json
import logging
import re
from pathlib import Path

from openai import OpenAI

from config import OPENAI_API_KEY, OPTIMIZER_MODEL, FIXED_METRICS

log    = logging.getLogger(__name__)
client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = Path("prompts/optimizer_system.txt").read_text(encoding="utf-8")
USER_PROMPT   = Path("prompts/optimizer_user.txt").read_text(encoding="utf-8")


def optimize_resume(resume_text: str, jd_analysis: dict,
                    company: str, position: str) -> dict:
    """
    Surgically rewrite only what's needed to maximize ATS score.
    Returns normalized resume dict ready for the PDF generator.
    """
    user = USER_PROMPT.format(
        resume_text=resume_text,
        jd_analysis=json.dumps(jd_analysis, indent=2),
        company=company,
        position=position,
    )

    print("MODEL:", OPTIMIZER_MODEL)
    
    response = client.chat.completions.create(
        model=OPTIMIZER_MODEL,
        temperature=0.1,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user},
        ],
    )

    raw = response.choices[0].message.content or ""
    raw = re.sub(r"(?i)^```json\s*", "", raw)
    raw = re.sub(r"```\s*$",         "", raw).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        log.error("Optimizer JSON parse failed: %s\nRaw: %s", e, raw[:300])
        raise

    # ── Normalize all possible summary structures ────────────────
    # Case 1: summary: { paragraph: "...", metrics: [] }  ← expected structure
    # Case 2: summary: "plain string"                      ← flat fallback
    # Case 3: "Professional Summary": { ... }              ← old key fallback

    paragraph = ""
    ai_metrics = []

    if "summary" in data:
        s = data["summary"]
        if isinstance(s, dict):
            paragraph  = s.get("paragraph", "")
            ai_metrics = s.get("metrics",   [])
        elif isinstance(s, str):
            paragraph  = s
            ai_metrics = []

    elif "Professional Summary" in data:
        ps = data.pop("Professional Summary")
        if isinstance(ps, dict):
            paragraph  = ps.get("paragraph", "")
            ai_metrics = ps.get("metrics",   [])
        else:
            paragraph  = str(ps)
            ai_metrics = []

    elif "summary_paragraph" in data:
        paragraph  = data.pop("summary_paragraph", "")
        ai_metrics = data.pop("summary_metrics",   [])

    # ── Always inject fixed metrics (AI returns [] per instructions) ──
    extra_metrics = [
        m for m in (ai_metrics or [])
        if isinstance(m, str) and m.strip()
        and not any(
            f.lower()[:20] == m.lower()[:20]
            for f in FIXED_METRICS
        )
    ]
    all_metrics = FIXED_METRICS + extra_metrics

    # ── Write back nested structure for latex_pdf_generator ──────
    data["summary"] = {
        "paragraph": paragraph,
        "metrics":   all_metrics,
    }

    # Remove flat keys if AI left them behind
    data.pop("summary_paragraph", None)
    data.pop("summary_metrics",   None)

    log.info("    Resume optimized — %d experience entries, %d metrics",
             len(data.get("experience", [])),
             len(data["summary"]["metrics"]))

    return data


# """
# optimizer.py — Call 2: surgical resume rewrite using o4-mini (temperature=0).
# Normalizes all possible summary structures.
# Always injects FIXED_METRICS — AI always returns metrics: [].
# """

# import json
# import logging
# import re
# from pathlib import Path

# from openai import OpenAI

# from config import OPENAI_API_KEY, OPTIMIZER_MODEL, FIXED_METRICS

# log    = logging.getLogger(__name__)
# client = OpenAI(api_key=OPENAI_API_KEY)

# SYSTEM_PROMPT = Path("prompts/optimizer_system.txt").read_text(encoding="utf-8")
# USER_PROMPT   = Path("prompts/optimizer_user.txt").read_text(encoding="utf-8")


# def optimize_resume(resume_text: str, jd_analysis: dict,
#                     company: str, position: str) -> dict:
#     """
#     Surgically rewrite only what's needed to maximize ATS score.
#     Returns normalized resume dict ready for the PDF generator.
#     """
#     user = USER_PROMPT.format(
#         resume_text=resume_text,
#         jd_analysis=json.dumps(jd_analysis, indent=2),
#         company=company,
#         position=position,
#     )

#     print("MODEL:", OPTIMIZER_MODEL)
    
#     response = client.chat.completions.create(
#         model=OPTIMIZER_MODEL,
#         temperature=0.1,
#         messages=[
#             {"role": "system", "content": SYSTEM_PROMPT},
#             {"role": "user",   "content": user},
#         ],
#     )

#     raw = response.choices[0].message.content or ""
#     raw = re.sub(r"(?i)^```json\s*", "", raw)
#     raw = re.sub(r"```\s*$",         "", raw).strip()

#     try:
#         data = json.loads(raw)
#     except json.JSONDecodeError as e:
#         log.error("Optimizer JSON parse failed: %s\nRaw: %s", e, raw[:300])
#         raise

#     # ── Normalize all possible summary structures ────────────────
#     # Case 1: summary: { paragraph: "...", metrics: [] }  ← new structure
#     # Case 2: summary: "plain string"                      ← flat fallback
#     # Case 3: "Professional Summary": { ... }              ← old key fallback
#     # Case 4: summary_paragraph already set correctly      ← already normalized

#     if "summary" in data:
#         s = data.pop("summary")
#         if isinstance(s, dict):
#             data["summary_paragraph"] = s.get("paragraph", "")
#             data["summary_metrics"]   = s.get("metrics",   [])
#         elif isinstance(s, str):
#             data["summary_paragraph"] = s
#             data["summary_metrics"]   = []
#         else:
#             data["summary_paragraph"] = ""
#             data["summary_metrics"]   = []

#     elif "Professional Summary" in data:
#         ps = data.pop("Professional Summary")
#         if isinstance(ps, dict):
#             data["summary_paragraph"] = ps.get("paragraph", "")
#             data["summary_metrics"]   = ps.get("metrics",   [])
#         else:
#             data["summary_paragraph"] = str(ps)
#             data["summary_metrics"]   = []

#     # Ensure keys exist even if AI omitted them
#     data.setdefault("summary_paragraph", "")
#     data.setdefault("summary_metrics",   [])

#     # ── Always inject fixed metrics (AI returns [] per instructions) ──
#     # Any valid AI-generated metric that doesn't duplicate a fixed one
#     # gets appended after the 5 fixed ones.
#     ai_metrics = [
#         m for m in data.get("summary_metrics", [])
#         if isinstance(m, str) and m.strip()
#         and not any(
#             f.lower()[:20] == m.lower()[:20]
#             for f in FIXED_METRICS
#         )
#     ]
#     data["summary_metrics"] = FIXED_METRICS + ai_metrics

#     log.info("    Resume optimized — %d experience entries, %d metrics",
#              len(data.get("experience", [])),
#              len(data["summary_metrics"]))

#     return data