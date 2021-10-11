#!/usr/bin/python3

from risiparse.risiparse import main
import sys
import pathlib
import pytest

SCRIPT = pathlib.Path(__file__).parent / "risiparse" / "risiparse.py"

@pytest.mark.parametrize(
    "test_link,expected_author",
    [
        ("https://web.archive.org/web/20190811214702/https://risific.fr/hey-msieur-silverstein-vnez-voir-un-peu-par-ici/", "connington"),
        ("https://web.archive.org/web/20190811232330/https://risific.fr/risitas-je-suis-parti-seul-trois-semaines-au-japon/", "rouxblard"),
        ("https://web.archive.org/web/20200926061547/https://risific.fr/bienvenue-en-prepa/", "jean-cassini")
    ],
)
def test_download_webarchive(monkeypatch, tmp_path, caplog, test_link, expected_author):
    tmpdir = tmp_path
    tmpdir.mkdir(exist_ok=True)
    testargs = [
        f"{SCRIPT}",
        "-o", f"{tmpdir}",
        "-l" , test_link,
        "--no-pdf",
        "--no-database",
    ]
    monkeypatch.setattr(sys, 'argv', testargs)
    main()
    output_file = caplog.records[-1].getMessage().split()[1]
    output_file_path = pathlib.Path(output_file)
    assert expected_author in caplog.records[-1].getMessage()
    assert output_file_path.exists()
    assert output_file_path.stat().st_size > 300
