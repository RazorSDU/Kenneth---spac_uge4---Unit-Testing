# test_original_requirements.py

import pytest
from pathlib import Path
import asyncio
import os
import pandas as pd
from unittest.mock import patch, AsyncMock, MagicMock

import dlpdf  # from dlpdf.py, in the same directory or your PYTHONPATH

# We'll call dlpdf.download_all_files() in each test, but
# we ensure the code sees the small test Excel path, not the giant default.

@pytest.mark.asyncio
async def test_alternative_link_first_fails_second_succeeds(tmp_path):
    """
    #1: If the first link fails, does the code try the second link?

    We create an XLSX with 1 row:
      - Pdf_URL => broken
      - Report Html Address => valid

    Then mock the first link to fail, second link to succeed.
    """
    # 1) Create a 1-row DataFrame
    df = pd.DataFrame({
        "BRnum": [123],
        "Pdf_URL": ["https://broken-link.example.com/does_not_exist.pdf"],
        "Report Html Address": ["https://example.com/real.pdf"]
    }, dtype=object)
    test_excel = tmp_path / "test.xlsx"
    df.to_excel(test_excel, index=False)

    # 2) Patch the dlpdf.py variables
    with patch("dlpdf.excel_file", str(test_excel)), \
         patch("dlpdf.output_folder", str(tmp_path)):

        # 3) Mock session.get
        async def mock_get(url, *args, **kwargs):
            mock_response = AsyncMock()
            mock_response.__aenter__.return_value = mock_response
            mock_response.__aexit__.return_value = None

            if "broken-link" in url:
                # Simulate broken/404
                raise Exception("Simulated broken link")
            else:
                # Good link => PDF content
                mock_response.content_type = "application/pdf"
                mock_response.content_length = 100

                # Provide an async generator for chunked PDF data
                async def iter_any():
                    yield b"%PDF-some-data"
                mock_response.content = MagicMock(iter_any=iter_any)
            return mock_response

        with patch("aiohttp.ClientSession.get", side_effect=mock_get):
            await dlpdf.download_all_files()

    # 4) Assert that "123.pdf" got created => fallback link was used
    out_file = tmp_path / "123.pdf"
    assert out_file.exists(), (
        "The second (fallback) link was never tried or the file didn't download."
    )


@pytest.mark.asyncio
async def test_download_file_naming(tmp_path):
    """
    #2: If a link is valid, the downloaded PDF must be named {BRnum}.pdf.
    """
    df = pd.DataFrame({
        "BRnum": [999],
        "Pdf_URL": ["https://example.com/dummy.pdf"],
        "Report Html Address": [None]
    }, dtype=object)
    test_excel = tmp_path / "test.xlsx"
    df.to_excel(test_excel, index=False)

    out_file = tmp_path / "999.pdf"

    # Patch dlpdf to use the test excel and output dir
    dlpdf.excel_file = str(test_excel)
    dlpdf.output_folder = str(tmp_path)

    async def mock_get(url, *args, **kwargs):
        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_response.content_type = "application/pdf"
        mock_response.content_length = 100

        async def iter_any():
            yield b"%PDF-some-data"

        mock_response.content = AsyncMock()
        mock_response.content.iter_any = iter_any

        return mock_response

    with patch("aiohttp.ClientSession.get", side_effect=mock_get), \
        patch("os.getcwd", return_value=str(tmp_path)):
        await dlpdf.download_all_files()


    assert out_file.exists(), (
        f"Missing file: {out_file} --- Files found: {[f.name for f in tmp_path.glob('*.pdf')]}"
    )


