"""
redflag_engine.py

A lightweight, rule-based "RedFlag Analyst" engine for institutional finance.
Designed to be runnable locally (no API keys) and produce deterministic JSON outputs.

Primary use: gate LLM-generated research drafts before they reach a PM.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import asdict, dataclass
from importlib.metadata import version as _pkg_version
from typing import Any, Dict, List

# ----------------------------
# Defaults / configuration
# ----------------------------
MAX_INPUT_CHARS = 500_000

# ----------------------------
# Sell-side source detection
# ----------------------------
# When a document is identified as published sell-side research, MNPI rules
# are suppressed because the compliance burden sits with the issuing firm's
# compliance department, not the buy-side reader.

SELLSIDE_FIRMS = [
    # Bulge bracket / major banks
    "goldman sachs",
    "morgan stanley",
    "jp morgan",
    "j.p. morgan",
    "citigroup",
    "citi research",
    "bank of america",
    "merrill lynch",
    "barclays",
    "ubs",
    "credit suisse",
    "deutsche bank",
    "hsbc",
    "jefferies",
    "wells fargo",
    "rbc capital",
    "nomura",
    # Independent / mid-cap research
    "bernstein",
    "wolfe research",
    "cowen",
    "piper sandler",
    "raymond james",
    "stifel",
    "baird",
    "oppenheimer",
    "evercore isi",
    "william blair",
    "redburn",
    "clsa",
    "macquarie",
    "keefe bruyette",
    "td cowen",
    "bmo capital",
    "canaccord",
    "needham",
    "wedbush",
    "leerink",
    "guggenheim",
    "truist",
]

SELLSIDE_LANGUAGE = [
    "equity research",
    "initiate coverage",
    "initiating coverage",
    "maintain rating",
    "maintaining rating",
    "upgrade to",
    "downgrade to",
    "price target",
    "analyst certification",
    "important disclosures",
    "investment rating",
    "sector rating",
    "industry rating",
    "this report has been prepared",
    "this research report",
]

_MNPI_RULE_IDS = ["MNPI_TIPPING_RISK", "EXPERT_NETWORK_STEERING"]

DEFAULT_THRESHOLDS = {
    "expert_network": {
        "medium": 10,
        "high": 15,
        "critical": 20,
    },
    "mnpi_indicators": [
        ("friend", "MENTION_OF_FRIEND"),
        ("investigator", "CLINICAL_SITE_INSIDER"),
        ("off the record", "OFF_THE_RECORD"),
        ("not public", "NOT_PUBLIC"),
        ("leak", "LEAK_LANGUAGE"),
        ("insider", "INSIDER_LANGUAGE"),
        ("told me", "DIRECT_TELL"),
        ("said things look good", "RESULTS_HINT"),
        ("preliminary results", "PRELIM_RESULTS"),
        ("guidance", "GUIDANCE_REFERENCE"),
        ("earnings", "EARNINGS_REFERENCE"),
    ],
    "mnpi_high_keywords": ["off the record", "not public", "leak", "insider"],
    "mnpi_critical_keywords": [
        "investigator",
        "said things look good",
        "preliminary results",
    ],
    "cross_border_eu_tokens": [
        "mifid",
        "eu",
        "europe",
        "london",
        "uk",
        "france",
        "french",
        "inducement",
    ],
}

# ----------------------------
# Severity utilities
# ----------------------------
_SEVERITY_ORDER = ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
_SEVERITY_TO_SCORE = {
    "NONE": 0,
    "LOW": 25,
    "MEDIUM": 50,
    "HIGH": 75,
    "CRITICAL": 100,
}


def _max_severity(a: str, b: str) -> str:
    return _SEVERITY_ORDER[max(_SEVERITY_ORDER.index(a), _SEVERITY_ORDER.index(b))]


def _now_utc_iso() -> str:
    return (
        _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


@dataclass
class Flag:
    """A single risk flag produced by the engine."""

    id: str
    title: str
    severity: str
    score: int
    evidence: List[str]
    explanation: str
    recommended_action: str


class RedFlagAnalyzer:
    """
    Deterministic, rule-based analyzer for buy-side compliance workflows.

    IMPORTANT: This is intentionally conservative and biased toward flagging
    institutional blow-up risks (compliance, MNPI, portfolio construction traps).

    Published sell-side research (Goldman Sachs, Morgan Stanley, etc.) and SEC
    filings are assumed to carry zero MNPI risk — the compliance burden sits
    with the issuing firm.  When sell-side source markers are detected, MNPI
    rules are suppressed; portfolio construction flags remain active.

    Args:
        config: Optional dict to override DEFAULT_THRESHOLDS keys.
        max_input_chars: Override the global MAX_INPUT_CHARS limit.
    """

    try:
        VERSION = _pkg_version("redflag-analyst")
    except Exception:
        VERSION = "0.2.1"

    def __init__(
        self,
        config: Dict[str, Any] | None = None,
        max_input_chars: int | None = None,
    ):
        self._cfg = {**DEFAULT_THRESHOLDS, **(config or {})}
        self._max_input_chars = max_input_chars if max_input_chars is not None else MAX_INPUT_CHARS

    def analyze(self, text: str) -> Dict[str, Any]:
        if len(text) > self._max_input_chars:
            raise ValueError(
                f"Input exceeds maximum allowed length "
                f"({len(text):,} chars > {self._max_input_chars:,} limit)"
            )
        normalized = self._normalize(text)

        sellside = self._detect_sellside_source(normalized)

        flags: List[Flag] = []

        # MNPI rules: suppressed for sell-side research (compliance burden
        # is on the issuing firm, not the buy-side reader)
        if not sellside["detected"]:
            flags.extend(self._detect_expert_network_steering(normalized))
            flags.extend(self._detect_mnpi_tipping(normalized))

        # Cross-border + portfolio construction traps: always run
        # (buy-side responsibility regardless of source)
        flags.extend(self._detect_cross_border_soft_dollars(normalized))
        flags.extend(self._detect_options_leverage_trap(normalized))
        flags.extend(self._detect_beta_neutral_momentum_trap(normalized))
        flags.extend(self._detect_mvo_optimizer_trap(normalized))
        flags.extend(self._detect_crowding_endogenous_risk(normalized))
        flags.extend(self._detect_liquidity_basis_mismatch(normalized))

        overall = self._aggregate(flags)

        return {
            "schema": "redflag_ex1_analyst.output.v1",
            "engine": {"name": "RedFlagAnalyzer", "version": self.VERSION},
            "timestamp_utc": _now_utc_iso(),
            "overall": overall,
            "flags": [asdict(f) for f in flags],
            "sellside_source": sellside,
        }

    # ----------------------------
    # Sell-side source detection
    # ----------------------------
    def _detect_sellside_source(self, text: str) -> Dict[str, Any]:
        """Detect whether the document is published sell-side research.

        Requires both a recognized firm name AND at least one sell-side
        language pattern (e.g. "equity research", "price target").  A stray
        mention of a bank name inside a buy-side memo does not trigger this.
        """
        matched_firm = None
        for firm in SELLSIDE_FIRMS:
            if firm in text:
                matched_firm = firm
                break

        if matched_firm is None:
            return {"detected": False}

        lang_hits = [pat for pat in SELLSIDE_LANGUAGE if pat in text]
        if not lang_hits:
            return {"detected": False}

        return {
            "detected": True,
            "firm": matched_firm,
            "evidence": [matched_firm] + lang_hits[:4],
            "note": "MNPI rules suppressed — compliance burden is on the issuing firm",
            "suppressed_rules": list(_MNPI_RULE_IDS),
        }

    # ----------------------------
    # Normalization
    # ----------------------------
    def _normalize(self, text: str) -> str:
        text = text or ""
        # Keep original meaning but make rules robust
        text = text.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
        text = re.sub(r"\s+", " ", text).strip()
        return text.lower()

    # ----------------------------
    # Detection rules
    # ----------------------------
    def _detect_expert_network_steering(self, text: str) -> List[Flag]:
        """
        Detect excessive expert contact counts (calls/hours) which often correlates with:
        - Steering risk
        - Mosaic theory abuse
        - Process control failures
        """
        # Examples: "10 one-hour calls", "15 calls", "20 hours"
        m = re.search(r"(\d+)\s+(one-hour calls|calls|hours|hrs)", text)
        if not m:
            return []

        count = int(m.group(1))
        en = self._cfg["expert_network"]
        severity = "NONE"
        if count >= en["critical"]:
            severity = "CRITICAL"
        elif count >= en["high"]:
            severity = "HIGH"
        elif count >= en["medium"]:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        if severity in ("NONE",):
            return []

        score = _SEVERITY_TO_SCORE[severity]

        return [
            Flag(
                id="EXPERT_NETWORK_STEERING",
                title="Expert network over-contact / potential steering",
                severity=severity,
                score=score,
                evidence=[m.group(0)],
                explanation=(
                    "High-volume repeated expert interactions elevate 'steering vs. mosaic' risk, "
                    "and can indicate a process-control failure even if content is nominally public."
                ),
                recommended_action=(
                    "PM_REVIEW + Compliance: require documented research plan, transcripts, "
                    "and justification for repeated contact; consider trading restriction if MNPI risk co-occurs."
                )
                if severity in ("MEDIUM", "HIGH")
                else (
                    "AUTO_REJECT + Compliance escalation: freeze the idea and audit expert interactions."
                ),
            )
        ]

    def _detect_mnpi_tipping(self, text: str) -> List[Flag]:
        """
        Detect common MNPI/tipping indicators in narrative notes.
        """
        indicators = self._cfg["mnpi_indicators"]
        hits = [token for token, _ in indicators if token in text]

        # Higher confidence if multiple indicators show up
        if len(hits) == 0:
            return []

        severity = "MEDIUM"
        if any(tok in hits for tok in self._cfg["mnpi_high_keywords"]):
            severity = "HIGH"
        critical_kw = self._cfg["mnpi_critical_keywords"]
        if ("investigator" in hits and "friend" in hits) or any(tok in hits for tok in critical_kw):
            severity = "CRITICAL"

        score = _SEVERITY_TO_SCORE[severity]
        return [
            Flag(
                id="MNPI_TIPPING_RISK",
                title="Potential MNPI / tipping / non-public information",
                severity=severity,
                score=score,
                evidence=sorted(set(hits))[:8],
                explanation=(
                    "Narrative contains non-public-information markers (direct hints, insiders, or off-the-record framing). "
                    "In institutional workflows this must be treated as MNPI until proven otherwise."
                ),
                recommended_action=(
                    "AUTO_REJECT: do not trade; escalate to Compliance; preserve notes and communications for review."
                )
                if severity in ("HIGH", "CRITICAL")
                else (
                    "PM_REVIEW + Compliance: clarify source and publicness; document mosaic rationale; consider restriction."
                ),
            )
        ]

    def _detect_cross_border_soft_dollars(self, text: str) -> List[Flag]:
        """
        Detect cross-border inducements / soft-dollar / corporate access risks.
        """
        soft = ("soft dollar" in text) or ("soft dollars" in text) or ("soft$" in text)
        access = ("corporate access" in text) or ("access" in text and "ceo" in text)
        eu = any(tok in text for tok in self._cfg["cross_border_eu_tokens"])

        if not (soft and (access or eu)):
            return []

        severity = "HIGH"
        if "mifid" in text or "inducement" in text:
            severity = "CRITICAL"

        return [
            Flag(
                id="CROSS_BORDER_INDUCEMENT",
                title="Cross-border compliance / inducement (MiFID II-style) risk",
                severity=severity,
                score=_SEVERITY_TO_SCORE[severity],
                evidence=[
                    tok
                    for tok in [
                        "soft dollars",
                        "corporate access",
                        "mifid",
                        "inducement",
                        "london",
                        "france",
                        "ceo",
                    ]
                    if tok in text
                ][:8],
                explanation=(
                    "Soft-dollar funded corporate access can trigger inducement restrictions in EU/UK regimes. "
                    "Treat as a high-risk compliance area requiring jurisdiction-specific review."
                ),
                recommended_action=(
                    "AUTO_REJECT: block execution until Compliance signs off on jurisdiction, payment method, and inducement analysis."
                ),
            )
        ]

    def _detect_options_leverage_trap(self, text: str) -> List[Flag]:
        if not any(
            tok in text
            for tok in [
                "naked call",
                "naked calls",
                "maximize leverage",
                "max leverage",
                "near max risk",
                "max risk",
            ]
        ):
            return []
        severity = "HIGH"
        return [
            Flag(
                id="OPTIONS_LEVERAGE_TRAP",
                title="Options leverage trap (IV crush / convexity misunderstanding)",
                severity=severity,
                score=_SEVERITY_TO_SCORE[severity],
                evidence=[
                    tok
                    for tok in ["naked calls", "maximize leverage", "near max risk"]
                    if tok in text
                ][:8],
                explanation=(
                    "Language indicates aggressive convexity positioning under tight risk constraints. "
                    "Common failure mode: IV crush, beta expansion ('success risk'), and inability to de-risk after a win."
                ),
                recommended_action="PM_REVIEW: require scenario analysis (IV, skew, beta expansion) and explicit exit/liquidity plan.",
            )
        ]

    def _detect_beta_neutral_momentum_trap(self, text: str) -> List[Flag]:
        if not (
            ("beta" in text or "beta ~" in text or "beta 0" in text)
            and ("market-neutral" in text or "market neutral" in text or "l/s" in text)
        ):
            return []
        severity = "MEDIUM"
        return [
            Flag(
                id="BETA_NEUTRALITY_FALLACY",
                title="Beta-neutrality fallacy (style/factor risk unaccounted)",
                severity=severity,
                score=_SEVERITY_TO_SCORE[severity],
                evidence=[
                    tok for tok in ["beta", "market-neutral", "market neutral"] if tok in text
                ][:8],
                explanation=(
                    "Beta neutrality does not imply factor neutrality. Books can blow up on momentum, junk/quality spreads, "
                    "or crowded factor rotations even with beta ~0."
                ),
                recommended_action="PM_REVIEW: require factor exposure report (momentum, size, quality, vol) and stress tests.",
            )
        ]

    def _detect_mvo_optimizer_trap(self, text: str) -> List[Flag]:
        if not any(
            tok in text
            for tok in [
                "mean-variance",
                "mean variance",
                "mvo",
                "maximize sharpe",
                "sharpe ratio",
                "optimizer",
            ]
        ):
            return []
        severity = "MEDIUM"
        return [
            Flag(
                id="MVO_OPTIMIZER_TRAP",
                title="Optimization trap (MVO / estimation error maximization)",
                severity=severity,
                score=_SEVERITY_TO_SCORE[severity],
                evidence=[
                    tok
                    for tok in ["mvo", "mean-variance", "sharpe ratio", "optimizer"]
                    if tok in text
                ][:8],
                explanation=(
                    "Mean-variance style optimizers are brittle under estimation error and can concentrate risk in illiquid names "
                    "based on spurious correlations."
                ),
                recommended_action="PM_REVIEW: prefer robust heuristics; cap position sizes; validate inputs and turnover constraints.",
            )
        ]

    def _detect_crowding_endogenous_risk(self, text: str) -> List[Flag]:
        if not any(
            tok in text
            for tok in [
                "crowded",
                "most held short",
                "#1 most held short",
                "13f",
                "short squeeze",
            ]
        ):
            return []
        severity = "MEDIUM"
        if "short squeeze" in text or "most held short" in text:
            severity = "HIGH"
        return [
            Flag(
                id="CROWDING_ENDOGENOUS_RISK",
                title="Crowding / endogenous risk (liquidity spiral, squeeze)",
                severity=severity,
                score=_SEVERITY_TO_SCORE[severity],
                evidence=[
                    tok
                    for tok in ["13f", "crowded", "most held short", "short squeeze"]
                    if tok in text
                ][:8],
                explanation=(
                    "Crowded positioning can dominate fundamentals and create endogenous risk via forced covering or liquidity spirals."
                ),
                recommended_action="PM_REVIEW: require borrow/liquidity checks, squeeze risk limits, and hedge plan.",
            )
        ]

    def _detect_liquidity_basis_mismatch(self, text: str) -> List[Flag]:
        # Example: small-cap long hedged with liquid ETF
        if (
            not any(tok in text for tok in ["small cap", "small-cap", "illiquid"])
            and "xbi" not in text
        ):
            return []
        if not any(tok in text for tok in ["hedge", "etf", "xbi"]):
            return []
        severity = "HIGH"
        return [
            Flag(
                id="LIQUIDITY_BASIS_MISMATCH",
                title="Liquidity/basis mismatch (long illiquidity vs short liquidity)",
                severity=severity,
                score=_SEVERITY_TO_SCORE[severity],
                evidence=[
                    tok
                    for tok in [
                        "xbi",
                        "small-cap",
                        "small cap",
                        "hedge",
                        "etf",
                        "illiquid",
                    ]
                    if tok in text
                ][:8],
                explanation=(
                    "ETF hedges can fail structurally in crises when small-cap liquidity disappears ('no-bid') "
                    "while the hedge remains tradable, breaking assumed correlation."
                ),
                recommended_action="PM_REVIEW: run crisis basis stress; cap gross; consider name-specific hedges where feasible.",
            )
        ]

    # ----------------------------
    # Aggregation / gating
    # ----------------------------
    def _aggregate(self, flags: List[Flag]) -> Dict[str, Any]:
        overall_sev = "NONE"
        overall_score = 0
        for f in flags:
            overall_sev = _max_severity(overall_sev, f.severity)
            overall_score = max(overall_score, f.score)

        gate_decision = "PASS"
        if overall_sev == "MEDIUM":
            gate_decision = "PM_REVIEW"
        elif overall_sev in ("HIGH", "CRITICAL"):
            gate_decision = "AUTO_REJECT"

        recommended_action = {
            "PASS": "PASS: no major red flags detected. Proceed to PM review as normal.",
            "PM_REVIEW": "PM_REVIEW: proceed, but require explicit PM signoff and risk/compliance checks for flagged items.",
            "AUTO_REJECT": "AUTO_REJECT: block execution; escalate to Compliance/PM; preserve artifacts and sources.",
        }[gate_decision]

        return {
            "severity": overall_sev,
            "score": overall_score,
            "gate_decision": gate_decision,
            "recommended_action": recommended_action,
        }
