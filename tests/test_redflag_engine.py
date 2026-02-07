"""
Tests for RedFlag Analyst Engine

Run with: pytest tests/ -v
"""

import os
import sys

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from redflag_engine import (
    _SEVERITY_TO_SCORE,
    MAX_INPUT_CHARS,
    RedFlagAnalyzer,
    _max_severity,
)


class TestSeverityUtilities:
    """Test severity helper functions."""

    def test_max_severity_ordering(self):
        assert _max_severity("NONE", "LOW") == "LOW"
        assert _max_severity("LOW", "MEDIUM") == "MEDIUM"
        assert _max_severity("MEDIUM", "HIGH") == "HIGH"
        assert _max_severity("HIGH", "CRITICAL") == "CRITICAL"

    def test_max_severity_same(self):
        assert _max_severity("HIGH", "HIGH") == "HIGH"
        assert _max_severity("CRITICAL", "CRITICAL") == "CRITICAL"

    def test_max_severity_reverse_order(self):
        assert _max_severity("CRITICAL", "LOW") == "CRITICAL"
        assert _max_severity("HIGH", "NONE") == "HIGH"

    def test_severity_scores(self):
        assert _SEVERITY_TO_SCORE["NONE"] == 0
        assert _SEVERITY_TO_SCORE["LOW"] == 25
        assert _SEVERITY_TO_SCORE["MEDIUM"] == 50
        assert _SEVERITY_TO_SCORE["HIGH"] == 75
        assert _SEVERITY_TO_SCORE["CRITICAL"] == 100


class TestRedFlagAnalyzer:
    """Test the main analyzer class."""

    @pytest.fixture
    def analyzer(self):
        return RedFlagAnalyzer()

    def test_empty_input(self, analyzer):
        result = analyzer.analyze("")
        assert result["overall"]["gate_decision"] == "PASS"
        assert result["overall"]["severity"] == "NONE"
        assert result["flags"] == []

    def test_clean_text(self, analyzer):
        text = "We recommend a buy based on strong Q3 revenue growth and improving margins."
        result = analyzer.analyze(text)
        assert result["overall"]["gate_decision"] == "PASS"
        assert len(result["flags"]) == 0

    def test_output_schema(self, analyzer):
        result = analyzer.analyze("test input")
        assert "schema" in result
        assert "engine" in result
        assert "timestamp_utc" in result
        assert "overall" in result
        assert "flags" in result
        assert result["engine"]["name"] == "RedFlagAnalyzer"


class TestExpertNetworkSteering:
    """Test detection of expert network steering/over-contact."""

    @pytest.fixture
    def analyzer(self):
        return RedFlagAnalyzer()

    def test_10_calls_medium_severity(self, analyzer):
        text = "After 10 one-hour calls with the expert, we have high conviction."
        result = analyzer.analyze(text)
        flags = [f for f in result["flags"] if f["id"] == "EXPERT_NETWORK_STEERING"]
        assert len(flags) == 1
        assert flags[0]["severity"] == "MEDIUM"

    def test_15_calls_high_severity(self, analyzer):
        text = "We conducted 15 calls with industry consultants over the quarter."
        result = analyzer.analyze(text)
        flags = [f for f in result["flags"] if f["id"] == "EXPERT_NETWORK_STEERING"]
        assert len(flags) == 1
        assert flags[0]["severity"] == "HIGH"

    def test_20_calls_critical_severity(self, analyzer):
        text = "The analyst logged 20 hours with the expert network on this single name."
        result = analyzer.analyze(text)
        flags = [f for f in result["flags"] if f["id"] == "EXPERT_NETWORK_STEERING"]
        assert len(flags) == 1
        assert flags[0]["severity"] == "CRITICAL"

    def test_5_calls_low_severity(self, analyzer):
        text = "We had 5 calls with consultants to understand the market."
        result = analyzer.analyze(text)
        flags = [f for f in result["flags"] if f["id"] == "EXPERT_NETWORK_STEERING"]
        # Engine flags even low counts (conservative behavior)
        assert len(flags) == 1
        assert flags[0]["severity"] == "LOW"


