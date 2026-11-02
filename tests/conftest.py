import sys
from pathlib import Path

import pytest
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from audit_ergo import Referentiel  # noqa: E402
from audit_ergo.lecture import libelle_champ, nom_colonne  # noqa: E402

TEMPLATE = ROOT / "template" / "Audit_ergonomique_FR.xlsx"

CONSTAT_VALIDE = {
    "ecran": "Paiement", "type": "Problème",
    "constat": "Aucun indicateur de chargement après le clic sur « Payer ».",
    "categorie": "GUI – Guidage", "critere": "GUI-03 – Feedback immédiat (Immediate Feedback)",
    "gravite": 3, "impact": "Fort", "frequence": "Systématique", "priorite": "P1",
    "recommandation": "Afficher un indicateur de chargement dans le bouton et le désactiver.",
}


@pytest.fixture(scope="session")
def ref():
    return Referentiel.charger()


@pytest.fixture
def audit_xlsx(tmp_path):
    """Fabrique un audit à partir du template : audit_xlsx([{champ: valeur}, ...], contexte={...})."""
    def fabriquer(constats, contexte=None, nom="audit.xlsx"):
        wb = load_workbook(TEMPLATE)
        ws = wb["Audit"]
        colonnes = {nom_colonne(c.value): c.column for c in ws[3] if c.value}
        for i, valeurs in enumerate(constats):
            for champ, valeur in valeurs.items():
                if champ not in colonnes:  # colonne d'un ancien template (fréquence, impact, priorité)
                    colonnes[champ] = ws.max_column + 1
                    ws.cell(row=3, column=colonnes[champ], value=libelle_champ(champ))
                ws.cell(row=5 + i, column=colonnes[champ], value=valeur)
        ctx = {"Produit / interface auditée *": "Produit test", "Cible utilisateurs *": "Tous",
               "Plateforme *": "Web desktop", "Parcours audités *": "Commande", "Designer *": "Test",
               "Date de l'audit *": "20/10/2026", **(contexte or {})}
        for row in wb["Contexte"].iter_rows(min_col=1, max_col=2):
            if row[0].value in ctx:
                row[1].value = ctx[row[0].value]
        chemin = tmp_path / nom
        wb.save(chemin)
        return chemin
    return fabriquer


@pytest.fixture(autouse=True)
def cache_isole(tmp_path, monkeypatch):
    """Chaque test a son propre cache de suggestions : jamais celui de l'utilisateur."""
    chemin = tmp_path / "cache" / "suggestions.sqlite"
    monkeypatch.setenv("AUDIT_ERGO_CACHE", str(chemin))
    return chemin


@pytest.fixture(autouse=True)
def historique_isole(tmp_path, monkeypatch):
    """Chaque test a son propre historique d'audits : jamais celui de l'utilisateur."""
    chemin = tmp_path / "historique"
    monkeypatch.setenv("AUDIT_ERGO_HISTORIQUE", str(chemin))
    return chemin
