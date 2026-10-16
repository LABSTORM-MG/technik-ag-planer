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

// Auswahlfelder, die beim Ändern direkt absenden (z. B. „AG wechseln“)
document.addEventListener("change", (event) => {
  const form = event.target.closest("form[data-auto-submit]");
  if (form && event.target.matches("select")) form.requestSubmit();
});

// Sicherheitsabfrage vor folgenreichen Aktionen: <form data-confirm="Wirklich …?">
document.addEventListener("submit", (event) => {
  const message = event.target.dataset?.confirm;
  if (message && !window.confirm(message)) event.preventDefault();
});

// Formulare im Bottom-Sheet: <a href="…" data-sheet-url> lädt die Seite ohne Rahmen ins Sheet.
// Ohne JavaScript öffnet der Link einfach die normale Seite.
document.addEventListener("click", async (event) => {
  const link = event.target.closest("a[data-sheet-url]");
  if (!link || event.metaKey || event.ctrlKey || event.shiftKey) return;
  const sheet = document.getElementById("sheet-form");
  if (!sheet) return;
  event.preventDefault();
  try {
    const response = await fetch(link.href, { headers: { "X-Sheet": "1" }, cache: "no-store" });
    if (!response.ok || response.redirected) throw new Error(String(response.status));
    const body = sheet.querySelector("[data-sheet-body]");
    body.innerHTML = await response.text();
    const heading = body.querySelector(".sheet-title");
    sheet.querySelector(".sheet__title").textContent = heading ? heading.textContent : "";
    document.getElementById("sheet-new")?.close();
    if (!sheet.open) sheet.showModal();
    initForms(body);
    body.querySelector("[autofocus]")?.focus();
  } catch {
    window.location.href = link.href;
  }
});

// Entwürfe: <form data-draft="schlüssel"> wird im Browser zwischengespeichert.
const DRAFT_PREFIX = "entwurf:";

