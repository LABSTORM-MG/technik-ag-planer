import pytest
from django.urls import reverse

from apps.core import navigation

PAGES = [
    ("productions:dashboard", "Dashboard"),
    ("scheduling:calendar", "Kalender"),
    ("productions:list", "Produktionen"),
    ("core:inventory", "Material"),
    ("board:index", "Board"),
    ("organizations:settings", "Einstellungen"),
]


PLACEHOLDER_PAGES = [page for page in PAGES if page[0].startswith("core:")]


@pytest.fixture
def client(member_client):
    return member_client


@pytest.mark.parametrize(("url_name", "title"), PLACEHOLDER_PAGES)
def test_placeholder_pages_render(client, url_name, title):
    response = client.get(reverse(url_name))

    assert response.status_code == 200
    content = response.content.decode()
    assert f'<h1 class="page-title">{title}</h1>' in content
    assert '<html lang="de">' in content


def test_sidebar_contains_all_menu_items_in_order(client):
    content = client.get(reverse("productions:dashboard")).content.decode()
    sidebar = content.split('<aside class="sidebar"', 1)[1].split("</aside>", 1)[0]

    positions = [
        sidebar.index(label)
        for label in ["Dashboard", "Kalender", "Produktionen", "Material", "Board", "Einstellungen"]
    ]
    assert positions == sorted(positions)
    assert "Neu" in sidebar


def test_mobile_tabbar_items(client):
    content = client.get(reverse("productions:dashboard")).content.decode()
    tabbar = content.split('<nav class="tabbar"', 1)[1].split("</nav>", 1)[0]

    for label in ["Home", "Kalender", "Produktionen", "Mehr"]:
        assert label in tabbar
    assert 'data-sheet-open="sheet-new"' in tabbar
    assert 'data-sheet-open="sheet-more"' in tabbar


def test_more_sheet_links_inventory_and_board(client):
    content = client.get(reverse("productions:dashboard")).content.decode()
    sheet = content.split('id="sheet-more"', 1)[1].split("</dialog>", 1)[0]

    assert reverse("core:inventory") in sheet
    assert reverse("board:index") in sheet


def _new_sheet(client):
    content = client.get(reverse("productions:dashboard")).content.decode()
    return content.split('id="sheet-new"', 1)[1].split("</dialog>", 1)[0]


def test_new_menu_for_students_only_offers_unavailability(client):
    sheet = _new_sheet(client)

    assert "Nicht verfügbar" in sheet
    assert "Termin" not in sheet
    assert "Produktion" not in sheet


@pytest.mark.parametrize("role", ["owner", "admin", "teacher"])
def test_new_menu_lists_all_entries_for_planners(org, make_member, login, role):
    membership = make_member(org, role)
    sheet = _new_sheet(login(membership.user, org))

    for label in ["Termin", "Produktion", "Nicht verfügbar"]:
        assert label in sheet


def test_active_menu_item_is_marked(client):
    content = client.get(reverse("scheduling:calendar")).content.decode()
    sidebar = content.split('<aside class="sidebar"', 1)[1].split("</aside>", 1)[0]

    active = sidebar.split('aria-current="page"', 1)[1].split("</a>", 1)[0]
    assert "Kalender" in active


def test_every_sidebar_section_has_a_page():
    for section in navigation.SIDEBAR:
        assert reverse(section.url_name)