@pytest.mark.asyncio
async def test_logging_downloaded_vs_not_downloaded(tmp_path):
    """
    #3: We want a final 'report.csv' showing 0 for success, 1 for error.

    We'll have 2 rows: one link is good, one fails => 
    check the log in 'report.csv'.
    """
    df = pd.DataFrame({
        "BRnum": [101, 102],
        "Pdf_URL": ["https://example.com/good.pdf",
                    "https://bad-link.example.com/fail.pdf"],
        "Report Html Address": [None, None]
    }, dtype=object)
    test_excel = tmp_path / "test.xlsx"
    df.to_excel(test_excel, index=False)

    with patch("dlpdf.excel_file", str(test_excel)), \
         patch("dlpdf.output_folder", str(tmp_path)), \
         patch("os.getcwd", return_value=str(tmp_path)):

         async def mock_get(url, *args, **kwargs):
             # Make an async mock for the response
             mock_response = AsyncMock()
             # Make sure __aenter__ and __aexit__ are async
             mock_response.__aenter__.return_value = mock_response
             mock_response.__aexit__.return_value = None
         
             # Then set the relevant attributes (content_type, content_length, etc.)
             mock_response.content_type = "application/pdf"
             mock_response.content_length = 100
         
             # If you need chunk iteration, define an async generator:
             async def iter_any():
                 yield b"%PDF-some-data"
         
             # Then attach it as well:
             mock_response.content = MagicMock(iter_any=iter_any)
             return mock_response
         
         with patch("aiohttp.ClientSession.get", new=AsyncMock(side_effect=mock_get)):
             await dlpdf.download_all_files()
    
    assert (tmp_path / "101.pdf").exists(), "Expected 101.pdf was not downloaded."

    # Check the final 'report.csv'
    report_csv = Path("report.csv")
    assert report_csv.exists(), "No 'report.csv' created."

    content = report_csv.read_text("utf-8")
    # Expect "0\t101" for success, "1\t102" for fail
    assert "0\t101\n" in content, "No success log for 101."
    assert "1\t102" in content, "No fail log for 102."


@pytest.mark.asyncio
async def test_wrong_content_type(tmp_path):
    """
    #4: If the server responds with non-PDF content_type, it's an error.
    """
    df = pd.DataFrame({
        "BRnum": [202],
        "Pdf_URL": ["https://example.com/html_link"],
        "Report Html Address": [None]
    }, dtype=object)
    test_excel = tmp_path / "test.xlsx"
    df.to_excel(test_excel, index=False)

    with patch("dlpdf.excel_file", str(test_excel)), \
         patch("dlpdf.output_folder", str(tmp_path)):

         async def mock_get(url, *args, **kwargs):
             # Make an async mock for the response
             mock_response = AsyncMock()
             # Make sure __aenter__ and __aexit__ are async
             mock_response.__aenter__.return_value = mock_response
             mock_response.__aexit__.return_value = None
         
             # Then set the relevant attributes (content_type, content_length, etc.)
             mock_response.content_type = "application/pdf"
             mock_response.content_length = 100
         
             # If you need chunk iteration, define an async generator:
             async def iter_any():
                 yield b"%PDF-some-data"
         
             # Then attach it as well:
             mock_response.content = MagicMock(iter_any=iter_any)
             return mock_response
         
         with patch("aiohttp.ClientSession.get", side_effect=mock_get):
             await dlpdf.download_all_files()

    report_csv = Path("report.csv")
    assert report_csv.exists(), "Expected 'report.csv' not found."

    content = report_csv.read_text("utf-8")
    # Because it wasn't PDF, it should be marked as an error => "1\t202"
    assert "1\t202" in content, "Should log an error for BRnum=202 with wrong content-type."


@pytest.mark.asyncio
async def test_developer_mode_large_file(tmp_path):
    """
    #5: If developer_mode is True and content_length>8192, code writes 'X' instead of real data.
    """
    df = pd.DataFrame({
        "BRnum": [300],
        "Pdf_URL": ["https://example.com/large.pdf"],
        "Report Html Address": [None]
    }, dtype=object)
    test_excel = tmp_path / "test.xlsx"
    df.to_excel(test_excel, index=False)

    with patch("dlpdf.excel_file", str(test_excel)), \
         patch("dlpdf.output_folder", str(tmp_path)):

         async def mock_get(url, *args, **kwargs):
             # Make an async mock for the response
             mock_response = AsyncMock()
             # Make sure __aenter__ and __aexit__ are async
             mock_response.__aenter__.return_value = mock_response
             mock_response.__aexit__.return_value = None
         
             # Then set the relevant attributes (content_type, content_length, etc.)
             mock_response.content_type = "application/pdf"
             mock_response.content_length = 99999
         
             # If you need chunk iteration, define an async generator:
             async def iter_any():
                 yield b"%PDF-some-data"
         
             # Then attach it as well:
             mock_response.content = MagicMock(iter_any=iter_any)
             return mock_response
         
         with patch("aiohttp.ClientSession.get", side_effect=mock_get):
             await dlpdf.download_all_files()

    out_file = tmp_path / "300.pdf"
    assert out_file.exists(), "No file written for large PDF in dev mode."

    size = out_file.stat().st_size
    assert size == 99999, (
        f"Developer mode should fill with X => 99999 bytes, got {size} bytes."
    )


