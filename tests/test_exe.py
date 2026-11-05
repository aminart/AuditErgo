"""Exécutable et versions : chemins valables depuis l'exe, numéro de version unique, script de version."""
import datetime as dt
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from audit_ergo import chemins

RACINE = Path(__file__).resolve().parent.parent


def test_depuis_les_sources():
    assert not chemins.empaquete()
    assert chemins.ressources() == RACINE and chemins.dossier_app() == RACINE
    assert chemins.cache_defaut() == RACINE / ".cache" / "suggestions.sqlite"
    assert chemins.historique_defaut() == RACINE / ".donnees" / "audits"


def test_depuis_l_exe(monkeypatch, tmp_path):
    """Ressources dans l'exe, .env à côté de l'exe, données écrites dans le dossier de l'utilisateur."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "interne"), raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "Programmes" / "AuditErgo.exe"))
    monkeypatch.setenv("AUDIT_ERGO_CONFIG", str(tmp_path / "AppData" / "AuditErgo"))
    assert chemins.empaquete()
    assert chemins.ressources() == tmp_path / "interne"
    assert chemins.dossier_app() == tmp_path / "Programmes"
    assert chemins.cache_defaut() == tmp_path / "AppData" / "AuditErgo" / "cache" / "suggestions.sqlite"
    assert chemins.historique_defaut() == tmp_path / "AppData" / "AuditErgo" / "audits"


def test_recette_embarque_les_ressources():
    recette = (RACINE / "AuditErgo.spec").read_text(encoding="utf-8")
    for source in ('"VERSION"', '"web/dist"', '"template"', '"referentiel/referentiel.json"'):
        assert source in recette
    assert (RACINE / "web" / "dist" / "index.html").is_file()


def test_version_unique():
    version = (RACINE / "VERSION").read_text(encoding="utf-8").strip()
    assert re.match(r"^\d+\.\d+\.\d+$", version)
    from serveur import VERSION
    assert VERSION == chemins.version() == version
    assert json.loads((RACINE / "web" / "package.json").read_text(encoding="utf-8"))["version"] == version
    journal = (RACINE / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [Non publié]" in journal and f"## [{version}]" in journal


def _bump():
    spec = importlib.util.spec_from_file_location("bump_version", RACINE / "scripts" / "bump_version.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(("demande", "attendu"), [("patch", "1.4.3"), ("minor", "1.5.0"), ("major", "2.0.0"), ("1.10.0", "1.10.0")])
def test_version_suivante(demande, attendu):
    assert _bump().next_version("1.4.2", demande) == attendu


def test_bump_date_la_section(tmp_path, monkeypatch):
    bump = _bump()
    journal = tmp_path / "CHANGELOG.md"
    journal.write_text("# H\n\n## [Non publié]\n\n### Ajouté\n\n- Une chose\n\n## [1.0.0] — référence\n", encoding="utf-8")
    monkeypatch.setattr(bump, "CHANGELOG", journal)
    bump.update_changelog("1.1.0", dt.date(2026, 11, 5))
    assert "## [Non publié]\n\n## [1.1.0] — 2026-11-05\n\n### Ajouté" in journal.read_text(encoding="utf-8")
