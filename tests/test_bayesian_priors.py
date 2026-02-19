"""
Tests for Bayesian risk prior module.

Run with: pytest tests/test_bayesian_priors.py -v
"""

import os
import sys

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bayesian_risk_priors import (
    SUBJECT_AREAS,
    RULE_TO_SUBJECT,
    DEFAULT_PRIORS,
    BetaPrior,
    AuditFocusItem,
    BayesianAnalysis,
    compute_posteriors,
    aggregate_subject_area_risk,
    rank_audit_focus,
    analyze_with_priors,
)


# ---------------------------------------------------------------------------
# BetaPrior
# ---------------------------------------------------------------------------

class TestBetaPrior:
    """Test the BetaPrior dataclass and its methods."""

    def test_mean_uniform(self):
        """Beta(1,1) is the uniform distribution — mean 0.5."""
        bp = BetaPrior(1.0, 1.0, "TEST")
        assert bp.mean == pytest.approx(0.5)

    def test_mean_skewed_high(self):
        bp = BetaPrior(8.0, 2.0, "TEST")
        assert bp.mean == pytest.approx(0.8)

    def test_mean_skewed_low(self):
        bp = BetaPrior(2.0, 8.0, "TEST")
        assert bp.mean == pytest.approx(0.2)

    def test_variance_positive(self):
        bp = BetaPrior(2.0, 5.0, "TEST")
        assert bp.variance > 0

    def test_variance_decreases_with_more_data(self):
        """More pseudo-counts → lower variance (more certainty)."""
        low_data = BetaPrior(2.0, 5.0, "TEST")
        high_data = BetaPrior(20.0, 50.0, "TEST")
        assert high_data.variance < low_data.variance

    def test_uncertainty_is_sqrt_variance(self):
        bp = BetaPrior(3.0, 4.0, "TEST")
        assert bp.uncertainty == pytest.approx(bp.variance ** 0.5)

    def test_posterior_observed_increases_alpha(self):
        prior = BetaPrior(2.0, 5.0, "TEST")
        post = prior.posterior(observed=1, total=1)
        assert post.alpha == 3.0
        assert post.beta_param == 5.0

    def test_posterior_not_observed_increases_beta(self):
        prior = BetaPrior(2.0, 5.0, "TEST")
        post = prior.posterior(observed=0, total=1)
        assert post.alpha == 2.0
        assert post.beta_param == 6.0

    def test_posterior_multiple_observations(self):
        prior = BetaPrior(1.0, 1.0, "TEST")
        post = prior.posterior(observed=3, total=10)
        assert post.alpha == 4.0
        assert post.beta_param == 8.0

    def test_posterior_preserves_rule_id(self):
        prior = BetaPrior(2.0, 5.0, "MNPI_TIPPING_RISK", "compliance")
        post = prior.posterior(observed=1, total=1)
        assert post.rule_id == "MNPI_TIPPING_RISK"
        assert post.subject_area == "compliance"

    def test_posterior_mean_increases_on_observation(self):
        prior = BetaPrior(2.0, 5.0, "TEST")
        post = prior.posterior(observed=1, total=1)
        assert post.mean > prior.mean

    def test_posterior_mean_decreases_on_non_observation(self):
        prior = BetaPrior(2.0, 5.0, "TEST")
        post = prior.posterior(observed=0, total=1)
        assert post.mean < prior.mean

    def test_to_dict_keys(self):
        bp = BetaPrior(2.0, 5.0, "TEST", "compliance")
        d = bp.to_dict()
        assert set(d.keys()) == {
            "rule_id", "subject_area", "alpha", "beta",
            "prior_risk", "uncertainty",
        }

    def test_to_dict_values_rounded(self):
        bp = BetaPrior(2.0, 5.0, "TEST")
        d = bp.to_dict()
        # Verify rounding to 4 decimals
        assert d["alpha"] == round(2.0, 4)
        assert d["beta"] == round(5.0, 4)


# ---------------------------------------------------------------------------
# Subject areas and default priors
# ---------------------------------------------------------------------------

