#!/usr/bin/python3

from risiparse.risiparse import main
import sys
import pathlib
import pytest
from bs4 import BeautifulSoup


SCRIPT = pathlib.Path(__file__).parent / "risiparse" / "risiparse.py"

@pytest.mark.parametrize(
    "test_link",
    [
        ("https://www.jeuxvideo.com/forums/42-51-66574499-1-0-1-0-risitas-au-bout-du-monde-un-khey-au-japon.htm"),
        ("https://www.jeuxvideo.com/forums/42-51-65706467-1-0-1-0-risitas-l-erasmus-en-angleterre-malaise-aventures-et-progres.htm")
    ],
)
def test_download_images(monkeypatch, tmp_path, caplog, test_link):
    tmpdir = tmp_path
    tmpdir.mkdir(exist_ok=True)
    testargs = [
        f"{SCRIPT}",
        "-o", f"{tmpdir}",
        "-l" , test_link,
        "--no-pdf",
        "--download-images",
        "--no-database",
    ]
    monkeypatch.setattr(sys, 'argv', testargs)
    main()
    output_file = caplog.records[-1].getMessage().split()[1]
    output_file_path = pathlib.Path(output_file)
    html = []
    with open(output_file_path) as f:
        for element in f:
            html.append(element.strip())
    html = "".join(html)
    soup = BeautifulSoup(html, features="lxml")
    img = soup.img.attrs["src"]
    assert not img.startswith("http")
