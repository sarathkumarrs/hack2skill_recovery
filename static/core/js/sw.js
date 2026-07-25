/* Recovery Pulse service worker.
 * Served both as a static asset (for reference/versioning) and at the root
 * scope via core.views.service_worker — root scope is required for Web Push
 * to have full-site delivery scope. */

self.addEventListener("install", function () {
  self.skipWaiting();
});

self.addEventListener("activate", function (event) {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", function (event) {
  var data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data = { body: event.data.text() };
    }
  }

  var title = data.title || "Recovery Pulse";
  var options = {
    body: data.body || "How are you feeling today?",
    icon: "/static/core/icons/icon.svg",
    badge: "/static/core/icons/icon.svg",
    data: { url: data.url || "/home/" },
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", function (event) {
  event.notification.close();
  var url = (event.notification.data && event.notification.data.url) || "/home/";
  event.waitUntil(self.clients.openWindow(url));
});
