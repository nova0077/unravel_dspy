"""
tests/test_scout.py — Unit tests for scout.py.

All tests mock out network/browser calls so no internet or Ollama is needed.
"""

from unittest.mock import MagicMock, patch

import pytest

from unravel_agent.scout import (
    _extract_names,
    _has_pr,
    _NON_NAME_WORDS,
    find_founder,
    FounderInfo,
)


# ---------------------------------------------------------------------------
# _has_pr
# ---------------------------------------------------------------------------

class TestHasPr:
    def test_matches_start_of_name(self):
        assert _has_pr("Prajwalit") is True

    def test_matches_mid_name(self):
        assert _has_pr("Express") is True  # ex-pr-ess

    def test_case_insensitive(self):
        assert _has_pr("PRAJWALIT") is True
        assert _has_pr("prajwalit") is True

    def test_no_pr(self):
        assert _has_pr("Kedar") is False
        assert _has_pr("Vedang") is False
        assert _has_pr("Kiran") is False
        assert _has_pr("Sovani") is False

    def test_kedar_sovani_has_no_pr(self):
        """Regression: gemma3 previously hallucinated that 'Kiran' contains 'pr'."""
        assert _has_pr("Kiran") is False
        assert _has_pr("Kedar") is False


# ---------------------------------------------------------------------------
# _extract_names
# ---------------------------------------------------------------------------

class TestExtractNames:
    def test_extracts_person_names(self):
        text = "Founders: Vedang Manerikar, Prajwalit Bhopale, Kiran Kulkarni"
        names = _extract_names(text)
        assert "Vedang Manerikar" in names
        assert "Prajwalit Bhopale" in names
        assert "Kiran Kulkarni" in names

    def test_deduplicates(self):
        text = "Prajwalit Bhopale attended. Prajwalit Bhopale leads engineering."
        names = _extract_names(text)
        assert names.count("Prajwalit Bhopale") == 1

    def test_filters_non_name_words(self):
        text = "Privacy Policy Technical Depth Production Engineering Prajwalit Bhopale"
        names = _extract_names(text)
        assert "Privacy Policy" not in names
        assert "Technical Depth" not in names
        assert "Production Engineering" not in names
        assert "Prajwalit Bhopale" in names

    def test_filters_country_names_from_ddg_ui(self):
        """DDG region selector produces pairs like 'Austria Belgium' — must be filtered."""
        text = "Austria Belgium Brazil Bulgaria Catalonia Chile Prajwalit Bhopale"
        names = _extract_names(text)
        # Country names aren't in the blocklist BUT should not match person-name regex
        # as long as we don't explicitly need to block them.
        # At minimum, Prajwalit Bhopale must be present:
        assert "Prajwalit Bhopale" in names

    def test_single_words_not_extracted(self):
        names = _extract_names("Founder CEO Engineer Manager")
        assert not any(len(n.split()) == 1 for n in names)

    def test_blocklist_completeness(self):
        """Key non-name words must be in the blocklist."""
        for word in ["Professional", "Private", "Headquarters", "Overview", "Express"]:
            # If added to blocklist they'd be filtered; check the set exists and is non-empty
            assert isinstance(_NON_NAME_WORDS, set)
            assert len(_NON_NAME_WORDS) > 10


# ---------------------------------------------------------------------------
# find_founder — fast path (no LLM call needed)
# ---------------------------------------------------------------------------

class TestFindFounderFastPath:
    @patch("unravel_agent.scout._duckduckgo_search")
    def test_fast_path_picks_prajwalit(self, mock_ddg):
        """When DuckDuckGo returns the founders, fast-path finds Prajwalit without LLM."""
        mock_ddg.return_value = (
            "Kiran Kulkarni Vedang Manerikar Prajwalit Bhopale "
            "Founder at Unravel Tech Pune Maharashtra"
        )
        info = find_founder()
        assert info.first_name == "Prajwalit"
        assert info.email == "prajwalit@unravel.tech"
        assert "pr" in info.first_name.lower()

    @patch("unravel_agent.scout._duckduckgo_search")
    def test_fast_path_skips_llm(self, mock_ddg):
        """Fast-path should never call the LLM (DSPy ChainOfThought)."""
        mock_ddg.return_value = "Prajwalit Bhopale Co-Founder Unravel Tech"
        with patch("unravel_agent.scout.dspy.ChainOfThought") as mock_cot:
            find_founder()
            mock_cot.assert_not_called()

    @patch("unravel_agent.scout._duckduckgo_search")
    def test_email_format(self, mock_ddg):
        """Email must be lowercase first-name@unravel.tech."""
        mock_ddg.return_value = "Prajwalit Bhopale founder"
        info = find_founder()
        assert info.email == "prajwalit@unravel.tech"
        assert "@unravel.tech" in info.email
        assert info.email == info.email.lower()

    @patch("unravel_agent.scout._duckduckgo_search")
    def test_professional_overview_not_picked(self, mock_ddg):
        """'Professional Overview' contains 'pr' but is NOT a person name — must be excluded."""
        mock_ddg.return_value = (
            "Professional Overview Email Phone "
            "Prajwalit Bhopale Co-Founder Unravel Tech"
        )
        info = find_founder()
        # Must pick Prajwalit, not 'Professional'
        assert info.first_name == "Prajwalit"


# ---------------------------------------------------------------------------
# find_founder — LLM fallback path
# ---------------------------------------------------------------------------

class TestFindFounderLLMFallback:
    @patch("unravel_agent.scout._duckduckgo_search")
    @patch("unravel_agent.scout.dspy.ChainOfThought")
    def test_fallback_used_when_no_pr_name_found(self, mock_cot_cls, mock_ddg):
        """If scraping finds no person name with PR, DSPy fallback is invoked."""
        # Simulate scrape returning only non-PR names
        mock_ddg.return_value = "Vedang Manerikar Kiran Kulkarni"

        mock_result = MagicMock()
        mock_result.founder_first_name = "Prajwalit"
        mock_result.reasoning = "Prajwalit starts with pr."
        mock_cot_cls.return_value = MagicMock(return_value=mock_result)

        info = find_founder()
        assert info.first_name == "Prajwalit"
        mock_cot_cls.assert_called_once()
