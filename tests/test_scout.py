"""
tests/test_scout.py — Unit tests for scout.py.
"""
from unittest.mock import MagicMock, patch

import pytest
from unravel_agent.scout import (
    _has_pr_name_parts,
    find_founder,
    ExtractFounders,
    SelectPRFounder
)

# ---------------------------------------------------------------------------
# _has_pr_name_parts
# ---------------------------------------------------------------------------

class TestHasPrNameParts:
    def test_matches_start_of_name(self):
        assert _has_pr_name_parts("Prajwalit") is True
        assert _has_pr_name_parts("Prajwalit Bhopale") is True

    def test_matches_last_name(self):
        assert _has_pr_name_parts("Express Chopra") is True  # cho-pr-a

    def test_middle_name_ignored(self):
        # "pr" is only allowed in the first or last name
        assert _has_pr_name_parts("Vedang Prajwalit Manerikar") is False

    def test_case_insensitive(self):
        assert _has_pr_name_parts("PRAJWALIT BHOPALE") is True
        assert _has_pr_name_parts("prajwalit bhopale") is True

    def test_no_pr(self):
        assert _has_pr_name_parts("Kedar") is False
        assert _has_pr_name_parts("Vedang") is False
        assert _has_pr_name_parts("Kiran") is False
        assert _has_pr_name_parts("Sovani") is False
        assert _has_pr_name_parts("Kedar Sovani") is False
        assert _has_pr_name_parts("Kiran Kulkarni") is False

    def test_regression_no_hallucination(self):
        """Regression: gemma3 previously hallucinated that 'Kiran' contains 'pr'."""
        assert _has_pr_name_parts("Kiran") is False
        assert _has_pr_name_parts("Kedar") is False

# ---------------------------------------------------------------------------
# find_founder
# ---------------------------------------------------------------------------

class TestFindFounder:
    @patch("unravel_agent.scout._duckduckgo_search")
    @patch("unravel_agent.scout.dspy.ChainOfThought")
    def test_find_founder_success(self, mock_cot_cls, mock_ddg):
        """Test successful finding and picking of a founder with 'pr' in their name."""
        mock_ddg.return_value = "Mocked text about Prajwalit Bhopale."

        def mock_cot_init(signature):
            mock_instance = MagicMock()
            if signature == ExtractFounders:
                mock_result = MagicMock()
                mock_result.founders = "Prajwalit Bhopale :: He is a founder\nVedang Manerikar :: Co-founder"
                mock_instance.return_value = mock_result
            elif signature == SelectPRFounder:
                mock_result = MagicMock()
                mock_result.first_name = "Prajwalit"
                mock_instance.return_value = mock_result
            return mock_instance
        
        mock_cot_cls.side_effect = mock_cot_init

        founders = find_founder()
        
        assert len(founders) == 2
        
        # Verify Prajwalit was selected
        prajwalit_entry = next((f for f in founders if f["name"] == "Prajwalit Bhopale"), None)
        assert prajwalit_entry is not None
        assert prajwalit_entry.get("selected") is True
        assert prajwalit_entry.get("email") == "prajwalit@unravel.tech"
        assert prajwalit_entry["reason"] == "He is a founder"

    @patch("unravel_agent.scout._duckduckgo_search")
    @patch("unravel_agent.scout.dspy.ChainOfThought")
    def test_find_founder_no_pr_founder(self, mock_cot_cls, mock_ddg):
        """Test scenario where founders are found, but none match the PR constraint."""
        mock_ddg.return_value = "Mocked text about Vedang Manerikar."

        def mock_cot_init(signature):
            mock_instance = MagicMock()
            if signature == ExtractFounders:
                mock_result = MagicMock()
                mock_result.founders = "Vedang Manerikar :: He is a founder"
                mock_instance.return_value = mock_result
            elif signature == SelectPRFounder:
                mock_result = MagicMock()
                mock_result.first_name = "NONE"
                mock_instance.return_value = mock_result
            return mock_instance
        
        mock_cot_cls.side_effect = mock_cot_init

        founders = find_founder()
        assert len(founders) == 1
        assert founders[0]["name"] == "Vedang Manerikar"
        assert founders[0].get("selected") is None

    @patch("unravel_agent.scout._duckduckgo_search")
    @patch("unravel_agent.scout.dspy.ChainOfThought")
    def test_find_founder_no_founders_found(self, mock_cot_cls, mock_ddg):
        """Test scenario where no founders are found at all."""
        mock_ddg.return_value = "Unrelated company text."
        
        def mock_cot_init(signature):
            mock_instance = MagicMock()
            if signature == ExtractFounders:
                mock_result = MagicMock()
                mock_result.founders = "NONE :: The text does not explicitly mention any founders."
                mock_instance.return_value = mock_result
            return mock_instance
            
        mock_cot_cls.side_effect = mock_cot_init

        founders = find_founder()
        assert len(founders) == 1
        assert founders[0]["name"] is None
        assert "explicitly mention" in founders[0]["reason"]
