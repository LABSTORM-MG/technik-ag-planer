"""Die Rechte-Tabelle im Code muss exakt der Tabelle in Abschnitt 2 entsprechen."""

import re
from pathlib import Path

import pytest

from apps.organizations.permissions import Perm, Role, role_has_perm

APP_DIR = Path(__file__).resolve().parents[3]
SPEC_CANDIDATES = [APP_DIR.parent / "docs" / "feature-liste.md", Path("/docs/feature-liste.md")]
COLUMNS = [Role.OWNER, Role.ADMIN, Role.TEACHER, Role.STUDENT]


def _spec_table():
    spec = next((p for p in SPEC_CANDIDATES if p.exists()), None)
    assert spec is not None, "docs/feature-liste.md nicht gefunden"
    text = spec.read_text()
    section = text.split("**Rollen**", 1)[1].split("## 3.", 1)[0]
    rows = {}
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 5 or cells[0] in ("Funktion", "") or re.fullmatch(r"-+", cells[1]):
            continue
        rows[cells[0]] = {
            role for role, cell in zip(COLUMNS, cells[1:], strict=True) if cell == "ja"
        }
    return rows


def test_every_row_of_the_spec_is_in_code_and_vice_versa():
    spec = _spec_table()
    code = {perm.label: set(perm.roles) for perm in Perm}

    assert set(spec) == set(code)
    for label, roles in spec.items():
        assert code[label] == roles, label


def test_spec_table_is_not_empty():
    assert len(_spec_table()) == len(Perm) >= 20


@pytest.mark.parametrize("perm", list(Perm))
@pytest.mark.parametrize("role", COLUMNS)
def test_role_has_perm_matches_table(role, perm):
    assert role_has_perm(role, perm) == (role in perm.roles)
