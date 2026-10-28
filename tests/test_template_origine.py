"""Audits remplis avec le template d'origine (referentiel/source/Heuristic_Evaluation_template.xlsx)."""
import warnings
from pathlib import Path

import pytest
from openpyxl import load_workbook

from audit_ergo import relire
from audit_ergo.lecture import lire_audit
from test_suggestion import FauxClient, reponse_ia

ORIGINE = Path(__file__).resolve().parent.parent / "referentiel" / "source" / "Heuristic_Evaluation_template.xlsx"


@pytest.fixture
def audit_origine(tmp_path):
    """Le template d'origine, rempli comme le ferait un designer (sous-critères avec leur retour à la ligne)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # extensions Excel non gérées par openpyxl
        wb = load_workbook(ORIGINE)
    ws = wb["Grid_for_Ergonomic inspection"]
    lignes = [
        # B Workflow, C Tasks, D Date, E Criteria, F Sub-criteria, G Description, I Location, J Severity,
        # K Type of reco, L Detail of reco
        ["Checkout", "Pay", "2026-10-20", "Guidance", "Immediate Feedback\n",
         "After clicking Pay, no loading indicator is shown for about 5 seconds.", "Payment page", "High", "Design",
         "Show a spinner in the Pay button and disable it until the server responds."],
        ["Account", "Sign up", None, "Guidance", "Leagibility/Readability\n",
         "The password rules are written in 10 px light grey text on white.", "Sign-up form", "Medium", "Design",
         "Use at least 14 px text with a 4.5:1 contrast ratio (WCAG 1.4.3)."],
        ["Cart", None, None, None, None, "The delete button removes the item with no confirmation and no undo.",
         "Cart", None, None, None],
    ]
    for i, valeurs in enumerate(lignes):
        for col, valeur in zip("BCDEFGIJKL", valeurs):
            if col == "B" and i > 0:
                continue  # B7:B12 est fusionnée dans le template d'origine : un cas d'usage pour le bloc
            ws[f"{col}{7 + i}"] = valeur
    chemin = tmp_path / "audit_origine.xlsx"
    wb.save(chemin)
    return chemin


def test_lecture_du_template_d_origine(audit_origine, ref):
    audit = lire_audit(audit_origine)
    assert audit.onglet == "Grid_for_Ergonomic inspection" and audit.ligne_entete == 6
    assert audit.langue == "en"
    assert {"parcours", "tache", "date", "categorie", "critere", "constat", "capture", "ecran", "gravite",
            "type_reco", "recommandation", "statut_maquette", "statut"} <= set(audit.colonnes)
    assert len(audit.constats) == 3
    premier = audit.constats[0]
    assert ref.trouver_critere(premier["critere"]) == "GUI-03"
    assert ref.trouver_critere(audit.constats[1]["critere"]) == "GUI-04"  # « Leagibility », coquille d'origine
    assert ref.trouver_categorie(premier["categorie"]) == "GUI"
    # B7:B12 fusionnée : le cas d'usage vaut pour les trois constats du bloc
    assert [c["parcours"] for c in audit.constats] == ["Checkout"] * 3


def test_controles_sans_colonne_type(audit_origine, ref, tmp_path):
    """Pas de colonne Type dans le template d'origine : chaque constat est un problème, sans anomalie."""
    _, anomalies, synthese, _, _ = relire(audit_origine, tmp_path / "relu.xlsx", ref)
    lignes_en_erreur = {a.ligne for a in anomalies if a.niveau == "bloquant"}
    assert lignes_en_erreur == {9}  # seule la ligne incomplète
    assert synthese.gravites == {1: 0, 2: 1, 3: 1, 4: 0}


def test_completion_du_template_d_origine(audit_origine, ref, tmp_path):
    client = FauxClient(reponse_ia(verdict_designer={"statut": "confirme", "commentaire": "OK"},
                                   recommandation={"proposee": "Ask for confirmation or offer an Undo link.",
                                                   "type": "design", "avis_designer": {"statut": "bonne",
                                                   "commentaire": "", "version_amelioree": ""},
                                                   "complementaires": []},
                                   gravite={"valeur": 3, "justification": "Data loss risk."}))
    audit, anomalies, synthese, sortie, _ = relire(audit_origine, tmp_path / "complete.xlsx", ref, client)
    assert synthese.pret, [a.message for a in anomalies]
    ws = load_workbook(sortie)["Grid_for_Ergonomic inspection"]
    # Valeurs écrites dans la langue du fichier (anglais) : cohérentes avec ses listes
    assert ws["E9"].value == "GUI – Guidance" and ws["F9"].value == "GUI-03 – Immediate Feedback"
    assert ws["J9"].value == "High" and ws["K9"].value == "Design"
    assert ws["L9"].value == "Ask for confirmation or offer an Undo link."
    assert ws["F7"].value == "Immediate Feedback\n"  # saisie du designer intacte
