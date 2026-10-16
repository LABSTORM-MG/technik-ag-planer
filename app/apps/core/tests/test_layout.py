import pytest
from django.urls import reverse

from apps.core import navigation

PAGES = [
    ("core:dashboard", "Dashboard"),
    ("core:calendar", "Kalender"),
    ("core:productions", "Produktionen"),
    ("core:inventory", "Material"),
    ("core:board", "Board"),
    ("core:settings", "Einstellungen"),
]


@pytest.mark.parametrize(("url_name", "title"), PAGES)
def test_placeholder_pages_render(client, url_name, title):
    response = client.get(reverse(url_name))

    assert response.status_code == 200
    content = response.content.decode()
    assert f'<h1 class="page-title">{title}</h1>' in content
    assert '<html lang="de">' in content


def test_sidebar_contains_all_menu_items_in_order(client):
    content = client.get(reverse("core:dashboard")).content.decode()
    sidebar = content.split('<aside class="sidebar"', 1)[1].split("</aside>", 1)[0]

    positions = [
        sidebar.index(label)
        for label in ["Dashboard", "Kalender", "Produktionen", "Material", "Board", "Einstellungen"]
    ]
    assert positions == sorted(positions)
    assert "Neu" in sidebar


def test_mobile_tabbar_items(client):
    content = client.get(reverse("core:dashboard")).content.decode()
    tabbar = content.split('<nav class="tabbar"', 1)[1].split("</nav>", 1)[0]

    for label in ["Home", "Kalender", "Produktionen", "Mehr"]:
        assert label in tabbar
    assert 'data-sheet-open="sheet-new"' in tabbar
    assert 'data-sheet-open="sheet-more"' in tabbar


def test_more_sheet_links_inventory_and_board(client):
    content = client.get(reverse("core:dashboard")).content.decode()
    sheet = content.split('id="sheet-more"', 1)[1].split("</dialog>", 1)[0]

    assert reverse("core:inventory") in sheet
    assert reverse("core:board") in sheet


def test_new_menu_lists_entries_from_section_4(client):
    content = client.get(reverse("core:dashboard")).content.decode()
    sheet = content.split('id="sheet-new"', 1)[1].split("</dialog>", 1)[0]

    for label in ["Termin", "Produktion", "Nicht verfügbar"]:
        assert label in sheet


def test_active_menu_item_is_marked(client):
    content = client.get(reverse("core:calendar")).content.decode()
    sidebar = content.split('<aside class="sidebar"', 1)[1].split("</aside>", 1)[0]

    active = sidebar.split('aria-current="page"', 1)[1].split("</a>", 1)[0]
    assert "Kalender" in active


def test_every_sidebar_section_has_a_page():
    for section in navigation.SIDEBAR:
        assert reverse(section.url_name)
