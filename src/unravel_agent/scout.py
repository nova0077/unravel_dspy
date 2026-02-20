"""
scout.py — Discovers Unravel.tech founders and identifies the one
with "PR" in their name using DuckDuckGo + DSPy reasoning.

Search strategy:
  1. DuckDuckGo HTML — scraper-friendly, no JS, no CAPTCHA
  2. DuckDuckGo broader team search

LLM is only called when the regex fast-path can't deterministically
pick the right person. A deterministic pre-check always verifies
that 'pr' is literally present in the output name (case-insensitive).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote_plus

import dspy
from playwright.sync_api import Page, sync_playwright


# ---------------------------------------------------------------------------
# DSPy Signature
# ---------------------------------------------------------------------------

class IdentifyFounder(dspy.Signature):
    """
    You are given a list of real person names scraped from web pages about
    Unravel.tech, a Pune-based AI engineering company.

    Your task: find the name where 'pr' appears as CONSECUTIVE LETTERS
    (case-insensitive) within the first name OR last name.

    IMPORTANT: check each name character by character.
    - 'Kedar'     → 'k','e','d'... → no 'pr' substring ✗
    - 'Sovani'    → 's','o','v'... → no 'pr' substring ✗

    Only output the FIRST NAME of the matching person.
    """
    people_list: str = dspy.InputField(
        desc="Newline-separated list of person names from web scraping"
    )
    founder_first_name: str = dspy.OutputField(
        desc="First name of the person whose name contains the consecutive letters 'pr'"
    )
    reasoning: str = dspy.OutputField(
        desc="Step-by-step check: show which letters of the chosen name spell 'pr'"
    )


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@dataclass
class FounderInfo:
    first_name: str
    email: str
    reasoning: str


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

# Non-name words to filter from regex matches
_NON_NAME_WORDS: set[str] = {
    "Privacy", "Policy", "Terms", "Agreement", "Service", "Cookie",
    "Technical", "Depth", "Production", "Engineering", "Product", "Rapid",
    "Prototyping", "Planning", "Assessment", "Architecture", "Systems",
    "Approach", "Mindset", "Results", "Resources", "Context", "Protocol",
    "Espressif", "Model", "User", "About", "Contact", "Login", "Sign",
    "Join", "Learn", "More", "View", "Profile", "People", "Company",
    "Google", "DuckDuckGo", "Twitter", "Youtube", "Github", "Apple",
    "Open", "Source", "Agent", "Build", "Ship", "Scale", "Team",
    "Artificial", "Intelligence", "Machine", "Learning", "Language",
    "Distributed", "Autonomous", "Sales", "Multi", "Modern", "Loop",
    "Senior", "Software", "Engineer", "Developer", "Director", "Manager",
    "Head", "Vice", "President", "Chief", "Officer", "Executive",
    "Home", "Blog", "Talks", "Events", "Talk", "Without", "Ceremony",
    "That", "Kill", "Ideas", "Work", "Unlike", "Prioritize", "Evaluate",
    "Risk", "Assess", "Optimize", "Deploy", "Minutes", "Memory", "Long",
    "Expensive", "Mistakes", "Prevents",
    # Common LinkedIn / DDG page chrome that slips through
    "Professional", "Overview", "Express", "Scripts", "Private", "Limited",
    "Privately", "Held", "Promise", "Provides", "Promoted",
}


# ---------------------------------------------------------------------------
# Browser / fetch helpers
# ---------------------------------------------------------------------------

def _fetch_html(url: str) -> str:
    """Fetch a page using requests-style GET (no JS execution needed)."""
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return f"[fetch error: {exc}]"


def _strip_html_tags(html: str) -> str:
    """Remove HTML tags, collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&[a-z]+;", " ", text)   # html entities
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _duckduckgo_search(query: str) -> str:
    """
    DuckDuckGo HTML endpoint — no JS, no CAPTCHA, scraper-friendly.
    Extracts only result titles + snippets, NOT the full page UI
    (which contains a country/region selector with 60+ country names).
    """
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    print(f"[scout] DuckDuckGo search: {query!r}")
    html = _fetch_html(url)

    # Extract only result titles and snippets — ignore page chrome
    titles   = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL)
    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</(?:a|span)>', html, re.DOTALL)
    parts    = titles + snippets

    if not parts:
        # Fallback: strip all tags if DDG changed its HTML structure
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text).strip()
        return f"=== DDG: {query!r} (raw) ===\n{text[:4000]}"

    combined = "\n".join(_strip_html_tags(p) for p in parts)
    return f"=== DDG: {query!r} ===\n{combined[:6000]}"





