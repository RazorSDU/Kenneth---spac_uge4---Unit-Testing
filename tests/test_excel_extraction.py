"""
test_excel_extraction.py

Unit tests for Excel-related functions from dlpdf_utils.py:
- get_num_links_from_excel
- extract_report_names

Goal: Maximize code coverage by testing all possible outcomes (empty file, valid data, invalid URLs, etc.)
"""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

from dlpdf_utils import get_num_links_from_excel, extract_report_names


# ────────────────────────────────────────────────────────────────────────────────
# get_num_links_from_excel
# ────────────────────────────────────────────────────────────────────────────────

@patch("dlpdf_utils.os.path.exists", return_value=False)
def test_get_num_links_file_missing(mock_exists):
    """Returns 0 when file does not exist"""
    assert get_num_links_from_excel("non_existing.xlsx") == 0


@patch("dlpdf_utils.os.path.exists", return_value=True)
@patch("dlpdf_utils.pd.read_excel")
def test_get_num_links_returns_correct_count(mock_read_excel, mock_exists):
    """Returns correct count based on Excel BRnum column"""
    mock_df = pd.DataFrame({"BRnum": [101, 102, 103]})
    mock_read_excel.return_value = mock_df

    count = get_num_links_from_excel("fake.xlsx")
    assert count == 3


# ────────────────────────────────────────────────────────────────────────────────
# extract_report_names
# ────────────────────────────────────────────────────────────────────────────────

@patch("dlpdf_utils.os.path.exists", return_value=False)
def test_extract_report_names_file_not_found(mock_exists):
    """Raises FileNotFoundError if Excel is missing"""
    with pytest.raises(FileNotFoundError):
        list(extract_report_names("missing.xlsx"))


@patch("dlpdf_utils.os.path.exists", return_value=True)
@patch("dlpdf_utils.pd.read_excel")
def test_extract_report_names_with_valid_links(mock_read_excel, mock_exists):
    """Returns cleaned (BRnum, URL) pairs if links are valid"""
    mock_df = pd.DataFrame({
        "BRnum": [123],
        "Pdf_URL": ["example.com/file1.pdf"],
        "Report Html Address": ["file://should_be_ignored"]
    })
    mock_read_excel.return_value = mock_df

    results = list(extract_report_names("test.xlsx"))

    assert len(results) == 1
    assert results[0] == ("123", "https://example.com/file1.pdf")


@patch("dlpdf_utils.os.path.exists", return_value=True)
@patch("dlpdf_utils.pd.read_excel")
def test_extract_report_names_multiple_valid_links(mock_read_excel, mock_exists):
    """Handles both PDF and HTML links if valid"""
    mock_df = pd.DataFrame({
        "BRnum": [999],
        "Pdf_URL": ["example.com/abc.pdf"],
        "Report Html Address": ["another.com/report"]
    })
    mock_read_excel.return_value = mock_df

    results = list(extract_report_names("test.xlsx"))
    expected = [("999", "https://example.com/abc.pdf"), ("999", "https://another.com/report")]

    assert results == expected


@patch("dlpdf_utils.os.path.exists", return_value=True)
@patch("dlpdf_utils.pd.read_excel")
def test_extract_report_names_handles_empty_links(mock_read_excel, mock_exists):
    """Skips None or invalid links from Excel"""
    mock_df = pd.DataFrame({
        "BRnum": [444],
        "Pdf_URL": [float("nan")],
        "Report Html Address": [".invalid.com"]
    })
    mock_read_excel.return_value = mock_df

    results = list(extract_report_names("test.xlsx"))

    # Only one valid link expected
    assert results == [("444", "https://invalid.com")]
