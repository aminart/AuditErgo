import pytest

from audit_ergo.controles import controler
from audit_ergo.lecture import lire_audit
from conftest import CONSTAT_VALIDE


def codes(audit_xlsx, ref, constats, **kw):
    audit = lire_audit(audit_xlsx(constats, **kw))
    return [a.code for a in controler(audit, ref)]


def test_constat_valide_sans_anomalie(audit_xlsx, ref):
    assert codes(audit_xlsx, ref, [CONSTAT_VALIDE]) == []


def test_ligne_exemple_et_lignes_vides_ignorees(audit_xlsx, ref):
    audit = lire_audit(audit_xlsx([CONSTAT_VALIDE]))
    assert len(audit.constats) == 1
    assert audit.constats[0].ligne == 5


@pytest.mark.parametrize("modif, attendu", [
    ({"ecran": None}, "CHAMP_VIDE"),
    ({"recommandation": None}, "CHAMP_VIDE"),
    ({"type": "Bug"}, "TYPE_INVALIDE"),
    ({"constat": "Menu pas clair"}, "CONSTAT_COURT"),
    ({"constat": "Le menu principal est confus pour les nouveaux utilisateurs."}, "CONSTAT_VAGUE"),
    ({"critere": "ERR-03 – Correction des erreurs"}, "CRITERE_HORS_CATEGORIE"),
    ({"critere": "Critère inventé"}, "CRITERE_INCONNU"),
    ({"categorie": "Catégorie inventée"}, "CATEGORIE_INCONNUE"),
    ({"secondaires": "ERR-01 ; XYZ-99"}, "SECONDAIRE_INCONNU"),
    ({"secondaires": "la gestion des erreurs"}, "SECONDAIRE_ILLISIBLE"),
    ({"secondaires": "GUI-03"}, "SECONDAIRE_EGAL_PRINCIPAL"),
    ({"regle": "R2"}, "REGLE_INCOHERENTE"),
    ({"regle": "R42"}, "REGLE_INCONNUE"),
    ({"gravite": 5}, "GRAVITE_INVALIDE"),
    ({"gravite": 0}, "GRAVITE_INVALIDE"),  # l'échelle du template d'origine va de 1 à 4
    ({"gravite": "Très grave"}, "GRAVITE_INVALIDE"),
    ({"gravite": "Critique", "impact": "Faible", "priorite": "P1"}, "GRAVITE_IMPACT_HAUTE"),
    ({"gravite": "Low", "impact": "High", "frequence": "Systematic", "priorite": "P3"}, "GRAVITE_IMPACT_BASSE"),
    ({"type_reco": "Marketing"}, "TYPE_RECO_INVALIDE"),
    ({"gravite": 3, "priorite": "P3"}, "PRIORITE_GRAVITE"),
    ({"priorite": "Urgent"}, "PRIORITE_INVALIDE"),
    ({"frequence": "Souvent"}, "FREQUENCE_INVALIDE"),
    ({"recommandation": "À corriger."}, "RECO_COURTE"),
    ({"recommandation": "Aucun indicateur de chargement après le clic sur « Payer »."}, "RECO_COPIE_CONSTAT"),
    ({"recommandation": "Il faudrait revoir l'ergonomie de cette page de paiement."}, "RECO_VAGUE"),
])
def test_chaque_anomalie_est_detectee(audit_xlsx, ref, modif, attendu):
    assert attendu in codes(audit_xlsx, ref, [{**CONSTAT_VALIDE, **modif}])


def test_regle_coherente_acceptee(audit_xlsx, ref):
    assert codes(audit_xlsx, ref, [{**CONSTAT_VALIDE, "regle": "r1"}]) == []


def test_point_fort(audit_xlsx, ref):
    point_fort = {**CONSTAT_VALIDE, "type": "Point fort", "recommandation": None, "priorite": None, "gravite": None}
    assert codes(audit_xlsx, ref, [point_fort]) == []  # ni recommandation ni gravité exigées
    assert "POINT_FORT_GRAVE" in codes(audit_xlsx, ref, [{**point_fort, "gravite": 2}])


@pytest.mark.parametrize("gravite", [3, "3", "High", "Élevée", "élevée", "HIGH", "3 – Élevée"])
def test_gravite_saisie_dans_les_deux_langues(audit_xlsx, ref, gravite):
    assert codes(audit_xlsx, ref, [{**CONSTAT_VALIDE, "gravite": gravite}]) == []


@pytest.mark.parametrize("type_", ["Problème", "Issue", "Point fort", "Strength"])
def test_type_dans_les_deux_langues(audit_xlsx, ref, type_):
    assert "TYPE_INVALIDE" not in codes(audit_xlsx, ref, [{**CONSTAT_VALIDE, "type": type_}])


def test_messages_en_anglais(audit_xlsx, ref):
    audit = lire_audit(audit_xlsx([{**CONSTAT_VALIDE, "ecran": None, "gravite": 9}]))
    messages = [a.message for a in controler(audit, ref, "en")]
    assert "“Screen / Location” is empty." in messages
    assert any(m.startswith("Severity “9” not on the scale (1 Low, 2 Medium, 3 High, 4 Critical)") for m in messages)


def test_doublon(audit_xlsx, ref):
    autre = {**CONSTAT_VALIDE, "constat": CONSTAT_VALIDE["constat"].replace("Aucun", "Pas d'")}
    assert "DOUBLON" in codes(audit_xlsx, ref, [CONSTAT_VALIDE, autre])
    ailleurs = {**autre, "ecran": "Panier"}
    assert "DOUBLON" not in codes(audit_xlsx, ref, [CONSTAT_VALIDE, ailleurs])


def test_controles_fichier(audit_xlsx, ref):
    assert "CONTEXTE_INCOMPLET" in codes(audit_xlsx, ref, [CONSTAT_VALIDE], contexte={"Designer *": None})
    assert "REFERENTIEL_PERIME" in codes(audit_xlsx, ref, [CONSTAT_VALIDE],
                                         contexte={"Version du référentiel": "0.9"})
    assert "AUDIT_VIDE" in codes(audit_xlsx, ref, [])
