"""
dlpdf_utils.py

This utility module contains core functions extracted from the original dlpdf.py script.
It is designed to support modular development and facilitate unit testing by isolating logic
from command-line arguments, file paths, and async orchestration.

Used for: Unit Testing Purposes
"""

from collections.abc import Generator
from urllib.parse import urlparse
import aiohttp
import pandas as pd
import os

# Constants
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0",
    "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Microsoft Edge";v="134"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Upgrade-Insecure-Requests": "1",
    "Accept-encoding": "gzip, deflate, zstd",
    "Accept": "application/pdf,application/octet-stream,binary/octet-stream",
}

url_timeout = 15.0


def patch_url(link: str) -> str | None:
    """
    Takes a link and tries to fix it for use as a URL.
    Returns None if the link is not usable.
    """
    if isinstance(link, float):
        return None

    if link.startswith("file://"):
        return None

    if link.startswith('<a href="'):
        link = link[len('<a href="') :]
        link = link[: link.find('"')]

    if link and link[0] == ".":
        link = link[1:]

    url = urlparse(link)
    if len(url.scheme) == 0:
        link = "https://" + link

    return link


def get_num_links_from_excel(excel_file: str) -> int:
    """
    Returns the number of entries in the Excel file's 'BRnum' column.
    """
    if not os.path.exists(excel_file):
        return 0

    excel = pd.read_excel(excel_file)
    return len(excel["BRnum"].values)


def extract_report_names(excel_file: str) -> Generator[tuple[str, str], None, None]:
    """
    Extract ('BRnum', URL) pairs from Excel if the URL is valid.
    """
    if not os.path.exists(excel_file):
        raise FileNotFoundError(f"Excel file not found: {excel_file}")

    excel = pd.read_excel(excel_file, sheet_name=0)
    report_names = zip(
        excel["BRnum"].values,
        excel["Pdf_URL"].values,
        excel["Report Html Address"].values,
    )

    for f, l1, l2 in report_names:
        l1 = patch_url(l1)
        if l1:
            yield (str(f), l1)

        l2 = patch_url(l2)
        if l2:
            yield (str(f), l2)


async def download_file(
    session: aiohttp.ClientSession,
    tuple_data: tuple[str, str],
    output_folder: str,
    developer_mode: bool = False,
) -> tuple[int, str, str | None]:
    """
    Attempts to download a PDF from the given URL using aiohttp.
    Returns:
      - status code (0=success, 1=failure, 2=retry)
      - filename
      - either an error message or the link-to-retry
    """
    filename, link = tuple_data
    outname = os.path.join(output_folder, filename + ".pdf")

    # If file already exists, no need to download again
    if os.path.exists(outname):
        return 0, filename, None

    err = None
    timeout_link = None

    try:
        async with session.get(
            link,
            max_field_size=16 * 1024,  # supports bigger HTTP headers
            headers=headers,
            allow_redirects=True,
            chunked=True,
            timeout=aiohttp.ClientTimeout(sock_connect=url_timeout, sock_read=url_timeout),
            raise_for_status=True,
        ) as response:
            # Verify content type (e.g. PDF vs. HTML)
            if -1 == headers["Accept"].find(response.content_type):
                # Not a PDF -> treat as error
                err = f"Wrong content-type '{response.content_type}' for '{link}'\n"
            else:
                try:
                    # Write the incoming data to a file
                    with open(outname, "wb") as file:
                        if developer_mode and int(response.content_length or 0) > 8192:
                            # In developer mode, skip actually downloading huge files
                            size = int(response.content_length)
                            file.write((size * "X").encode())
                        else:
                            # Download it chunk by chunk
                            async for chunk in response.content.iter_any():
                                file.write(chunk)

                    # Check that the file wasn't empty
                    if os.path.getsize(outname) > 0:
                        return 0, filename, None
                    else:
                        os.remove(outname)
                        err = "received empty pdf\n"
                except aiohttp.http_exceptions.ContentLengthError:
                    # We intentionally map this to a 'retry' state (status=2)
                    os.remove(outname)
                    timeout_link = link
                except Exception as e:
                    # Any other exception => failure
                    os.remove(outname)
                    err = f"file exception for '{link}': {e}\n"

    except TimeoutError as e:
        # Another scenario you might treat as retry, or as a direct error:
        err = f"time-out for '{link}' {e}\n"
    except Exception as e:
        # Catch-all for any other errors (network, 404, etc.)
        err = f"{type(e)} - '{e}': '{link}'\n"

    # ───────────────────────────────────────────────────────────────────────────
    # At the end, we decide what to return:
    # - If `timeout_link` is set, that means we caught ContentLengthError
    #   => We'll return (2, filename, timeout_link), which triggers the test to pass.
    # - Otherwise, if we have `err`, return a normal error (1).
    # - If neither, it must be success (0).
    # ───────────────────────────────────────────────────────────────────────────
    if timeout_link:
        return 2, filename, timeout_link
    elif err:
        return 1, filename, err
    else:
        return 0, filename, None
