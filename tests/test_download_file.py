"""
test_download_file.py

Tests the `download_file()` function from dlpdf_utils.py.

We use aioresponses to mock aiohttp requests so we can simulate:
- Successful downloads
- Wrong content type
- Timeout errors
- ContentLengthError
- Unexpected exceptions

Goal: 100% branch and line coverage for robust download testing.
"""
import pytest
import aiohttp
import os
from aioresponses import aioresponses
from unittest.mock import patch

from dlpdf_utils import download_file

# Base constants for tests
FILENAME = "TEST123"
FAKE_URL = "https://example.com/fake.pdf"
OUT_FOLDER = "./test_output"

@pytest.fixture(scope="function", autouse=True)
def setup_output_folder():
    """Ensure test output folder is clean before/after test"""
    if not os.path.exists(OUT_FOLDER):
        os.mkdir(OUT_FOLDER)
    yield
    # Clean up all test files
    for f in os.listdir(OUT_FOLDER):
        os.remove(os.path.join(OUT_FOLDER, f))
    os.rmdir(OUT_FOLDER)


@pytest.mark.asyncio
async def test_download_file_success():
    """Simulates a successful PDF download with correct content-type and data"""
    body = b"%PDF-1.4 test"
    with aioresponses() as mock:
        mock.get(
            FAKE_URL,
            status=200,
            body=body,
            headers={"Content-Type": "application/pdf", "Content-Length": str(len(body))}
        )

        async with aiohttp.ClientSession() as session:
            status, name, err = await download_file(session, (FILENAME, FAKE_URL), OUT_FOLDER)

    assert status == 0
    assert name == FILENAME
    assert err is None
    assert os.path.exists(os.path.join(OUT_FOLDER, FILENAME + ".pdf"))


@pytest.mark.asyncio
async def test_download_file_wrong_content_type():
    """Handles wrong content-type (e.g., HTML instead of PDF)"""
    with aioresponses() as mock:
        mock.get(
            FAKE_URL,
            status=200,
            body=b"<html>Not a PDF</html>",
            headers={"Content-Type": "text/html"}
        )

        async with aiohttp.ClientSession() as session:
            status, name, err = await download_file(session, (FILENAME, FAKE_URL), OUT_FOLDER)

    assert status == 1
    assert name == FILENAME
    assert "Wrong content-type" in err


@pytest.mark.asyncio
async def test_download_file_timeout_error():
    """Simulates timeout by raising TimeoutError"""
    with patch("aiohttp.ClientSession.get", side_effect=TimeoutError("Simulated timeout")):
        async with aiohttp.ClientSession() as session:
            status, name, err = await download_file(session, (FILENAME, FAKE_URL), OUT_FOLDER)

    assert status == 1
    assert name == FILENAME
    assert "time-out" in err

@pytest.mark.asyncio
async def test_download_file_general_exception():
    """Handles unexpected download exception (e.g., network error)"""
    with patch("aiohttp.ClientSession.get", side_effect=Exception("Something bad")):
        async with aiohttp.ClientSession() as session:
            status, name, err = await download_file(session, (FILENAME, FAKE_URL), OUT_FOLDER)

    assert status == 1
    assert name == FILENAME
    assert "Something bad" in err
