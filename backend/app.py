"""
QuickShare — LAN file sharing server (Snapdrop-style).
Run via run.bat or: python -m backend.app
"""

import os
import sys
import webbrowser
import threading
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent
# Project root on path so `backend.socket` does not shadow stdlib `socket`
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from flask import Flask, jsonify, request, send_from_directory
from flask_socketio import SocketIO
from werkzeug.utils import secure_filename
import qrcode

from backend.utils import (
    UPLOADS_DIR,
    STATIC_DIR,
    QR_PATH,
    ensure_directories,
    generate_session_id,
    get_local_ip,
    session_upload_dir,
    safe_filename,
    list_session_files,
    delete_file,
    cleanup_old_files,
    format_size,
)
from backend.socket import register_socket_events, get_session_devices

FRONTEND_DIR = ROOT_DIR / "frontend"
PORT = int(os.environ.get("QUICKSHARE_PORT", "5000"))

# Active server session (regenerated on each start)
CURRENT_SESSION_ID = generate_session_id()
LOCAL_IP = get_local_ip()

app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR),
    static_url_path="/static-frontend",
)
app.config["SECRET_KEY"] = os.environ.get("QUICKSHARE_SECRET", "quickshare-lan-local")
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024  # 512 MB max upload

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    logger=False,
    engineio_logger=False,
)
register_socket_events(socketio)


def generate_qr_code(url: str) -> None:
    """Generate QR PNG for the session join URL."""
    ensure_directories()
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="white", back_color="#0f1419")
    img.save(str(QR_PATH))


def session_url(session_id: str | None = None) -> str:
    sid = session_id or CURRENT_SESSION_ID
    return f"http://{LOCAL_IP}:{PORT}/session/{sid}"


# ---------------------------------------------------------------------------
# HTTP routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """PC homepage with QR and file transfer UI."""
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/phone")
def phone_page():
    """Direct mobile page (session passed via query)."""
    return send_from_directory(FRONTEND_DIR, "phone.html")


@app.route("/session/<session_id>")
def join_session(session_id: str):
    """Mobile entry point from QR scan."""
    return send_from_directory(FRONTEND_DIR, "phone.html")


@app.route("/style.css")
def styles():
    return send_from_directory(FRONTEND_DIR, "style.css")


@app.route("/app.js")
def app_js():
    return send_from_directory(FRONTEND_DIR, "app.js")


@app.route("/boot.js")
def boot_js():
    return send_from_directory(FRONTEND_DIR, "boot.js")


@app.route("/static/qr.png")
def qr_image():
    return send_from_directory(STATIC_DIR, "qr.png")


@app.route("/api/info")
def api_info():
    """Server and session metadata for clients."""
    cleanup_old_files()
    return jsonify({
        "session_id": CURRENT_SESSION_ID,
        "local_ip": LOCAL_IP,
        "port": PORT,
        "session_url": session_url(),
        "qr_url": f"/static/qr.png?t={os.path.getmtime(QR_PATH) if QR_PATH.exists() else 0}",
        "devices": get_session_devices(CURRENT_SESSION_ID),
    })


@app.route("/api/files")
def api_files():
    session_id = request.args.get("session_id", CURRENT_SESSION_ID)
    files = list_session_files(session_id)
    for f in files:
        f["size_human"] = format_size(f["size"])
    return jsonify({"files": files})


@app.route("/api/upload", methods=["POST"])
def api_upload():
    """Receive file via multipart form."""
    # Single active session per server run — ignore stale IDs from old QR links
    session_id = CURRENT_SESSION_ID
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "No file provided"}), 400

    filename = safe_filename(secure_filename(uploaded.filename))
    if not filename:
        return jsonify({"error": "Invalid file name"}), 400

    ensure_directories()
    dest = session_upload_dir(session_id) / filename
    try:
        uploaded.save(str(dest))
    except OSError as exc:
        return jsonify({"error": f"Could not save file: {exc}"}), 500
    stat = dest.stat()

    file_info = {
        "name": filename,
        "size": stat.st_size,
        "size_human": format_size(stat.st_size),
        "session_id": session_id,
    }

    # Notify room via Socket.IO
    socketio.emit(
        "file_receive",
        {"file": file_info},
        room=f"session_{session_id}",
    )
    socketio.emit(
        "file_transfer",
        {"status": "uploaded", "file": file_info},
        room=f"session_{session_id}",
    )

    return jsonify({"ok": True, "file": file_info})


@app.route("/api/download/<session_id>/<filename>")
def api_download(session_id: str, filename: str):
    """Download a file; optionally delete after send."""
    folder = session_upload_dir(session_id)
    safe_name = safe_filename(filename)
    path = folder / safe_name
    if not path.is_file():
        return jsonify({"error": "File not found"}), 404

    socketio.emit(
        "progress_update",
        {"session_id": session_id, "file": safe_name, "progress": 100, "phase": "download"},
        room=f"session_{session_id}",
    )

    delete_after = request.args.get("delete", "0") == "1"

    response = send_from_directory(
        folder,
        safe_name,
        as_attachment=True,
        download_name=safe_name,
    )
    if delete_after:
        threading.Timer(2.0, lambda: delete_file(session_id, safe_name)).start()
    return response


@app.route("/api/delete/<session_id>/<filename>", methods=["DELETE"])
def api_delete(session_id: str, filename: str):
    if delete_file(session_id, safe_filename(filename)):
        socketio.emit(
            "file_transfer",
            {"status": "deleted", "file": {"name": filename}},
            room=f"session_{session_id}",
        )
        return jsonify({"ok": True})
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": "File too large (max 512 MB)"}), 413


def open_browser():
    """Open Chrome (or default browser) to localhost after short delay."""
    import time
    time.sleep(1.2)
    url = f"http://localhost:{PORT}"
    chrome_paths = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for chrome in chrome_paths:
        if os.path.isfile(chrome):
            os.spawnl(os.P_NOWAIT, chrome, chrome, url)
            return
    webbrowser.open(url)


def main():
    global CURRENT_SESSION_ID, LOCAL_IP

    ensure_directories()
    LOCAL_IP = get_local_ip()
    CURRENT_SESSION_ID = generate_session_id()

    join_url = session_url(CURRENT_SESSION_ID)
    generate_qr_code(join_url)

    print("=" * 56)
    print("  QuickShare — LAN File Sharing")
    print("=" * 56)
    print(f"  Local:   http://localhost:{PORT}")
    print(f"  LAN:     http://{LOCAL_IP}:{PORT}")
    print(f"  Session: {CURRENT_SESSION_ID}")
    print(f"  QR URL:  {join_url}")
    print("=" * 56)
    print("  Scan the QR code on your phone to connect.")
    print("=" * 56)

    threading.Thread(target=open_browser, daemon=True).start()

    try:
        socketio.run(
            app,
            host="0.0.0.0",
            port=PORT,
            debug=False,
            use_reloader=False,
        )
    except OSError as exc:
        win_err = getattr(exc, "winerror", None)
        if win_err == 10048 or exc.errno in (98, 10048):
            print()
            print("  ERROR: Port", PORT, "is already in use.")
            print("  - Close any other QuickShare window, or")
            print("  - Run stop.bat, then run.bat again")
            print("  - Or set QUICKSHARE_PORT=5001 in run.bat")
            print()
            sys.exit(1)
        raise


if __name__ == "__main__":
    main()
