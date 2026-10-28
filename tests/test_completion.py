"""Complétion d'un audit : les cellules vides sont remplies, celles du designer ne sont jamais modifiées."""
from openpyxl import Workbook, load_workbook

from audit_ergo import relire
from audit_ergo.lecture import lire_audit
from audit_ergo.suggestion import construire_requete, suggerer
from test_suggestion import FauxClient, erreur_api, reponse_ia

VIOLET = "E4DFEC"
RECO_IA = "Afficher un indicateur de chargement dans le bouton « Payer » et le désactiver jusqu'à la réponse."


def reponse_complete(code="GUI-03", statut_reco="non_fournie", gravite=3, **modif):
    return reponse_ia(code=code, recommandation={
        "proposee": RECO_IA,
        "avis_designer": {"statut": statut_reco, "commentaire": "Trop vague : quel élément ?",
                          "version_amelioree": "Désactiver le bouton « Payer » pendant le traitement."},
        "complementaires": ["Afficher une confirmation après le paiement."],
    }, gravite={"valeur": gravite, "justification": "Risque de double paiement."}, **modif)


def cellules(chemin, ligne=5):
    ws = load_workbook(chemin)["Audit"]
    entetes = {c.value: c.column for c in ws[3] if c.value}
    return ws, entetes, lambda titre: ws.cell(row=ligne, column=entetes[titre])


def test_audit_avec_seulement_les_constats(audit_xlsx, ref, tmp_path):
    chemin = audit_xlsx([{"ecran": "Paiement", "constat": "Après un clic sur Payer, rien ne se passe pendant 5 s."}])
    audit, anomalies, synthese, sortie, ia = relire(chemin, tmp_path / "complete.xlsx", ref,
                                                    FauxClient(reponse_complete()))
    ws, entetes, cell = cellules(sortie)
    attendu = {
        "Type": "Problème",
        "Catégorie *": "GUI – Guidage",
        "Critère principal *": "GUI-03 – Feedback immédiat (Immediate Feedback)",
        "Critères secondaires (codes séparés par ;)": "ERR-01",
        "Règle de départage": "R1",
        "Justification du critère": "Réaction après l'action. (R1) Checklist : "
                                    "« Is information displayed during the loading? »",
        "Gravité * (si problème)": "Élevée",
        "Recommandation * (si problème)": RECO_IA,
    }
    for titre, valeur in attendu.items():
        assert cell(titre).value == valeur, titre
        assert cell(titre).fill.fgColor.rgb.endswith(VIOLET), titre
        assert "à valider" in cell(titre).comment.text or "à vérifier" in cell(titre).comment.text
    assert "Proposé par l'IA" in cell("Recommandation * (si problème)").comment.text
    assert "Complété automatiquement" in cell("Type").comment.text
    assert cell("Écran / Emplacement *").fill.fgColor.rgb.endswith("FFF9E5")  # saisie du designer intacte
    assert synthese.pret, [a.message for a in anomalies]  # plus aucun champ obligatoire vide
    assert cell("IA : verdict critère").value == "Proposé (cellule remplie)"
    assert cell("IA : avis recommandation").value == "Proposée (cellule remplie)"


