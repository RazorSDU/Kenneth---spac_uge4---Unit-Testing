[![Python CI](https://github.com/RazorSDU/Kenneth---spac_uge4---Unit-Testing/actions/workflows/ci.yml/badge.svg)](https://github.com/RazorSDU/Kenneth---spac_uge4---Unit-Testing/actions/workflows/ci.yml)

Note that the Badge is failing on purpose.


# PDF Downloader & Unit Tests

## Overview

This project is a **PDF Downloader** that reads links from an Excel file (using `pandas`) and downloads associated PDF documents asynchronously. The main script handles Excel reading, downloading, timeout handling, and logging

### Main File

- `dlpdf.py` – The main script containing the logic for reading Excel, downloading PDFs, handling timeouts, retry logic, and more.

We have implemented a suite of **unit and integration tests** to ensure the downloader functions correctly and complies with the original project requirements.

---

## Project Structure

```
.
├── dlpdf.py
├── tests
│   ├── test_dlpdf_script.py
│   ├── test_download_file.py
│   ├── test_excel_extraction.py
│   ├── test_patch_url.py
│   └── test_original_requirements.py
└── requirements.txt  (optional)
```

---

## Test Suite Breakdown

### `tests/test_dlpdf_script.py`

- **What it tests**: Integration-style testing via `run_main(...)` and `download_all_files(...)`.
- **Why/how**: Tests developer-mode, retry logic, chunked downloading, and exit code behaviors.

### `tests/test_download_file.py`

- **What it tests**: Unit tests for downloading a single PDF (with mocked network calls).
- **Why/how**: Validates handling of content types, timeouts, partial downloads, and exceptions.

### `tests/test_excel_extraction.py`

- **What it tests**: Utility functions for extracting URLs from Excel.
- **Why/how**: Handles cases like empty files, missing data, or incomplete columns.

### `tests/test_patch_url.py`

- **What it tests**: Normalization logic for URLs via `patch_url()`.
- **Why/how**: Fixes edge cases like missing schemes, leading dots, and malformed URLs.

### `tests/test_original_requirements.py`

- **What it tests**: Compliance with original project requirements:
  - Fallback to second link if the first fails.
  - Log format: `0\tBRnum` for success, `1\tBRnum` for errors.
  - Enforce a 10-download prototype limit.
  - Timeout behavior and correct logging.

- **Why some fail**: Some original requirements are unimplemented in `dlpdf.py`. These tests illustrate feature gaps.

---

## Installation & Setup

1. **Clone this repository** or download the ZIP.

2. **Create a virtual environment** (recommended):
```bash
python -m venv .venv
source .venv/bin/activate  # on Linux/Mac
.venv\Scripts\activate   # on Windows
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

If `requirements.txt` is missing, install manually:
```bash
pip install pytest pytest-asyncio aiohttp pandas
```

---

## Running the Tests

To run all tests:
```bash
pytest
```

With coverage report:
```bash
pytest --cov=dlpdf --cov-report=term-missing
```

> Ensure `dlpdf.py` is discoverable (same directory or Python path) if coverage reports fail.

---

## Concurrency Note

> _Assignment Note:_  
> “To avoid overloading the network at Specialisterne—If you choose to test the PDF downloader’s concurrency, please test with a maximum of 10 PDFs…”

Make sure to limit concurrent downloads to **10 or fewer**. The test `test_prototype_only_downloads_10` checks this limit. If not enforced in code, this test will fail.

---

## Why Some Tests Fail (But Are Still Useful)

- **Fallback logic**: Test expects sequential fallback; current code may attempt parallel.
- **Wrong content type**: Test expects specific types; mocks might mismatch.
- **10‐file limit**: Not enforced = test fails.
- **Timeout logging**: Test checks for exact log string like `1\t555`.

> These failing tests help identify missing features or outdated requirements. Update `dlpdf.py` if you want full test compliance.

# dlpdf-utils & Tests — taming a legacy PDF-scraper  
> A refactor + test‐suite that wraps an existing async downloader, adds utilities, and drives it to 100 % coverage.  
---

## 🛠 Tech Stack & Skills Demonstrated
| Area                  | Stack / Library                                  | Highlights shown in this project                            |
|-----------------------|--------------------------------------------------|-------------------------------------------------------------|
| Async I/O            | `asyncio`, `aiohttp`, `tqdm`                     | High-concurrency downloads, graceful timeouts, progress bar |
| Data handling        | `pandas`, `openpyxl`, `urllib.parse`             | Excel parsing, robust URL-patching logic                    |
| Testing & Mocking    | `pytest`, `pytest-asyncio`, `aioresponses`, `unittest.mock` | 100 % branch coverage, async mocks, controlled side-effects |
| CI-friendly design   | Pure-Python, no external services                | Runs in any pipeline in <60 s                               |
| Code quality         | Split into `dlpdf_utils.py`                      | Separation of concerns, single-responsibility utilities     |

## ✨ What the App Does
### Core Functionality  
* Reads an Excel sheet containing **BRnum**, primary, and fallback URLs.  
* Cleans malformed links (`file://`, `<a href="">`, missing scheme, etc.).  
* Downloads each PDF asynchronously, skipping existing files and retrying smartly.  
* Logs a `report.csv` where `0` = success, `1` = error — ready for audit.

### Visuals & UX  
* CLI progress via `tqdm` keeps long batches transparent.  
* Developer-mode writes dummy bytes for huge files to speed local runs.

### Engineering Features  
* Utilities extracted into **dlpdf_utils.py** for isolated unit testing.  
* 70+ tests hit every branch, including intentional “red” tests that reflect the
  *original* requirements before refactor.  
* Heavy use of async-aware mocks to avoid network traffic and flakiness.  
* Prototype guard lets you cap downloads to 10 when experimenting.

### Running Locally
> **Prerequisites:** Python ≥ 3.10 and a virtualenv.  
> (No external services; no need for MAUI / .NET.)

```bash
# Clone & install
git clone https://github.com/your-handle/dlpdf-utils.git
cd dlpdf-utils
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run the full test suite
pytest -v

# Scrape your own Excel (outputs to ./download/)
python dlpdf.py data/GRI_2017_2020\ \(1\).xlsx download/
