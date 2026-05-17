"""Unit tests for backend.utils."""

import backend.utils as utils


def test_safe_filename_strips_path():
    assert utils.safe_filename("../../etc/passwd") == "passwd"
    assert utils.safe_filename("doc.pdf") == "doc.pdf"


def test_safe_filename_replaces_invalid_chars():
    assert utils.safe_filename('file<>:".txt') == "file____.txt"


def test_format_size():
    assert utils.format_size(500) == "500 B"
    assert "KB" in utils.format_size(2048)


def test_generate_session_id_length():
    sid = utils.generate_session_id()
    assert len(sid) == 12
    assert sid.isalnum()


def test_list_and_delete_file(tmp_path, monkeypatch):
    monkeypatch.setattr(utils, "UPLOADS_DIR", tmp_path / "uploads")
    session = "testsess123"
    folder = utils.session_upload_dir(session)
    sample = folder / "hello.txt"
    sample.write_text("hi", encoding="utf-8")

    files = utils.list_session_files(session)
    assert len(files) == 1
    assert files[0]["name"] == "hello.txt"

    assert utils.delete_file(session, "hello.txt") is True
    assert utils.list_session_files(session) == []
