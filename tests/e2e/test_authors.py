#!/usr/bin/python3

from risiparse.risiparse import main
import sys
import pathlib
import pytest

SCRIPT = pathlib.Path(__file__).parent / "risiparse" / "risiparse.py"

@pytest.mark.parametrize(
    "test_link",
    [
        ("https://www.jeuxvideo.com/forums/42-51-49656557-1-0-1-0-risitas-fille-from-dechet-to-dechet-une-histoire-peu-banale.htm")
    ],
)
def test_authors(monkeypatch, tmp_path, caplog, test_link):
    tmpdir = tmp_path
    tmpdir.mkdir(exist_ok=True)
    testargs = [
        f"{SCRIPT}",
        "-o", f"{tmpdir}",
        "-l" , test_link,
        "--no-pdf",
        "--authors", "ProlEtendard"
    ]
    monkeypatch.setattr(sys, 'argv', testargs)
    main()
    post_numbers = int(caplog.records[-3].msg.split()[-1])
    assert post_numbers == 15
