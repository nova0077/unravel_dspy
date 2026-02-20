"""
resume_parser.py — Extracts text content from a resume PDF for use
as context in cover letter generation.
"""

from __future__ import annotations

import re
from pathlib import Path

import pdfplumber


def extract_resume_text(resume_path: str | Path) -> str:
    """
    Parse a PDF resume and return its full text content.

    Args:
        resume_path: Path to the resume PDF file.

    Returns:
        Cleaned text extracted from all pages.

    Raises:
        FileNotFoundError: If the PDF does not exist.
        ValueError: If the PDF appears to be empty or unreadable.
    """
    path = Path(resume_path)
    if not path.exists():
        raise FileNotFoundError(f"Resume not found at: {path}")

    pages_text: list[str] = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                pages_text.append(text.strip())
            else:
                print(f"[resume_parser] Warning: page {i+1} returned no text (may be image-based)")

    if not pages_text:
        raise ValueError(
            f"Could not extract any text from {path}. "
            "Make sure the PDF is text-based and not a scanned image."
        )

    full_text = "\n\n".join(pages_text)

    # Light cleanup: collapse excessive whitespace
    full_text = re.sub(r"\n{3,}", "\n\n", full_text)
    full_text = re.sub(r" {2,}", " ", full_text)

    print(f"[resume_parser] Extracted {len(full_text)} chars from {len(pages_text)} page(s)")
    return full_text
