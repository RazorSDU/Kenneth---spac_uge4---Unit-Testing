"""
test_patch_url.py

This module tests the patch_url() function from dlpdf_utils.py to ensure all edge cases and transformation
rules are handled correctly. The goal is to reach 100% code coverage and validate all expected outcomes
for valid and invalid input cases.
"""
import pytest
import math
from dlpdf_utils import patch_url  # Clean import for single-project setup

# ────────────────────────────────────────────────────────────────────────────────
# Group 1: Tests for invalid or ignorable input values
# ────────────────────────────────────────────────────────────────────────────────

def test_patch_url_returns_none_for_float():
    """Test that a float input (e.g., from empty Excel cells) returns None"""
    assert patch_url(float("nan")) is None
    assert patch_url(1.23) is None

def test_patch_url_returns_none_for_file_scheme():
    """Test that file:// links are ignored and return None"""
    assert patch_url("file://some/local/path") is None

# ────────────────────────────────────────────────────────────────────────────────
# Group 2: Tests for HTML-embedded links
# ────────────────────────────────────────────────────────────────────────────────

def test_patch_url_extracts_from_html_anchor():
    """Test that embedded <a href=""> links are parsed correctly"""
    input_url = '<a href="https://example.com/mydoc.pdf">'
    expected = "https://example.com/mydoc.pdf"
    assert patch_url(input_url) == expected

# ────────────────────────────────────────────────────────────────────────────────
# Group 3: Tests for fixing malformed links
# ────────────────────────────────────────────────────────────────────────────────

def test_patch_url_removes_leading_dot():
    """Test that links starting with a dot are corrected"""
    input_url = ".https://dotstart.com/resource.pdf"
    expected = "https://dotstart.com/resource.pdf"
    assert patch_url(input_url) == expected

def test_patch_url_adds_https_if_missing():
    """Test that links without scheme get 'https://' prepended"""
    input_url = "example.com/thing.pdf"
    expected = "https://example.com/thing.pdf"
    assert patch_url(input_url) == expected

# ────────────────────────────────────────────────────────────────────────────────
# Group 4: Test fully valid and already well-formed links
# ────────────────────────────────────────────────────────────────────────────────

def test_patch_url_leaves_valid_url_unchanged():
    """Test that fully valid URLs are not modified"""
    input_url = "https://already.good/path/to/file.pdf"
    assert patch_url(input_url) == input_url

# ────────────────────────────────────────────────────────────────────────────────
# Group 5: Combined edge cases
# ────────────────────────────────────────────────────────────────────────────────

def test_patch_url_combined_html_and_dot():
    """Test a link that is embedded in HTML and starts with a dot"""
    input_url = '<a href=".example.com/doc.pdf">'
    expected = "https://example.com/doc.pdf"
    assert patch_url(input_url) == expected

def test_patch_url_weird_malformed_html_but_valid():
    """Test an edge case with slightly malformed but valid anchor"""
    input_url = '<a href="http://weird.net/paper">'
    expected = "http://weird.net/paper"
    assert patch_url(input_url) == expected

def test_patch_url_html_with_extra_suffix_ignored():
    """Ensure that only the content inside href is used"""
    input_url = '<a href="http://a.com/x.pdf">junk extra here'
    expected = "http://a.com/x.pdf"
    assert patch_url(input_url) == expected

# ────────────────────────────────────────────────────────────────────────────────

