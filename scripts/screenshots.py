"""Screenshots für die Landingpage (Abschnitt 12) mit den Beispieldaten.

    make reset-db && make beispieldaten && make dev       # in einem anderen Terminal
    uv run --with selenium --with pillow scripts/screenshots.py [http://localhost:8000]

Braucht Firefox; Selenium lädt den passenden geckodriver selbst. Schreibt nach
app/static/landing/.
"""

import io
import sys
import time
from pathlib import Path

from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "app" / "static" / "landing"
BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000"

PHONE = (390, 844)
DESKTOP = (1280, 800)


MIN_WIDTH = 500  # Firefox ohne Fenster wird nicht schmaler – Handybreite per CSS-Zoom


def driver(width, height, mobile):
    options = webdriver.FirefoxOptions()
    options.add_argument("-headless")
    if mobile:
        options.set_preference(
            "general.useragent.override",
            "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Mobile",
        )
    browser = webdriver.Firefox(options=options)
    browser.zoom = max(1, MIN_WIDTH / width)
    target = (round(width * browser.zoom), round(height * browser.zoom))
    for _ in range(3):  # Fenster so einstellen, dass der sichtbare Bereich genau passt
        inner = browser.execute_script("return [window.innerWidth, window.innerHeight]")
        rect = browser.get_window_rect()
        browser.set_window_rect(
            width=rect["width"] + target[0] - inner[0],
            height=rect["height"] + target[1] - inner[1],
        )
    browser.target = target
    return browser


def login(browser, email="schueler@example.org", password="schueler"):
    browser.get(f"{BASE}/anmelden/")
    browser.find_element(By.NAME, "email").send_keys(email)
    browser.find_element(By.NAME, "password").send_keys(password)
    browser.find_element(By.CSS_SELECTOR, "form button[type=submit]").click()
    time.sleep(1)


def shot(browser, path, name, size):
    browser.get(f"{BASE}{path}")
    if browser.zoom > 1:
        browser.execute_script(f"document.documentElement.style.zoom = {browser.zoom}")
    time.sleep(1.2)
    image = Image.open(io.BytesIO(browser.get_screenshot_as_png())).convert("RGB")
    image = image.crop((0, 0, *browser.target)).resize(size, Image.LANCZOS)
    image.save(OUT / name, optimize=True)
    print(name, image.size)


def production_url(browser, name):
    browser.get(f"{BASE}/produktionen/")
    link = browser.find_element(By.PARTIAL_LINK_TEXT, name)
    return link.get_attribute("href").removeprefix(BASE)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    phone = driver(*PHONE, mobile=True)
    try:
        login(phone)
        shot(phone, "/", "handy-dashboard.png", PHONE)
        shot(phone, production_url(phone, "Schulkonzert"), "handy-produktion.png", PHONE)
        shot(phone, "/material/", "handy-material.png", PHONE)
    finally:
        phone.quit()
    desktop = driver(*DESKTOP, mobile=False)
    try:
        login(desktop, "lehrer@example.org", "lehrer")
        shot(desktop, "/kalender/", "computer-kalender.png", DESKTOP)
    finally:
        desktop.quit()


if __name__ == "__main__":
    main()
