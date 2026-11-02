// Bottom-Sheets: öffnen, schließen (Button, Hintergrund, Escape) und nach unten wischen.
(() => {
  "use strict";

  const CLOSE_DISTANCE = 80; // px, ab denen ein Wisch nach unten schließt

  const closeSheet = (sheet) => {
    if (window.confirmLeaveForm?.(sheet) !== false) sheet.close();
  };

  // Escape: abbrechbar, damit die Warnung vor ungespeicherten Änderungen greift
  document.addEventListener(
    "cancel",
    (event) => {
      if (event.target.matches?.("[data-sheet]") && window.confirmLeaveForm?.(event.target) === false) {
        event.preventDefault();
      }
    },
    true,
  );

  document.addEventListener("click", (event) => {
    const opener = event.target.closest("[data-sheet-open]");
    if (opener) {
      const sheet = document.getElementById(opener.dataset.sheetOpen);
      if (sheet && !sheet.open) sheet.showModal();
      return;
    }

    const closer = event.target.closest("[data-sheet-close]");
    if (closer) {
      const dialog = closer.closest("dialog");
      if (dialog) closeSheet(dialog);
      return;
    }

    // Klick auf den abgedunkelten Hintergrund
    if (event.target instanceof HTMLDialogElement && event.target.matches("[data-sheet]")) {
      const rect = event.target.getBoundingClientRect();
      const inside =
        event.clientX >= rect.left && event.clientX <= rect.right &&
        event.clientY >= rect.top && event.clientY <= rect.bottom;
      if (!inside) closeSheet(event.target);
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
      if (offset > CLOSE_DISTANCE) closeSheet(sheet);
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

// Material-Auswahl: Suche und Filter nur mit JavaScript, ohne bleibt die ganze Liste nutzbar.
// Über das Dokument, weil Sheet-Inhalte erst später in die Seite kommen.
function filterPicker(picker) {
  const query = picker.querySelector("[data-picker-search]").value.trim().toLowerCase();
  const category = picker.querySelector("[data-picker-category][aria-current]")?.dataset.pickerCategory;
  let visible = 0;
  picker.querySelectorAll("[data-picker-item]").forEach((item) => {
    const match =
      (!category || item.dataset.category === category) &&
      (!query || item.dataset.name.includes(query));
    item.hidden = !match;
    if (match) visible += 1;
  });
  picker.querySelector("[data-picker-empty]").hidden = visible > 0;
}

// Aufklappbare Auswahl: Name übernehmen und wieder zuklappen
document.addEventListener("change", (event) => {
  const collapse = event.target.closest?.("[data-picker-collapse]");
  if (!collapse || event.target.type !== "radio") return;
  const name = event.target.closest("[data-picker-item]").querySelector(".picker__name");
  collapse.querySelector("[data-picker-summary]").textContent = name.textContent;
  collapse.open = false;
});

function enhancePickers(root = document) {
  root.querySelectorAll("[data-picker]").forEach((picker) => {
    picker.querySelector("[data-picker-search]").hidden = false;
    const chips = picker.querySelector("[data-picker-chips]");
    if (chips) chips.hidden = false;
  });
}

enhancePickers();
new MutationObserver(() => enhancePickers()).observe(document.body, { childList: true, subtree: true });
document.addEventListener("input", (event) => {
  const picker = event.target.closest?.("[data-picker-search]")?.closest("[data-picker]");
  if (picker) filterPicker(picker);
});
document.addEventListener("click", (event) => {
  const chip = event.target.closest("[data-picker-category]");
  if (!chip) return;
  const picker = chip.closest("[data-picker]");
  picker.querySelectorAll("[data-picker-category]").forEach((other) => {
    other.removeAttribute("aria-current");
  });
  chip.setAttribute("aria-current", "true");
  filterPicker(picker);
});

// Warnung vor ungespeicherten Änderungen beim Verlassen eines Formulars.
// Vergleicht mit den Startwerten, zurückgesetzte Eingaben zählen also nicht.
(() => {
  const LEAVE_TEXT = "Du hast ungespeicherte Änderungen. Wirklich verlassen, ohne zu speichern?";
  let leaving = false;

  function isDirty(form) {
    return [...form.elements].some((element) => {
      if (!element.name || element.name === "csrfmiddlewaretoken") return false;
      if (element.type === "checkbox" || element.type === "radio") {
        return element.checked !== element.defaultChecked;
      }
      if (element.tagName === "SELECT") {
        return [...element.options].some((option) => option.selected !== option.defaultSelected);
      }
      return "defaultValue" in element && element.value !== element.defaultValue;
    });
  }

  function dirtyForms(root = document) {
    return [...root.querySelectorAll('form.form[method="post"]:not([data-no-unsaved])')].filter(
      (form) => {
        if (!form.closest(".main, dialog")) return false;
        const dialog = form.closest("dialog");
        return (!dialog || dialog.open) && isDirty(form);
      },
    );
  }

  // Für die Sheets: false, wenn jemand lieber bleiben möchte
  window.confirmLeaveForm = (root) => !dirtyForms(root).length || window.confirm(LEAVE_TEXT);

  document.addEventListener("submit", (event) => {
    if (!event.defaultPrevented) leaving = true;
  });

  document.addEventListener(
    "click",
    (event) => {
      const link = event.target.closest?.("a[href]");
      if (!link || link.target === "_blank" || link.hasAttribute("download")) return;
      if ("sheetUrl" in link.dataset || link.getAttribute("href").startsWith("#")) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey) return;
      if (!dirtyForms().length) return;
      if (window.confirm(LEAVE_TEXT)) {
        leaving = true;
      } else {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    },
    true,
  );

  // Zurück-Geste, Tab schließen, Neu laden: Der Browser zeigt seine eigene Nachfrage
  window.addEventListener("beforeunload", (event) => {
    if (leaving || !dirtyForms().length) return;
    event.preventDefault();
    event.returnValue = "";
  });
  window.addEventListener("pageshow", () => {
    leaving = false;
  });
})();

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
    const direct = response.headers.get("X-Sheet-Navigate");
    if (direct) {
      window.location.href = direct;
      return;
    }
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
  data.__rows = form.querySelector("[data-formset]")?.children.length || 0;
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
  while (container && container.children.length < (data.__rows || 0)) addFormsetRow(form, container.dataset.formset);
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

// Formset: „+ Job“, „+ Link“ usw. fügt eine leere Zeile aus <template data-formset-template> ein.
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

// QR-Codes drucken: „Alle auswählen“
document.querySelectorAll("[data-labels]").forEach((form) => {
  const all = form.querySelector("[data-labels-all]");
  const boxes = [...form.querySelectorAll('input[name="ids"]')];
  const update = () => {
    const checked = boxes.filter((box) => box.checked).length;
    all.checked = checked === boxes.length;
    all.indeterminate = checked > 0 && checked < boxes.length;
  };
  all.addEventListener("change", () => {
    boxes.forEach((box) => {
      box.checked = all.checked;
    });
    update();
  });
  boxes.forEach((box) => box.addEventListener("change", update));
  update();
});

// Stundenraster: Pausen anzeigen und neue Stunden sinnvoll vorbelegen
function toMinutes(value) {
  const [hours, minutes] = value.split(":").map(Number);
  return hours * 60 + minutes;
}

function toTime(minutes) {
  const wrapped = Math.min(minutes, 23 * 60 + 59);
  return `${String(Math.floor(wrapped / 60)).padStart(2, "0")}:${String(wrapped % 60).padStart(2, "0")}`;
}

function activePeriodRows(root) {
  return [...root.querySelectorAll("[data-period-row]")].filter(
    (row) => !row.querySelector('.periods__remove input').checked,
  );
}

function updatePeriodGaps(root) {
  let previousEnd = null;
  activePeriodRows(root).forEach((row) => {
    const [start, end] = row.querySelectorAll('input[type="time"]');
    const gap = row.querySelector("[data-period-gap]");
    const minutes = previousEnd && start.value ? toMinutes(start.value) - toMinutes(previousEnd) : 0;
    gap.hidden = minutes <= 0;
    gap.textContent = minutes > 0 ? `${minutes} Min. Pause` : "";
    previousEnd = end.value || previousEnd;
  });
}

document.querySelectorAll("[data-periods]").forEach((root) => {
  updatePeriodGaps(root);
  root.addEventListener("input", () => updatePeriodGaps(root));
  root.addEventListener("change", () => updatePeriodGaps(root));
  root.querySelector('[data-formset-add="periods"]').addEventListener("click", () => {
    window.setTimeout(() => {
      const rows = activePeriodRows(root);
      const row = rows.at(-1);
      const previous = rows.at(-2);
      const [start, end] = row.querySelectorAll('input[type="time"]');
      if (previous) {
        const [lastStart, lastEnd] = previous.querySelectorAll('input[type="time"]');
        if (lastEnd.value) {
          const length = lastStart.value ? toMinutes(lastEnd.value) - toMinutes(lastStart.value) : 45;
          start.value = lastEnd.value;
          end.value = toTime(toMinutes(lastEnd.value) + Math.max(length, 5));
        }
      }
      updatePeriodGaps(root);
      start.focus();
    });
  });
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
  let polling = null;

  // Bis ganz unten: Das Eingabefeld klebt über dem Seitenende und darf nichts verdecken
  const scrollToEnd = () =>
    requestAnimationFrame(() => window.scrollTo(0, document.documentElement.scrollHeight));

  function autosize() {
    input.style.height = "auto";
    input.style.height = `${input.scrollHeight}px`;
  }

  function poll() {
    // Läuft schon eine Abfrage, warten alle Aufrufer auf deren Ergebnis
    polling ??= fetchNew().finally(() => {
      polling = null;
    });
    return polling;
  }

  async function fetchNew() {
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
    }
  }

  // Tastatur offen lassen: Der Senden-Knopf darf dem Eingabefeld den Fokus nicht nehmen
  const send = form.querySelector("[type=submit]");
  send.addEventListener("mousedown", (event) => event.preventDefault());
  send.addEventListener("touchend", (event) => {
    event.preventDefault();
    form.requestSubmit();
  });

  let sending = false;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (sending || !input.value.trim()) return;
    sending = true;
    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { "X-Board": "1" },
      });
      if (response.status === 204) {
        input.value = "";
        autosize();
        // Eine laufende Abfrage kennt die neue Nachricht vielleicht noch nicht
        await polling;
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
      sending = false;
    }
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  input.addEventListener("input", autosize);

  // Das Eingabefeld ist fest positioniert: Platz dafür freihalten, auch wenn es wächst
  const root = document.documentElement;
  new ResizeObserver(() => {
    root.style.setProperty("--chat-input-height", `${form.offsetHeight}px`);
  }).observe(form);

  // Offene Tastatur: Viele Browser verkleinern nur den sichtbaren Bereich
  const viewport = window.visualViewport;
  if (viewport) {
    const placeAboveKeyboard = () => {
      const keyboard = window.innerHeight - viewport.height - viewport.offsetTop;
      const open = keyboard > 80 && document.activeElement === input;
      form.classList.toggle("chat-input--keyboard", open);
      root.style.setProperty("--keyboard-height", `${Math.max(0, Math.round(keyboard))}px`);
      if (open) scrollToEnd();
    };
    viewport.addEventListener("resize", placeAboveKeyboard);
    viewport.addEventListener("scroll", placeAboveKeyboard);
    input.addEventListener("blur", placeAboveKeyboard);
  }

  // Chat-Blasen: beim kleinsten Hochscrollen da, beim Runterscrollen wieder weg
  const chatBar = board.querySelector(".chat-bar");
  if (chatBar) {
    let lastY = window.scrollY;
    window.addEventListener(
      "scroll",
      () => {
        const y = window.scrollY;
        if (Math.abs(y - lastY) < 4) return;
        chatBar.classList.toggle("chat-bar--hidden", y > lastY && y > chatBar.offsetHeight);
        lastY = y;
      },
      { passive: true },
    );
  }

  // Auswahl: gedrückt halten (am PC auch Rechtsklick), danach Antippen zum Zu- und Abwählen
  const bar = board.querySelector("[data-chat-select]");
  const selectAll = bar.querySelector("[data-select-all]");
  const editLink = bar.querySelector("[data-select-edit]");
  const copyButton = bar.querySelector("[data-select-copy]");
  const deleteForm = bar.querySelector("[data-select-delete]");
  const HOLD_MS = 450;
  let holdTimer = null;
  let holdStart = null;
  let justHeld = false;

  const selected = () => [...list.querySelectorAll("[data-msg].is-selected")];
  const deletable = () => [...list.querySelectorAll("[data-msg][data-can-delete]")];

  function renderSelection() {
    const items = selected();
    bar.hidden = items.length === 0;
    bar.querySelector("[data-select-count]").textContent = `${items.length} ausgewählt`;
    const single = items.length === 1 ? items[0] : null;
    editLink.hidden = !single?.dataset.editUrl;
    if (single?.dataset.editUrl) editLink.href = single.dataset.editUrl;
    copyButton.hidden = !items.some((item) => item.querySelector(".chat-message__text"));
    deleteForm.hidden = !items.length || !items.every((item) => "canDelete" in item.dataset);
    const all = deletable();
    selectAll.closest("label").hidden = all.length === 0;
    selectAll.checked = all.length > 0 && all.every((item) => item.classList.contains("is-selected"));
    deleteForm.dataset.confirm =
      items.length === 1 ? "Nachricht löschen?" : `${items.length} Nachrichten löschen?`;
    deleteForm.querySelectorAll("[name=ids]").forEach((input) => input.remove());
    items.forEach((item) => {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "ids";
      input.value = item.dataset.msgId;
      deleteForm.append(input);
    });
  }

  function clearSelection() {
    selected().forEach((item) => item.classList.remove("is-selected"));
    renderSelection();
  }

  function hold(item) {
    justHeld = true;
    item.classList.add("is-selected");
    renderSelection();
    navigator.vibrate?.(15);
  }

  function cancelHold() {
    window.clearTimeout(holdTimer);
    holdTimer = null;
  }

  list.addEventListener("pointerdown", (event) => {
    const item = event.target.closest("[data-msg]");
    if (!item || event.button !== 0) return;
    justHeld = false;
    holdStart = [event.clientX, event.clientY];
    holdTimer = window.setTimeout(() => hold(item), HOLD_MS);
  });
  list.addEventListener("pointermove", (event) => {
    if (!holdTimer) return;
    if (Math.hypot(event.clientX - holdStart[0], event.clientY - holdStart[1]) > 10) cancelHold();
  });
  ["pointerup", "pointercancel", "pointerleave"].forEach((name) => {
    list.addEventListener(name, cancelHold);
  });
  list.addEventListener("contextmenu", (event) => {
    const item = event.target.closest("[data-msg]");
    if (!item) return;
    event.preventDefault();
    cancelHold();
    if (!item.classList.contains("is-selected")) hold(item);
  });
  list.addEventListener("click", (event) => {
    const item = event.target.closest("[data-msg]");
    if (justHeld) {
      justHeld = false;
      event.preventDefault();
      return;
    }
    if (!selected().length) return;
    event.preventDefault();
    if (!item) return;
    item.classList.toggle("is-selected");
    renderSelection();
  });
  selectAll.addEventListener("change", () => {
    selected().forEach((item) => item.classList.remove("is-selected"));
    if (selectAll.checked) deletable().forEach((item) => item.classList.add("is-selected"));
    renderSelection();
  });
  bar.querySelector("[data-select-cancel]").addEventListener("click", clearSelection);
  // Absender nur am Anfang und wenn er wechselt, Nachrichten durch eine Leerzeile getrennt
  function copiedText(items) {
    let author = null;
    const parts = [];
    items.forEach((item) => {
      const text = item.querySelector(".chat-message__text")?.innerText.trim();
      if (!text) return;
      parts.push(item.dataset.author !== author ? `${item.dataset.author}: ${text}` : text);
      author = item.dataset.author;
    });
    return parts.join("\n\n");
  }

  copyButton.addEventListener("click", async () => {
    const text = copiedText(selected());
    if (text) await navigator.clipboard?.writeText(text);
    clearSelection();
  });
  editLink.addEventListener("click", () => window.setTimeout(clearSelection));

  window.setInterval(() => {
    if (document.visibilityState === "visible") poll();
  }, POLL_MS);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") poll();
  });
  if (!window.location.hash || window.location.hash === "#ende") scrollToEnd();
})();

