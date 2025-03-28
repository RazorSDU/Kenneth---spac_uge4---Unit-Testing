# test_dlpdf_script.py

import pytest
import os
import aiohttp
from unittest.mock import patch, MagicMock
import pandas as pd
from pathlib import Path

import dlpdf


def test_no_arguments_uses_defaults():
    """
    Verifies that if we call run_main() with no arguments,
    dlpdf.py uses the default excel_file and output_folder
    and does NOT raise an error (assuming both exist).
    """
    # 1) Mock os.path.exists to return True for the default Excel path
    with patch("os.path.exists", return_value=True), \
         patch("pandas.read_excel") as mock_xl, \
         patch("aiohttp.ClientSession.get") as mock_get:

        # 2) Return an empty DataFrame so no real downloads occur
        mock_xl.return_value = pd.DataFrame({
            "BRnum": [],
            "Pdf_URL": [],
            "Report Html Address": []
        })

        # 3) Mock the GET call so it won't actually do network IO
        mock_resp = MagicMock()
        mock_resp.__aenter__.return_value = mock_resp
        mock_resp.__aexit__.return_value = None
        mock_get.return_value = mock_resp

        # 4) Simply run_main with no arguments => uses defaults
        dlpdf.run_main()  # Should not raise FileNotFoundError

    # If no exception was raised, we've covered the "defaults" path.


def test_excel_file_missing():
    """
    If the provided Excel file doesn't exist, run_main() should raise FileNotFoundError.
    """
    with pytest.raises(FileNotFoundError) as exc:
        dlpdf.run_main("fake_missing.xlsx", "some_out")
    assert "fake_missing.xlsx" in str(exc.value)


def test_with_arguments_provided(tmp_path):
    """
    Pass a specific Excel path and output folder to run_main, 
    ensure that the folder is created and no error is raised if Excel is found.
    """
    fake_excel = tmp_path / "fake_data.xlsx"
    fake_excel.touch()  # create an empty Excel file
    outdir = tmp_path / "my_outputs"

    # run_main(...) with valid arguments
    dlpdf.run_main(str(fake_excel), str(outdir))

    # The code should create 'outdir' if it doesn't exist
    assert outdir.exists(), "dlpdf did not create the specified output folder."

def test_retry_logic_covers_all_prints(tmp_path):
    """
    1) Force an error that sets status=2 (ContentLengthError).
    2) Then succeed on retry -> covers the "Retrying X links" code.
    """
    # Provide 1 row in Excel
    excel_path = tmp_path / "test.xlsx"
    pd.DataFrame({
        "BRnum": [101],
        "Pdf_URL": ["https://retry.example.com/file.pdf"],
        "Report Html Address": [None],
    }).to_excel(excel_path, index=False)

    call_count = 0

    async def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # first attempt => ContentLengthError => status=2 => triggers retry
            raise aiohttp.http_exceptions.ContentLengthError("Sim mismatch")
        else:
            # second attempt => success
            resp = MagicMock()
            resp.__aenter__.return_value = resp
            resp.__aexit__.return_value = None
            resp.content_type = "application/pdf"
            resp.content_length = 100
            async def iter_any():
                yield b"%PDF-data-chunk"
            resp.content.iter_any = iter_any
            return resp

    with patch("aiohttp.ClientSession.get", side_effect=mock_get), \
         patch("dlpdf.os.path.exists", return_value=True):
        # run_main with real Excel, real output=tmp_path
        dlpdf.run_main(str(excel_path), str(tmp_path))

    # The 2nd attempt should create 101.pdf
    assert (tmp_path / "101.pdf").exists()


def test_main_loop_top_level_exception(tmp_path):
    """
    Force a raised exception in the middle of download_all_files() 
    so we cover the big 'except Exception' block.
    """
    # Make a trivial Excel
    excel_path = tmp_path / "test.xlsx"
    pd.DataFrame({
        "BRnum": [999],
        "Pdf_URL": ["http://dummy"]
    }).to_excel(excel_path, index=False)

    # Patch session so it raises a top-level RuntimeError
    with patch("aiohttp.ClientSession") as mock_sess, \
         patch("dlpdf.os.path.exists", return_value=True):
        mock_ctx = MagicMock()
        def raise_soon(*a, **kw):
            raise RuntimeError("Simulated top-level error in session context")

        mock_ctx.__aenter__.side_effect = raise_soon
        mock_sess.return_value = mock_ctx

        dlpdf.run_main(str(excel_path), str(tmp_path))
    # If no crash, we covered the 'except Exception' + 'finally' lines.


def test_chunk_iteration_exception(tmp_path):
    """
    Simulate an OSError during chunk iteration to ensure coverage of the 
    exception block that removes the partial file.
    """
    excel_path = tmp_path / "test.xlsx"
    pd.DataFrame({
        "BRnum": [777],
        "Pdf_URL": ["http://chunk.fail"]
    }).to_excel(excel_path, index=False)

    async def mock_get(url, *args, **kwargs):
        resp = MagicMock()
        resp.__aenter__.return_value = resp
        resp.__aexit__.return_value = None
        resp.content_type = "application/pdf"
        resp.content_length = 50
        async def iter_any():
            raise OSError("Simulated read error in chunk iteration")
        resp.content.iter_any = iter_any
        return resp

    with patch("aiohttp.ClientSession.get", side_effect=mock_get), \
         patch("dlpdf.os.path.exists", return_value=True):
        dlpdf.run_main(str(excel_path), str(tmp_path))

    # The code should catch OSError, remove partial file, and log an error.
    assert not (tmp_path / "777.pdf").exists(), "Partial file should have been removed."