class TestSubjectAreas:
    """Test subject area definitions and mappings."""

    def test_two_subject_areas(self):
        assert set(SUBJECT_AREAS.keys()) == {"compliance", "portfolio"}

    def test_compliance_has_three_rules(self):
        assert len(SUBJECT_AREAS["compliance"]) == 3

    def test_portfolio_has_five_rules(self):
        assert len(SUBJECT_AREAS["portfolio"]) == 5

    def test_rule_to_subject_covers_all(self):
        all_rules = []
        for rules in SUBJECT_AREAS.values():
            all_rules.extend(rules)
        assert set(RULE_TO_SUBJECT.keys()) == set(all_rules)

    def test_rule_to_subject_compliance(self):
        assert RULE_TO_SUBJECT["MNPI_TIPPING_RISK"] == "compliance"
        assert RULE_TO_SUBJECT["EXPERT_NETWORK_STEERING"] == "compliance"
        assert RULE_TO_SUBJECT["CROSS_BORDER_INDUCEMENT"] == "compliance"

    def test_rule_to_subject_portfolio(self):
        assert RULE_TO_SUBJECT["OPTIONS_LEVERAGE_TRAP"] == "portfolio"
        assert RULE_TO_SUBJECT["CROWDING_ENDOGENOUS_RISK"] == "portfolio"


class TestDefaultPriors:
    """Test the default prior configuration."""

    def test_eight_default_priors(self):
        assert len(DEFAULT_PRIORS) == 8

    def test_all_priors_have_positive_params(self):
        for rule_id, prior in DEFAULT_PRIORS.items():
            assert prior.alpha > 0, f"{rule_id} alpha must be positive"
            assert prior.beta_param > 0, f"{rule_id} beta must be positive"

    def test_all_priors_have_subject_area(self):
        for rule_id, prior in DEFAULT_PRIORS.items():
            assert prior.subject_area in ("compliance", "portfolio"), (
                f"{rule_id} has invalid subject area: {prior.subject_area}"
            )

    def test_all_priors_have_matching_rule_id(self):
        for rule_id, prior in DEFAULT_PRIORS.items():
            assert prior.rule_id == rule_id

    def test_mnpi_highest_compliance_prior(self):
        """MNPI tipping risk should have highest compliance prior mean."""
        compliance_priors = {
            k: v for k, v in DEFAULT_PRIORS.items()
            if v.subject_area == "compliance"
        }
        mnpi = compliance_priors["MNPI_TIPPING_RISK"]
        for rule_id, prior in compliance_priors.items():
            assert mnpi.mean >= prior.mean, (
                f"MNPI mean {mnpi.mean} should be >= {rule_id} mean {prior.mean}"
            )


# ---------------------------------------------------------------------------
# compute_posteriors
# ---------------------------------------------------------------------------

class TestComputePosteriors:
    """Test posterior computation."""

    def test_no_flags_fired(self):
        posteriors = compute_posteriors([])
        for rule_id, post in posteriors.items():
            prior = DEFAULT_PRIORS[rule_id]
            assert post.alpha == prior.alpha
            assert post.beta_param == prior.beta_param + 1

    def test_one_flag_fired(self):
        posteriors = compute_posteriors(["MNPI_TIPPING_RISK"])
        mnpi = posteriors["MNPI_TIPPING_RISK"]
        prior = DEFAULT_PRIORS["MNPI_TIPPING_RISK"]
        assert mnpi.alpha == prior.alpha + 1
        assert mnpi.beta_param == prior.beta_param

    def test_multiple_flags_fired(self):
        fired = ["MNPI_TIPPING_RISK", "OPTIONS_LEVERAGE_TRAP"]
        posteriors = compute_posteriors(fired)
        for rule_id in fired:
            prior = DEFAULT_PRIORS[rule_id]
            assert posteriors[rule_id].alpha == prior.alpha + 1

    def test_all_flags_fired(self):
        fired = list(DEFAULT_PRIORS.keys())
        posteriors = compute_posteriors(fired)
        for rule_id in fired:
            prior = DEFAULT_PRIORS[rule_id]
            assert posteriors[rule_id].alpha == prior.alpha + 1
            assert posteriors[rule_id].beta_param == prior.beta_param

    def test_returns_all_rules(self):
        posteriors = compute_posteriors(["MNPI_TIPPING_RISK"])
        assert set(posteriors.keys()) == set(DEFAULT_PRIORS.keys())

    def test_custom_priors(self):
        custom = {
            "RULE_A": BetaPrior(1.0, 1.0, "RULE_A", "test"),
        }
        posteriors = compute_posteriors(["RULE_A"], priors=custom)
        assert "RULE_A" in posteriors
        assert posteriors["RULE_A"].alpha == 2.0

    def test_unknown_fired_id_ignored(self):
        """Firing a rule not in priors should not raise."""
        posteriors = compute_posteriors(["NONEXISTENT_RULE"])
        assert len(posteriors) == len(DEFAULT_PRIORS)


