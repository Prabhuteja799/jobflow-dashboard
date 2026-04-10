"""
pdf_client.py — generates PDF via latex_pdf_generator (pdflatex).
Drop-in replacement for the old ReportLab-based pdf_generator.
"""

import logging
from latex_pdf_generator import build_resume

log = logging.getLogger(__name__)


def generate_pdf(resume_data: dict, file_name: str) -> bytes:
    """
    Generate PDF from resume_data dict.
    Returns raw PDF bytes.
    """
    try:
        pdf_bytes = build_resume(resume_data)
        log.info("    PDF generated — %d bytes", len(pdf_bytes))
        return pdf_bytes
    except Exception as e:
        log.error("PDF generation failed: %s", e)
        raise



# """
# pdf_client.py — generates PDF by calling pdf_generator directly.
# No Docker container, no HTTP request needed.
# """

# import logging
# from pdf_generator import build_resume

# log = logging.getLogger(__name__)


# def generate_pdf(resume_data: dict, file_name: str) -> bytes:
#     """
#     Generate PDF from resume_data dict.
#     Returns raw PDF bytes.
#     """
#     try:
#         pdf_bytes = build_resume(resume_data)
#         log.info("    PDF generated — %d bytes", len(pdf_bytes))
#         return pdf_bytes
#     except Exception as e:
#         log.error("PDF generation failed: %s", e)
#         raise