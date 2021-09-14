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
    ],
)
def test_resize_images(monkeypatch, tmp_path, caplog, test_link):
    tmpdir = tmp_path
    tmpdir.mkdir(exist_ok=True)
    testargs = [
        f"{SCRIPT}",
        "-o", f"{tmpdir}",
        "-l" , test_link,
        "--no-pdf",
        "--download-images"
    ]
    monkeypatch.setattr(sys, 'argv', testargs)
    main()
    assert 'full scale' in caplog.text
    output_file = caplog.records[-1].msg.split()[1]
    output_file_path = pathlib.Path(output_file)
    with open(output_file_path) as f:
        soup = BeautifulSoup(f, features="lxml")
    imgs = soup.select("img")
    for i in range(2,16):
        img = imgs[-i]
        assert 'width' and 'height' not in img.attrs
