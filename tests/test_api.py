"""Tests de l'API de l'application (serveur FastAPI), avec un faux modèle : ni modèle ni réseau nécessaires."""
import time

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

import serveur.api as api
from audit_ergo.lecture import nom_colonne
from conftest import CONSTAT_VALIDE
from test_rapport import SYNTHESE, THEMES
from test_suggestion import FauxClient, reponse_ia

SUGGESTION = reponse_ia(
    verdict_designer={"statut": "a_revoir", "commentaire": "GUI-01 décrit l'avant de l'action."},
    recommandation={"proposee": "Afficher un indicateur de chargement dans le bouton.", "type": "design",
                    "avis_designer": {"statut": "non_fournie", "commentaire": "", "version_amelioree": ""},
                    "complementaires": []},
    gravite={"valeur": 3, "justification": "Risque de double paiement."},
)


class FauxModele(FauxClient):
    """Répond selon la requête : suggestion de critère, thématiques ou synthèse du rapport."""

    def _create(self, **requete):
        nom = requete.get("response_format", {}).get("json_schema", {}).get("name", "")
        self.reponses = [THEMES if "theme" in nom else SYNTHESE if "synthese" in nom else SUGGESTION]
        return super()._create(**requete)


@pytest.fixture
def client(ref, monkeypatch):
    modele = FauxModele(SUGGESTION, prompt_tokens=20000)
    monkeypatch.setattr(api, "client_ou_none", lambda *a, **k: modele)
    monkeypatch.setattr(api, "ia_configuree", lambda: True)
    return TestClient(api.creer_app(ref))


def attendre(client, tache):
    for _ in range(200):
        if tache["etat"] != "en_cours":
            break
        time.sleep(0.05)
        tache = client.get(f"/api/taches/{tache['id']}").json()
    assert tache["etat"] == "terminee", tache["erreur"]
    return tache["resultat"]


def deposer(client, chemin, langue="fr"):
    with open(chemin, "rb") as f:
        return client.post("/api/audits", files={"fichier": (chemin.name, f)}, data={"langue": langue})


def test_config(client):
    c = client.get("/api/config?langue=en").json()
    assert c["referentiel"]["criteres"][0]["libelle"].startswith("GUI-01 – ")
    assert c["ia"]["active"] and c["ia"]["locale"]
    assert c["referentiel"]["champs"]["constat"] == "Finding"


def test_hote_refuse(ref):
    """Une page web ne peut pas joindre l'application par un autre nom que ce poste (DNS rebinding)."""
    r = TestClient(api.creer_app(ref), base_url="http://exemple.com").get("/api/config")
    assert r.status_code == 400


def test_depot_et_controles(client, audit_xlsx):
    r = deposer(client, audit_xlsx([CONSTAT_VALIDE, {"ecran": "Panier", "constat": "Menu confus."}]))
    assert r.status_code == 200
    e = r.json()
    assert e["synthese"]["nb_constats"] == 2 and e["ia"] is None
    assert any(a["code"] == "CHAMP_VIDE" for a in e["constats"][1]["anomalies"])
    # Changer de langue relance les contrôles dans cette langue
    en = client.get(f"/api/audits/{e['id']}?langue=en").json()
    assert en["langue"] == "en" and en["anomalies"][0]["message"] != e["anomalies"][0]["message"]
    fichier = client.get(f"/api/audits/{e['id']}/fichier")
    assert fichier.status_code == 200 and fichier.content[:2] == b"PK"


def test_depot_refuse(client, tmp_path):
    texte = tmp_path / "notes.txt"
    texte.write_text("pas un audit")
    assert deposer(client, texte).status_code == 400
    faux = tmp_path / "faux.xlsx"
    faux.write_bytes(b"pas un fichier Excel")
    r = deposer(client, faux)
    assert r.status_code == 400 and "xlsx" in r.json()["detail"]
    assert client.get("/api/audits/inconnu").status_code == 404