// Technik-Anfragen: „Kopieren“ (data-copy="Text") und „Einfügen“ (data-paste="feld-id").
// Einfügen nimmt den zuletzt auf der Seite kopierten Text – das klappt in jedem Browser –,
// sonst die Zwischenablage (nicht überall erlaubt).
(() => {
  let lastCopied = null;

  const flash = (button, text) => {
    const original = button.textContent;
    button.textContent = text;
    setTimeout(() => {
      button.textContent = original;
    }, 1200);
  };

  document.addEventListener("click", async (event) => {
    const copy = event.target.closest("[data-copy]");
    if (copy) {
      lastCopied = copy.dataset.copy;
      try {
        await navigator.clipboard.writeText(lastCopied);
      } catch {
        /* Zwischenablage gesperrt – „Einfügen“ funktioniert trotzdem */
      }
      flash(copy, "Kopiert ✓");
      return;
    }
    const paste = event.target.closest("[data-paste]");
    if (!paste) return;
    let text = lastCopied;
    if (text === null) {
      try {
        text = await navigator.clipboard.readText();
      } catch {
        text = null;
      }
    }
    const field = document.getElementById(paste.dataset.paste);
    if (text === null || !field) {
      flash(paste, "Erst kopieren");
      return;
    }
    field.value = text;
    field.dispatchEvent(new Event("input", { bubbles: true }));
    field.focus();
  });

  // Geteilte Ansicht: auf schmalen Bildschirmen Umschalter „Anfrage | Produktion“
  document.querySelectorAll("[data-split]").forEach((split) => {
    split.classList.add("split--js");
    const links = split.querySelectorAll("[data-split-switch] [data-show]");
    const show = (name) => {
      split.querySelectorAll("[data-pane]").forEach((pane) => {
        pane.classList.toggle("is-active", pane.dataset.pane === name);
      });
      links.forEach((link) => {
        if (link.dataset.show === name) link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
      });
    };
    links.forEach((link) =>
      link.addEventListener("click", (event) => {
        event.preventDefault();
        show(link.dataset.show);
      }),
    );
    show(split.dataset.split || "anfrage");
  });
})();

