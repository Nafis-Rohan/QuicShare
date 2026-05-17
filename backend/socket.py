"""
Flask-SocketIO event handlers for QuickShare.
Import via importlib in app.py to avoid clashing with Python's stdlib 'socket'.
"""

from flask import request
from flask_socketio import join_room, leave_room, emit

# In-memory session state (no database)
# session_id -> { "devices": { sid: {name, role, connected_at} } }
sessions: dict[str, dict] = {}


def _room(session_id: str) -> str:
    return f"session_{session_id}"


def register_socket_events(socketio):
    """Register all Socket.IO event handlers on the given SocketIO instance."""

    @socketio.on("connect")
    def on_connect():
        emit("connected", {"sid": request.sid})

    @socketio.on("disconnect")
    def on_disconnect():
        sid = request.sid
        for session_id, data in list(sessions.items()):
            devices = data.get("devices", {})
            if sid in devices:
                device = devices.pop(sid)
                leave_room(_room(session_id))
                emit(
                    "device_left",
                    {"sid": sid, "device": device, "count": len(devices)},
                    room=_room(session_id),
                )
                if not devices:
                    sessions.pop(session_id, None)

    @socketio.on("join_session")
    def on_join_session(data):
        """
        Client joins a session room.
        Payload: { session_id, device_name?, role? }  role: 'pc' | 'phone'
        """
        session_id = (data or {}).get("session_id", "").strip()
        if not session_id:
            emit("error", {"message": "Missing session_id"})
            return

        role = (data or {}).get("role", "unknown")
        device_name = (data or {}).get("device_name") or (
            "PC" if role == "pc" else "Phone"
        )

        if session_id not in sessions:
            sessions[session_id] = {"devices": {}}

        join_room(_room(session_id))
        sessions[session_id]["devices"][request.sid] = {
            "name": device_name,
            "role": role,
            "sid": request.sid,
        }

        devices = list(sessions[session_id]["devices"].values())
        emit(
            "join_room",
            {
                "session_id": session_id,
                "sid": request.sid,
                "devices": devices,
            },
        )
        emit(
            "device_joined",
            {
                "sid": request.sid,
                "device": sessions[session_id]["devices"][request.sid],
                "devices": devices,
                "count": len(devices),
            },
            room=_room(session_id),
            include_self=False,
        )

    @socketio.on("connect_to_server")
    def on_connect_to_server(data):
        """Alias used by mobile client — forwards to join_session."""
        on_join_session(data)

    @socketio.on("file_upload")
    def on_file_upload(data):
        """Notify room that a file was uploaded via HTTP."""
        session_id = (data or {}).get("session_id")
        file_info = (data or {}).get("file")
        if not session_id or not file_info:
            return
        emit(
            "file_receive",
            {"file": file_info, "from": request.sid},
            room=_room(session_id),
            include_self=False,
        )
        emit("file_transfer", {"status": "ready", "file": file_info})

    @socketio.on("file_transfer")
    def on_file_transfer(data):
        """Relay transfer status / metadata to the session room."""
        session_id = (data or {}).get("session_id")
        if not session_id:
            return
        emit("file_transfer", data, room=_room(session_id), include_self=False)

    @socketio.on("send_file")
    def on_send_file(data):
        """Signal that a file send is starting (metadata before HTTP upload)."""
        session_id = (data or {}).get("session_id")
        if not session_id:
            return
        emit(
            "receive_file",
            {**data, "from": request.sid},
            room=_room(session_id),
            include_self=False,
        )

    @socketio.on("receive_file")
    def on_receive_file(data):
        """Acknowledge file received on client."""
        session_id = (data or {}).get("session_id")
        if session_id:
            emit("receive_file", data, room=_room(session_id))

    @socketio.on("progress")
    def on_progress(data):
        """Broadcast upload/download progress to session."""
        session_id = (data or {}).get("session_id")
        if not session_id:
            return
        emit(
            "progress_update",
            data,
            room=_room(session_id),
            include_self=False,
        )

    @socketio.on("progress_update")
    def on_progress_update(data):
        session_id = (data or {}).get("session_id")
        if session_id:
            emit("progress_update", data, room=_room(session_id), include_self=False)

    @socketio.on("file_send")
    def on_file_send(data):
        """Notify peers of outgoing file (Snapdrop-style event name)."""
        session_id = (data or {}).get("session_id")
        if session_id:
            emit("file_send", data, room=_room(session_id), include_self=False)

    @socketio.on("file_receive")
    def on_file_receive(data):
        session_id = (data or {}).get("session_id")
        if session_id:
            emit("file_receive", data, room=_room(session_id), include_self=False)

    return socketio


def get_session_devices(session_id: str) -> list:
    """Return connected devices for a session."""
    if session_id not in sessions:
        return []
    return list(sessions[session_id].get("devices", {}).values())
