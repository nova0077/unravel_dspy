"""
agent.py — Main orchestrator for the Unravel.tech job application agent.

Usage:
    python agent.py            # sends the email
    python agent.py --dry-run  # prints email without sending
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import dspy
from dotenv import load_dotenv

# Load .env before importing local modules
load_dotenv()

from unravel_agent.composer import compose_email
from unravel_agent.mailer import send_email
from unravel_agent.resume_parser import extract_resume_text
from unravel_agent.scout import find_founder


# ---------------------------------------------------------------------------
# LLM setup
# ---------------------------------------------------------------------------

def configure_dspy() -> None:
    """Configure DSPy. Tries Gemini models then falls back to local Ollama gemma3."""
    api_key = os.environ.get("GEMINI_API_KEY", "")

    MODELS = [
        ("ollama_chat/gemma3",                  {}),  # local fallback, no quota
        ("gemini/gemini-2.0-flash",             {"api_key": api_key}),
        ("gemini/gemini-1.5-pro-latest",        {"api_key": api_key}),
        ("gemini/gemini-1.5-flash",             {"api_key": api_key}),
    ]

    for model, kwargs in MODELS:
        if not api_key and "gemini" in model:
            continue
        try:
            dspy.configure(lm=dspy.LM(model=model, **kwargs))
            print(f"[agent] DSPy configured with {model}")
            return
        except Exception as e:
            err = str(e)
            if any(x in err for x in ["429", "quota", "rate limit", "404", "not found"]):
                print(f"[agent] ⚠️  {model} unavailable, trying next...")
                continue
            raise

    sys.exit("❌ All models failed. Check Gemini API key or ensure Ollama is running.")



# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _require_env(var: str) -> str:
    val = os.environ.get(var, "").strip()
    if not val:
        sys.exit(f"❌ {var} is not set in your .env file.")
    return val


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(
    dry_run: bool = False,
    mock_recipient: str | None = None,
    auto_confirm: bool = False,
) -> None:
    print("\n🚀 Unravel.tech Job Application Agent\n" + "=" * 42)

    # --- Config ---
    configure_dspy()

    resume_path = Path(_require_env("RESUME_PATH"))
    sender_email = _require_env("SENDER_EMAIL")
    sender_app_password = _require_env("SENDER_APP_PASSWORD")
    candidate_name = os.environ.get("YOUR_NAME", "Praveen")

    # --- Step 1: Parse resume ---
    print(f"\n📄 Step 1: Parsing resume from {resume_path}...")
    resume_text = extract_resume_text(resume_path)

    # --- Step 2: Scout LinkedIn to find the right founder ---
    print("\n🔍 Step 2: Scouting LinkedIn for Unravel.tech founders...")
    founder = find_founder()
    print(f"   → Found: {founder.first_name} ({founder.email})")

    # --- Step 3: Compose cover letter grounded in resume ---
    print("\n✍️  Step 3: Composing cover letter with DSPy...")
    composed = compose_email(
        founder_name=founder.first_name,
        founder_email=founder.email,
        resume_text=resume_text,
        candidate_name=candidate_name,
        agent_name="Gemini",
    )

    # --- Step 4: Send (or dry-run) ---
    recipient = mock_recipient if mock_recipient else composed.to
    if mock_recipient:
        print(f"\n⚠️  [TEST MODE] Recipient overridden: {composed.to} → {mock_recipient}")
    print(f"\n📬 Step 4: {'[DRY RUN] Printing' if dry_run else 'Sending'} email...")
    is_sent = send_email(
        to=recipient,
        subject=composed.subject,
        body=composed.body,
        resume_path=resume_path,
        sender_email=sender_email,
        sender_app_password=sender_app_password,
        dry_run=dry_run,
        require_confirmation=not auto_confirm,
    )

    if is_sent:
        print(f"\n✅ Done! Application sent to {recipient}")
        print(f"   Subject: {composed.subject}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unravel.tech Job Application Agent")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the email instead of sending it",
    )
    parser.add_argument(
        "--mock-recipient",
        metavar="EMAIL",
        default=None,
        help="Override the recipient email (for testing, e.g. your own address)",
    )
    parser.add_argument(
        "--auto-confirm",
        action="store_true",
        help="Skip the y/n confirmation prompt before sending.",
    )
    args = parser.parse_args()
    main(
        dry_run=args.dry_run,
        mock_recipient=args.mock_recipient,
        auto_confirm=args.auto_confirm,
    )
