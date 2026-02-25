"""
Bayesian risk prior module for RedFlag Analyst.

Implements beta-binomial conjugate priors for each detection rule,
enabling probabilistic risk assessment and audit focus narrowing.
Inspired by the AuditAgent paper (2025) which uses variational
inference to narrow audit focus from 60-80 to 15 high-risk subjects.

Each rule has a prior Beta(alpha, beta) distribution representing
belief about how likely that risk is present before observing any
flags.  When a flag fires, the prior is updated to a posterior via
conjugate Bayesian updating.

Subject areas group related rules for aggregate risk assessment:
    - compliance: MNPI, expert network, cross-border
    - portfolio: options, beta-neutral, MVO, crowding, liquidity

References:
    AuditAgent (2025): "AuditAgent: A Multi-Agent Framework for
    Financial Statement Audit" — Bayesian prior model with
    variational inference for audit risk narrowing
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Subject area definitions
# ---------------------------------------------------------------------------

SUBJECT_AREAS = {
    "compliance": [
        "EXPERT_NETWORK_STEERING",
        "MNPI_TIPPING_RISK",
        "CROSS_BORDER_INDUCEMENT",
    ],
    "portfolio": [
        "OPTIONS_LEVERAGE_TRAP",
        "BETA_NEUTRALITY_FALLACY",
        "MVO_OPTIMIZER_TRAP",
        "CROWDING_ENDOGENOUS_RISK",
        "LIQUIDITY_BASIS_MISMATCH",
    ],
}

# Reverse mapping: rule_id → subject_area
RULE_TO_SUBJECT: Dict[str, str] = {}
for _area, _rules in SUBJECT_AREAS.items():
    for _rule in _rules:
        RULE_TO_SUBJECT[_rule] = _area


# ---------------------------------------------------------------------------
# Beta-binomial prior
# ---------------------------------------------------------------------------


@dataclass
class BetaPrior:
    """Beta distribution prior for a single detection rule.

    alpha: pseudo-count of "flag observed" events (higher = more risky prior)
    beta_param: pseudo-count of "flag not observed" events
    """

    alpha: float
    beta_param: float
    rule_id: str
    subject_area: str = ""

    @property
    def mean(self) -> float:
        """Prior mean = expected probability of risk."""
        return self.alpha / (self.alpha + self.beta_param)

    @property
    def variance(self) -> float:
        """Prior variance — higher = more uncertain."""
        a, b = self.alpha, self.beta_param
        return (a * b) / ((a + b) ** 2 * (a + b + 1))

    @property
    def uncertainty(self) -> float:
        """Standard deviation of the prior."""
        return self.variance**0.5

    def posterior(self, observed: int, total: int) -> "BetaPrior":
        """Bayesian update: return posterior after observing data.

        Args:
            observed: Number of times the flag was triggered.
            total: Total number of documents/analyses.

        Returns:
            New BetaPrior with updated parameters.
        """
        return BetaPrior(
            alpha=self.alpha + observed,
            beta_param=self.beta_param + (total - observed),
            rule_id=self.rule_id,
            subject_area=self.subject_area,
        )

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "subject_area": self.subject_area,
            "alpha": round(self.alpha, 4),
            "beta": round(self.beta_param, 4),
            "prior_risk": round(self.mean, 4),
            "uncertainty": round(self.uncertainty, 4),
        }


# ---------------------------------------------------------------------------
# Default priors (calibrated to institutional finance base rates)
# ---------------------------------------------------------------------------

DEFAULT_PRIORS: Dict[str, BetaPrior] = {
    # Compliance rules — higher prior risk (more common in practice)
    "EXPERT_NETWORK_STEERING": BetaPrior(2.0, 5.0, "EXPERT_NETWORK_STEERING", "compliance"),
    "MNPI_TIPPING_RISK": BetaPrior(3.0, 4.0, "MNPI_TIPPING_RISK", "compliance"),
    "CROSS_BORDER_INDUCEMENT": BetaPrior(1.5, 8.0, "CROSS_BORDER_INDUCEMENT", "compliance"),
    # Portfolio/risk rules — moderate prior risk
    "OPTIONS_LEVERAGE_TRAP": BetaPrior(1.5, 6.0, "OPTIONS_LEVERAGE_TRAP", "portfolio"),
    "BETA_NEUTRALITY_FALLACY": BetaPrior(1.0, 7.0, "BETA_NEUTRALITY_FALLACY", "portfolio"),
    "MVO_OPTIMIZER_TRAP": BetaPrior(1.5, 6.0, "MVO_OPTIMIZER_TRAP", "portfolio"),
    "CROWDING_ENDOGENOUS_RISK": BetaPrior(2.0, 4.0, "CROWDING_ENDOGENOUS_RISK", "portfolio"),
    "LIQUIDITY_BASIS_MISMATCH": BetaPrior(1.0, 8.0, "LIQUIDITY_BASIS_MISMATCH", "portfolio"),
}


# ---------------------------------------------------------------------------
# Bayesian analysis
# ---------------------------------------------------------------------------


@dataclass
class AuditFocusItem:
    """A single item in the prioritized audit focus list."""

    rule_id: str
    subject_area: str
    posterior_risk: float
    uncertainty: float
    priority_score: float  # posterior_risk * uncertainty — high = needs attention
    flag_fired: bool

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "subject_area": self.subject_area,
            "posterior_risk": round(self.posterior_risk, 4),
            "uncertainty": round(self.uncertainty, 4),
            "priority_score": round(self.priority_score, 4),
            "flag_fired": self.flag_fired,
        }


@dataclass
class BayesianAnalysis:
    """Complete Bayesian risk analysis result."""

    posteriors: Dict[str, BetaPrior]
    subject_area_risks: Dict[str, float]
    audit_focus: List[AuditFocusItem]
    total_rules: int = 8
    flags_fired: int = 0

    def to_dict(self) -> dict:
        return {
            "total_rules": self.total_rules,
            "flags_fired": self.flags_fired,
            "subject_area_risks": {k: round(v, 4) for k, v in self.subject_area_risks.items()},
            "posteriors": {k: v.to_dict() for k, v in self.posteriors.items()},
            "audit_focus": [item.to_dict() for item in self.audit_focus],
        }


def compute_posteriors(
    fired_rule_ids: List[str],
    priors: Dict[str, BetaPrior] | None = None,
) -> Dict[str, BetaPrior]:
    """Compute posterior distributions for all rules given observed flags.

    Args:
        fired_rule_ids: List of rule IDs that were triggered.
        priors: Optional custom priors (defaults to DEFAULT_PRIORS).

    Returns:
        Dict mapping rule_id → posterior BetaPrior.
    """
    priors = priors or DEFAULT_PRIORS
    posteriors: Dict[str, BetaPrior] = {}

    for rule_id, prior in priors.items():
        observed = 1 if rule_id in fired_rule_ids else 0
        posteriors[rule_id] = prior.posterior(observed=observed, total=1)

    return posteriors


def aggregate_subject_area_risk(
    posteriors: Dict[str, BetaPrior],
) -> Dict[str, float]:
    """Compute average posterior risk per subject area.

    Returns:
        Dict mapping subject_area → average posterior risk probability.
    """
    area_risks: Dict[str, List[float]] = {}

    for rule_id, posterior in posteriors.items():
        area = posterior.subject_area or RULE_TO_SUBJECT.get(rule_id, "unknown")
        area_risks.setdefault(area, []).append(posterior.mean)

    return {area: sum(risks) / len(risks) for area, risks in area_risks.items()}


def rank_audit_focus(
    posteriors: Dict[str, BetaPrior],
    fired_rule_ids: List[str],
) -> List[AuditFocusItem]:
    """Rank rules by priority for targeted audit review.

    Priority score = posterior_risk * uncertainty.  Rules with both
    high risk AND high uncertainty get the most audit attention, per
    the AuditAgent paper's variational inference methodology.

    Returns:
        Sorted list of AuditFocusItem (highest priority first).
    """
    items: List[AuditFocusItem] = []

    for rule_id, posterior in posteriors.items():
        risk = posterior.mean
        unc = posterior.uncertainty
        items.append(
            AuditFocusItem(
                rule_id=rule_id,
                subject_area=posterior.subject_area,
                posterior_risk=risk,
                uncertainty=unc,
                priority_score=risk * unc,
                flag_fired=rule_id in fired_rule_ids,
            )
        )

    items.sort(key=lambda x: x.priority_score, reverse=True)
    return items


def analyze_with_priors(
    redflag_result: Dict[str, Any],
    priors: Dict[str, BetaPrior] | None = None,
) -> BayesianAnalysis:
    """Run Bayesian analysis on an existing RedFlag engine result.

    This is the main entry point.  Takes the output of
    RedFlagAnalyzer.analyze() and enriches it with posterior
    distributions, subject area risk aggregation, and prioritized
    audit focus ranking.

    Args:
        redflag_result: Output of RedFlagAnalyzer.analyze().
        priors: Optional custom priors.

    Returns:
        BayesianAnalysis with posteriors, subject risks, and audit focus.
    """
    fired_ids = [f["id"] for f in redflag_result.get("flags", [])]

    posteriors = compute_posteriors(fired_ids, priors)
    subject_risks = aggregate_subject_area_risk(posteriors)
    audit_focus = rank_audit_focus(posteriors, fired_ids)

    return BayesianAnalysis(
        posteriors=posteriors,
        subject_area_risks=subject_risks,
        audit_focus=audit_focus,
        total_rules=len(posteriors),
        flags_fired=len(fired_ids),
    )
