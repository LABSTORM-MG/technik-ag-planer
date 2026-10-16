// Bottom-Sheets: öffnen, schließen (Button, Hintergrund, Escape) und nach unten wischen.
(() => {
  "use strict";

  const CLOSE_DISTANCE = 80; // px, ab denen ein Wisch nach unten schließt

  document.addEventListener("click", (event) => {
    const opener = event.target.closest("[data-sheet-open]");
    if (opener) {
      const sheet = document.getElementById(opener.dataset.sheetOpen);
      if (sheet && !sheet.open) sheet.showModal();
      return;
    }

    const closer = event.target.closest("[data-sheet-close]");
    if (closer) {
      closer.closest("dialog")?.close();
      return;
    }

    // Klick auf den abgedunkelten Hintergrund
    if (event.target instanceof HTMLDialogElement && event.target.matches("[data-sheet]")) {
      const rect = event.target.getBoundingClientRect();
      const inside =
        event.clientX >= rect.left && event.clientX <= rect.right &&
        event.clientY >= rect.top && event.clientY <= rect.bottom;
      if (!inside) event.target.close();
    }
  });

  document.querySelectorAll("[data-sheet]").forEach((sheet) => {
    const grip = sheet.querySelector("[data-sheet-grip]");
    if (!grip) return;

    let startY = null;

    grip.addEventListener("pointerdown", (event) => {
      startY = event.clientY;
      grip.setPointerCapture(event.pointerId);
    });

    grip.addEventListener("pointermove", (event) => {
      if (startY === null) return;
      const offset = Math.max(0, event.clientY - startY);
      sheet.style.transform = `translateY(${offset}px)`;
    });

    const end = (event) => {
      if (startY === null) return;
      const offset = event.clientY - startY;
      startY = null;
      sheet.style.transform = "";
      if (offset > CLOSE_DISTANCE) sheet.close();
    };

    grip.addEventListener("pointerup", end);
    grip.addEventListener("pointercancel", end);
  });
})();