# ---------------------------------------------------------------------------
# aggregate_subject_area_risk
# ---------------------------------------------------------------------------

class TestAggregateSubjectAreaRisk:
    """Test subject area risk aggregation."""

    def test_returns_both_areas(self):
        posteriors = compute_posteriors([])
        risks = aggregate_subject_area_risk(posteriors)
        assert "compliance" in risks
        assert "portfolio" in risks

    def test_risks_between_zero_and_one(self):
        posteriors = compute_posteriors(["MNPI_TIPPING_RISK"])
        risks = aggregate_subject_area_risk(posteriors)
        for area, risk in risks.items():
            assert 0.0 < risk < 1.0, f"{area} risk {risk} out of bounds"

    def test_fired_area_has_higher_risk(self):
        """Area with a fired flag should have higher aggregate risk."""
        posteriors_none = compute_posteriors([])
        posteriors_mnpi = compute_posteriors(["MNPI_TIPPING_RISK"])
        risk_none = aggregate_subject_area_risk(posteriors_none)
        risk_mnpi = aggregate_subject_area_risk(posteriors_mnpi)
        assert risk_mnpi["compliance"] > risk_none["compliance"]

    def test_unfired_area_unchanged(self):
        """Firing compliance rule shouldn't change portfolio risk."""
        posteriors_none = compute_posteriors([])
        posteriors_mnpi = compute_posteriors(["MNPI_TIPPING_RISK"])
        risk_none = aggregate_subject_area_risk(posteriors_none)
        risk_mnpi = aggregate_subject_area_risk(posteriors_mnpi)
        assert risk_mnpi["portfolio"] == pytest.approx(risk_none["portfolio"])


# ---------------------------------------------------------------------------
# rank_audit_focus
# ---------------------------------------------------------------------------

class TestRankAuditFocus:
    """Test audit focus ranking."""

    def test_returns_all_rules(self):
        posteriors = compute_posteriors([])
        focus = rank_audit_focus(posteriors, [])
        assert len(focus) == len(DEFAULT_PRIORS)

    def test_sorted_by_priority_descending(self):
        posteriors = compute_posteriors(["MNPI_TIPPING_RISK"])
        focus = rank_audit_focus(posteriors, ["MNPI_TIPPING_RISK"])
        scores = [item.priority_score for item in focus]
        assert scores == sorted(scores, reverse=True)

    def test_fired_flag_marked(self):
        posteriors = compute_posteriors(["MNPI_TIPPING_RISK"])
        focus = rank_audit_focus(posteriors, ["MNPI_TIPPING_RISK"])
        mnpi_items = [f for f in focus if f.rule_id == "MNPI_TIPPING_RISK"]
        assert len(mnpi_items) == 1
        assert mnpi_items[0].flag_fired is True

    def test_unfired_flag_not_marked(self):
        posteriors = compute_posteriors(["MNPI_TIPPING_RISK"])
        focus = rank_audit_focus(posteriors, ["MNPI_TIPPING_RISK"])
        other_items = [f for f in focus if f.rule_id != "MNPI_TIPPING_RISK"]
        for item in other_items:
            assert item.flag_fired is False

    def test_priority_score_is_risk_times_uncertainty(self):
        posteriors = compute_posteriors([])
        focus = rank_audit_focus(posteriors, [])
        for item in focus:
            expected = item.posterior_risk * item.uncertainty
            assert item.priority_score == pytest.approx(expected)

    def test_audit_focus_item_to_dict(self):
        item = AuditFocusItem(
            rule_id="TEST",
            subject_area="compliance",
            posterior_risk=0.5,
            uncertainty=0.15,
            priority_score=0.075,
            flag_fired=True,
        )
        d = item.to_dict()
        assert d["rule_id"] == "TEST"
        assert d["flag_fired"] is True
        assert "priority_score" in d


