"""
scout.py — Discovers Unravel.tech founders using DSPy-first reasoning.

Takes references from the web and uses DSPy to extract founders.
Filters founder names with "PR" constraint using DSPy.
"""

from __future__ import annotations

import re
import time
import hashlib
import os
from dataclasses import dataclass
from urllib.parse import quote_plus, urlparse, parse_qs, unquote

import dspy

# ---------------------------------------------------------------------------
# DSPy Signature
# ---------------------------------------------------------------------------


class ExtractFounders(dspy.Signature):
    """
    You are given noisy web text about Unravel Tech, a Pune-based AI company.

    Task:
    - Identify ONLY the real founders of Unravel Tech.
    - A person must be explicitly described in the text as founding or co-founding Unravel Tech.
    - Ignore investors, employees, executives of other companies, or unrelated people.

    Strict rules:
    - If the text does NOT clearly mention any Unravel Tech founders, output EXACTLY: NONE
    - Do NOT guess.
    - Do NOT include people unless the Unravel connection is explicit.

    Output format (STRICT):
    - One founder per line
    - Format: Full Name :: Reason why you think this person is a founder of Unravel Tech
    - No extra commentary
    """

    corpus: str = dspy.InputField(desc="Web text mentioning Unravel Tech")
    founders: str = dspy.OutputField(
        desc="Lines of 'Full Name :: Reason why you think this person is a founder'"
    )


# ---------------------------------------------------------------------------
# Inserted: DSPy PR founder selector signature
# ---------------------------------------------------------------------------

class SelectPRFounder(dspy.Signature):
    """
    You are given founder candidates of Unravel Tech with supporting evidence.

    Task:
    - Identify the founder whose FIRST or LAST name contains the
      consecutive letters "pr" (case-insensitive).
    - Example matches: "Prajwalit", "Prem", "Chopra".
    - Example non-matches: "Kiran", "Vedang", "Sunny".

    Strict rules:
    - The selected person MUST have "pr" in their name.
    - Return ONLY the first name of that matching person.
    - If no valid match exists, output EXACTLY: NONE
    """

    candidates: str = dspy.InputField(
        desc="Founder candidates with reasons"
    )
    first_name: str = dspy.OutputField(
        desc="First name of the founder containing 'pr'"
    )
    
# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------


def _fetch_html(url: str, retries: int = 2) -> str:
    """Fetch a page with retry + disk cache."""
    import urllib.request

    cache_dir = ".cache/scout"
    os.makedirs(cache_dir, exist_ok=True)
    key = hashlib.md5(url.encode()).hexdigest()
    cache_path = os.path.join(cache_dir, key + ".html")

    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass

    last_err: Exception | None = None

    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as resp:
                text = resp.read().decode("utf-8", errors="replace")

            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    f.write(text)
            except Exception:
                pass

            return text

        except Exception as exc:
            last_err = exc
            if attempt < retries:
                time.sleep(0.8 * (2 ** attempt))
            else:
                return f"[fetch error: {exc}]"

    return f"[fetch error: {last_err}]"



def _strip_html_tags(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()



def _unwrap_ddg_url(url: str) -> str:
    if "duckduckgo.com/l/?" not in url:
        return url
    try:
        qs = parse_qs(urlparse(url).query)
        real = qs.get("uddg")
        if real:
            return unquote(real[0])
    except Exception:
        pass
    return url


# ---------------------------------------------------------------------------
# DuckDuckGo search
# ---------------------------------------------------------------------------


def _duckduckgo_search(query: str) -> str:
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    print(f"[scout] DuckDuckGo search: {query!r}")

    html = _fetch_html(url)

    titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL)
    snippets = re.findall(
        r'class="result__snippet"[^>]*>(.*?)</(?:a|span)>', html, re.DOTALL
    )
    links = re.findall(r'class="result__a" href="(.*?)"', html)

    parts = titles + snippets
    cleaned_parts = [_strip_html_tags(p) for p in parts]

    fetched_pages: list[str] = []
    for link in links[:2]:
        try:
            real_link = _unwrap_ddg_url(link)
            page_html = _fetch_html(real_link)
            fetched_pages.append(_strip_html_tags(page_html)[:4000])
            print(f"[scout] fetched: {real_link}")
        except Exception as e:
            print(f"[scout] fetch failed: {link} :: {e}")

    combined = "\n".join(cleaned_parts + fetched_pages)
    return combined[:14000]


# ---------------------------------------------------------------------------
# Deterministic helpers
# ---------------------------------------------------------------------------