// Teilen: Am Handy das Teilen-Menü des Systems, am Computer „Link kopieren“.
(() => {
  "use strict";

  const button = document.querySelector("[data-share-pdf]");
  if (!button) return;
  const url = new URL(button.dataset.sharePdf, window.location.href).href;
  const title = button.dataset.shareTitle;
  const phone = Boolean(navigator.share) && window.matchMedia("(pointer: coarse)").matches;
  button.hidden = false;

  if (!phone) {
    button.textContent = "Link kopieren";
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(url);
        button.textContent = "Link kopiert";
      } catch {
        window.prompt("Link zum Kopieren:", url);
      }
    });
    return;
  }

  // Die Datei liegt beim Klick schon bereit: Teilen geht nur direkt aus dem Antippen heraus
  let file = null;
  if (navigator.canShare) {
    fetch(url, { credentials: "same-origin" })
      .then((response) => (response.ok ? response.blob() : Promise.reject(response.status)))
      .then((blob) => {
        const candidate = new File([blob], button.dataset.shareName, { type: "application/pdf" });
        if (navigator.canShare({ files: [candidate] })) file = candidate;
      })
      .catch(() => {});
  }
  button.addEventListener("click", () => {
    const data = file ? { files: [file], title } : { url, title };
    navigator.share(data).catch(() => {});
  });
})();

// Service Worker für Push-Mitteilungen (kein Offline-Modus). Nur über HTTPS bzw. localhost.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {});
  });
}
