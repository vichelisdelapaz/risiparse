#!/usr/bin/python3

from risiparse.risiparse import main
import sys
import pathlib
import pytest

SCRIPT = pathlib.Path(__file__).parent / "risiparse" / "risiparse.py"

@pytest.mark.parametrize(
    "test_link",
    [
        ("https://www.jeuxvideo.com/forums/42-51-67616891-1-0-1-0-risitas-comment-j-ai-couche-avec-une-milf-ce-dimanche.htm")
    ],
)
def test_authors(monkeypatch, tmp_path, caplog, test_link):
    tmpdir = tmp_path
    tmpdir.mkdir(exist_ok=True)
    testargs = [
        f"{SCRIPT}",
        "-o", f"{tmpdir}",
        "-l" , test_link,
    ]
    monkeypatch.setattr(sys, 'argv', testargs)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 0
    last_message = caplog.records[-1].msg
    assert "Creating" in last_message
    output_file = last_message.split()[1]
    output_file_path = pathlib.Path(output_file)
    assert output_file_path.exists()
    assert output_file_path.stat().st_size > 1000