def _has_pr_name_parts(name: str) -> bool:
    parts = name.strip().lower().split()
    if not parts:
        return False
    if len(parts) == 1:
        return "pr" in parts[0]
    return "pr" in parts[0] or "pr" in parts[-1]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def find_founder() -> list[dict]:
    """DSPy-first founder discovery returning list of {name: reason} mappings."""

    sections: list[str] = []

    QUERIES = [
        "unravel tech pune founders",
        "who founded unravel.tech company",
        "unravel.tech team founders",
        "site:linkedin.com unravel tech founders",
    ]

    for q in QUERIES:
        sections.append(_duckduckgo_search(q))

    # ------------------------------------------------------------------
    # DSPy founder extraction PER SOURCE (more agentic)
    # ------------------------------------------------------------------

    extractor = dspy.ChainOfThought(ExtractFounders)

    candidate_lines: list[str] = []

    for idx, section in enumerate(sections):
        try:
            print(f"[scout] DSPy extracting founders from section {idx}")
            result = extractor(corpus=section[:12000])

            lines = [
                line.strip()
                for line in result.founders.splitlines()
                if line.strip()
            ]

            print(f"[scout] Section {idx} candidates: {lines}")
            candidate_lines.extend(lines)

        except Exception as e:
            print(f"[scout] DSPy extraction failed for section {idx}: {e}")

    # dedupe while preserving order
    seen = set()
    deduped_lines: list[str] = []
    for line in candidate_lines:
        key = line.lower()
        if key not in seen:
            seen.add(key)
            deduped_lines.append(line)

    print(f"[scout] Aggregated founder candidates: {deduped_lines}")

    # Build list of founder entries with name and reason
    all_candidates: list[dict] = []
    for line in deduped_lines:
        low = line.lower()
        name = None
        reason = line
        
        if "::" in line:
            name_part, reason_part = line.split("::", 1)
            name = name_part.strip()
            reason = reason_part.strip()
            if name.lower() == "none":
                name = None
        elif "none" in low or any(x in low for x in ["does not", "no information", "not explicitly"]):
            name = None
            reason = line.strip()
        else:
            name = line.strip()
            reason = "Supporting evidence found in source text."

        all_candidates.append({"name": name, "reason": reason})

    # "if none then skip adding it to result list" (filter for the final result list)
    found_founders = [c for c in all_candidates if c["name"] is not None]

    # "If no name is found then it should return {None, & a reason}"
    if not found_founders:
        reason = "No founder information found."
        if all_candidates:
            reason = all_candidates[0]["reason"]
        return [{"name": None, "reason": reason}]

    print(f"[scout] Filtered founder entries: {found_founders}")

    # ------------------------------------------------------------------
    # DSPy PR selection (agentic final step)
    # ------------------------------------------------------------------

    # Prepare candidates string for selector
    candidates_str = "\n".join([f"{e['name']} :: {e['reason']}" for e in found_founders])
    selector = dspy.ChainOfThought(SelectPRFounder)
    selection = selector(candidates=candidates_str)

    picked_raw = selection.first_name.strip()
    if not picked_raw or picked_raw.upper() == "NONE":
        print("[scout] ⚠️ No founder name containing 'pr' found by DSPy.")
        return found_founders

    # The LLM might return multiple names or extra text; we clean and filter locally
    picked_names = [n.strip() for n in picked_raw.splitlines() if n.strip()]
    
    matched = None
    final_picked_name = None

    for name_candidate in picked_names:
        # Enforce the PR constraint in Python as a final safeguard
        if not _has_pr_name_parts(name_candidate):
            continue
            
        # Match against our found_founders list
        for f in found_founders:
            # Check if picked name is first name OR contained in full name
            if name_candidate.lower() == f["name"].split()[0].lower() or name_candidate.lower() in f["name"].lower():
                matched = f
                final_picked_name = name_candidate
                break
        
        if matched:
            break

    if matched:
        email = f"{final_picked_name.lower()}@unravel.tech"
        matched["email"] = email
        matched["selected"] = True
        print(f"[scout] ✅ Identified: {final_picked_name} → {email}")
    else:
        print(f"[scout] ⚠️ Could not reliably map selection {picked_raw!r} to a candidate containing 'pr'.")

    return found_founders


# ---------------------------------------------------------------------------
# Live test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY", "")

    MODELS = [
        ("ollama_chat/gemma3", {}),
        ("gemini/gemini-2.5-pro-preview-03-25", {"api_key": api_key}),
        ("gemini/gemini-2.0-flash", {"api_key": api_key}),
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
            status = getattr(e, "status_code", getattr(e, "code", None))
            err_str = str(e).lower()

            is_rate_limit = status in (429, 403) or any(
                x in err_str for x in ["429", "quota", "rate", "exhausted"]
            )
            is_not_found = status == 404 or any(
                x in err_str for x in ["404", "not found"]
            )

            if is_rate_limit or is_not_found:
                print(f"[scout] ⚠️  {model} unavailable, trying next...")
                continue
            raise

    if info is None:
        raise SystemExit("❌ All models exhausted.")

    print("\n" + "=" * 50)
    # Find the selected founder if any
    selected = next((f for f in info if f.get("selected")), None)
    if selected:
        print(f"✅ Selected Founder   : {selected['name']}")
        print(f"✅ Email address      : {selected['email']}")
        print(f"💡 Reasoning          : {selected['reason']}")
    elif info and info[0].get("name") is None:
         print(f"❌ No founders found. Reason: {info[0]['reason']}")
    else:
        print(f"✅ All found founders:")
        for f in info:
            print(f"   - {f['name']}: {f['reason']}")
    print("=" * 50)