class TestMNPITipping:
    """Test detection of MNPI/tipping indicators."""

    @pytest.fixture
    def analyzer(self):
        return RedFlagAnalyzer()

    def test_friend_mention(self, analyzer):
        text = "A friend at the company mentioned they're seeing strong demand."
        result = analyzer.analyze(text)
        flags = [f for f in result["flags"] if f["id"] == "MNPI_TIPPING_RISK"]
        assert len(flags) == 1
        assert "friend" in flags[0]["evidence"]

    def test_investigator_and_friend_critical(self, analyzer):
        text = "The investigator is a friend who said things look good for the trial."
        result = analyzer.analyze(text)
        flags = [f for f in result["flags"] if f["id"] == "MNPI_TIPPING_RISK"]
        assert len(flags) == 1
        assert flags[0]["severity"] == "CRITICAL"

    def test_off_the_record_high(self, analyzer):
        text = "Off the record, the CFO indicated guidance will be raised."
        result = analyzer.analyze(text)
        flags = [f for f in result["flags"] if f["id"] == "MNPI_TIPPING_RISK"]
        assert len(flags) == 1
        assert flags[0]["severity"] == "HIGH"

    def test_insider_language_high(self, analyzer):
        text = "An insider at the firm confirmed the deal is happening."
        result = analyzer.analyze(text)
        flags = [f for f in result["flags"] if f["id"] == "MNPI_TIPPING_RISK"]
        assert len(flags) == 1
        assert flags[0]["severity"] == "HIGH"

    def test_preliminary_results_critical(self, analyzer):
        text = "We've heard preliminary results from the Phase 3 trial."
        result = analyzer.analyze(text)
        flags = [f for f in result["flags"] if f["id"] == "MNPI_TIPPING_RISK"]
        assert len(flags) == 1
        assert flags[0]["severity"] == "CRITICAL"

    def test_no_mnpi_indicators(self, analyzer):
        # Note: "earnings" is flagged as a conservative indicator
        text = "Based on public filings and conference calls, we expect growth."
        result = analyzer.analyze(text)
        flags = [f for f in result["flags"] if f["id"] == "MNPI_TIPPING_RISK"]
        assert len(flags) == 0


class TestCrossBorderCompliance:
    """Test detection of cross-border/MiFID II risks."""

    @pytest.fixture
    def analyzer(self):
        return RedFlagAnalyzer()

    def test_soft_dollars_corporate_access_eu(self, analyzer):
        text = "We'll pay for corporate access to the French CEO using soft dollars."
        result = analyzer.analyze(text)
        flags = [f for f in result["flags"] if f["id"] == "CROSS_BORDER_INDUCEMENT"]
        assert len(flags) == 1
        assert flags[0]["severity"] == "HIGH"

    def test_mifid_mention_critical(self, analyzer):
        text = "Soft dollars for corporate access may trigger MiFID inducement rules."
        result = analyzer.analyze(text)
        flags = [f for f in result["flags"] if f["id"] == "CROSS_BORDER_INDUCEMENT"]
        assert len(flags) == 1
        assert flags[0]["severity"] == "CRITICAL"

    def test_london_soft_dollars(self, analyzer):
        text = "Our London analyst arranged corporate access paid via soft dollars."
        result = analyzer.analyze(text)
        flags = [f for f in result["flags"] if f["id"] == "CROSS_BORDER_INDUCEMENT"]
        assert len(flags) == 1

    def test_no_cross_border_flag(self, analyzer):
        text = "We use hard dollars for all research payments."
        result = analyzer.analyze(text)
        flags = [f for f in result["flags"] if f["id"] == "CROSS_BORDER_INDUCEMENT"]
        assert len(flags) == 0