def test_saisies_du_designer_jamais_modifiees(audit_xlsx, ref, tmp_path):
    saisie = {"ecran": "Paiement", "type": "Problème", "constat": "Après un clic sur Payer, rien ne se passe.",
              "categorie": "GUI – Guidage", "critere": "GUI-01 – Incitation (Prompting)", "gravite": 1,
              "recommandation": "Améliorer le bouton de paiement."}
    client = FauxClient(reponse_complete(statut_reco="a_ameliorer"))
    _, _, _, sortie, ia = relire(audit_xlsx([saisie]), tmp_path / "c.xlsx", ref, client)
    _, _, cell = cellules(sortie)
    assert cell("Critère principal *").value == "GUI-01 – Incitation (Prompting)"
    assert cell("Gravité * (si problème)").value == 1  # saisie du designer (ancienne échelle chiffrée) conservée
    assert cell("Recommandation * (si problème)").value == "Améliorer le bouton de paiement."
    assert not cell("Critère principal *").fill.fgColor.rgb.endswith(VIOLET)
    # Les corrections sont proposées à côté, pas à la place
    assert cell("IA : verdict critère").value == "À revoir"
    assert cell("IA : recommandation").value == "Désactiver le bouton « Payer » pendant le traitement."
    assert cell("IA : avis recommandation").value.startswith("À améliorer : Trop vague")
    assert cell("IA : gravité").value == "3 – Élevée (vous : Faible)"
    assert "double paiement" in cell("IA : remarques").value
    assert "Recommandations complémentaires" in cell("IA : remarques").value
    assert cell("IA : justification critère").value.startswith("Réaction après l'action. (R1)")
    assert "GUI-01 décrit l'avant" in cell("IA : justification critère").value  # avis sur le choix du designer
    assert cell("Justification du critère").value is None  # critère à revoir : pas de justification remplie
    # Ce qui a été envoyé à l'IA contient bien les choix du designer
    message = client.appels[0]["messages"][-1]["content"]
    assert "Recommandation rédigée par le designer : Améliorer le bouton" in message
    assert "Gravité indiquée par le designer : 1 (Faible)" in message


def test_categorie_deduite_du_critere_du_designer(audit_xlsx, ref, tmp_path):
    saisie = {"ecran": "Panier", "type": "Problème", "constat": "La suppression d'un article est immédiate.",
              "critere": "ERR-01", "gravite": 3, "recommandation": "Demander confirmation avant suppression."}
    audit, *_ = relire(audit_xlsx([saisie]), tmp_path / "c.xlsx", ref, FauxClient(reponse_complete("GUI-03")))
    valeur, origine, _ = audit.completions[5]["categorie"]
    assert valeur == "ERR – Gestion des erreurs" and origine == "auto"  # pas la catégorie proposée par l'IA


def test_justification_du_critere_confirme(audit_xlsx, ref, tmp_path):
    """Critère du designer confirmé par l'IA : sa justification est remplie ; une justification saisie est gardée."""
    saisie = {"ecran": "Paiement", "type": "Problème", "constat": "Après un clic sur Payer, rien ne se passe.",
              "critere": "GUI-03", "gravite": 3, "recommandation": "Afficher un indicateur de chargement sur le bouton."}
    confirme = reponse_complete(verdict_designer={"statut": "confirme", "commentaire": "OK"})
    audit, *_ = relire(audit_xlsx([saisie]), tmp_path / "a.xlsx", ref, FauxClient(confirme))
    assert audit.completions[5]["justification"][0].startswith("Réaction après l'action. (R1)")

    a_moi = {**saisie, "justification": "Ma propre justification."}
    _, _, _, sortie, _ = relire(audit_xlsx([a_moi], nom="b.xlsx"), tmp_path / "b_relu.xlsx", ref, FauxClient(confirme))
    _, _, cell = cellules(sortie)
    assert cell("Justification du critère").value == "Ma propre justification."


def test_sans_remplissage(audit_xlsx, ref, tmp_path):
    chemin = audit_xlsx([{"ecran": "Paiement", "constat": "Après un clic sur Payer, rien ne se passe."}])
    audit, anomalies, synthese, sortie, ia = relire(chemin, tmp_path / "c.xlsx", ref,
                                                    FauxClient(reponse_complete()), remplir=False)
    _, _, cell = cellules(sortie)
    assert cell("Critère principal *").value is None and not audit.completions
    assert cell("IA : critère suggéré").value.startswith("GUI-03")  # la proposition reste visible
    assert not synthese.pret


