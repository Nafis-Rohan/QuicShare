"""
Utility helpers for QuickShare LAN file sharing.
"""

import os
import re
import socket
import uuid
import time
import shutil
from pathlib import Path

# Project root (D:\QuickShare)
ROOT_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = ROOT_DIR / "uploads"
STATIC_DIR = ROOT_DIR / "static"
QR_PATH = STATIC_DIR / "qr.png"

# Auto-delete uploads older than this many seconds after download
FILE_TTL_SECONDS = 3600


def ensure_directories() -> None:
    """Create required folders if they do not exist."""
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)


def generate_session_id() -> str:
    """Return a short unique session identifier for room pairing."""
    return uuid.uuid4().hex[:12]


def get_local_ip() -> str:
    """
    Detect the machine's LAN IPv4 address.
    Uses a UDP socket trick — no packets are actually sent.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
    except OSError:
        pass

    # Fallback: enumerate interfaces
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip.startswith("192.168.") or ip.startswith("10.") or re.match(r"172\.(1[6-9]|2\d|3[01])\.", ip):
                return ip
    except OSError:
        pass

    return "127.0.0.1"


def session_upload_dir(session_id: str) -> Path:
    """Return (and create) the upload directory for a session."""
    path = UPLOADS_DIR / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_filename(name: str) -> str:
    """Strip path components and dangerous characters from a filename."""
    name = os.path.basename(name)
    name = re.sub(r'[<>:"/\\|?*\x00]', "_", name)
    return name or "unnamed_file"


def list_session_files(session_id: str) -> list[dict]:
    """List files available for download in a session."""
    folder = session_upload_dir(session_id)
    files = []
    for entry in folder.iterdir():
        if entry.is_file():
            stat = entry.stat()
            files.append({
                "name": entry.name,
                "size": stat.st_size,
                "modified": stat.st_mtime,
            })
    files.sort(key=lambda f: f["modified"], reverse=True)
    return files


def delete_file(session_id: str, filename: str) -> bool:
    """Delete a single file from a session upload folder."""
    path = session_upload_dir(session_id) / safe_filename(filename)
    if path.is_file():
        path.unlink()
        return True
    return False


def cleanup_old_files(max_age_seconds: int = FILE_TTL_SECONDS) -> int:
    """Remove stale files across all sessions. Returns count deleted."""
    if not UPLOADS_DIR.exists():
        return 0

    now = time.time()
    deleted = 0
    for session_dir in UPLOADS_DIR.iterdir():
        if not session_dir.is_dir():
            continue
        for file_path in session_dir.iterdir():
            if file_path.is_file() and (now - file_path.stat().st_mtime) > max_age_seconds:
                file_path.unlink()
                deleted += 1
        # Remove empty session folders
        try:
            if session_dir.is_dir() and not any(session_dir.iterdir()):
                session_dir.rmdir()
        except OSError:
            pass
    return deleted


def cleanup_session(session_id: str) -> None:
    """Remove all files for a session."""
    folder = UPLOADS_DIR / session_id
    if folder.exists():
        shutil.rmtree(folder, ignore_errors=True)


def format_size(num_bytes: int) -> str:
    """Human-readable file size."""
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"
