(function () {
  "use strict";

  function urlBase64ToUint8Array(base64String) {
    var padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    var base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    var rawData = atob(base64);
    var outputArray = new Uint8Array(rawData.length);
    for (var i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }

  function getCsrfToken() {
    var el = document.querySelector("[name=csrfmiddlewaretoken]");
    return el ? el.value : "";
  }

  function enablePush(vapidPublicKey, statusEl) {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
      if (statusEl) statusEl.textContent = "Push notifications aren't supported in this browser.";
      return;
    }

    navigator.serviceWorker
      .register("/service-worker.js")
      .then(function (registration) {
        return Notification.requestPermission().then(function (permission) {
          if (permission !== "granted") {
            throw new Error("Notification permission was not granted.");
          }
          return registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
          });
        });
      })
      .then(function (subscription) {
        return fetch("/notifications/subscribe/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
          body: JSON.stringify(subscription.toJSON()),
        });
      })
      .then(function (res) {
        if (!res.ok) throw new Error("Server rejected the subscription.");
        if (statusEl) statusEl.textContent = "Push notifications enabled on this device.";
      })
      .catch(function (err) {
        if (statusEl) statusEl.textContent = err.message || "Couldn't enable push notifications.";
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var btn = document.getElementById("enable-push-button");
    if (!btn) return;
    var statusEl = document.getElementById("push-status");
    btn.addEventListener("click", function () {
      enablePush(btn.dataset.vapidPublicKey, statusEl);
    });
  });
})();
