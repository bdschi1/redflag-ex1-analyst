"""
boilerplate_filter.py

Strip standard institutional research boilerplate / legal disclaimers
from analyst notes before they reach the RedFlag detection engine.

Design goals:
- Conservative: when in doubt, KEEP the text (never hide real risk content).
- Protected-keyword safety net: any paragraph containing an engine-vocabulary
  risk keyword is never removed, even if it matches a boilerplate pattern.
- On by default, fully configurable / disableable.
- Produces an audit trail of what was removed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Protected keywords — drawn from redflag_engine.DEFAULT_THRESHOLDS
# Any paragraph containing one of these is NEVER stripped.
# ---------------------------------------------------------------------------
DEFAULT_PROTECTED_KEYWORDS: list[str] = [
    # MNPI / tipping
    "friend",
    "investigator",
    "off the record",
    "not public",
    "leak",
    "insider",
    "told me",
    "said things look good",
    "preliminary results",
    # Options / leverage
    "naked call",
    "naked calls",
    "maximize leverage",
    "max leverage",
    "near max risk",
    # Cross-border / inducements
    "soft dollar",
    "soft dollars",
    "corporate access",
    "mifid",
    "inducement",
    # Crowding / positioning
    "crowded",
    "most held short",
    "short squeeze",
    "13f",
]

# ---------------------------------------------------------------------------
# Boilerplate section headers (case-insensitive)
# When one of these is detected as a section header, everything from that
# line until the next substantive header (or EOF) is removed.
# ---------------------------------------------------------------------------
_BOILERPLATE_SECTION_HEADERS: list[str] = [
    r"important\s+disclosures?",
    r"analyst\s+certifications?",
    r"required\s+disclosures?",
    r"general\s+disclosures?",
    r"legal\s+disclos",
    r"conflicts?\s+of\s+interest",
    r"distribution\s+restrictions?",
    r"regulatory\s+disclos",
    r"terms\s+of\s+use",
    r"disclaimers?",
]

_SUBSTANTIVE_SECTION_HEADERS: list[str] = [
    r"(?:investment\s+)?thesis",
    r"executive\s+summary",
    r"summary",
    r"key\s+(?:points?|findings?|insights?|takeaways?)",
    r"recommendations?",
    r"valuations?",
    r"risks?(?:\s+factors?)?",
    r"catalysts?",
    r"(?:financial\s+)?model",
    r"appendix",
    r"methodology",
    r"overview",
    r"analysis",
    r"conclusion",
]

# ---------------------------------------------------------------------------
# Paragraph-level boilerplate patterns, grouped by category.
# Each pattern is matched case-insensitively against individual paragraphs.
# ---------------------------------------------------------------------------
_DISCLAIMER_PATTERNS: list[str] = [
    r"this\s+(?:report|material|document|publication)\s+is\s+(?:for|intended\s+for)\s+institutional\s+(?:investors?|clients?)\s+only",
    r"past\s+performance\s+is\s+not\s+(?:indicative|a\s+guarantee|necessarily\s+indicative)\s+of\s+future\s+results",
    r"the\s+information\s+(?:herein|contained\s+herein|in\s+this\s+report)\s+is\s+believed\s+to\s+be\s+reliable",
    r"this\s+(?:report|material)\s+(?:does\s+not|is\s+not\s+intended\s+to)\s+(?:constitute|provide)\s+(?:investment|legal|tax)\s+advice",
    r"no\s+representation\s+or\s+warranty.*?(?:accuracy|completeness|reliability)",
    r"(?:we|the\s+author|this\s+firm)\s+(?:do(?:es)?\s+not|cannot)\s+(?:guarantee|warrant|assure)",
    r"investing\s+involves?\s+(?:risk|risks|substantial\s+risk)",
    r"(?:you\s+should|investors?\s+should)\s+(?:consult|seek)\s+(?:your\s+own|independent|professional)\s+(?:financial|legal|tax)\s+advi",
]

_CERTIFICATION_PATTERNS: list[str] = [
    r"i(?:,?\s+\w+(?:\s+\w+)?,?)?\s+hereby\s+certify\s+that",
    r"the\s+views?\s+expressed\s+(?:herein|in\s+this\s+(?:report|research))\s+accurately\s+reflect",
    r"(?:my|our)\s+compensation\s+(?:is|was)\s+not.*?(?:related|tied|linked)\s+to",
    r"(?:the\s+)?analyst(?:s)?\s+(?:certif|responsible\s+for)",
]

_DISTRIBUTION_PATTERNS: list[str] = [
    r"this\s+(?:report|material|document)\s+(?:may\s+not|should\s+not)\s+be\s+(?:reproduced|distributed|copied|forwarded)",
    r"(?:not\s+for\s+)?distribution\s+(?:in|to)\s+(?:the\s+)?(?:united\s+states|u\.?s\.?|japan|australia)",
    r"(?:intended\s+for|restricted\s+to)\s+(?:professional|qualified|accredited|eligible)\s+investors?\s+only",
    r"do\s+not\s+(?:forward|distribute|copy|reproduce)\s+this\s+(?:report|material|document)",
]

_REGULATORY_PATTERNS: list[str] = [
    r"(?:registered|regulated)\s+(?:with|by)\s+(?:the\s+)?(?:sec|finra|fca|bafin|amf|esma)",
    r"member\s+(?:of\s+)?(?:finra|sipc|nfa)",
    r"(?:authorized|regulated)\s+(?:and\s+regulated\s+)?by\s+the\s+financial\s+conduct\s+authority",
    r"(?:securities|investment)\s+(?:offered|provided)\s+through\s+.{5,60}(?:llc|inc|ltd|plc)",
]

_CONFIDENTIALITY_PATTERNS: list[str] = [
    r"this\s+(?:material|document|email|message|communication)\s+is\s+(?:strictly\s+)?confidential",
    r"if\s+you\s+(?:have\s+)?received\s+this\s+(?:in\s+error|by\s+mistake)",
    r"(?:proprietary|confidential)\s+(?:and\s+)?(?:not\s+for\s+)?(?:distribution|redistribution|public\s+use)",
]

_COPYRIGHT_PATTERNS: list[str] = [
    r"(?:\u00a9|copyright)\s*(?:\d{4})",
    r"all\s+rights\s+reserved",
]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
@dataclass
class BoilerplateFilterConfig:
    """Configuration for the boilerplate filter."""

    enabled: bool = True
    strip_disclaimers: bool = True
    strip_certifications: bool = True
    strip_distribution_notices: bool = True
    strip_regulatory_notices: bool = True
    strip_confidentiality_notices: bool = True
    strip_copyright_notices: bool = True
    custom_patterns: list[str] = field(default_factory=list)
    protected_keywords: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------
@dataclass
class FilterResult:
    """Result of boilerplate filtering."""

    filtered_text: str
    original_length: int
    filtered_length: int
    sections_removed: list[str]
    chars_removed: int


# ---------------------------------------------------------------------------
# Filter implementation
# ---------------------------------------------------------------------------
class BoilerplateFilter:
    """
    Remove standard institutional research boilerplate from analyst notes.

    Conservative by design: only removes clearly boilerplate content.
    When in doubt, keeps the text.
    """

    def __init__(self, config: BoilerplateFilterConfig | None = None) -> None:
        self._config = config or BoilerplateFilterConfig()
        self._paragraph_patterns = self._build_paragraph_patterns()
        self._protected = self._build_protected_keywords()

        # Pre-compile section header regexes
        self._boilerplate_header_re = re.compile(
            r"^\s*(?:" + "|".join(_BOILERPLATE_SECTION_HEADERS) + r")\s*:?\s*$",
            re.IGNORECASE | re.MULTILINE,
        )
        self._substantive_header_re = re.compile(
            r"^\s*(?:" + "|".join(_SUBSTANTIVE_SECTION_HEADERS) + r")\s*:?\s*$",
            re.IGNORECASE | re.MULTILINE,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def filter(self, text: str) -> FilterResult:
        """Strip boilerplate from *text* and return a FilterResult."""
        original_length = len(text)

        if not self._config.enabled or not text.strip():
            return FilterResult(
                filtered_text=text,
                original_length=original_length,
                filtered_length=len(text),
                sections_removed=[],
                chars_removed=0,
            )

        sections_removed: list[str] = []

        # Pass 1 — section-level removal
        text = self._remove_boilerplate_sections(text, sections_removed)

        # Pass 2 — paragraph-level pattern matching
        text = self._remove_boilerplate_paragraphs(text, sections_removed)

        # Clean up excessive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

        filtered_length = len(text)
        return FilterResult(
            filtered_text=text,
            original_length=original_length,
            filtered_length=filtered_length,
            sections_removed=sections_removed,
            chars_removed=original_length - filtered_length,
        )

    # ------------------------------------------------------------------
    # Pass 1: section-level removal
    # ------------------------------------------------------------------

    def _remove_boilerplate_sections(self, text: str, sections_removed: list[str]) -> str:
        """Remove entire sections that start with boilerplate headers."""
        lines = text.split("\n")
        result_lines: list[str] = []
        in_boilerplate_section = False
        current_section_header = ""

        for line in lines:
            stripped = line.strip()

            # Check if this line is a boilerplate section header
            if self._boilerplate_header_re.match(stripped):
                # Check protected keywords in the header itself (unlikely but safe)
                if not self._contains_protected_keyword(stripped):
                    in_boilerplate_section = True
                    current_section_header = stripped
                    continue

            # Check if a substantive header ends the boilerplate section
            if in_boilerplate_section and self._substantive_header_re.match(stripped):
                in_boilerplate_section = False
                if current_section_header:
                    sections_removed.append(f"section:{current_section_header}")
                    current_section_header = ""

            if in_boilerplate_section:
                # Still check protected keywords — if found, stop removing
                if self._contains_protected_keyword(stripped):
                    in_boilerplate_section = False
                    if current_section_header:
                        sections_removed.append(f"section:{current_section_header}")
                        current_section_header = ""
                    result_lines.append(line)
                # Otherwise skip this line (it's part of a boilerplate section)
                continue

            result_lines.append(line)

        # If we ended while still in a boilerplate section, record it
        if in_boilerplate_section and current_section_header:
            sections_removed.append(f"section:{current_section_header}")

        return "\n".join(result_lines)

    # ------------------------------------------------------------------
    # Pass 2: paragraph-level pattern matching
    # ------------------------------------------------------------------

    def _remove_boilerplate_paragraphs(self, text: str, sections_removed: list[str]) -> str:
        """Remove individual paragraphs that match boilerplate patterns."""
        if not self._paragraph_patterns:
            return text

        paragraphs = re.split(r"\n\s*\n", text)
        kept: list[str] = []

        for para in paragraphs:
            stripped = para.strip()
            if not stripped:
                continue

            # Never remove paragraphs containing protected keywords
            if self._contains_protected_keyword(stripped):
                kept.append(para)
                continue

            # Check if this paragraph matches any boilerplate pattern
            lower = stripped.lower()
            matched_category = self._match_boilerplate(lower)
            if matched_category:
                sections_removed.append(f"paragraph:{matched_category}")
                continue

            kept.append(para)

        return "\n\n".join(kept)

    # ------------------------------------------------------------------
    # Pattern building and matching
    # ------------------------------------------------------------------

    def _build_paragraph_patterns(self) -> list[tuple[re.Pattern[str], str]]:
        """Build compiled regex patterns grouped by category."""
        patterns: list[tuple[re.Pattern[str], str]] = []
        cfg = self._config

        category_map: list[tuple[bool, list[str], str]] = [
            (cfg.strip_disclaimers, _DISCLAIMER_PATTERNS, "disclaimer"),
            (cfg.strip_certifications, _CERTIFICATION_PATTERNS, "certification"),
            (cfg.strip_distribution_notices, _DISTRIBUTION_PATTERNS, "distribution"),
            (cfg.strip_regulatory_notices, _REGULATORY_PATTERNS, "regulatory"),
            (
                cfg.strip_confidentiality_notices,
                _CONFIDENTIALITY_PATTERNS,
                "confidentiality",
            ),
            (cfg.strip_copyright_notices, _COPYRIGHT_PATTERNS, "copyright"),
        ]

        for enabled, raw_patterns, category in category_map:
            if not enabled:
                continue
            for pat_str in raw_patterns:
                patterns.append((re.compile(pat_str, re.IGNORECASE), category))

        # Add custom patterns
        for pat_str in cfg.custom_patterns:
            patterns.append((re.compile(pat_str, re.IGNORECASE), "custom"))

        return patterns

    def _build_protected_keywords(self) -> list[str]:
        """Combine default + user-supplied protected keywords."""
        keywords = list(DEFAULT_PROTECTED_KEYWORDS)
        keywords.extend(self._config.protected_keywords)
        return [kw.lower() for kw in keywords]

    def _contains_protected_keyword(self, text: str) -> bool:
        """Return True if *text* contains any protected keyword."""
        lower = text.lower()
        return any(kw in lower for kw in self._protected)

    def _match_boilerplate(self, lower_text: str) -> str | None:
        """Return the category name if *lower_text* matches a boilerplate pattern."""
        for compiled, category in self._paragraph_patterns:
            if compiled.search(lower_text):
                return category
        return None
