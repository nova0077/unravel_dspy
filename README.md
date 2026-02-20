# Unravel.tech Job Application Agent

This project is an automated AI agent designed to programmatically apply for a Software Engineering role at Unravel.tech. It uses DSPy to dynamically generate a cover letter grounded in a provided resume and sends the application via email to the scouted founder.

## High-Level Overview

1. **Parse Resume**: Reads text from your provided PDF resume.
2. **Scout Founder**: Uses DuckDuckGo search and a deterministic fast-path to find the founder of Unravel.tech whose name contains "pr".
3. **Compose Email**: Uses DSPy and an LLM to generate a personalized cover letter matching specific constraints.
4. **Send Application**: Sends the generated email with the resume attached via Gmail SMTP.

## Prerequisites

- Python 3.11+
- A Google/Gmail App Password to send emails programmatically.
- An LLM API key (e.g., Gemini). The agent falls back to a local `ollama` model (`gemma3`) if no API keys are provided.

## Setup Instructions

1. **Clone the repository** and navigate into it.
2. **Create and activate a virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
3. **Install dependencies**:
   ```bash
   pip install -e .
   ```
4. **Configure environment variables**:
   Create a `.env` file in the root directory and add the following:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   SENDER_EMAIL=your_gmail_address@gmail.com
   SENDER_APP_PASSWORD=your_gmail_app_password
   RESUME_PATH=Praveen's_resume.pdf
   YOUR_NAME="Praveen"
   ```

## Running the Agent

You can run the agent in different modes using the `agent.py` script.

### 1. Dry Run (Preview Mode)
To see the entire process and print the generated email *without* actually sending it:
```bash
python agent.py --dry-run
```

### 2. Mock Recipient (End-to-End Test)
To run the full pipeline and actually send the email, but route it to a test email address instead of the real founder's email:
```bash
python agent.py --mock-recipient your_test_email@gmail.com
```

### 3. Full Production Run
To send the application to the actual Unravel.tech founder scouted by the agent:
```bash
python agent.py
```
*(Note: By default, the agent will pause and prompt you with a `(y/n)` confirmation to review the generated email before shipping it).*

### Flags Reference

- `--dry-run`: Runs the agent but explicitly blocks the final SMTP send command.
- `--mock-recipient <EMAIL>`: Overrides the scouted founder's email and sends the application to the provided test address.
- `--auto-confirm`: Skips the interactive `y/n` confirmation prompt before sending the email. Useful for automated CI testing or if you fully trust the agent's generated result.
# unravel_dspy
