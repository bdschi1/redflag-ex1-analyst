"""
Tests for document_loader.py

Run with: pytest tests/test_document_loader.py -v
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from document_loader import DocumentLoader, LoadResult, UnsupportedFormatError


class TestTxtLoading:
    """Test TXT file loading (backward compatibility with legacy path)."""

    def test_load_txt_file(self, sample_txt_path):
        loader = DocumentLoader()
        result = loader.load_file(sample_txt_path)
        assert result.format == "txt"
        assert "ACME Corp" in result.text
        assert result.page_count is None
        assert result.char_count > 0
        assert result.source_path == sample_txt_path

    def test_load_txt_bytes(self, sample_txt_path):
        loader = DocumentLoader()
        with open(sample_txt_path, "rb") as f:
            data = f.read()
        result = loader.load_bytes(data, "sample.txt")
        assert result.format == "txt"
        assert "ACME Corp" in result.text
        assert result.source_path is None

    def test_load_empty_txt(self, empty_txt_path):
        loader = DocumentLoader()
        result = loader.load_file(empty_txt_path)
        assert result.text == ""
        assert result.char_count == 0

    def test_load_txt_utf8_with_errors(self, tmp_dir):
        path = os.path.join(tmp_dir, "bad_utf8.txt")
        with open(path, "wb") as f:
            f.write(b"Hello \xff\xfe world")
        loader = DocumentLoader()
        result = loader.load_file(path)
        # Should not crash; errors="replace" substitutes bad bytes
        assert "Hello" in result.text
        assert "world" in result.text


class TestPdfLoading:
    """Test PDF file loading."""

    def test_load_simple_pdf(self, sample_pdf_path):
        loader = DocumentLoader()
        result = loader.load_file(sample_pdf_path)
        assert result.format == "pdf"
        assert "ACME Corp" in result.text
        assert result.page_count == 1
        assert result.char_count > 0
        assert len(result.warnings) == 0

    def test_load_multi_page_pdf(self, multi_page_pdf_path):
        loader = DocumentLoader()
        result = loader.load_file(multi_page_pdf_path)
        assert result.page_count == 3
        assert "Page 1" in result.text
        assert "Page 3" in result.text

    def test_load_pdf_bytes(self, sample_pdf_path):
        loader = DocumentLoader()
        with open(sample_pdf_path, "rb") as f:
            data = f.read()
        result = loader.load_bytes(data, "report.pdf")
        assert result.format == "pdf"
        assert "ACME Corp" in result.text
        assert result.source_path is None

    def test_load_risky_pdf(self, risky_pdf_path):
        loader = DocumentLoader()
        result = loader.load_file(risky_pdf_path)
        assert "investigator" in result.text.lower()
        assert "off the record" in result.text.lower()

    def test_load_invalid_pdf_bytes(self):
        loader = DocumentLoader()
        with pytest.raises(ValueError, match="Failed to open PDF"):
            loader.load_bytes(b"this is not a pdf", "fake.pdf")


class TestDocxLoading:
    """Test DOCX file loading."""

    def test_load_simple_docx(self, sample_docx_path):
        loader = DocumentLoader()
        result = loader.load_file(sample_docx_path)
        assert result.format == "docx"
        assert "ACME Corp" in result.text
        assert result.page_count is None
        assert result.char_count > 0

    def test_load_docx_with_table(self, docx_with_table_path):
        loader = DocumentLoader()
        result = loader.load_file(docx_with_table_path)
        assert "Revenue" in result.text
        assert "$1.5B" in result.text

    def test_load_docx_bytes(self, sample_docx_path):
        loader = DocumentLoader()
        with open(sample_docx_path, "rb") as f:
            data = f.read()
        result = loader.load_bytes(data, "report.docx")
        assert result.format == "docx"
        assert result.source_path is None

    def test_load_risky_docx(self, risky_docx_path):
        loader = DocumentLoader()
        result = loader.load_file(risky_docx_path)
        assert "investigator" in result.text.lower()

    def test_load_invalid_docx_bytes(self):
        loader = DocumentLoader()
        with pytest.raises(ValueError, match="Failed to open DOCX"):
            loader.load_bytes(b"not a docx file", "fake.docx")


class TestErrorHandling:
    """Test error handling and format validation."""

    def test_unsupported_extension(self, tmp_dir):
        path = os.path.join(tmp_dir, "data.xls")
        with open(path, "w") as f:
            f.write("data")
        loader = DocumentLoader()
        with pytest.raises(UnsupportedFormatError, match="Unsupported file format"):
            loader.load_file(path)

    def test_doc_format_gives_guidance(self, tmp_dir):
        path = os.path.join(tmp_dir, "old.doc")
        with open(path, "w") as f:
            f.write("data")
        loader = DocumentLoader()
        with pytest.raises(UnsupportedFormatError, match="convert to .docx"):
            loader.load_file(path)

    def test_nonexistent_file(self):
        loader = DocumentLoader()
        with pytest.raises(FileNotFoundError):
            loader.load_file("/nonexistent/file.txt")

    def test_load_result_char_count(self):
        result = LoadResult(text="hello world", source_path=None, format="txt", page_count=None)
        assert result.char_count == 11
