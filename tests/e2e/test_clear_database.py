#!/usr/bin/python3

from risiparse.risiparse import main
import risiparse.utils.database as database

import pytest
import sys
import pathlib

SCRIPT = pathlib.Path(__file__).parent / "risiparse" / "risiparse.py"

def test_clear_database(monkeypatch, tmp_path, caplog):
    tmpdir = tmp_path
    tmpdir.mkdir(exist_ok=True)
    database_path = tmp_path / "risiparse.db"
    database_path.write_text("This is a test database for risiparse")
    testargs = [
        f"{SCRIPT}",
        "--clear-database"
    ]
    monkeypatch.setattr(sys, 'argv', testargs)
    monkeypatch.setattr(database, 'DB_PATH', database_path)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert pytest_wrapped_e.type == SystemExit
    last_message = caplog.records[-1].getMessage()
    assert "Deleted database" in last_message
    assert not database_path.exists()
