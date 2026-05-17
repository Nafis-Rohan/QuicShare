/**
 * Load Socket.IO client (server or CDN), then start app.js.
 */
(function () {
  "use strict";

  var APP = "/app.js?v=5";
  var CDN = "https://cdn.socket.io/4.7.5/socket.io.min.js";

  function addScript(src, done) {
    var s = document.createElement("script");
    s.src = src;
    s.async = false;
    s.onload = function () { done(null); };
    s.onerror = function () { done(new Error("load failed: " + src)); };
    document.body.appendChild(s);
  }

  function startApp() {
    addScript(APP, function () {});
  }

  function loadSocketThenApp() {
    if (typeof io !== "undefined") {
      startApp();
      return;
    }
    addScript("/socket.io/socket.io.js", function () {
      if (typeof io !== "undefined") {
        startApp();
        return;
      }
      addScript(CDN, function () {
        startApp();
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadSocketThenApp);
  } else {
    loadSocketThenApp();
  }
})();
