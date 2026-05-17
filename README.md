# QuickShare

LAN file sharing between your PC and phone — similar to [Snapdrop](https://snapdrop.net/). Run a small server on your PC, scan a QR code from your phone, and send files both ways over the same Wi‑Fi network.

**Not Django** — this project uses **Flask**, **Flask-SocketIO**, and plain HTML/CSS/JavaScript.

---

## Features

- PC web UI with QR code for instant phone pairing
- Mobile-friendly phone UI (`/session/<id>`)
- **Choose files** buttons on PC and phone (plus drag & drop)
- Shared file list on both devices with download and delete
- Real-time updates via Socket.IO (device join/leave, upload progress)
- Uploads work over HTTP even if live sync is unavailable
- Auto-opens browser on PC when the server starts
- Stale file cleanup (~1 hour)
- Max upload size: **512 MB**
- Windows launcher keeps venv, cache, and temp on **D:** (not C:)

---

## Requirements

| Item | Details |
|------|---------|
| OS | Windows 10/11 for `run.bat` / `stop.bat` (server code runs on any OS with Python 3.10+) |
| Python | 3.10 or newer (must be on PATH) |
| Network | PC and phone on the **same local Wi‑Fi** |
| Location | Project folder at **`D:\QuickShare`** (required by the launcher) |
| Browser | Chrome recommended on PC; any modern mobile browser |

> **Note:** Python itself may be installed on C:. Only QuickShare’s project files, venv, uploads, cache, and temp are kept on D:.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Backend | Python, **Flask** 3.x |
| Real-time | **Flask-SocketIO** (threading mode) |
| QR codes | `qrcode` + Pillow |
| Frontend | HTML, CSS, vanilla JavaScript |
| Client loader | `boot.js` (loads Socket.IO from server or CDN fallback) |
| Tests | pytest |

---

## Quick start

1. Place the project at **`D:\QuickShare`**.
2. Double-click **`run.bat`**.
   - First run creates `D:\QuickShare\venv` and installs dependencies.
   - Your browser opens `http://localhost:5000`.
3. On your phone, **scan the QR code** (same Wi‑Fi as the PC).
4. Use **Choose files from PC** or **Choose files from phone** to upload.
5. Download files from **Shared files** on the other device.

### If the server won’t start

| Problem | Fix |
|---------|-----|
| Port already in use | Run **`stop.bat`**, then **`run.bat`** again |
| Another app uses port 5000 | In `run.bat`, add: `set QUICKSHARE_PORT=5001` (near the top) |
| Status shows **Offline** / `io is not defined` | Run `stop.bat` → `run.bat`, then **Ctrl+F5** on PC; rescan QR on phone |
| Upload does nothing | Hard refresh (Ctrl+F5), rescan QR after server restart |
| Phone shows old session | Always scan the **new** QR after restarting the server |

---

## Scripts

| File | Purpose |
|------|---------|
| **`run.bat`** | Start server; create venv on D:; set temp/cache on D:; free port 5000 if a previous Python instance is running |
| **`stop.bat`** | Stop whatever is listening on port 5000 (or `QUICKSHARE_PORT`) |

### What `run.bat` does

- `cd` to `D:\QuickShare`
- Sets `TMP` / `TEMP` → `D:\QuickShare\.tmp`
- Sets `PIP_CACHE_DIR` → `D:\QuickShare\.pip-cache`
- Activates or creates `D:\QuickShare\venv`
- Installs `requirements.txt` if Flask is missing
- Kills a previous QuickShare Python process on the port if needed
- Runs `python -m backend.app`

### Manual start (without `run.bat`)

```bat
cd /d D:\QuickShare
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
set QUICKSHARE_PORT=5000
python -m backend.app
```

---

## Usage

### PC (`http://localhost:5000`)

| Action | How |
|--------|-----|
| Connect | Opened automatically by `run.bat` |
| Upload | **Choose files from PC** or drag & drop into the drop zone |
| Download | **Download** in Shared files |
| Delete | **×** next to a file |
| See activity | **Transfer log** panel |
| Pair phone | Scan the QR code or open the LAN URL shown |

### Phone (`http://<PC-IP>:5000/session/<id>`)

| Action | How |
|--------|-----|
| Connect | Scan QR from PC (do not reuse an old tab after restart) |
| Upload | **Choose files from phone** or drag & drop |
| Download | **Download** in Shared files (removes file from server after download) |
| Status | Message under the Mobile header (uploading / success / error) |

### How sharing works

1. Files upload to the **PC server** via HTTP (`POST /api/upload`).
2. They are saved under `uploads/<session_id>/`.
3. Both PC and phone list the same files via `GET /api/files`.
4. Socket.IO notifies both sides when files change (optional; HTTP still works without it).

Transfers are **not** direct phone-to-phone (no WebRTC). Everything goes through the PC.

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `QUICKSHARE_PORT` | `5000` | HTTP port |
| `QUICKSHARE_SECRET` | built-in local value | Flask secret key (set your own for production) |

Set in `run.bat` before starting, e.g.:

```bat
set QUICKSHARE_PORT=5001
```

---

## Project structure

```
D:\QuickShare\
├── backend/
│   ├── __init__.py
│   ├── app.py          # Flask app, routes, server entry (python -m backend.app)
│   ├── socket.py       # Socket.IO events (join, progress, file notifications)
│   └── utils.py        # Paths, session IDs, file list/delete, cleanup
├── frontend/
│   ├── index.html      # PC UI
│   ├── phone.html      # Mobile UI
│   ├── app.js          # Upload, download, Socket.IO client logic
│   ├── boot.js         # Loads Socket.IO then app.js
│   └── style.css       # Dark UI theme
├── static/
│   └── .gitkeep        # qr.png generated at runtime (gitignored)
├── tests/
│   ├── conftest.py
│   ├── test_api.py
│   └── test_utils.py
├── uploads/            # Per-session files (gitignored, created at runtime)
├── .tmp/               # Temp files (gitignored)
├── .pip-cache/         # Pip cache on D: (gitignored)
├── venv/               # Python virtualenv on D: (gitignored)
├── run.bat             # Start server
├── stop.bat            # Stop server on port
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
├── .gitignore
└── README.md
```

---

## API reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | PC homepage |
| GET | `/phone` | Phone page (optional; session via query) |
| GET | `/session/<session_id>` | Phone entry from QR |
| GET | `/api/info` | Server IP, port, session ID, QR URL, connected devices |
| GET | `/api/files?session_id=` | List files in session |
| POST | `/api/upload` | Multipart upload (`file`, `session_id`) |
| GET | `/api/download/<session_id>/<filename>` | Download file (`?delete=1` removes after send) |
| DELETE | `/api/delete/<session_id>/<filename>` | Delete file |
| GET | `/static/qr.png` | QR code image |
| GET | `/style.css`, `/app.js`, `/boot.js` | Frontend assets |

Socket.IO events (examples): `join_session`, `file_upload`, `file_receive`, `progress`, `device_joined`, `device_left`.

---

## Storage and cleanup

| Path | Contents |
|------|----------|
| `uploads/<session_id>/` | Uploaded files for the current server session |
| `static/qr.png` | QR image (regenerated each server start) |
| `.tmp/` | Windows temp redirected here by `run.bat` |
| `.pip-cache/` | Pip download cache on D: |

- Files older than **~1 hour** are auto-deleted (`cleanup_old_files` in `utils.py`).
- **Restarting the server** creates a new session ID → scan the **new** QR code.
- Phone downloads use `?delete=1` to remove the server copy after download.

---

## Development

### Install dev dependencies

```bat
cd /d D:\QuickShare
venv\Scripts\activate
pip install -r requirements-dev.txt
```

### Run tests

```bat
pytest
```

Tests cover utilities and HTTP API (upload, list, download, delete).

---

## Pushing to Git

Safe to commit: source code, `README.md`, `requirements*.txt`, `run.bat`, `stop.bat`, `pytest.ini`, `static/.gitkeep`, tests.

**Do not commit** (already in `.gitignore`):

- `venv/`
- `uploads/`
- `static/qr.png`
- `.tmp/`, `.pip-cache/`
- `.env`
- `__pycache__/`, `.pytest_cache/`

Example:

```bat
cd /d D:\QuickShare
git init
git add .
git commit -m "Initial commit: QuickShare LAN file sharing"
git remote add origin https://github.com/YOUR_USER/QuickShare.git
git branch -M main
git push -u origin main
```

---

## Security and limitations

- **No login or encryption** — intended for trusted home/office LANs only.
- Anyone on your Wi‑Fi who knows the URL could access files while the server is running.
- Firewall may block phone access; allow Python on private networks if needed.
- Single active session per server run (one QR at a time).
- Not a cloud service; PC must stay on and server running.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `WinError 10048` | Port 5000 in use | `stop.bat` → `run.bat` |
| **Offline** / `io is not defined` | Socket.IO script failed; init crashed | Hard refresh; ensure server is running; `boot.js` loads CDN fallback |
| Upload succeeds but file not visible | Stale session / old QR | Rescan QR after restart |
| Phone can’t connect | Different Wi‑Fi or firewall | Same network; allow port 5000 |
| **Devices (0)** | Phone not joined yet | Scan QR and open the session URL |
| Large file fails | Over 512 MB | Split file or raise limit in `app.py` (`MAX_CONTENT_LENGTH`) |

---

