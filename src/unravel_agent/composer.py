"""
composer.py — Generates a personalized cover letter using DSPy,
grounded in the candidate's resume content.
"""

from __future__ import annotations

from dataclasses import dataclass

import dspy


# ---------------------------------------------------------------------------
# DSPy Signatures
# ---------------------------------------------------------------------------

class WriteCoverLetter(dspy.Signature):
    """
    Write a compelling, concise cover letter email body for a backend engineering role at Unravel.

    The cover letter must:
    - Start with a conversational greeting (e.g., "Hi [Founder Name], Hope you're doing well.")
    - Synthesize an overview from the candidate's resume that frames them as a Backend Engineer with ~2 years of experience building scalable, low-latency systems.
    - Highlight high-level themes from the resume (like improving system reliability, handling real traffic at scale, and driving performance optimizations end-to-end) rather than listing specific bullet points or project details.
    - Convey a tone of being a passionate developer and a fast learner who enjoys taking on challenging problems and owning them through to production.
    - Express excitement about adding value to the backend team at Unravel.tech and mention that the resume is attached for review.
    - Keep the tone professional, concise, and genuine. DO NOT include a subject line or email headers.
    """
    founder_name: str = dspy.InputField(desc="First name of the founder to address")
    company_description: str = dspy.InputField(desc="Brief description of Unravel.tech and what they build")
    resume_text: str = dspy.InputField(desc="Full text of the candidate's resume")
    candidate_name: str = dspy.InputField(desc="The candidate's first name for sign-off")
    agent_name: str = dspy.InputField(desc="Name of the AI agent used (e.g. Gemini)")
    cover_letter: str = dspy.OutputField(desc="The complete cover letter body text, ready to send as email")


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

COMPANY_DESCRIPTION = """
Unravel.tech is a company building production-grade agentic AI systems. They believe
the old way of building software is dying and are at the forefront of this change.
They care deeply about: rapid experimentation, technical depth, honesty about what
works, and adaptive planning. They heavily use DSPy for structured AI systems,
and are looking for hands-on engineers who are great communicators and take their
craft seriously.
"""


@dataclass
class ComposedEmail:
    subject: str
    body: str
    to: str
    rhyming_word: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RHYMING_WORDS = ["reply", "comply", "amplify", "satisfy", "qualify", "apply", "simplify"]
# "Apply" is required. We pick a third word that rhymes with DSPy / Apply.
# "simplify" fits the custom logic Quote the candidate selected.
THIRD_RHYMING_WORD = "simplify"


def build_subject() -> str:
    """Subject must contain: Apply, DSPy, and a rhyming third word."""
    return f"Apply with DSPy — I {THIRD_RHYMING_WORD.title()}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compose_email(
    founder_name: str,
    founder_email: str,
    resume_text: str,
    candidate_name: str = "Praveen",
    agent_name: str = "Gemini AI 3.5 pro, ollema gemma3, Claude Sonnet 4.6",
) -> ComposedEmail:
    """
    Generate the full application email using DSPy.

    Args:
        founder_name:   First name of the target founder.
        founder_email:  Email address to send to.
        resume_text:    Parsed text from the candidate's resume PDF.
        candidate_name: Candidate's first name (for sign-off).
        agent_name:     AI agent name for co-signature.

    Returns:
        ComposedEmail with subject, body, and recipient.
    """
    print(f"[composer] Generating cover letter for {founder_name} using resume context...")

    writer = dspy.ChainOfThought(WriteCoverLetter)
    result = writer(
        founder_name=founder_name,
        company_description=COMPANY_DESCRIPTION.strip(),
        resume_text=resume_text,
        candidate_name=candidate_name,
        agent_name=agent_name,
    )

    body = result.cover_letter.strip()

    # Deterministically add the rhyming logic rather than relying on the LLM
    quote_block = (
        "\n\nI choose the 3rd rhyming word as Simplify because, it fits well with the quote\n"
        "Apply the pattern,\n"
        "DSPy the chain,\n"
        "Simplify the logic,\n\n"
        "Thanks for your time."
    )
    if "Simplify because" not in body:
        body += quote_block

    # Ensure the agent co-signature is present
    signature_block = f"\n\nThanks,\n{candidate_name} (with assistance from {agent_name})"
    if "with assistance from" not in body.lower():
        body += signature_block

    subject = build_subject()

    print(f"[composer] Subject: {subject}")
    print(f"[composer] Cover letter generated ({len(body)} chars)")

    return ComposedEmail(
        subject=subject,
        body=body,
        to=founder_email,
        rhyming_word=THIRD_RHYMING_WORD,
    )
