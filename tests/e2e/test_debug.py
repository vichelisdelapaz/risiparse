#!/usr/bin/python3

from risiparse.risiparse import main, STDOUT_HANDLER
import risiparse.utils.database as database

import pytest
import sys
import pathlib

SCRIPT = pathlib.Path(__file__).parent / "risiparse" / "risiparse.py"

def test_debug(monkeypatch, tmp_path):
    testargs = [
        f"{SCRIPT}",
        "--debug",
        "--no-download",
        "--no-pdf",
        "--output-dir",
        f"{tmp_path}"
    ]
    monkeypatch.setattr(sys, 'argv', testargs)
    main()
    assert STDOUT_HANDLER.level == 10