# ---------------------------------------------------------------------------
# analyze_with_priors (main entry point)
# ---------------------------------------------------------------------------

class TestAnalyzeWithPriors:
    """Test the main entry point."""

    def _make_redflag_result(self, flag_ids):
        """Helper to build a minimal redflag result dict."""
        return {
            "flags": [{"id": fid} for fid in flag_ids],
            "overall_severity": "HIGH" if flag_ids else "NONE",
        }

    def test_no_flags(self):
        result = analyze_with_priors(self._make_redflag_result([]))
        assert result.flags_fired == 0
        assert result.total_rules == 8

    def test_one_flag(self):
        result = analyze_with_priors(
            self._make_redflag_result(["MNPI_TIPPING_RISK"])
        )
        assert result.flags_fired == 1

    def test_multiple_flags(self):
        fired = ["MNPI_TIPPING_RISK", "OPTIONS_LEVERAGE_TRAP", "CROWDING_ENDOGENOUS_RISK"]
        result = analyze_with_priors(self._make_redflag_result(fired))
        assert result.flags_fired == 3

    def test_posteriors_populated(self):
        result = analyze_with_priors(self._make_redflag_result([]))
        assert len(result.posteriors) == 8
        for rule_id in DEFAULT_PRIORS:
            assert rule_id in result.posteriors

    def test_subject_area_risks_populated(self):
        result = analyze_with_priors(self._make_redflag_result([]))
        assert "compliance" in result.subject_area_risks
        assert "portfolio" in result.subject_area_risks

    def test_audit_focus_sorted(self):
        result = analyze_with_priors(
            self._make_redflag_result(["MNPI_TIPPING_RISK"])
        )
        scores = [item.priority_score for item in result.audit_focus]
        assert scores == sorted(scores, reverse=True)

    def test_to_dict_keys(self):
        result = analyze_with_priors(self._make_redflag_result([]))
        d = result.to_dict()
        assert set(d.keys()) == {
            "total_rules", "flags_fired", "subject_area_risks",
            "posteriors", "audit_focus",
        }

    def test_to_dict_posteriors_nested(self):
        result = analyze_with_priors(self._make_redflag_result([]))
        d = result.to_dict()
        for rule_id, prior_dict in d["posteriors"].items():
            assert "prior_risk" in prior_dict
            assert "uncertainty" in prior_dict

    def test_custom_priors(self):
        custom = {
            "CUSTOM_RULE": BetaPrior(5.0, 5.0, "CUSTOM_RULE", "custom"),
        }
        result = analyze_with_priors(
            self._make_redflag_result(["CUSTOM_RULE"]),
            priors=custom,
        )
        assert result.total_rules == 1
        assert result.flags_fired == 1
        assert result.posteriors["CUSTOM_RULE"].alpha == 6.0

    def test_empty_flags_list(self):
        result = analyze_with_priors({"flags": []})
        assert result.flags_fired == 0

    def test_missing_flags_key(self):
        result = analyze_with_priors({})
        assert result.flags_fired == 0


# ---------------------------------------------------------------------------
# BayesianAnalysis
# ---------------------------------------------------------------------------

class TestBayesianAnalysis:
    """Test BayesianAnalysis dataclass."""

    def test_default_total_rules(self):
        ba = BayesianAnalysis(
            posteriors={},
            subject_area_risks={},
            audit_focus=[],
        )
        assert ba.total_rules == 8

    def test_custom_total_rules(self):
        ba = BayesianAnalysis(
            posteriors={},
            subject_area_risks={},
            audit_focus=[],
            total_rules=3,
            flags_fired=1,
        )
        assert ba.total_rules == 3
        assert ba.flags_fired == 1