# ---------------------------------------------------------------------------
# Name extraction
# ---------------------------------------------------------------------------

def _extract_names(text: str) -> list[str]:
    """
    Extract exactly-two-word Title-Cased names, filtered by a non-name blocklist.
    """
    pattern = r"\b([A-Z][a-z]{2,14})\s+([A-Z][a-z]{2,14})\b"
    raw_matches = re.findall(pattern, text)

    seen: set[str] = set()
    unique: list[str] = []
    for first, last in raw_matches:
        if first in _NON_NAME_WORDS or last in _NON_NAME_WORDS:
            continue
        full = f"{first} {last}"
        if full not in seen:
            seen.add(full)
            unique.append(full)
    return unique


def _has_pr(name: str) -> bool:
    """Return True if 'pr' appears as consecutive letters in the name."""
    return "pr" in name.lower()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_founder() -> FounderInfo:
    """
    Discovers Unravel.tech founders via DuckDuckGo + website scraping,
    then deterministically or via DSPy identifies the one with 'PR' in their name.
    """
    sections: list[str] = []

    # 1. DuckDuckGo — founder search (Pune location context)
    sections.append(
        _duckduckgo_search("founder names of unravel tech company, location Pune maharashtra")
    )

    combined_text = "\n\n".join(sections)

    # Extract candidate names
    names = _extract_names(combined_text)
    print(f"[scout] Extracted {len(names)} candidate names: {names[:25]}")

    # --- Fast path: deterministic 'pr' substring check on PERSON names only ---
    # Filter through the blocklist so 'Professional Overview', 'Express Scripts' etc.
    # don't count — only real person names (both words pass the blocklist)
    person_pr_names = [
        n for n in names
        if _has_pr(n)
        and n.split()[0] not in _NON_NAME_WORDS
        and n.split()[1] not in _NON_NAME_WORDS
    ]
    print(f"[scout] Person names with literal 'PR': {person_pr_names}")

    if len(person_pr_names) >= 1:
        # Use the matched name directly — never truncate via LLM
        matched_name  = person_pr_names[0]          # e.g. 'Prajwalit Bhopale'
        first_name    = matched_name.split()[0]      # e.g. 'Prajwalit'
        reasoning = (
            f"Deterministic fast-path: '{matched_name}' is a person name "
            f"where 'pr' appears as consecutive letters (no LLM needed)."
        )
        print(f"[scout] ✅ Fast-path identified: {first_name} (from '{matched_name}')")
    else:
        # Fall back to DSPy
        people_list = "\n".join(names[:60]) if names else combined_text[:3000]
        identifier  = dspy.ChainOfThought(IdentifyFounder)
        result      = identifier(people_list=people_list)
        first_name  = result.founder_first_name.strip().split()[0]
        reasoning   = result.reasoning

        # Sanity check
        if not _has_pr(first_name):
            print(f"[scout] ⚠️  WARNING: LLM picked '{first_name}' which does NOT contain 'pr'!")

    email = f"{first_name.lower()}@unravel.tech"
    print(f"[scout] ✅ Identified: {first_name} → {email}")
    print(f"[scout] Reasoning: {reasoning}")

    return FounderInfo(first_name=first_name, email=email, reasoning=reasoning)


# ---------------------------------------------------------------------------
# Live test entrypoint — run with: python src/unravel_agent/scout.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    api_key = os.environ.get("GEMINI_API_KEY", "")

    # Ollama-first model list — Gemini as optional upgrade if key is valid
    MODELS = [
        ("ollama_chat/gemma3", {}),                              # local, no quota
        ("gemini/gemini-2.5-pro-preview-03-25", {"api_key": api_key}),
        ("gemini/gemini-2.0-flash",             {"api_key": api_key}),
    ]

    print("🔍 Running scout live test...\n")
    info = None
    for model, kwargs in MODELS:
        if not api_key and "gemini" in model:
            print(f"[scout] Skipping {model} — no API key set")
            continue
        try:
            print(f"[scout] Trying model: {model}")
            dspy.configure(lm=dspy.LM(model=model, **kwargs))
            info = find_founder()
            break
        except Exception as e:
            err = str(e)
            if any(x in err for x in ["429", "quota", "rate", "404", "not found"]):
                print(f"[scout] ⚠️  {model} unavailable, trying next...")
                continue
            raise

    if info is None:
        raise SystemExit("❌ All models exhausted.")

    print("\n" + "=" * 50)
    print(f"✅ Founder first name : {info.first_name}")
    print(f"✅ Email address      : {info.email}")
    print(f"💡 Reasoning          : {info.reasoning}")
    print("=" * 50)
