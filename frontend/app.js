/**
 * QuickShare client — Socket.IO + HTTP file transfer
 */

(function () {
  "use strict";

  const ROLE = document.body.dataset.role || "pc";
  const pathMatch = window.location.pathname.match(/\/session\/([a-f0-9]+)/i);
  let sessionId = pathMatch ? pathMatch[1] : null;
  let socket = null;
  let serverInfo = null;
  let appReady = false;

  const $ = (sel) => document.querySelector(sel);

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
  }

  function setStatus(connected, text) {
    const pill = $("#connection-status");
    if (!pill) return;
    pill.classList.toggle("connected", connected);
    const label = pill.querySelector(".status-text");
    if (label) label.textContent = text || (connected ? "Connected" : "Connecting…");
  }

  function showMessage(message, type) {
    const phoneStatus = $("#phone-status");
    if (phoneStatus) {
      phoneStatus.textContent = message;
      phoneStatus.classList.toggle("upload-error", type === "error");
      phoneStatus.classList.toggle("upload-ok", type === "ok");
    }
    logTransfer(message, type);
  }

  function logTransfer(message, type) {
    const log = $("#transfer-log");
    if (!log) return;
    const empty = log.querySelector(".empty-state");
    if (empty) empty.remove();
    const el = document.createElement("div");
    el.className = "transfer-item";
    el.innerHTML =
      '<span class="name">' +
      message +
      '</span><span class="badge">' +
      (type || "info") +
      "</span>";
    log.prepend(el);
    while (log.children.length > 20) log.lastChild.remove();
  }

  function renderDevices(devices) {
    const list = $("#device-list");
    const countEl = $("#device-count");
    if (!list) return;
    list.innerHTML = "";
    if (!devices || !devices.length) {
      list.innerHTML = '<li class="empty-state">Waiting for phone…</li>';
      if (countEl) countEl.textContent = "0";
      return;
    }
    if (countEl) countEl.textContent = String(devices.length);
    devices.forEach((d) => {
      const li = document.createElement("li");
      const icon = d.role === "pc" ? "🖥️" : "📱";
      li.innerHTML =
        '<span class="device-icon">' +
        icon +
        '</span><span>' +
        (d.name || d.role) +
        " (" +
        d.role +
        ")</span>";
      list.appendChild(li);
    });
  }

  function renderFiles(files) {
    const list = $("#file-list");
    if (!list) return;
    list.innerHTML = "";
    if (!files || !files.length) {
      list.innerHTML = '<li class="empty-state">No files yet</li>';
      return;
    }
    files.forEach((f) => {
      const li = document.createElement("li");
      const size = f.size_human || formatSize(f.size);
      const actions = document.createElement("div");
      actions.style.display = "flex";
      actions.style.gap = "0.5rem";
      const dl = document.createElement("button");
      dl.className = "btn btn-primary";
      dl.textContent = "Download";
      dl.onclick = () => downloadFile(f.name);
      const del = document.createElement("button");
      del.className = "btn btn-ghost";
      del.textContent = "×";
      del.title = "Delete";
      del.onclick = () => deleteFile(f.name);
      actions.appendChild(dl);
      actions.appendChild(del);
      li.innerHTML =
        '<div class="file-meta"><div class="fname">' +
        f.name +
        '</div><div class="fsize">' +
        size +
        "</div></div>";
      li.appendChild(actions);
      list.appendChild(li);
    });
  }

  async function fetchInfo() {
    const res = await fetch("/api/info");
    if (!res.ok) {
      throw new Error("Cannot reach QuickShare server");
    }
    serverInfo = await res.json();
    const serverSession = serverInfo.session_id;

    // Always use the server's active session (QR may be stale after restart)
    if (ROLE === "phone" && sessionId && sessionId !== serverSession) {
      window.location.replace("/session/" + serverSession);
      return null;
    }
    sessionId = serverSession;

    const qrImg = $("#qr-code");
    if (qrImg && serverInfo.qr_url) {
      qrImg.src = serverInfo.qr_url + "&_=" + Date.now();
    }
    const urlEl = $("#session-url");
    if (urlEl) urlEl.textContent = serverInfo.session_url;

    const sidEl = $("#session-id");
    if (sidEl) sidEl.textContent = sessionId;

    return serverInfo;
  }

  async function refreshFiles() {
    if (!sessionId) return;
    try {
      const res = await fetch("/api/files?session_id=" + encodeURIComponent(sessionId));
      if (!res.ok) return;
      const data = await res.json();
      renderFiles(data.files);
    } catch (_err) {
      /* ignore refresh errors */
    }
  }

  function joinSocketRoom() {
    if (!socket || !socket.connected || !sessionId) return;
    const payload = {
      session_id: sessionId,
      role: ROLE,
      device_name: ROLE === "pc" ? "PC Host" : "Mobile",
    };
    socket.emit("join_session", payload);
    if (ROLE === "phone") socket.emit("connect_to_server", payload);
  }

  function connectSocket() {
    if (typeof io === "undefined") {
      setStatus(true, ROLE === "pc" ? "Server ready" : "Connected");
      return;
    }

    socket = io({ transports: ["websocket", "polling"] });

    socket.on("connect", function () {
      setStatus(true, ROLE === "pc" ? "Server ready" : "Connected to PC");
      joinSocketRoom();
    });

    socket.on("disconnect", function () {
      setStatus(false, "Disconnected");
    });

    socket.on("join_room", function (data) {
      renderDevices(data.devices);
    });

    socket.on("device_joined", function (data) {
      renderDevices(data.devices);
      logTransfer((data.device && data.device.name) + " joined", "ok");
      if (ROLE === "phone") setStatus(true, "Connected to PC");
    });

    socket.on("device_left", function () {
      logTransfer("Device left", "warn");
      refreshFiles();
    });

    socket.on("file_receive", function (data) {
      showMessage("Received: " + (data.file && data.file.name), "receive");
      refreshFiles();
    });

    socket.on("file_transfer", function (data) {
      if (data.file) showMessage("Transfer: " + data.file.name, data.status || "info");
      refreshFiles();
    });

    socket.on("receive_file", function (data) {
      logTransfer("Peer sending: " + (data.name || "file"), "send");
    });

    socket.on("progress_update", function (data) {
      const bar = $("#progress-fill");
      const label = $("#progress-label");
      if (bar) bar.style.width = (data.progress || 0) + "%";
      if (label) {
        label.textContent =
          (data.file || "") +
          " — " +
          (data.progress || 0) +
          "%" +
          (data.phase ? " (" + data.phase + ")" : "");
      }
    });
  }

  function uploadFile(file) {
    if (!file) return;

    if (!appReady || !sessionId) {
      showMessage("Still connecting… wait a moment and try again.", "error");
      return;
    }

    showMessage("Uploading: " + file.name + "…", "info");

    if (socket && socket.connected) {
      socket.emit("send_file", {
        session_id: sessionId,
        name: file.name,
        size: file.size,
      });
    }

    const form = new FormData();
    form.append("file", file);
    form.append("session_id", sessionId);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/upload");

    xhr.upload.onprogress = function (e) {
      if (e.lengthComputable) {
        const pct = Math.round((e.loaded / e.total) * 100);
        if (socket && socket.connected) {
          socket.emit("progress", {
            session_id: sessionId,
            file: file.name,
            progress: pct,
            phase: "upload",
          });
        }
        const bar = $("#progress-fill");
        const label = $("#progress-label");
        if (bar) bar.style.width = pct + "%";
        if (label) label.textContent = file.name + " — " + pct + "%";
        showMessage("Uploading: " + file.name + " (" + pct + "%)", "info");
      }
    };

    xhr.onload = function () {
      const bar = $("#progress-fill");
      let body = null;
      try {
        body = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch (_e) {
        body = null;
      }

      if (xhr.status >= 200 && xhr.status < 300 && body && body.file) {
        if (body.session_id) sessionId = body.session_id;
        showMessage("Uploaded: " + file.name, "ok");
        if (socket && socket.connected) {
          socket.emit("file_upload", {
            session_id: sessionId,
            file: body.file,
          });
        }
        refreshFiles();
      } else {
        const err =
          (body && body.error) ||
          "Upload failed (" + xhr.status + "): " + file.name;
        showMessage(err, "error");
      }
      if (bar) setTimeout(function () { bar.style.width = "0%"; }, 800);
    };

    xhr.onerror = function () {
      showMessage("Upload failed — check Wi‑Fi and that the PC server is running.", "error");
      const bar = $("#progress-fill");
      if (bar) bar.style.width = "0%";
    };

    xhr.send(form);
  }

  function downloadFile(name) {
    if (!sessionId) return;
    const deleteParam = ROLE === "phone" ? "?delete=1" : "";
    const url =
      "/api/download/" +
      encodeURIComponent(sessionId) +
      "/" +
      encodeURIComponent(name) +
      deleteParam;
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    logTransfer("Downloaded: " + name, "ok");
    setTimeout(refreshFiles, 500);
  }

  function deleteFile(name) {
    if (!sessionId) return;
    fetch(
      "/api/delete/" +
        encodeURIComponent(sessionId) +
        "/" +
        encodeURIComponent(name),
      { method: "DELETE" }
    ).then(refreshFiles);
  }

  function setupFileInputs() {
    ["file-input", "phone-file-input"].forEach(function (id) {
      const input = document.getElementById(id);
      if (!input) return;
      input.addEventListener("change", function () {
        const files = Array.from(input.files || []);
        if (!files.length) return;
        files.forEach(uploadFile);
        input.value = "";
      });
    });
  }

  function setupDropZone() {
    const zone = $("#drop-zone");
    if (!zone) return;

    zone.addEventListener("dragover", function (e) {
      e.preventDefault();
      zone.classList.add("dragover");
    });
    zone.addEventListener("dragleave", function () {
      zone.classList.remove("dragover");
    });
    zone.addEventListener("drop", function (e) {
      e.preventDefault();
      zone.classList.remove("dragover");
      Array.from(e.dataTransfer.files).forEach(uploadFile);
    });
  }

  async function init() {
    try {
      const info = await fetchInfo();
      if (info === null) return;

      setupFileInputs();
      setupDropZone();
      appReady = true;

      connectSocket();
      await refreshFiles();
      setInterval(refreshFiles, 4000);

      if (ROLE === "phone") {
        showMessage("Ready — choose files to upload", "ok");
      } else {
        setStatus(true, "Server ready");
      }
    } catch (err) {
      showMessage(err.message || "Failed to connect to server", "error");
      setStatus(false, "Offline");
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
