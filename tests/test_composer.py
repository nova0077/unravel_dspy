"""
tests/test_composer.py — Unit tests for the email composer.
"""

from unittest.mock import MagicMock, patch

from unravel_agent.composer import build_subject, compose_email, THIRD_RHYMING_WORD


class TestBuildSubject:
    def test_contains_apply(self):
        assert "Apply" in build_subject() or "apply" in build_subject().lower()

    def test_contains_dspy(self):
        assert "DSPy" in build_subject() or "dspy" in build_subject().lower()

    def test_contains_rhyming_word(self):
        subject = build_subject().lower()
        assert THIRD_RHYMING_WORD.lower() in subject


class TestComposeEmail:
    @patch("unravel_agent.composer.dspy.ChainOfThought")
    def test_signature_block_added_if_missing(self, mock_cot_cls):
        mock_result = MagicMock()
        mock_result.cover_letter = "Dear Prabhat,\n\nI would love to join Unravel.\n\nBest, Praveen"
        mock_cot_cls.return_value = MagicMock(return_value=mock_result)

        composed = compose_email(
            founder_name="Prabhat",
            founder_email="prabhat@unravel.tech",
            resume_text="Skills: Python, DSPy, AI systems...",
        )

        assert "with assistance from" in composed.body.lower()

    @patch("unravel_agent.composer.dspy.ChainOfThought")
    def test_correct_recipient(self, mock_cot_cls):
        mock_result = MagicMock()
        mock_result.cover_letter = "Body text here. Thanks, Praveen (with assistance from Gemini)"
        mock_cot_cls.return_value = MagicMock(return_value=mock_result)

        composed = compose_email(
            founder_name="Prabhat",
            founder_email="prabhat@unravel.tech",
            resume_text="Resume text",
        )
        assert composed.to == "prabhat@unravel.tech"

    @patch("unravel_agent.composer.dspy.ChainOfThought")
    def test_no_duplicate_signature(self, mock_cot_cls):
        mock_result = MagicMock()
        mock_result.cover_letter = "Body. Thanks, Praveen (with assistance from Gemini)"
        mock_cot_cls.return_value = MagicMock(return_value=mock_result)

        composed = compose_email(
            founder_name="Prabhat",
            founder_email="prabhat@unravel.tech",
            resume_text="Resume",
        )
        # Should not double-add the signature block
        assert composed.body.lower().count("with assistance from") == 1
