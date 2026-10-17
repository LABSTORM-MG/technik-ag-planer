# Hilfsskripte

- `screenshots.py` – Screenshots für die Landingpage aus den Beispieldaten (Dev-Server muss laufen): `uv run --with selenium --with pillow scripts/screenshots.py`
- `app_icon.py` – zeichnet das App-Icon (drei Entwürfe, Vorschau in `docs/design/app-icon/`): `uv run --with pillow scripts/app_icon.py [A|B|C]`

Die Beispieldaten für die Entwicklung sind ein Django-Befehl: `make beispieldaten` (siehe ADR 0001).
