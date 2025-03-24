from collections.abc import Generator
from genericpath import exists
from tqdm import tqdm
from urllib.parse import urlparse
import asyncio
import aiohttp
import urllib.parse
import pandas
import os
import sys

excel_file = sys.argv[1] if len(sys.argv) > 1 else "./data/GRI_2017_2020 (1).xlsx"
output_folder = sys.argv[2] if len(sys.argv) > 2 else "./download/"
url_timeout = 15.0
developer_mode = True

# Headers used to pretend we are a browser.
# Some sites reject requests if they do not look like
# they originate from a browser.
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0",
    "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Microsoft Edge";v="134"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Upgrade-Insecure-Requests": "1",
    "Accept-encoding": "gzip, deflate, zstd",
    # "Accept": "text/html,application/xhtml+xml,application/xml",
    "Accept": "application/pdf,application/octet-stream,binary/octet-stream",
}


def patch_url(link: str) -> str | None:
    """
    Takes a link and tries to fix it
    """
    # Empty Excel cells become 'float', for some reason
    if type(link) is float:
        return None

    # Ignore local files
    if link.startswith("file://"):
        return None

    # Fix html
    if link.startswith('<a href="'):
        link = link[len('<a href="') :]
        link = link[: link.find('"')]

    # Fix address starting with a dot
    if link[0] == ".":
        link = link[1:]

    # Patch incomplete urls
    url = urlparse(link)
    if len(url.scheme) == 0:
        # links.insert(0, "ftp://" + link)
        # links.insert(0, "http://" + link)
        link = "https://" + link

    return link


def get_num_links_from_excel() -> int:
    """
    Returns the number of entries in the excel file
    """
    if not exists(excel_file):
        return 0

    excel = pandas.read_excel(excel_file)
    return len(excel["BRnum"].values)


def extract_report_names() -> Generator[tuple[str, str]]:
    """
    Extract the report names from the excel file.
    Yields ('BRnum', 'Pdf_URL') and ('BRnum', 'Report Html Address') if they are valid values,
    for each entry in the excel file.
    """
    if not exists(excel_file):
        print(f'"{excel_file}" was not found!')
        exit(1)

    excel = pandas.read_excel(excel_file, sheet_name=0)
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
    session: aiohttp.ClientSession, tuple_data: tuple[str, str]
) -> tuple[int, str, str | None]:
    """
    Tries to download a pdf file from the two url.
    """
    filename, link = tuple_data
    outname = os.path.join(output_folder, filename + ".pdf")

    # Don't download existing reports
    if exists(outname):
        return 0, filename, None

    err = None
    timeout_link = None

    # Try links
    try:
        # Download the file
        # - 'max_field_size' is set to 16K, because some sites return more
        #   than the default 8K bytes allowed
        # - 'headers' is used to pretend we are a browser. Some sites
        #   seem to reject requests without headers
        # - 'allow_redirects' determines if the destination site can
        #   send us somewhere else.
        # - 'chunked' requests that data is sent in chunks, and
        #   not all at once.
        # - 'timeout' sets timelimits on socket connections
        # - 'raise_for_status' 404/403/etc. status codes raise exceptions.
        async with session.get(
            link,
            max_field_size=16 * 1024,  # 16k bytes response headers
            headers=headers,
            allow_redirects=True,
            chunked=True,
            timeout=aiohttp.ClientTimeout(
                sock_connect=url_timeout, sock_read=url_timeout
            ),
            raise_for_status=True,
        ) as response:
            # Check that the returned data is correct format
            if -1 == headers["Accept"].find(response.content_type):
                err = f"Wrong content-type '{response.content_type}' for '{link}'\n"
            else:
                try:
                    # Write the file to the drive
                    with open(outname, "wb") as file:
                        if developer_mode and int(response.content_length) > 8192:
                            # Don't bother downloading large files, just fill it
                            # with X's matching the file size
                            size = (
                                response.content_length
                                if response.content_length
                                else 1
                            )
                            file.write((size * "X").encode())
                        else:
                            # Do a chunked download of the pdf file
                            async for chunk in response.content.iter_any():
                                file.write(chunk)

                    # Verify that the file is not empty
                    if os.path.getsize(outname) > 0:
                        return 0, filename, None
                    else:
                        os.remove(outname)
                        err = f"received empty pdf\n"
                except aiohttp.http_exceptions.ContentLengthError as cle:
                    # Error happened during download, so retry the link
                    os.remove(outname)
                    timeout_link = link
                except Exception as e:
                    os.remove(outname)
                    err = f"file exception for '{link}' {e}\n"
    except TimeoutError as e:
        # Time-out happened during download, so retry the link
        # timeout_link = link
        err = f"time-out for '{link}' {e}\n"
    except Exception as e:
        err = f"{type(e)} - '{e}': '{link}'\n"

    if timeout_link:
        return 2, filename, timeout_link
    elif err:
        return 1, filename, err
    else:
        return 0, filename, None


async def download_all_files():
    """
    Tries to download pdf files from the specified excel file.
    """
    # Create the download folder if it doesn't exists
    if not exists(output_folder):
        os.mkdir(output_folder)

    # Pull the links from the excel file, including the count
    count = get_num_links_from_excel()
    report_data = extract_report_names()

    # Create the session used for the downloads.
    # - Attach a cookie jar. This is needed for sites that redirect pages.
    # - The connector does not validate ssl, and the connection limit is set to 100
    # - Disable timeouts. The list is large, so items at the end can hit a timeout.
    session = aiohttp.ClientSession(
        cookie_jar=aiohttp.CookieJar(),
        connector=aiohttp.TCPConnector(ssl=False, limit=100),
        timeout=aiohttp.ClientTimeout(total=0),
    )

    # Lists of successful, failed, and downloads that need to be retried
    good = []
    bad = []
    retry = []

    # Helper function to handle the status of completed download
    def handle_status(status: int, filename: str, error):
        if 0 == status:
            good.append(filename + "\n")
        elif 1 == status:
            bad.append(filename + "\t" + error)
        elif 2 == status:
            retry.append((filename, error))

    # Do the actual downloads
    try:
        async with session:
            # Generate a list of tasks from the data extracted from the excel file
            tasks = [download_file(session, tuple_data) for tuple_data in report_data]

            # Fire up the downloads
            for f in tqdm(asyncio.as_completed(tasks), unit="pdf", total=count):
                try:
                    status, filename, error = await f
                    handle_status(status, filename, error)
                except Exception as e:
                    bad.append("async io error\t" + str(e) + "\n")

            print(f"\nDownloaded {len(good)} pdf files")

            # Retry links that might work
            count = len(retry)
            if count > 0:
                print(f"Retrying {count} links...")
                tasks = [download_file(session, (f, l)) for f, l in retry]
                retry.clear()
                prev_good_files = len(good)

                for f in tqdm(asyncio.as_completed(tasks), unit="pdf", total=count):
                    try:
                        status, filename, error = await f
                        handle_status(status, filename, error)
                    except Exception as e:
                        bad.append("async io error\t" + str(e) + "\n")

                good_retries = len(good) - prev_good_files
                print(f"\n{good_retries} retries succeeded")
                print(f"{len(good)} pfd files downloaded total")
    except Exception as e:
        print(f"Exception caught while downloading: '{e}'")
        print("Please re-run the script to try again.")
    finally:
        # Write out the report of good/bad downloads
        with open("report.csv", "wb") as report:
            for filename in good:
                report.write(f"0\t{filename}".encode())

            for err in bad:
                report.write(f"1\t{err}".encode())


if __name__ == "__main__":
    asyncio.run(download_all_files())