def test_point_fort_sans_recommandation(audit_xlsx, ref, tmp_path):
    point_fort = {"ecran": "Fiche produit", "type": "Point fort", "constat": "Les photos sont zoomables et nettes."}
    audit, *_ = relire(audit_xlsx([point_fort]), tmp_path / "c.xlsx", ref, FauxClient(reponse_complete(gravite=1)))
    assert "recommandation" not in audit.completions[5]
    assert "gravite" not in audit.completions[5]  # pas de gravité pour un point fort


def test_erreur_ia_seul_le_type_est_complete(audit_xlsx, ref, tmp_path):
    import openai

    chemin = audit_xlsx([{"ecran": "Paiement", "constat": "Après un clic sur Payer, rien ne se passe."}])
    audit, *_ = relire(chemin, tmp_path / "c.xlsx", ref, FauxClient(erreur_api(openai.InternalServerError, 500)))
    assert set(audit.completions[5]) == {"type"}


def test_critere_inconnu_du_designer_non_ecrase(audit_xlsx, ref, tmp_path):
    saisie = {"ecran": "Paiement", "constat": "Après un clic sur Payer, rien ne se passe.", "critere": "Feedback ?"}
    audit, anomalies, *_ = relire(audit_xlsx([saisie]), tmp_path / "c.xlsx", ref, FauxClient(reponse_complete()))
    assert "critere" not in audit.completions[5]
    assert "CRITERE_INCONNU" in [a.code for a in anomalies]


def test_fichier_libre_colonnes_creees(tmp_path, ref):
    """Un simple tableau Écran / Constat : les colonnes manquantes sont créées et remplies."""
    wb = Workbook()
    ws = wb.active
    ws.append(["Écran", "Constat", "Commentaire interne"])
    ws.append(["Paiement", "Après un clic sur Payer, rien ne se passe pendant 5 secondes.", "vu en test"])
    ws.append(["Panier", "Le bouton supprimer retire l'article sans confirmation.", ""])
    chemin = tmp_path / "libre.xlsx"
    wb.save(chemin)

    audit, anomalies, synthese, sortie, _ = relire(chemin, tmp_path / "complete.xlsx", ref,
                                                   FauxClient(reponse_complete()))
    assert synthese.pret, [a.message for a in anomalies]
    relu = lire_audit(sortie)  # le fichier produit se relit : colonnes ajoutées reconnues
    assert {"categorie", "critere", "gravite", "recommandation"} <= set(relu.colonnes)
    assert relu.constats[0]["critere"].startswith("GUI-03") and relu.constats[1]["recommandation"] == RECO_IA
    assert "type" not in relu.colonnes  # pas de colonne Type ajoutée à un tableau libre : problème par défaut


def test_tableau_avec_une_seule_colonne_constat(tmp_path, ref):
    wb = Workbook()
    ws = wb.active
    ws.append(["Constats relevés"])
    ws.append(["Constat"])
    ws.append(["Après un clic sur Payer, rien ne se passe pendant 5 secondes."])
    chemin = tmp_path / "seul.xlsx"
    wb.save(chemin)
    audit = lire_audit(chemin)
    assert audit.ligne_entete == 2 and len(audit.constats) == 1


def test_avis_reco_ignore_sans_reco_du_designer(ref):
    s = suggerer(FauxClient(reponse_complete(statut_reco="a_ameliorer")), ref, "Rien ne se passe après le clic.")
    assert s.reco_statut == "non_fournie" and s.reco_amelioree == "" and s.reco_a_retenir == RECO_IA
    s = suggerer(FauxClient(reponse_complete(statut_reco="bonne")), ref, "Rien ne se passe après le clic.",
                 recommandation_designer="Désactiver le bouton pendant le traitement.")
    assert s.reco_statut == "bonne" and s.reco_amelioree == ""  # une bonne reco n'est pas réécrite


def test_schema_demande_recommandation_et_gravite(ref):
    schema = construire_requete(ref, "x")["response_format"]["json_schema"]["schema"]
    assert {"recommandation", "gravite"} <= set(schema["required"])
