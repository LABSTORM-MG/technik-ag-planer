// Service Worker der App: nur Push-Mitteilungen, kein Offline-Modus (Abschnitt 1).
"use strict";

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (error) {
    data = { title: event.data ? event.data.text() : "" };
  }
  event.waitUntil(
    self.registration.showNotification(data.title || "Technik-AG Planer", {
      body: data.body || "",
      tag: data.tag || undefined,
      renotify: Boolean(data.tag),
      icon: "{{ icon }}",
      badge: "{{ icon }}",
      lang: "de",
      data: { url: data.url || "/" },
    }),
  );
});

// Antippen öffnet die passende Seite – im schon offenen Fenster, sonst in einem neuen
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = new URL(event.notification.data?.url || "/", self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      for (const client of windows) {
        if (client.url.startsWith(self.location.origin) && "focus" in client) {
          client.navigate(url);
          return client.focus();
        }
      }
      return self.clients.openWindow(url);
    }),
  );
});

// Ändert der Browser das Abo (z. B. abgelaufen), merkt sich die App das beim nächsten Öffnen
self.addEventListener("pushsubscriptionchange", () => {});