class TestOptionsLeverageTrap:
    """Test detection of options/leverage traps."""

    @pytest.fixture
    def analyzer(self):
        return RedFlagAnalyzer()

    def test_naked_calls_detected(self, analyzer):
        text = "We plan to buy naked calls to maximize leverage ahead of earnings."
        result = analyzer.analyze(text)
        flags = [f for f in result["flags"] if f["id"] == "OPTIONS_LEVERAGE_TRAP"]
        assert len(flags) == 1
        assert flags[0]["severity"] == "HIGH"

    def test_max_risk_detected(self, analyzer):
        text = "Running near max risk, we want to add to the position."
        result = analyzer.analyze(text)
        flags = [f for f in result["flags"] if f["id"] == "OPTIONS_LEVERAGE_TRAP"]
        assert len(flags) == 1


class TestCrowdingRisk:
    """Test detection of crowding/endogenous risk."""

    @pytest.fixture
    def analyzer(self):
        return RedFlagAnalyzer()

    def test_most_held_short_high(self, analyzer):
        text = "According to 13F data, this is the most held short in the sector."
        result = analyzer.analyze(text)
        flags = [f for f in result["flags"] if f["id"] == "CROWDING_ENDOGENOUS_RISK"]
        assert len(flags) == 1
        assert flags[0]["severity"] == "HIGH"

    def test_short_squeeze_high(self, analyzer):
        text = "There's significant short squeeze potential given the crowded positioning."
        result = analyzer.analyze(text)
        flags = [f for f in result["flags"] if f["id"] == "CROWDING_ENDOGENOUS_RISK"]
        assert len(flags) == 1
        assert flags[0]["severity"] == "HIGH"

    def test_13f_crowded_medium(self, analyzer):
        text = "13F analysis shows the name is getting crowded."
        result = analyzer.analyze(text)
        flags = [f for f in result["flags"] if f["id"] == "CROWDING_ENDOGENOUS_RISK"]
        assert len(flags) == 1


class TestGateDecisions:
    """Test overall gate decision logic."""

    @pytest.fixture
    def analyzer(self):
        return RedFlagAnalyzer()

    def test_pass_decision(self, analyzer):
        text = "Strong fundamentals support our buy thesis."
        result = analyzer.analyze(text)
        assert result["overall"]["gate_decision"] == "PASS"

    def test_pm_review_decision(self, analyzer):
        # Medium severity should trigger PM_REVIEW
        text = "We had 10 calls with the expert to understand the thesis."
        result = analyzer.analyze(text)
        assert result["overall"]["gate_decision"] == "PM_REVIEW"

    def test_auto_reject_decision_high(self, analyzer):
        # High severity should trigger AUTO_REJECT
        text = "Off the record, the insider confirmed the deal."
        result = analyzer.analyze(text)
        assert result["overall"]["gate_decision"] == "AUTO_REJECT"

    def test_auto_reject_decision_critical(self, analyzer):
        # Critical severity should trigger AUTO_REJECT
        text = "After 20 hours of calls, the investigator friend said things look good."
        result = analyzer.analyze(text)
        assert result["overall"]["gate_decision"] == "AUTO_REJECT"


