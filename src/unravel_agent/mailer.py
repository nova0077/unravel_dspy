"""
mailer.py — Sends the composed application email via Gmail SMTP
with the resume attached as a PDF.
"""

from __future__ import annotations

import os
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


def send_email(
    to: str,
    subject: str,
    body: str,
    resume_path: str | Path,
    sender_email: str,
    sender_app_password: str,
    dry_run: bool = False,
    require_confirmation: bool = True,
) -> bool:
    """
    Send the cover letter email with resume PDF attached.

    Args:
        to:                  Recipient email address.
        subject:             Email subject line.
        body:                Plain-text email body (cover letter).
        resume_path:         Path to the resume PDF to attach.
        sender_email:        Your Gmail address.
        sender_app_password: Gmail App Password (not regular password).
        dry_run:             If True, prints everything but does NOT send.
        require_confirmation: If True, blocks on a y/n prompt before sending (when not dry_run).
    """
    resume_path = Path(resume_path)

    # --- Build message ---
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = to
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain", "utf-8"))

    # --- Attach resume ---
    if not resume_path.exists():
        raise FileNotFoundError(f"Resume not found: {resume_path}")

    with open(resume_path, "rb") as f:
        attachment = MIMEBase("application", "octet-stream")
        attachment.set_payload(f.read())
    encoders.encode_base64(attachment)
    attachment.add_header(
        "Content-Disposition",
        f'attachment; filename="{resume_path.name}"',
    )
    msg.attach(attachment)

    # --- Dry run or Confirmation Preview ---
    print("\n" + "=" * 60)
    print(f"[mailer] {'DRY RUN — email NOT sent' if dry_run else 'PREVIEW — Email Ready to Send'}")
    print("=" * 60)
    print(f"To:      {to}")
    print(f"From:    {sender_email}")
    print(f"Subject: {subject}")
    print(f"Resume:  {resume_path.name}")
    print("-" * 60)
    print(body)
    print("=" * 60 + "\n")

    if dry_run:
        return False

    # --- Interactive Confirmation ---
    if require_confirmation:
        while True:
            try:
                choice = input(f"Send this email to {to}? (y/n): ").strip().lower()
            except EOFError:
                # If run in an environment without standard input attached
                choice = 'n'
                
            if choice == 'y':
                break
            elif choice == 'n':
                print("[mailer] ❌ Sending aborted by user.")
                return False
            else:
                print("Please enter 'y' to send or 'n' to abort.")

    # --- Send via Gmail SMTP ---
    print(f"\n[mailer] Sending email to {to}...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, sender_app_password)
        server.sendmail(sender_email, to, msg.as_string())

    print(f"[mailer] ✅ Email successfully sent to {to}")
    return True
