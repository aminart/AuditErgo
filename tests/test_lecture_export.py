from openpyxl import Workbook, load_workbook

from audit_ergo import relire
from audit_ergo.i18n import t
from audit_ergo.lecture import lire_audit
from conftest import CONSTAT_VALIDE


def test_lecture_tolerante_fichier_libre(tmp_path, ref):
    """Un fichier qui n'est pas le template : autre onglet, en-tête décalé, colonnes renommées et déplacées."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Mon audit"
    ws["A1"] = "Audit du site X"
    ws.append([])
    ws.append(["Critère", "Constat", "Page", "Gravité", "Préconisation", "Type", "Catégorie", "Commentaire"])
    ws.append(["Immediate Feedback", "Aucun retour visuel après l'envoi du formulaire de contact.", "Contact", 2,
               "Afficher un message de confirmation après l'envoi.", "Problème", "Guidage", "à revoir"])
    chemin = tmp_path / "libre.xlsx"
    wb.save(chemin)

    audit = lire_audit(chemin)
    assert audit.onglet == "Mon audit" and audit.ligne_entete == 3
    assert audit.colonnes_manquantes == []
    assert audit.colonnes_inconnues == ["Commentaire"]
    assert audit.constats[0]["critere"] == "Immediate Feedback"
    assert ref.trouver_critere(audit.constats[0]["critere"]) == "GUI-03"


def test_export_annote_et_conserve_le_fichier(audit_xlsx, tmp_path):
    erreur = {**CONSTAT_VALIDE, "gravite": 9}
    chemin = audit_xlsx([CONSTAT_VALIDE, erreur])
    _, anomalies, synthese, sortie, _ = relire(chemin, tmp_path / "relu.xlsx")
    assert synthese.nb_constats == 2 and not synthese.pret

    wb = load_workbook(sortie)
    assert wb.sheetnames[:2] == [t("onglet.synthese"), t("onglet.anomalies")]
    ws = wb["Audit"]
    entetes = [c.value for c in ws[3]]
    assert entetes[-2:] == ["Relecture : niveau", "Relecture : remarques"]
    assert ws.cell(row=5, column=len(entetes) - 1).value == "✓ Conforme"
    assert ws.cell(row=6, column=len(entetes) - 1).value == "Bloquant"
    col_gravite = next(c.column for c in ws[3] if str(c.value).startswith("Gravité"))
    assert ws.cell(row=6, column=col_gravite).comment is not None  # cellule Gravité fautive commentée
    assert str(ws["A5"].value).startswith("=")  # formules du designer conservées
    assert len(ws.data_validations.dataValidation) >= 7  # listes déroulantes conservées

    # Relire le fichier déjà relu ne duplique pas les colonnes de relecture
    _, _, _, sortie2, _ = relire(sortie, tmp_path / "relu2.xlsx")
    assert [c.value for c in load_workbook(sortie2)["Audit"][3]] == entetes


def test_synthese_couverture(audit_xlsx, ref):
    secondaire = {**CONSTAT_VALIDE, "secondaires": "ERR-01"}
    _, _, synthese, _, _ = relire(audit_xlsx([secondaire]))
    assert synthese.par_critere == {"GUI-03": 1}
    assert synthese.secondaires == {"ERR-01": 1}
    assert "GUI-03" not in synthese.non_couverts and "ERR-01" not in synthese.non_couverts
    assert len(synthese.non_couverts) == 22
    assert synthese.pret
