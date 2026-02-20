# Technical Deep Dive: Unravel DSPy Agent

This document provides an in-depth explanation of the architecture, modules, and core logic behind the Unravel.tech job application agent. This is intended for revision and quick understanding of the codebase.

## 1. Project Structure

The project is structured as a standard Python package, allowing it to be installed via `pip install -e .`.

```text
├── agent.py               # Main entrypoint and orchestrator script.
├── pyproject.toml         # Packaging, dependencies, and metadata.
├── README.md              # Setup and execution instructions.
├── .env                   # Environment variables (API keys, credentials).
└── src/unravel_agent/     # Core package source code.
    ├── __init__.py
    ├── composer.py        # DSPy integration for generating the cover letter.
    ├── mailer.py          # SMTP logic for sending the email.
    ├── resume_parser.py   # PDF text extraction logic.
    └── scout.py           # Logic for finding the founder's metadata.
```

## 2. Core Modules

### `agent.py` (The Orchestrator)
This script chains together the entire workflow. 
1. **Configures the LLM backend**: It attempts to load `gemini/gemini-2.0-flash` or falls back to a local `ollama_chat/gemma3` model.
2. **Validates Environment Variables**: Ensures API keys, target email, resume path, and Google App Passwords are provided.
3. **Execution Steps**:
   - Parses the resume (`step 1`)
   - Scouts the correct founder (`step 2`)
   - Uses DSPy to generate the application email (`step 3`)
   - Sends the email using `mailer.py` (`step 4`)

### `src/unravel_agent/scout.py` (The Finder)
Responsible for identifying the Unravel.tech founder, *specifically* looking for the condition that their name contains `"pr"` (a constraint from the hiring riddle).
- It performs a DuckDuckGo web search via the `duckduckgo_search` library to find names associated with Unravel.tech in Pune.
- It leverages a deterministic sequence filtering to parse the search results for names containing `"pr"` (like Prajwalit).
- If it fails natively, it falls back to passing the search payload to DSPy's `IdentifyFounder` signature.

### `src/unravel_agent/resume_parser.py` (The Extractor)
A utility wrapper around `pdfplumber`. It opens the local PDF resume and extracts and sanitizes the available text layout to provide contextual grounding for the cover letter generation in `composer.py`.

### `src/unravel_agent/composer.py` (The Brain)
This module acts as the prompt engineering layer, utilizing **DSPy Chains of Thought**.
- It defines the `WriteCoverLetter` DSPy signature, explicitly defining input constraints (`founder_name`, `company_description`, `resume_text`) and the required output structures.
- Based on the user's constraints, it ensures the cover letter adheres to a specific format:
  1. Starts with "Hi [Founder]..." and Synthesizes an overview as a Backend Engineer with ~2 YOE.
  2. Embeds the exact required quote defining the "Apply, DSPy, Simplify" rhyming convention to solve the riddle.
  3. Returns a `ComposedEmail` dataclass with the subject, body, and recipient ready to ship.

### `src/unravel_agent/mailer.py` (The Courier)
Handles the standard library `smtplib` implementation.
- Uses `MIMEMultipart`, `MIMEText`, and `MIMEBase` to construct an email with attachments.
- Encodes the parsed resume as a PDF payload (`application/octet-stream`).
- Exposes a `dry_run` flag that safely prints the fully-constructed email headers and body without establishing an SMTP connection.

## 3. Notable Patterns

### DSPy Signatures vs Traditional Prompts
Instead of brittle f-string prompts, the project uses DSPy's declarative signatures (`dspy.Signature`). This allows the LLM to structure its own Chain of Thought process and implicitly figure out *how* to fulfill the constraints (like tone, synthesizing experience, embedding rhyming words) rather than just being told *what* the output string should look like.

### Mock CLI Flags
The project provides built-in testing boundaries:
- `--dry-run`: Prevents sending the email while running the full DSPy chain.
- `--mock-recipient`: Still sends an actual email, but overrides the destination to a local test inbox to ensure SMTP networking and PDF attachments are functioning properly in production.
