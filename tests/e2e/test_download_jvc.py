#!/usr/bin/python3

from risiparse.risiparse import main
import sys
import pathlib
import pytest

SCRIPT = pathlib.Path(__file__).parent / "risiparse" / "risiparse.py"

@pytest.mark.parametrize(
    "test_link,expected_author",
    [
        ("https://www.jeuxvideo.com/forums/42-51-67052724-1-0-1-0-risitas-un-celestin-a-istanbul.htm", "turkissou"),
        ("https://www.jeuxvideo.com/forums/42-51-66574499-1-0-1-0-risitas-au-bout-du-monde-un-khey-au-japon.htm", "cybercuck1997"),
        ("https://www.jeuxvideo.com/forums/42-51-65706467-1-0-1-0-risitas-l-erasmus-en-angleterre-malaise-aventures-et-progres.htm", "brummie")
    ],
)
def test_download_jvc(monkeypatch, tmp_path, caplog, test_link, expected_author):
    tmpdir = tmp_path
    tmpdir.mkdir(exist_ok=True)
    testargs = [
        f"{SCRIPT}",
        "-o", f"{tmpdir}",
        "-l" , test_link,
        "--no-pdf",
    ]
    monkeypatch.setattr(sys, 'argv', testargs)
    main()
    output_file = caplog.records[-1].msg.split()[1]
    output_file_path = pathlib.Path(output_file)
    assert expected_author in caplog.records[-1].msg
    assert output_file_path.exists()
    assert output_file_path.stat().st_size > 300