class TestRealWorldScenarios:
    """Test against realistic analyst note scenarios."""

    @pytest.fixture
    def analyzer(self):
        return RedFlagAnalyzer()

    def test_earnings_preview_with_mnpi(self, analyzer):
        text = """
        Q4 Earnings Preview - MEGACORP
        After 15 calls with our expert network, conviction is HIGH.
        A friend at their largest customer said orders are up 40%.
        An insider confirmed guidance will be raised - not public yet.
        Target: $180. We're 100% certain this beats.
        """
        result = analyzer.analyze(text)
        # HIGH severity from 15 calls + insider language = AUTO_REJECT
        assert result["overall"]["gate_decision"] == "AUTO_REJECT"
        flag_ids = [f["id"] for f in result["flags"]]
        assert "EXPERT_NETWORK_STEERING" in flag_ids
        assert "MNPI_TIPPING_RISK" in flag_ids

    def test_compliant_research_note(self, analyzer):
        text = """
        Investment Thesis - TECHCORP
        Based on public filings and management commentary from the
        investor day, we see 15% upside. Our DCF model uses conservative
        assumptions. Primary risks include competition and margin pressure.
        """
        result = analyzer.analyze(text)
        assert result["overall"]["gate_decision"] == "PASS"

    def test_regulatory_violation_scenario(self, analyzer):
        text = """
        Our London analyst is arranging corporate access with the
        French CEO. Payment will be via soft dollars through our
        standard CSA arrangement.
        """
        result = analyzer.analyze(text)
        assert result["overall"]["gate_decision"] == "AUTO_REJECT"
        flag_ids = [f["id"] for f in result["flags"]]
        assert "CROSS_BORDER_INDUCEMENT" in flag_ids


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def analyzer(self):
        return RedFlagAnalyzer()

    def test_unicode_handling(self, analyzer):
        text = 'The CEO\'s "guidance" was shared off-the-record.'
        result = analyzer.analyze(text)
        # Should not crash and should detect the flags
        assert "overall" in result

    def test_very_long_input(self, analyzer):
        text = "This is a test. " * 10000
        result = analyzer.analyze(text)
        assert "overall" in result
        assert result["overall"]["gate_decision"] == "PASS"

    def test_special_characters(self, analyzer):
        text = "Revenue: $1.5B (+15% YoY) | EPS: $2.50 | P/E: 25x"
        result = analyzer.analyze(text)
        assert "overall" in result

    def test_case_insensitivity(self, analyzer):
        text = "OFF THE RECORD, the INSIDER confirmed PRELIMINARY RESULTS."
        result = analyzer.analyze(text)
        flags = [f for f in result["flags"] if f["id"] == "MNPI_TIPPING_RISK"]
        assert len(flags) == 1
        assert flags[0]["severity"] == "CRITICAL"

    def test_input_size_limit_default(self):
        analyzer = RedFlagAnalyzer()
        text = "x" * (MAX_INPUT_CHARS + 1)
        with pytest.raises(ValueError, match="exceeds maximum allowed length"):
            analyzer.analyze(text)

    def test_input_size_limit_custom(self):
        analyzer = RedFlagAnalyzer(max_input_chars=100)
        with pytest.raises(ValueError, match="exceeds maximum allowed length"):
            analyzer.analyze("x" * 101)
        # Under limit should work fine
        result = analyzer.analyze("x" * 100)
        assert result["overall"]["gate_decision"] == "PASS"


class TestConfigOverride:
    """Test that detection thresholds can be overridden via config."""

    def test_custom_expert_network_thresholds(self):
        config = {"expert_network": {"medium": 5, "high": 8, "critical": 12}}
        analyzer = RedFlagAnalyzer(config=config)
        # 5 calls should now be MEDIUM (default would be LOW)
        result = analyzer.analyze("We had 5 calls with experts.")
        flags = [f for f in result["flags"] if f["id"] == "EXPERT_NETWORK_STEERING"]
        assert len(flags) == 1
        assert flags[0]["severity"] == "MEDIUM"

    def test_custom_mnpi_indicators(self):
        config = {
            "mnpi_indicators": [
                ("secret", "SECRET_LANGUAGE"),
                ("confidential", "CONFIDENTIAL_LANGUAGE"),
            ],
            "mnpi_high_keywords": ["confidential"],
            "mnpi_critical_keywords": [],
        }
        analyzer = RedFlagAnalyzer(config=config)
        result = analyzer.analyze("This is confidential information about the deal.")
        flags = [f for f in result["flags"] if f["id"] == "MNPI_TIPPING_RISK"]
        assert len(flags) == 1
        assert flags[0]["severity"] == "HIGH"

    def test_default_config_unchanged(self):
        analyzer = RedFlagAnalyzer()
        # 10 calls should still be MEDIUM with defaults
        result = analyzer.analyze("We had 10 calls with the expert.")
        flags = [f for f in result["flags"] if f["id"] == "EXPERT_NETWORK_STEERING"]
        assert len(flags) == 1
        assert flags[0]["severity"] == "MEDIUM"