@pytest.mark.asyncio
async def test_timeout_content_length_retry(tmp_path):
    """
    #6: If ContentLengthError or TimeoutError occurs, does the code attempt a retry?
    We'll simulate first attempt => ContentLengthError, second => success.
    """
    df = pd.DataFrame({
        "BRnum": [401],
        "Pdf_URL": ["https://example.com/content_length_bug"],
        "Report Html Address": [None]
    }, dtype=object)
    test_excel = tmp_path / "test.xlsx"
    df.to_excel(test_excel, index=False)

    from aiohttp.http_exceptions import ContentLengthError
    call_count = {"calls": 0}

    async def mock_get(url, *args, **kwargs):
        # first time => ContentLengthError, second => success
        if call_count["calls"] == 0:
            call_count["calls"] += 1
            raise ContentLengthError("Simulated mismatch")
        else:
            mock_response = AsyncMock()
            mock_response.__aenter__.return_value = mock_response
            mock_response.__aexit__.return_value = None

            mock_response.content_type = "application/pdf"
            mock_response.content_length = 50
            async def iter_any():
                yield b"%PDF-second-try"
            mock_response.content = MagicMock(iter_any=iter_any)
            return mock_response

    with patch("dlpdf.excel_file", str(test_excel)), \
         patch("dlpdf.output_folder", str(tmp_path)), \
         patch("aiohttp.ClientSession.get", side_effect=mock_get):
        await dlpdf.download_all_files()

    # If the code truly retries, second attempt should succeed => file created
    out_file = tmp_path / "401.pdf"
    assert out_file.exists(), "After ContentLengthError, no retry or no success on second attempt."


@pytest.mark.asyncio
async def test_empty_excel_no_rows(tmp_path):
    """
    #7: If Excel is empty (0 rows), we expect 0 downloads and no crash.
    """
    df = pd.DataFrame(columns=["BRnum", "Pdf_URL", "Report Html Address"])
    test_excel = tmp_path / "test.xlsx"
    df.to_excel(test_excel, index=False)

    with patch("dlpdf.excel_file", str(test_excel)), \
         patch("dlpdf.output_folder", str(tmp_path)), \
         patch("aiohttp.ClientSession.get") as mock_get:
        await dlpdf.download_all_files()
        # No rows => should not call 'get' at all
        mock_get.assert_not_called()

    # Possibly also check "report.csv" was created (could be empty)
    report_csv = Path("report.csv")
    assert report_csv.exists(), "Expected an empty 'report.csv' with 0 rows, but none found."


@pytest.mark.asyncio
async def test_missing_columns(tmp_path):
    """
    #8: If columns (like BRnum) are missing, code should raise KeyError or handle it.

    We'll intentionally omit 'BRnum'.
    """
    # We'll have just "Pdf_URL" and "Report Html Address" columns
    df = pd.DataFrame({
        "Pdf_URL": ["https://example.com/pdf1"],
        "Report Html Address": ["https://example.com/pdf2"]
    }, dtype=object)
    test_excel = tmp_path / "test.xlsx"
    df.to_excel(test_excel, index=False)

    with patch("dlpdf.excel_file", str(test_excel)), \
         patch("dlpdf.output_folder", str(tmp_path)), \
        patch("os.getcwd", return_value=str(tmp_path)):
        with pytest.raises(KeyError):
            await dlpdf.download_all_files()


