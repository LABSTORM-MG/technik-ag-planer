// Einstellungen → Benachrichtigungen: Push auf diesem Gerät an- und abmelden.
(() => {
  "use strict";

  const box = document.querySelector("[data-push]");
  if (!box) return;
  const status = box.querySelector("[data-push-status]");
  const enable = box.querySelector("[data-push-enable]");
  const disable = box.querySelector("[data-push-disable]");
  const csrf = box.dataset.csrf;

  const show = (text, { on = false, off = false } = {}) => {
    status.textContent = text;
    enable.hidden = !on;
    disable.hidden = !off;
  };

  const isIos = /iPad|iPhone|iPod/.test(navigator.userAgent);
  const standalone =
    window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;

  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    show(
      isIos && !standalone
        ? "Auf dem iPhone/iPad gehen Push-Mitteilungen nur, wenn die App auf dem Home-Bildschirm liegt: Teilen → „Zum Home-Bildschirm“, dann die App von dort öffnen."
        : "Dieser Browser unterstützt keine Push-Mitteilungen (oder die Seite läuft nicht über HTTPS).",
    );
    return;
  }

  const keyBytes = (base64) => {
    const padded = (base64 + "=".repeat((4 - (base64.length % 4)) % 4))
      .replace(/-/g, "+")
      .replace(/_/g, "/");
    return Uint8Array.from(atob(padded), (c) => c.charCodeAt(0));
  };

  const post = (url, body) =>
    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      credentials: "same-origin",
      body: JSON.stringify(body),
    });

  const refresh = async () => {
    if (Notification.permission === "denied") {
      show("Mitteilungen sind für diese Seite blockiert – bitte in den Browser-Einstellungen erlauben.");
      return;
    }
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription();
    if (subscription) {
      await post(box.dataset.subscribeUrl, subscription.toJSON()); // beim Server aktuell halten
      show("Auf diesem Gerät aktiv.", { off: true });
    } else {
      show("Auf diesem Gerät noch nicht aktiviert.", { on: true });
    }
  };

  enable.addEventListener("click", async () => {
    enable.disabled = true;
    try {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        await refresh();
        return;
      }
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: keyBytes(box.dataset.vapidKey),
      });
      const response = await post(box.dataset.subscribeUrl, subscription.toJSON());
      if (!response.ok) throw new Error("Speichern fehlgeschlagen");
      window.location.reload();
    } catch (error) {
      show("Das hat nicht geklappt. Bitte später erneut versuchen.", { on: true });
    } finally {
      enable.disabled = false;
    }
  });

  disable.addEventListener("click", async () => {
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription();
    if (subscription) {
      await post(box.dataset.unsubscribeUrl, { endpoint: subscription.endpoint });
      await subscription.unsubscribe();
    }
    window.location.reload();
  });

  refresh();
})();