def test_ia_puis_decisions(client, audit_xlsx, tmp_path):
    e = deposer(client, audit_xlsx([{"ecran": "Paiement", "constat": CONSTAT_VALIDE["constat"]}])).json()
    e = attendre(client, client.post(f"/api/audits/{e['id']}/ia", json={"langue": "fr"}).json())
    c = e["constats"][0]
    assert c["ia"]["code"] == "GUI-03" and c["ia"]["critere"]["code"] == "GUI-03"
    assert c["completions"]["critere"]["origine"] == "ia"
    assert e["a_valider"] == e["nb_completions"] > 0

    # Valider le critère, corriger la recommandation, refuser la gravité
    e = client.post(f"/api/audits/{e['id']}/decisions", json={"langue": "fr", "decisions": [
        {"ligne": c["ligne"], "champ": "critere", "action": "valider"},
        {"ligne": c["ligne"], "champ": "recommandation", "action": "modifier", "valeur": "Désactiver le bouton."},
        {"ligne": c["ligne"], "champ": "gravite", "action": "refuser"},
    ]}).json()
    c = e["constats"][0]
    assert c["completions"]["critere"]["origine"] == "valide"
    assert c["valeurs"]["recommandation"] == "Désactiver le bouton."
    assert "gravite" not in c["completions"] and c["valeurs"]["gravite"] is None
    assert any(a["code"] == "CHAMP_VIDE" and a["champ"] == "gravite" for a in c["anomalies"])

    # Le fichier exporté contient les décisions : valeur validée sans fond violet, gravité vide
    sortie = tmp_path / "sortie.xlsx"
    sortie.write_bytes(client.get(f"/api/audits/{e['id']}/fichier").content)
    ws = load_workbook(sortie)["Audit"]
    entetes = {nom_colonne(cell.value): cell.column for cell in ws[3] if cell.value}
    reco = ws.cell(row=c["ligne"], column=entetes["recommandation"])
    assert reco.value == "Désactiver le bouton." and reco.fill.fgColor.rgb != "00E4DFEC"
    assert ws.cell(row=c["ligne"], column=entetes["gravite"]).value is None

    erreur = client.post(f"/api/audits/{e['id']}/decisions", json={"decisions": [
        {"ligne": c["ligne"], "champ": "gravite", "action": "valider"}]})
    assert erreur.status_code == 400


def test_rapport(client, audit_xlsx):
    e = deposer(client, audit_xlsx([CONSTAT_VALIDE, {**CONSTAT_VALIDE, "ecran": "Panier", "gravite": 4}])).json()
    assert client.get(f"/api/audits/{e['id']}/rapport").status_code == 404
    r = attendre(client, client.post(f"/api/audits/{e['id']}/rapport", json={"langue": "fr"}).json())
    assert r["ia"] and r["resume"].startswith("L'audit révèle")
    assert r["libelles"]["s1"] == "Synthèse générale"
    assert r["faits"]["gravites"] == {"3": 1, "4": 1}
    assert all(k in {p["cle"] for p in r["faits"]["problemes"]} for th in r["themes"] for k in th["problemes"])
    assert client.get(f"/api/audits/{e['id']}/rapport").json()["resume"] == r["resume"]
    word = client.get(f"/api/audits/{e['id']}/rapport.docx")
    assert word.status_code == 200 and word.content[:2] == b"PK"
    # Changer la langue de l'interface ne rend pas le rapport obsolète
    assert client.get(f"/api/audits/{e['id']}?langue=en").json()["rapport"] == "a_jour"


def test_rapport_sans_ia(client, audit_xlsx):
    e = deposer(client, audit_xlsx([CONSTAT_VALIDE])).json()
    r = attendre(client, client.post(f"/api/audits/{e['id']}/rapport", json={"ia": False, "langue": "en"}).json())
    assert not r["ia"] and r["langue"] == "en" and r["quick_wins_candidats"]


def test_suggestion(client):
    assert client.post("/api/suggestion", json={"constat": "  "}).status_code == 400
    r = attendre(client, client.post("/api/suggestion", json={
        "constat": CONSTAT_VALIDE["constat"], "critere": "GUI-01", "gravite": 9, "langue": "en"}).json())
    s = r["suggestion"]
    assert s["code"] == "GUI-03" and s["critere_designer"] == "GUI-01" and s["verdict"] == "a_revoir"
    assert s["critere"]["libelle"] == "GUI-03 – Immediate Feedback"
    assert s["gravite"] == 3 and s["reco_a_retenir"]


def test_ia_desactivee(ref, monkeypatch, audit_xlsx):
    monkeypatch.setenv("AUDIT_ERGO_IA", "0")
    c = TestClient(api.creer_app(ref))
    assert c.post("/api/settings/test", json={}).json()["field"] == "disabled"
    e = deposer(c, audit_xlsx([CONSTAT_VALIDE])).json()
    assert c.post(f"/api/audits/{e['id']}/ia", json={}).status_code == 400
    assert c.post("/api/suggestion", json={"constat": "Un constat"}).status_code == 400


def test_interface_servie(client):
    if not (api.WEB / "index.html").exists():
        pytest.skip("interface non compilée")
    assert "<div id=\"root\">" in client.get("/").text
    assert "<div id=\"root\">" in client.get("/rapport").text  # navigation côté navigateur
    assert client.get("/api/inconnu").status_code == 404
