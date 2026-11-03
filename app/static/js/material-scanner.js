(() => {
  const workspace = document.querySelector('[data-issue-workspace]');
  if (!workspace) return;
  const form = document.getElementById('scan-form');
  const button = document.getElementById('camera');
  const status = document.getElementById('scan-status');
  let scanner, active = false, starting = false, busy = false, disposed = false;
  const recent = new Map();

  // Ein Schalter für alles: zeigt nur, was zum gewählten Vorgang gehört
  const radios = [...document.querySelectorAll('input[name="mode"]')];
  const mode = () => radios.find((radio) => radio.checked)?.value || 'issue';
  const applyMode = () => { workspace.dataset.mode = mode(); };
  radios.forEach((radio) => radio.addEventListener('change', applyMode));
  applyMode();

  // Die Meldung klebt über dem Kamerabild, damit man sie beim Scannen sieht
  function show(text, kind = '') {
    status.hidden = false;
    status.textContent = text;
    status.className = kind ? `message message--${kind} inventory-scan-status` : 'inventory-scan-status';
  }

  // Ton ohne Audiodatei; Browser erlauben ihn erst nach einem Tippen, darum unlockAudio
  let audio;
  const unlockAudio = () => {
    const Context = window.AudioContext || window.webkitAudioContext;
    if (!Context) return;
    audio ||= new Context();
    if (audio.state === 'suspended') void audio.resume();
  };
  function beep(ok) {
    if (!audio) return;
    const tones = ok ? [[880, 0], [1320, 0.1]] : [[220, 0], [165, 0.18]];
    for (const [frequency, delay] of tones) {
      const start = audio.currentTime + delay;
      const oscillator = audio.createOscillator();
      const gain = audio.createGain();
      oscillator.type = ok ? 'sine' : 'square';
      oscillator.frequency.value = frequency;
      gain.gain.setValueAtTime(0.3, start);
      gain.gain.exponentialRampToValueAtTime(0.001, start + 0.16);
      oscillator.connect(gain).connect(audio.destination);
      oscillator.start(start);
      oscillator.stop(start + 0.16);
    }
  }

  const toast = document.getElementById('scan-toast');
  let toastTimer;
  function showToast(title, detail, ok) {
    document.getElementById('scan-toast-title').textContent = title;
    document.getElementById('scan-toast-detail').textContent = detail;
    toast.className = `message message--${ok ? 'success' : 'error'} scan-toast`;
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast.hidden = true; }, 3000);
  }

  // Rückmeldung nach dem Speichern: Popup, Ton, Vibration und die Meldung auf der Seite
  function announce(title, detail, ok) {
    show(detail ? `${title}. ${detail}` : title, ok ? 'success' : 'error');
    showToast(title, detail, ok);
    beep(ok);
    navigator.vibrate?.(ok ? 80 : [60, 60, 60]);
  }

  // Stand neu holen, ohne die Seite neu zu laden; Kamera und Scrollposition bleiben
  async function refresh() {
    const page = await fetch(location.href, {credentials: 'same-origin'});
    if (!page.ok) return;
    const next = new DOMParser().parseFromString(await page.text(), 'text/html');
    for (const id of ['material-state', 'issue-progress', 'teardown-state']) {
      const updated = next.getElementById(id);
      if (updated) document.getElementById(id)?.replaceWith(updated);
    }
  }

  async function post(url, data) {
    const response = await fetch(url, {method: 'POST', body: data, headers: {Accept: 'application/json'}, credentials: 'same-origin'});
    if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) throw new Error('Sitzung abgelaufen oder Anfrage fehlgeschlagen. Bitte Seite neu laden.');
    const result = await response.json();
    if (result.name) announce(`„${result.name}“ wurde gescannt`, result.message, result.ok);
    else announce(result.message, '', result.ok);
    if (result.ok) await refresh();
    return result;
  }

  // Mengen: Absenden ohne Neuladen; ohne JavaScript greift das normale Formular
  document.addEventListener('submit', async (event) => {
    const quantity = event.target.closest?.('[data-quantity-form]');
    if (!quantity) return;
    event.preventDefault();
    if (busy) return;
    busy = true;
    unlockAudio();
    try { await post(quantity.action, new FormData(quantity)); }
    catch (error) { announce(error.message, '', false); }
    finally { busy = false; }
  });

  if (!form) return;

  const overlay = document.getElementById('scan-overlay');
  let historyEntry = false;

  async function stop() {
    const wasOpen = !overlay.hidden;
    overlay.hidden = true;
    workspace.append(toast);
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    // Eigener Verlaufseintrag: Der Zurück-Knopf des Handys schließt nur die Kamera
    if (historyEntry && !disposed) { historyEntry = false; history.back(); }
    if (wasOpen) button.focus();
    if (active) { active = false; try { await scanner.stop(); } catch {} }
  }
  window.addEventListener('pagehide', () => { disposed = true; void stop(); });
  window.addEventListener('popstate', () => { if (historyEntry) { historyEntry = false; void stop(); } });
  document.addEventListener('fullscreenchange', () => { if (!document.fullscreenElement && !overlay.hidden) void stop(); });
  document.getElementById('camera-close').addEventListener('click', () => { void stop(); });

  async function submit(code) {
    const now = Date.now();
    // Solange ein Code im Bild bleibt, zählt er nur einmal; sonst piept es alle paar Sekunden
    if ((recent.get(code) || 0) > now - 3000) { recent.set(code, now); return; }
    if (busy) return;
    busy = true;
    recent.set(code, now);
    for (const [key, time] of recent) if (time < now - 10000) recent.delete(key);
    show('Code wird verarbeitet …');
    try {
      const data = new FormData(form);
      data.set('code', code);
      data.set('mode', mode());
      await post(form.action || location.href, data);
      form.elements.code.value = '';
    } catch (error) { announce(error.message, '', false); }
    finally { busy = false; }
  }
  form.addEventListener('submit', (event) => { event.preventDefault(); unlockAudio(); void submit(form.elements.code.value.trim()); });

  const newScanner = (id) => new Html5Qrcode(id, {verbose: false, experimentalFeatures: {useBarCodeDetectorIfSupported: true}});
  // Rückfallweg: Ein Foto ist schärfer als das Kamerabild und braucht keinen Autofokus im Browser
  const photo = document.getElementById('photo');
  const photoReader = document.getElementById('photo-reader');
  photo?.addEventListener('click', unlockAudio);
  photo?.addEventListener('change', async () => {
    const file = photo.files[0];
    photo.value = '';
    if (!file) return;
    try {
      if (!window.Html5Qrcode) throw new Error('Scanner konnte nicht geladen werden. Bitte Code von Hand eingeben.');
      photoReader.hidden = false;
      const code = await newScanner('photo-reader').scanFile(file, false);
      photoReader.hidden = true;
      await submit(code);
    } catch (error) {
      photoReader.hidden = true;
      show(typeof error === 'string' || !error?.message ? 'Im Foto wurde kein QR-Code erkannt. Bitte näher heran und ohne Spiegelung.' : error.message, 'error');
    }
  });

  button.addEventListener('click', async () => {
    if (starting) return;
    starting = true;
    unlockAudio();
    try {
      if (!window.isSecureContext) throw new Error('Die Kamera benötigt HTTPS oder localhost.');
      if (!window.Html5Qrcode) throw new Error('Kamerascanner konnte nicht geladen werden. Bitte Code von Hand eingeben.');
      document.getElementById('scan-overlay-mode').textContent = mode() === 'return' ? 'Rückgabe' : 'Ausgabe';
      overlay.hidden = false;
      overlay.append(toast);
      document.getElementById('camera-close').focus();
      history.pushState({scanCamera: true}, '');
      historyEntry = true;
      // Echtes Vollbild, wo es geht (nicht auf dem iPhone); die Ansicht füllt das Fenster ohnehin
      await overlay.requestFullscreen?.().catch(() => {});
      scanner = newScanner('preview');
      await scanner.start({facingMode: 'environment'}, {fps: 15, videoConstraints: {facingMode: {ideal: 'environment'}, width: {ideal: 1920}, height: {ideal: 1080}, advanced: [{focusMode: 'continuous'}]}, qrbox: (w, h) => {const size = Math.floor(Math.min(w, h) * 0.9); return {width: size, height: size};}}, code => { if (!disposed) void submit(code); }, () => {});
      active = true;
      // In der Zwischenzeit geschlossen: Kamera nicht unsichtbar weiterlaufen lassen
      if (disposed || overlay.hidden) { await stop(); return; }
      show('Kamera aktiv. Etikett in den Rahmen halten.');
    } catch (error) { await stop(); announce(error.message, '', false); }
    finally { starting = false; }
  });
})();