function storage() {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function saveDraft(form) {
  const data = {};
  for (const element of form.elements) {
    if (!element.name || element.type === "hidden" || element.type === "password") continue;
    if (element.type === "checkbox") data[element.name] = element.checked;
    else if (element.type === "radio") {
      if (element.checked) data[element.name] = element.value;
    } else data[element.name] = element.value;
  }
  data.__jobs = form.querySelectorAll("[data-formset] > .job-form").length;
  try {
    storage()?.setItem(DRAFT_PREFIX + form.dataset.draft, JSON.stringify(data));
  } catch {
    /* Speicher voll oder gesperrt – Entwurf entfällt */
  }
}

function restoreDraft(form) {
  let data;
  try {
    data = JSON.parse(storage()?.getItem(DRAFT_PREFIX + form.dataset.draft) || "null");
  } catch {
    data = null;
  }
  if (!data) return;
  const container = form.querySelector("[data-formset]");
  while (container && container.children.length < (data.__jobs || 0)) addFormsetRow(form, container.dataset.formset);
  for (const element of form.elements) {
    if (!element.name || !(element.name in data)) continue;
    if (element.type === "checkbox") element.checked = Boolean(data[element.name]);
    else if (element.type === "radio") element.checked = element.value === data[element.name];
    else element.value = data[element.name];
  }
  form.querySelector("[data-draft-note]")?.removeAttribute("hidden");
}

function clearDraft(form) {
  try {
    storage()?.removeItem(DRAFT_PREFIX + form.dataset.draft);
  } catch {
    /* nichts zu tun */
  }
}

// Formset: „+ Job“ fügt eine leere Zeile aus <template data-formset-template> ein.
function addFormsetRow(form, prefix) {
  const container = form.querySelector(`[data-formset="${prefix}"]`);
  const template = form.querySelector(`[data-formset-template="${prefix}"]`);
  const total = form.querySelector(`[name="${prefix}-TOTAL_FORMS"]`);
  if (!container || !template || !total) return;
  const index = Number(total.value);
  container.insertAdjacentHTML("beforeend", template.innerHTML.replaceAll("__prefix__", String(index)));
  total.value = String(index + 1);
}

function initForms(root) {
  root.querySelectorAll("form[data-draft]").forEach((form) => {
    if (form.dataset.draftReady) return;
    form.dataset.draftReady = "1";
    restoreDraft(form);
    form.addEventListener("input", () => saveDraft(form));
    form.addEventListener("change", () => saveDraft(form));
    form.addEventListener("submit", () => clearDraft(form));
    form.querySelector("[data-draft-discard]")?.addEventListener("click", () => {
      clearDraft(form);
      form.reset();
      form.querySelector("[data-draft-note]")?.setAttribute("hidden", "");
      const sheet = form.closest("dialog");
      if (sheet) sheet.close();
      else window.location.reload();
    });
  });
  root.querySelectorAll("[data-formset-add]").forEach((button) => {
    if (button.dataset.ready) return;
    button.dataset.ready = "1";
    button.addEventListener("click", () => {
      const form = button.closest("form");
      addFormsetRow(form, button.dataset.formsetAdd);
      if (form.dataset.draft) saveDraft(form);
    });
  });
}

initForms(document);

// Schulstunde gewählt → zugehöriges Zeitfeld sofort ausfüllen (Server rechnet zusätzlich um)
document.addEventListener("change", (event) => {
  const select = event.target.closest("select[data-period-map]");
  if (!select || !select.value) return;
  const target = document.getElementById(select.dataset.periodTarget.replace("__prefix__", ""))
    || select.closest(".time-period")?.querySelector('input[type="time"]');
  const times = JSON.parse(select.dataset.periodMap)[select.value];
  if (target && times) target.value = select.dataset.periodEdge === "start" ? times[0] : times[1];
});

// Board: neue Nachrichten alle 10 s holen, per fetch senden, Enter sendet (Shift+Enter = neue Zeile).
// Ohne JavaScript funktioniert alles über normale Formulare und Neuladen der Seite.
(() => {
  const board = document.querySelector("[data-board]");
  if (!board) return;
  const POLL_MS = 10000;
  const list = board.querySelector("[data-board-list]");
  const form = board.querySelector("[data-board-form]");
  const input = form.querySelector("textarea");
  let lastId = Number(board.dataset.lastId) || 0;
  let busy = false;

  const scrollToEnd = () => document.getElementById("ende")?.scrollIntoView({ block: "end" });

  function autosize() {
    input.style.height = "auto";
    input.style.height = `${input.scrollHeight}px`;
  }

  async function poll() {
    if (busy) return;
    busy = true;
    try {
      const url = new URL(board.dataset.pollUrl, window.location.href);
      url.searchParams.set("nach", String(lastId));
      const response = await fetch(url, { cache: "no-store" });
      if (response.status !== 200) return;
      const nearEnd = window.innerHeight + window.scrollY >= document.body.scrollHeight - 160;
      list.querySelectorAll("[data-board-last]").forEach((el) => el.remove());
      const template = document.createElement("template");
      template.innerHTML = await response.text();
      // Datumstrenner nicht doppelt anzeigen
      template.content.querySelectorAll("[data-day]").forEach((day) => {
        if (list.querySelector(`[data-day="${day.dataset.day}"]`)) day.remove();
      });
      list.append(template.content);
      lastId = Number(list.querySelector("[data-board-last]")?.dataset.boardLast) || lastId;
      board.querySelector("[data-board-empty]")?.remove();
      if (nearEnd) scrollToEnd();
    } catch {
      /* offline – nächster Versuch beim nächsten Intervall */
    } finally {
      busy = false;
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!input.value.trim()) return;
    const button = form.querySelector("[type=submit]");
    button.disabled = true;
    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { "X-Board": "1" },
      });
      if (response.status === 204) {
        input.value = "";
        autosize();
        await poll();
        scrollToEnd();
      } else if (response.status === 400) {
        window.alert(await response.text());
      } else {
        form.submit();
      }
    } catch {
      form.submit();
    } finally {
      button.disabled = false;
      input.focus();
    }
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  input.addEventListener("input", autosize);

  window.setInterval(() => {
    if (document.visibilityState === "visible") poll();
  }, POLL_MS);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") poll();
  });
  if (!window.location.hash || window.location.hash === "#ende") scrollToEnd();
})();
