"""Tests du rapport Word de synthèse, avec un faux serveur (aucun modèle ni réseau nécessaire)."""
import openai
import pytest
from docx import Document

from audit_ergo.lecture import lire_audit
from audit_ergo.rapport import BUDGET, generer_rapport, maturite_indicative, rediger
from test_suggestion import FauxClient, erreur_api

PROBLEMES = [
    {"ecran": "Paiement", "constat": "Aucun indicateur de chargement après le clic sur « Payer ».",
     "critere": "GUI-03", "gravite": 3, "recommandation": "Afficher un indicateur dans le bouton « Payer »."},
    {"ecran": "Panier", "constat": "La suppression d'un article se fait sans confirmation ni annulation.",
     "critere": "ERR-03", "gravite": 4, "recommandation": "Proposer « Annuler » après la suppression."},
    {"ecran": "Inscription", "constat": "Le format de la date de naissance n'est pas indiqué.",
     "critere": "GUI-01", "gravite": 2, "recommandation": "Indiquer le format JJ/MM/AAAA sous le champ."},
    {"ecran": "Paiement", "constat": "Le message « Erreur 402 » s'affiche sans explication.",
     "critere": "ERR-02", "gravite": 3, "recommandation": "Expliquer la cause du refus et la marche à suivre."},
    {"ecran": "Accueil", "constat": "Le menu mélange catégories de produits et pages de service.",
     "critere": "GUI-02", "gravite": 1, "recommandation": "Séparer les catégories des pages de service."},
]
POINT_FORT = {"ecran": "Fiche produit", "type": "Point fort", "constat": "Les photos produit sont zoomables."}

THEMES = {"themes": [
    {"titre": "Gestion des erreurs", "constats": ["C2", "C4", "C99"], "description": "Erreurs mal expliquées.",
     "pourquoi": "L'utilisateur ne comprend pas.", "consequences": "Abandon du paiement."},
    {"titre": "Retour d'information", "constats": ["C1", "c3", "C2"], "description": "Pas de retour.",
     "pourquoi": "État du système invisible.", "consequences": "Doubles clics."},
]}
SYNTHESE = {
    "synthese": {"resume": "L'audit révèle des faiblesses dans le paiement.",
                 "maturite": {"niveau": 5, "justification": "Peu de problèmes."},
                 "points_forts": ["Photos zoomables"], "faiblesses": ["Erreurs opaques"],
                 "problemes_recurrents": ["Manque de retour"], "impact": "Des abandons de panier."},
    "recommandations": [
        {"titre": "Harmoniser les retours", "objectif": "O1", "importance": "I1", "benefices": "B1",
         "problemes_resolus": "P1", "themes": ["T2"], "impact": "moyen", "effort": "faible"},
        {"titre": "Refondre la gestion des erreurs", "objectif": "O2", "importance": "I2", "benefices": "B2",
         "problemes_resolus": "P2", "themes": ["T1", "T9"], "impact": "fort", "effort": "moyen"},
    ],
    "quick_wins": [{"titre": "Indicateur sur « Payer »", "description": "D", "valeur": "Moins de doubles clics",
                    "constats": ["C1", "C42"]}],
    "moyen_long_terme": [{"titre": "Design system", "horizon": "long", "description": "Composants"},
                         {"titre": "Tests utilisateurs", "horizon": "moyen", "description": "Paiement"}],
    "demarche_amelioration_continue": ["Mesurer", "Réauditer"],
}


@pytest.fixture
def audit(audit_xlsx):
    return lire_audit(audit_xlsx(PROBLEMES + [POINT_FORT]))


def texte_docx(chemin):
    doc = Document(chemin)
    morceaux = [p.text for p in doc.paragraphs]
    morceaux += [c.text for t in doc.tables for row in t.rows for c in row.cells]
    return "\n".join(morceaux)


def test_rapport_avec_ia(audit, ref, tmp_path):
    client = FauxClient(THEMES, SYNTHESE)
    r, sortie = generer_rapport(audit, ref, tmp_path / "rapport.docx", client, "fr")
    assert r.ia and not r.erreur and len(client.appels) == 2

    # Thématiques : clés inconnues et doublons ignorés, constat non classé regroupé, tri par poids
    assert [t.titre for t in r.themes] == ["Gestion des erreurs", "Retour d'information", "Autres constats"]
    assert [p.cle for p in r.themes[0].problemes] == ["C2", "C4"]
    assert [p.cle for p in r.themes[1].problemes] == ["C1", "C3"]
    assert [p.cle for p in r.themes[2].problemes] == ["C5"]
    assert r.themes[0].recurrent and r.themes[0].gravite_max == 4
    assert [t.titre for t in r.cas_isoles] == ["Autres constats"]  # un seul écran

    # Maturité : l'IA ne peut s'écarter que d'un niveau du niveau indicatif
    assert r.faits.maturite_indicative == 1  # un critique et 60 % de problèmes élevés ou critiques
    assert r.maturite == 2
    # Recommandations hiérarchisées par impact ; thématique inconnue ignorée
    assert [c.titre for c in r.recommandations] == ["Refondre la gestion des erreurs", "Harmoniser les retours"]
    assert [t.titre for t in r.recommandations[0].themes] == ["Gestion des erreurs"]
    assert [p.cle for p in r.quick_wins[0].problemes] == ["C1"]
    assert [s.horizon for s in r.suites] == ["moyen", "long"]

    texte = texte_docx(sortie)
    for attendu in ["1. Synthèse générale", "2. Problèmes UX principaux", "3. Recommandations UX et UI",
                    "4. Prochaines étapes", "4.1 Quick wins", "4.2 Recommandations à moyen et long terme",
                    "4.3 Démarche d'amélioration continue", "L'audit révèle des faiblesses", "Niveau 2 sur 5 : Fragile",
                    "Photos zoomables", "Abandon du paiement", "Refondre la gestion des erreurs",
                    "Moins de doubles clics", "Design system", "Réauditer", "Rédaction assistée par l'IA"]:
        assert attendu in texte, attendu


