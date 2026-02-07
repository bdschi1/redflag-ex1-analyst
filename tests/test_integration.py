"""
Integration tests: full pipeline from file loading through analysis.

Run with: pytest tests/test_integration.py -v
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from boilerplate_filter import BoilerplateFilter
from document_loader import DocumentLoader
from redflag_engine import RedFlagAnalyzer


class TestEndToEnd:
    """Full pipeline: load -> filter -> analyze."""

    @pytest.fixture
    def pipeline(self):
        return DocumentLoader(), BoilerplateFilter(), RedFlagAnalyzer()

    def test_txt_backward_compat(self, pipeline, sample_txt_path):
        """TXT through new pipeline produces same result as old path."""
        loader, bp_filter, analyzer = pipeline

        # New pipeline
        load_result = loader.load_file(sample_txt_path)
        filter_result = bp_filter.filter(load_result.text)
        result = analyzer.analyze(filter_result.filtered_text)

        # Should be PASS — clean note
        assert result["overall"]["gate_decision"] == "PASS"
        assert result["overall"]["severity"] == "NONE"

    def test_risky_txt_end_to_end(self, pipeline, risky_txt_path):
        loader, bp_filter, analyzer = pipeline
        load_result = loader.load_file(risky_txt_path)
        filter_result = bp_filter.filter(load_result.text)
        result = analyzer.analyze(filter_result.filtered_text)
        assert result["overall"]["gate_decision"] == "AUTO_REJECT"

    def test_pdf_end_to_end(self, pipeline, sample_pdf_path):
        loader, bp_filter, analyzer = pipeline
        load_result = loader.load_file(sample_pdf_path)
        assert load_result.format == "pdf"
        filter_result = bp_filter.filter(load_result.text)
        result = analyzer.analyze(filter_result.filtered_text)
        assert result["overall"]["gate_decision"] == "PASS"

    def test_risky_pdf_end_to_end(self, pipeline, risky_pdf_path):
        loader, bp_filter, analyzer = pipeline
        load_result = loader.load_file(risky_pdf_path)
        filter_result = bp_filter.filter(load_result.text)
        result = analyzer.analyze(filter_result.filtered_text)
        # Must catch the MNPI flags even from a PDF
        assert result["overall"]["gate_decision"] == "AUTO_REJECT"
        flag_ids = [f["id"] for f in result["flags"]]
        assert "MNPI_TIPPING_RISK" in flag_ids

    def test_docx_end_to_end(self, pipeline, sample_docx_path):
        loader, bp_filter, analyzer = pipeline
        load_result = loader.load_file(sample_docx_path)
        assert load_result.format == "docx"
        filter_result = bp_filter.filter(load_result.text)
        result = analyzer.analyze(filter_result.filtered_text)
        assert result["overall"]["gate_decision"] == "PASS"

    def test_risky_docx_end_to_end(self, pipeline, risky_docx_path):
        loader, bp_filter, analyzer = pipeline
        load_result = loader.load_file(risky_docx_path)
        filter_result = bp_filter.filter(load_result.text)
        result = analyzer.analyze(filter_result.filtered_text)
        assert result["overall"]["gate_decision"] == "AUTO_REJECT"

    def test_pdf_with_boilerplate_still_catches_risk(self, pipeline, pdf_with_boilerplate_path):
        """
        Golden test: a PDF with both boilerplate disclaimers AND risky MNPI
        content. The filter should strip the boilerplate but preserve the
        risky content, so the engine still flags it.
        """
        loader, bp_filter, analyzer = pipeline
        load_result = loader.load_file(pdf_with_boilerplate_path)

        # Filter should remove some boilerplate
        filter_result = bp_filter.filter(load_result.text)

        # But the engine should still catch the MNPI
        result = analyzer.analyze(filter_result.filtered_text)
        assert result["overall"]["gate_decision"] == "AUTO_REJECT"
        flag_ids = [f["id"] for f in result["flags"]]
        assert "MNPI_TIPPING_RISK" in flag_ids

    def test_no_filter_flag(self, pipeline, pdf_with_boilerplate_path):
        """Test that skipping the filter still works end to end."""
        loader, _, analyzer = pipeline
        load_result = loader.load_file(pdf_with_boilerplate_path)
        # Skip filter, use raw text
        result = analyzer.analyze(load_result.text)
        assert result["overall"]["gate_decision"] == "AUTO_REJECT"


class TestExistingExamples:
    """Verify existing example files still produce correct results through the new pipeline."""

    @pytest.fixture
    def pipeline(self):
        return DocumentLoader(), BoilerplateFilter(), RedFlagAnalyzer()

    def _run(self, pipeline, path):
        loader, bp_filter, analyzer = pipeline
        load_result = loader.load_file(path)
        filter_result = bp_filter.filter(load_result.text)
        return analyzer.analyze(filter_result.filtered_text)

    def test_example_clean(self, pipeline):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples",
            "analyst_note_clean.txt",
        )
        if not os.path.exists(path):
            pytest.skip("Example file not found")
        result = self._run(pipeline, path)
        assert result["overall"]["gate_decision"] in ("PASS", "PM_REVIEW")

    def test_example_risky(self, pipeline):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples",
            "analyst_note_risky.txt",
        )
        if not os.path.exists(path):
            pytest.skip("Example file not found")
        result = self._run(pipeline, path)
        assert result["overall"]["gate_decision"] == "AUTO_REJECT"
