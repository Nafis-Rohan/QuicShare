"""HTTP API tests for QuickShare."""

import io

from backend.app import CURRENT_SESSION_ID


def test_index_returns_html(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"QuickShare" in res.data


def test_phone_page(client):
    res = client.get("/session/abc123")
    assert res.status_code == 200
    assert b"Mobile" in res.data


def test_api_info(client):
    res = client.get("/api/info")
    assert res.status_code == 200
    data = res.get_json()
    assert data["session_id"] == CURRENT_SESSION_ID
    assert "session_url" in data
    assert "port" in data


def test_upload_list_download_delete(client):
    session_id = CURRENT_SESSION_ID
    payload = {
        "file": (io.BytesIO(b"quickshare test"), "note.txt"),
        "session_id": session_id,
    }
    up = client.post("/api/upload", data=payload, content_type="multipart/form-data")
    assert up.status_code == 200
    assert up.get_json()["file"]["name"] == "note.txt"

    listing = client.get(f"/api/files?session_id={session_id}")
    assert listing.status_code == 200
    names = [f["name"] for f in listing.get_json()["files"]]
    assert "note.txt" in names

    dl = client.get(f"/api/download/{session_id}/note.txt")
    assert dl.status_code == 200
    assert dl.get_data() == b"quickshare test"
    dl.close()

    deleted = client.delete(f"/api/delete/{session_id}/note.txt")
    assert deleted.status_code == 200
    assert client.get(f"/api/files?session_id={session_id}").get_json()["files"] == []


def test_download_not_found(client):
    res = client.get(f"/api/download/{CURRENT_SESSION_ID}/missing.bin")
    assert res.status_code == 404


def test_upload_without_file(client):
    res = client.post("/api/upload", data={"session_id": CURRENT_SESSION_ID})
    assert res.status_code == 400
