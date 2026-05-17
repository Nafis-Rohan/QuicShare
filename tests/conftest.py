"""Pytest fixtures for QuickShare."""

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Keep pytest temp files on D: when running from D:\QuickShare
_tmp = ROOT / ".tmp"
_tmp.mkdir(exist_ok=True)
os.environ.setdefault("TMP", str(_tmp))
os.environ.setdefault("TEMP", str(_tmp))


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Flask test client with isolated upload/static directories."""
    uploads = tmp_path / "uploads"
    static = tmp_path / "static"
    static.mkdir(parents=True)

    import backend.utils as utils

    monkeypatch.setattr(utils, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(utils, "STATIC_DIR", static)
    monkeypatch.setattr(utils, "QR_PATH", static / "qr.png")

    from backend.app import app

    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client