@pytest.mark.asyncio
async def test_prototype_only_downloads_10(tmp_path):
    """
    #9: If the code truly respects "download at most 10" in a prototype scenario,
    let's provide 12 rows. If the code tries all 12, the test fails.
    """
    brnums = list(range(1000, 1012))  # 12 items
    df = pd.DataFrame({
        "BRnum": brnums,
        "Pdf_URL": [f"https://example.com/fake{i}.pdf" for i in range(12)],
        "Report Html Address": [None]*12
    }, dtype=object)
    test_excel = tmp_path / "test.xlsx"
    df.to_excel(test_excel, index=False)

    # We'll do a simple success mock
    async def mock_get(url, *args, **kwargs):
        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_response.content_type = "application/pdf"
        mock_response.content_length = 10

        async def iter_any():
            yield b"%PDF-something"
        mock_response.content = MagicMock(iter_any=iter_any)
        return mock_response

    with patch("dlpdf.excel_file", str(test_excel)), \
         patch("dlpdf.output_folder", str(tmp_path)), \
         patch("os.getcwd", return_value=str(tmp_path)), \
         patch("aiohttp.ClientSession.get", side_effect=mock_get):
        await dlpdf.download_all_files()

    # Check how many actually got saved
    pdfs = list(tmp_path.glob("*.pdf"))
    assert len(pdfs) <= 10, (
        f"We expected at most 10 in prototype mode, found {len(pdfs)}"
    )


@pytest.mark.asyncio
async def test_unresponsive_url_timeout(tmp_path):
    """
    #10: If the URL never responds, code should eventually time out & log an error.
    """
    df = pd.DataFrame({
        "BRnum": [555],
        "Pdf_URL": ["https://unresponsive.example.com/hang"],
        "Report Html Address": [None]
    }, dtype=object)
    test_excel = tmp_path / "test.xlsx"
    df.to_excel(test_excel, index=False)

    async def mock_get(url, *args, **kwargs):
        # Just never return => infinite hang unless code times out
        await asyncio.sleep(9999)

    with patch("dlpdf.excel_file", str(test_excel)), \
         patch("dlpdf.output_folder", str(tmp_path)), \
         patch("os.getcwd", return_value=str(tmp_path)), \
         patch("aiohttp.ClientSession.get", side_effect=mock_get):
        await dlpdf.download_all_files()

    report_csv = Path("report.csv")
    assert report_csv.exists(), "No 'report.csv' => possibly code crashed."
    content = report_csv.read_text("utf-8")
    # We expect an error line => "1\t555"
    assert "1\t555" in content, "Unresponsive URL never timed out or wasn't logged as error."


@pytest.mark.asyncio
async def test_final_report_has_all_rows(tmp_path):
    """
    #11: For each row, we want a line in 'report.csv'.

    We'll do 3 rows: 2 succeed, 1 fails => check final lines.
    """
    df = pd.DataFrame({
        "BRnum": [111, 222, 333],
        "Pdf_URL": [
            "https://example.com/first.pdf",
            "https://broken.example.com/second.pdf",
            "https://example.com/third.pdf"
        ],
        "Report Html Address": [None, None, None]
    }, dtype=object)
    test_excel = tmp_path / "test.xlsx"
    df.to_excel(test_excel, index=False)

    async def mock_get(url, *args, **kwargs):
        if call_count["calls"] == 0:
            call_count["calls"] += 1
            raise ContentLengthError("Simulated mismatch")
        else:
            # Return an async mock response for the second (successful) call
            mock_response = AsyncMock()
            # Make sure it's recognized as an async context manager
            mock_response.__aenter__.return_value = mock_response
            mock_response.__aexit__.return_value = None

            # Provide metadata so dlpdf.py sees it as a valid PDF
            mock_response.content_type = "application/pdf"
            mock_response.content_length = 50

            # Provide an async generator for chunked data
            async def iter_any():
                yield b"%PDF-second-try"
            mock_response.content = MagicMock(iter_any=iter_any)

            return mock_response

    with patch("dlpdf.excel_file", str(test_excel)), \
         patch("dlpdf.output_folder", str(tmp_path)), \
         patch("os.getcwd", return_value=str(tmp_path)), \
         patch("aiohttp.ClientSession.get", side_effect=mock_get):
        await dlpdf.download_all_files()

    report_csv = Path("report.csv")
    assert report_csv.exists(), "No 'report.csv' at all."

    content = report_csv.read_text("utf-8")
    # We want lines for each: 111 (success), 222 (fail), 333 (success).
    assert "111" in content, "Missing row for BRnum=111."
    assert "222" in content, "Missing row for BRnum=222."
    assert "333" in content, "Missing row for BRnum=333."
