(() => {
  const workspace = document.querySelector('[data-issue-workspace]');
  if (!workspace) return;
  const form = document.getElementById('scan-form');
  const button = document.getElementById('camera');
  const preview = document.getElementById('preview');
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
    show(result.message, result.ok ? 'success' : 'error');
    navigator.vibrate?.(result.ok ? 80 : [60, 60, 60]);
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
    try { await post(quantity.action, new FormData(quantity)); }
    catch (error) { show(error.message, 'error'); }
    finally { busy = false; }
  });

  if (!form) return;

  async function stop() {
    if (active) { active = false; try { await scanner.stop(); } catch {} }
    preview.hidden = true;
    button.textContent = 'Kamera starten';
  }
  window.addEventListener('pagehide', () => { disposed = true; void stop(); });

  async function submit(code) {
    const now = Date.now();
    if (busy || (recent.get(code) || 0) > now - 3000) return;
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
    } catch (error) { show(error.message, 'error'); }
    finally { busy = false; }
  }
  form.addEventListener('submit', (event) => { event.preventDefault(); void submit(form.elements.code.value.trim()); });

  const newScanner = () => new Html5Qrcode('preview', {verbose: false, experimentalFeatures: {useBarCodeDetectorIfSupported: true}});
  // Rückfallweg: Ein Foto ist schärfer als das Kamerabild und braucht keinen Autofokus im Browser
  const photo = document.getElementById('photo');
  photo?.addEventListener('change', async () => {
    const file = photo.files[0];
    photo.value = '';
    if (!file) return;
    try {
      if (!window.Html5Qrcode) throw new Error('Scanner konnte nicht geladen werden. Bitte Code von Hand eingeben.');
      await stop();
      preview.hidden = false;
      const code = await newScanner().scanFile(file, false);
      preview.hidden = true;
      await submit(code);
    } catch (error) {
      preview.hidden = true;
      show(typeof error === 'string' || !error?.message ? 'Im Foto wurde kein QR-Code erkannt. Bitte näher heran und ohne Spiegelung.' : error.message, 'error');
    }
  });

  button.addEventListener('click', async () => {
    if (starting) return;
    if (active) { await stop(); return; }
    starting = true;
    try {
      if (!window.isSecureContext) throw new Error('Die Kamera benötigt HTTPS oder localhost.');
      if (!window.Html5Qrcode) throw new Error('Kamerascanner konnte nicht geladen werden. Bitte Code von Hand eingeben.');
      preview.hidden = false;
      scanner = newScanner();
      await scanner.start({facingMode: 'environment'}, {fps: 15, videoConstraints: {facingMode: {ideal: 'environment'}, width: {ideal: 1920}, height: {ideal: 1080}, advanced: [{focusMode: 'continuous'}]}, qrbox: (w, h) => {const size = Math.floor(Math.min(w, h) * 0.9); return {width: size, height: size};}}, code => { if (!disposed) void submit(code); }, () => {});
      active = true;
      if (disposed) { await stop(); return; }
      button.textContent = 'Kamera schließen';
      show('Kamera aktiv. Etikett in den Rahmen halten.');
    } catch (error) { await stop(); show(error.message, 'error'); }
    finally { starting = false; }
  });
})();
