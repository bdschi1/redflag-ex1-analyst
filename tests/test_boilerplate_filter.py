"""
Tests for boilerplate_filter.py

Run with: pytest tests/test_boilerplate_filter.py -v
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from boilerplate_filter import BoilerplateFilter, BoilerplateFilterConfig


class TestBasicFiltering:
    """Test basic boilerplate filtering operations."""

    @pytest.fixture
    def bp_filter(self):
        return BoilerplateFilter()

    def test_empty_input(self, bp_filter):
        result = bp_filter.filter("")
        assert result.filtered_text == ""
        assert result.chars_removed == 0

    def test_no_boilerplate(self, bp_filter):
        text = "Revenue grew 15% YoY. Margins expanded. We recommend Buy."
        result = bp_filter.filter(text)
        assert result.filtered_text == text
        assert result.chars_removed == 0

    def test_substantive_text_preserved(self, bp_filter):
        text = (
            "After 15 calls with the expert, conviction is high.\n\n"
            "We see 20% upside based on channel checks."
        )
        result = bp_filter.filter(text)
        assert "15 calls" in result.filtered_text
        assert "20% upside" in result.filtered_text


class TestDisclaimerStripping:
    """Test removal of each boilerplate category."""

    @pytest.fixture
    def bp_filter(self):
        return BoilerplateFilter()

    def test_strip_institutional_investors_only(self, bp_filter):
        text = "Strong Q4 results.\n\nThis report is for institutional investors only."
        result = bp_filter.filter(text)
        assert "Strong Q4 results" in result.filtered_text
        assert "institutional investors only" not in result.filtered_text
        assert result.chars_removed > 0

    def test_strip_past_performance(self, bp_filter):
        text = "Buy recommendation.\n\nPast performance is not indicative of future results."
        result = bp_filter.filter(text)
        assert "Buy recommendation" in result.filtered_text
        assert "past performance" not in result.filtered_text.lower()

    def test_strip_believed_reliable(self, bp_filter):
        text = (
            "Revenue analysis.\n\n"
            "The information herein is believed to be reliable but not guaranteed."
        )
        result = bp_filter.filter(text)
        assert "Revenue analysis" in result.filtered_text
        assert "believed to be reliable" not in result.filtered_text.lower()

    def test_strip_analyst_certification(self, bp_filter):
        text = (
            "Price target $150.\n\n"
            "I, John Smith, hereby certify that the views expressed in this report "
            "accurately reflect my personal views."
        )
        result = bp_filter.filter(text)
        assert "Price target" in result.filtered_text
        assert "hereby certify" not in result.filtered_text.lower()

    def test_strip_distribution_notice(self, bp_filter):
        text = (
            "Overweight.\n\nThis report may not be reproduced or distributed without prior consent."
        )
        result = bp_filter.filter(text)
        assert "Overweight" in result.filtered_text
        assert "may not be reproduced" not in result.filtered_text.lower()

    def test_strip_regulatory_notice(self, bp_filter):
        text = "Target $200.\n\nRegistered with the SEC. Member FINRA/SIPC."
        result = bp_filter.filter(text)
        assert "Target $200" in result.filtered_text
        assert "member finra" not in result.filtered_text.lower()

    def test_strip_confidentiality_notice(self, bp_filter):
        text = "Strong buy.\n\nThis material is strictly confidential and not for public use."
        result = bp_filter.filter(text)
        assert "Strong buy" in result.filtered_text
        assert "strictly confidential" not in result.filtered_text.lower()

    def test_strip_copyright(self, bp_filter):
        text = "Analysis complete.\n\nCopyright 2024 All rights reserved."
        result = bp_filter.filter(text)
        assert "Analysis complete" in result.filtered_text
        assert "all rights reserved" not in result.filtered_text.lower()


class TestSectionRemoval:
    """Test removal of entire boilerplate sections."""

    @pytest.fixture
    def bp_filter(self):
        return BoilerplateFilter()

    def test_remove_important_disclosures_section(self, bp_filter):
        text = (
            "Buy ACME at $150.\n\n"
            "Important Disclosures\n"
            "This report is prepared by analysts who are compensated.\n"
            "We have no position in the security.\n"
            "Further information available upon request.\n\n"
            "Summary\n"
            "Reiterate Buy."
        )
        result = bp_filter.filter(text)
        assert "Buy ACME at $150" in result.filtered_text
        assert "Reiterate Buy" in result.filtered_text
        assert "compensated" not in result.filtered_text
        assert any("section:" in s for s in result.sections_removed)

    def test_remove_disclaimer_section(self, bp_filter):
        text = (
            "Strong fundamentals.\n\n"
            "Disclaimer\n"
            "This is not investment advice.\n"
            "Consult your own advisor."
        )
        result = bp_filter.filter(text)
        assert "Strong fundamentals" in result.filtered_text
        assert "not investment advice" not in result.filtered_text

    def test_remove_analyst_certification_section(self, bp_filter):
        text = (
            "PT $200.\n\n"
            "Analyst Certification\n"
            "I certify that all views are my own.\n"
            "My compensation is not related to recommendations."
        )
        result = bp_filter.filter(text)
        assert "PT $200" in result.filtered_text
        assert "certify" not in result.filtered_text.lower()


class TestProtectedKeywords:
    """
    CRITICAL: Test that the protected-keyword safety mechanism
    prevents stripping of paragraphs containing risk-relevant terms.
    """

    @pytest.fixture
    def bp_filter(self):
        return BoilerplateFilter()

    def test_insider_in_disclaimer_preserved(self, bp_filter):
        """A paragraph matching boilerplate BUT containing 'insider' is kept."""
        text = (
            "Analysis.\n\n"
            "This report is for institutional investors only. "
            "An insider confirmed the deal is real."
        )
        result = bp_filter.filter(text)
        assert "insider confirmed" in result.filtered_text.lower()

    def test_friend_in_boilerplate_preserved(self, bp_filter):
        """Paragraph with 'friend' is never stripped."""
        text = (
            "Revenue up.\n\n"
            "The information herein is believed to be reliable. "
            "A friend at the company said demand is strong."
        )
        result = bp_filter.filter(text)
        assert "friend" in result.filtered_text.lower()

    def test_off_the_record_in_disclaimer_preserved(self, bp_filter):
        text = (
            "Buy.\n\n"
            "Past performance is not indicative of future results. "
            "Off the record, the CFO said guidance will be raised."
        )
        result = bp_filter.filter(text)
        assert "off the record" in result.filtered_text.lower()

    def test_preliminary_results_in_boilerplate_preserved(self, bp_filter):
        text = (
            "Thesis.\n\n"
            "This report does not constitute investment advice. "
            "Preliminary results from the Phase 3 trial were positive."
        )
        result = bp_filter.filter(text)
        assert "preliminary results" in result.filtered_text.lower()

    def test_soft_dollar_in_disclaimer_preserved(self, bp_filter):
        text = (
            "Recommendation.\n\n"
            "The information herein is believed to be reliable. "
            "Payment via soft dollars for corporate access to the CEO."
        )
        result = bp_filter.filter(text)
        assert "soft dollar" in result.filtered_text.lower()

    def test_leak_in_boilerplate_preserved(self, bp_filter):
        text = (
            "Position.\n\n"
            "This material is strictly confidential. "
            "There was a leak of non-public data."
        )
        result = bp_filter.filter(text)
        assert "leak" in result.filtered_text.lower()

    def test_protected_keyword_in_section_stops_removal(self, bp_filter):
        """If a boilerplate section contains a protected keyword, stop removing."""
        text = (
            "Buy.\n\n"
            "Important Disclosures\n"
            "Standard disclaimer text here.\n"
            "However, an insider at the firm confirmed the merger.\n"
            "More text after."
        )
        result = bp_filter.filter(text)
        # The line with 'insider' and everything after should be preserved
        assert "insider" in result.filtered_text.lower()


class TestFilterConfig:
    """Test configuration options."""

    def test_filter_disabled(self):
        config = BoilerplateFilterConfig(enabled=False)
        bp_filter = BoilerplateFilter(config=config)
        text = "This report is for institutional investors only."
        result = bp_filter.filter(text)
        assert result.filtered_text == text
        assert result.chars_removed == 0

    def test_selective_disable_certifications(self):
        config = BoilerplateFilterConfig(strip_certifications=False)
        bp_filter = BoilerplateFilter(config=config)
        text = (
            "Buy.\n\n"
            "I, John Smith, hereby certify that the views expressed in this "
            "report accurately reflect my personal views.\n\n"
            "Past performance is not indicative of future results."
        )
        result = bp_filter.filter(text)
        # Certifications kept, disclaimers stripped
        assert "hereby certify" in result.filtered_text.lower()
        assert "past performance" not in result.filtered_text.lower()

    def test_selective_disable_disclaimers(self):
        config = BoilerplateFilterConfig(strip_disclaimers=False)
        bp_filter = BoilerplateFilter(config=config)
        text = "Buy.\n\nThis report is for institutional investors only.\n\nMember FINRA/SIPC."
        result = bp_filter.filter(text)
        # Disclaimers kept, regulatory stripped
        assert "institutional investors" in result.filtered_text.lower()
        assert "member finra" not in result.filtered_text.lower()

    def test_custom_patterns(self):
        config = BoilerplateFilterConfig(custom_patterns=[r"proprietary model"])
        bp_filter = BoilerplateFilter(config=config)
        text = "Strong buy.\n\nGenerated by our proprietary model XYZ-3000."
        result = bp_filter.filter(text)
        assert "Strong buy" in result.filtered_text
        assert "proprietary model" not in result.filtered_text.lower()

    def test_custom_protected_keywords(self):
        config = BoilerplateFilterConfig(protected_keywords=["special_term"])
        bp_filter = BoilerplateFilter(config=config)
        text = (
            "Buy.\n\n"
            "This report is for institutional investors only. "
            "The special_term indicates high conviction."
        )
        result = bp_filter.filter(text)
        assert "special_term" in result.filtered_text


class TestFilterResultMetadata:
    """Test that FilterResult metadata is accurate."""

    def test_chars_removed_arithmetic(self):
        bp_filter = BoilerplateFilter()
        text = "Analysis.\n\nThis report is for institutional investors only."
        result = bp_filter.filter(text)
        assert result.original_length == len(text)
        assert result.chars_removed == result.original_length - result.filtered_length

    def test_sections_removed_populated(self):
        bp_filter = BoilerplateFilter()
        text = "Buy.\n\nImportant Disclosures\nVarious disclaimer text."
        result = bp_filter.filter(text)
        assert len(result.sections_removed) > 0

    def test_no_sections_removed_for_clean_text(self):
        bp_filter = BoilerplateFilter()
        text = "Revenue grew 15%. Margins expanded. Buy rating."
        result = bp_filter.filter(text)
        assert len(result.sections_removed) == 0
        assert result.chars_removed == 0


class TestRealWorldScenarios:
    """Test with realistic multi-section research reports."""

    @pytest.fixture
    def bp_filter(self):
        return BoilerplateFilter()

    def test_full_research_report(self, bp_filter):
        text = (
            "Investment Thesis\n"
            "ACME Corp (ACME) is well-positioned for growth. Revenue grew 15% YoY.\n"
            "We recommend Buy with a $150 price target.\n\n"
            "Risk Factors\n"
            "Key risks include competition and margin pressure.\n\n"
            "Important Disclosures\n"
            "This report is prepared by Example Securities LLC.\n"
            "The analyst has no position in ACME.\n"
            "This report is for institutional investors only.\n"
            "Past performance is not indicative of future results.\n\n"
            "Analyst Certification\n"
            "I hereby certify that the views expressed herein accurately reflect "
            "my personal views about the subject security.\n"
            "My compensation was not related to the recommendation.\n\n"
            "Copyright 2024 Example Securities. All rights reserved."
        )
        result = bp_filter.filter(text)

        # Substantive content preserved
        assert "ACME Corp" in result.filtered_text
        assert "$150 price target" in result.filtered_text
        assert "competition and margin pressure" in result.filtered_text

        # Boilerplate removed
        assert "hereby certify" not in result.filtered_text.lower()
        assert "all rights reserved" not in result.filtered_text.lower()
        assert result.chars_removed > 0
        assert len(result.sections_removed) > 0

    def test_boilerplate_only_document(self, bp_filter):
        text = (
            "Disclaimer\n"
            "This report is for institutional investors only.\n"
            "Past performance is not indicative of future results.\n"
            "The information herein is believed to be reliable.\n"
            "All rights reserved."
        )
        result = bp_filter.filter(text)
        # Should remove most/all content
        assert result.chars_removed > 0
        # filtered text should be much shorter
        assert result.filtered_length < result.original_length

    def test_mnpi_near_boilerplate_is_caught(self, bp_filter):
        """Golden test: MNPI content adjacent to boilerplate is never stripped."""
        text = (
            "A friend who is an investigator said things look good.\n\n"
            "Important Disclosures\n"
            "This report is for institutional investors only.\n"
            "Past performance is not indicative of future results.\n\n"
            "Off the record, the insider confirmed preliminary results."
        )
        result = bp_filter.filter(text)
        # ALL MNPI content must be preserved
        assert "friend" in result.filtered_text.lower()
        assert "investigator" in result.filtered_text.lower()
        assert "off the record" in result.filtered_text.lower()
        assert "insider" in result.filtered_text.lower()
        assert "preliminary results" in result.filtered_text.lower()
