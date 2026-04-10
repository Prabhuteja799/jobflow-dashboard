"""
jd_analysis.py — Call 1: extract JD keywords using gpt-4o-mini.
Fast, cheap, deterministic (temperature=0).
"""

import json
import logging
import re
from pathlib import Path

from openai import OpenAI

from config import OPENAI_API_KEY, JD_MODEL

log    = logging.getLogger(__name__)
client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = Path("prompts/jd_analysis_system.txt").read_text(encoding="utf-8")
USER_PROMPT   = Path("prompts/jd_analysis_user.txt").read_text(encoding="utf-8")


def analyze_jd(job_desc: str, company: str, position: str) -> dict:
    """
    Extract ATS keywords, required/preferred skills, seniority, domain.
    Returns a dict matching the JD analysis JSON schema.
    """
    user = USER_PROMPT.format(
        job_desc=job_desc,
        company=company,
        position=position,
    )

    response = client.chat.completions.create(
        model=JD_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user},
        ],
    )

    raw = response.choices[0].message.content or ""
    raw = re.sub(r"(?i)^```json\s*", "", raw)
    raw = re.sub(r"```\s*$",         "", raw).strip()

    try:
        result = json.loads(raw)
        log.info("    JD analysis: %d required, %d preferred skills",
                 len(result.get("required_skills", [])),
                 len(result.get("preferred_skills", [])))
        return result
    except json.JSONDecodeError as e:
        log.error("JD analysis JSON parse failed: %s\nRaw: %s", e, raw[:300])
        raise