def test_requetes(audit, ref):
    client = FauxClient(THEMES, SYNTHESE)
    rediger(audit, ref, client, "en")
    themes, synthese = client.appels
    assert themes["response_format"]["json_schema"]["name"] == "themes_audit"
    assert synthese["response_format"]["json_schema"]["name"] == "synthese_audit"
    donnees = themes["messages"][-1]["content"]
    assert all(f"C{i} |" in donnees for i in range(1, 6)) and "zoomables" not in donnees  # problèmes seulement
    assert "en anglais" in donnees
    assert "Checklist" not in themes["messages"][0]["content"]  # pas tout le référentiel : prompt court
    assert "T1 – Gestion des erreurs" in synthese["messages"][-1]["content"]
    assert "Niveau indicatif" in synthese["messages"][-1]["content"]


def test_rapport_sans_ia(audit, ref, tmp_path):
    r, sortie = generer_rapport(audit, ref, tmp_path / "rapport.docx", None, "fr")
    assert not r.ia and not r.erreur
    assert r.maturite == r.faits.maturite_indicative
    assert r.themes[0].titre.startswith("ERR")  # regroupement par catégorie du référentiel
    assert r.recommandations[0].pistes and r.quick_wins_candidats
    texte = texte_docx(sortie)
    assert "[À rédiger]" in texte and "Rapport généré sans IA" in texte
    assert "Les photos produit sont zoomables." in texte


def test_repli_si_la_synthese_echoue(audit, ref, tmp_path):
    client = FauxClient(THEMES, erreur_api(openai.InternalServerError, 500, "panne"))
    r, sortie = generer_rapport(audit, ref, tmp_path / "rapport.docx", client, "fr")
    assert not r.ia and "500" in r.erreur
    assert r.themes[0].titre == "Gestion des erreurs"  # thématiques de l'IA conservées
    assert r.recommandations and "n'a pas pu rédiger" in texte_docx(sortie)


def test_cache(audit, ref):
    rediger(audit, ref, FauxClient(THEMES, SYNTHESE), "fr")
    panne = FauxClient(erreur_api(openai.InternalServerError, 500, "panne"))
    r = rediger(audit, ref, panne, "fr")
    assert r.ia and not panne.appels
    r = rediger(audit, ref, FauxClient(THEMES, SYNTHESE), "fr", forcer=True)
    assert r.ia


def test_rapport_en_anglais(audit, ref, tmp_path):
    _, sortie = generer_rapport(audit, ref, tmp_path / "report.docx", None, "en")
    texte = texte_docx(sortie)
    assert "1. Executive summary" in texte and "4.1 Quick wins" in texte and "[To be written]" in texte


def test_octets_sans_sortie(audit, ref):
    _, contenu = generer_rapport(audit, ref, None, None, "fr")
    assert contenu[:2] == b"PK"  # un .docx est une archive zip


def test_audit_sans_probleme(audit_xlsx, ref, tmp_path):
    client = FauxClient(THEMES)
    r, _ = generer_rapport(lire_audit(audit_xlsx([POINT_FORT])), ref, tmp_path / "r.docx", client, "fr")
    assert not client.appels and r.maturite == 5 and not r.themes


def test_gros_audit_tient_dans_le_budget(audit_xlsx, ref):
    long = "Le libellé du bouton ne décrit pas l'action et l'utilisateur hésite avant de cliquer. " * 4
    audit = lire_audit(audit_xlsx([{**PROBLEMES[0], "ecran": f"Écran {i}", "constat": long} for i in range(200)]))
    client = FauxClient({"themes": [{"titre": "Libellés", "constats": [f"C{i}" for i in range(1, 201)],
                                     "description": "", "pourquoi": "", "consequences": ""}]}, SYNTHESE)
    r = rediger(audit, ref, client, "fr")
    assert len(client.appels[0]["messages"][-1]["content"]) <= BUDGET + 500
    assert len(r.themes) == 1 and len(r.themes[0].problemes) == 200


@pytest.mark.parametrize("gravites, n, niveau", [
    ({}, 0, 5), ({1: 5, 2: 5}, 10, 5), ({2: 9, 3: 1}, 10, 4), ({2: 8, 3: 2}, 10, 3), ({2: 6, 3: 4}, 10, 2),
    ({2: 9, 4: 1}, 10, 2), ({3: 3, 4: 1, 2: 6}, 10, 1), ({4: 3, 1: 17}, 20, 1),
])
def test_maturite_indicative(gravites, n, niveau):
    assert maturite_indicative(gravites, n) == niveau


def test_ligne_de_commande(audit_xlsx, monkeypatch):
    from audit_ergo.__main__ import main

    monkeypatch.setenv("AUDIT_ERGO_IA", "0")
    chemin = audit_xlsx(PROBLEMES)
    main([str(chemin), "--rapport"])
    assert chemin.with_name("audit_rapport.docx").exists()
