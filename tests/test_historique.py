"""Historique des audits, comparaison de deux audits et modifications du rapport par le designer."""
from docx import Document
from fastapi.testclient import TestClient

import serveur.api as api
from conftest import CONSTAT_VALIDE
from serveur.historique import Historique
from test_api import FauxModele, SUGGESTION, attendre, deposer


def nouvelle_app(ref, monkeypatch):
    """Une nouvelle instance de l'application : comme après un redémarrage du poste."""
    modele = FauxModele(SUGGESTION, prompt_tokens=20000)
    monkeypatch.setattr(api, "client_ou_none", lambda *a, **k: modele)
    monkeypatch.setattr(api, "ia_configuree", lambda: True)
    return TestClient(api.creer_app(ref))


def test_audit_rouvert_apres_redemarrage(ref, monkeypatch, audit_xlsx, historique_isole):
    client = nouvelle_app(ref, monkeypatch)
    e = deposer(client, audit_xlsx([{"ecran": "Paiement", "constat": CONSTAT_VALIDE["constat"]}])).json()
    e = attendre(client, client.post(f"/api/audits/{e['id']}/ia", json={"langue": "fr"}).json())
    ligne = e["constats"][0]["ligne"]
    client.post(f"/api/audits/{e['id']}/decisions", json={"decisions": [
        {"ligne": ligne, "champ": "critere", "action": "valider"}]})
    attendre(client, client.post(f"/api/audits/{e['id']}/rapport", json={"langue": "fr"}).json())
    assert e["persistant"] and (historique_isole / e["id"] / "etat.pkl").exists()

    apres = nouvelle_app(ref, monkeypatch)
    liste = apres.get("/api/audits").json()
    assert liste["persistant"] and [a["id"] for a in liste["audits"]] == [e["id"]]
    assert liste["audits"][0]["ia"] and liste["audits"][0]["rapport"] and liste["audits"][0]["produit"] == "Produit test"
    r = apres.get(f"/api/audits/{e['id']}").json()
    assert r["constats"][0]["completions"]["critere"]["origine"] == "valide"
    assert r["constats"][0]["ia"]["code"] == "GUI-03" and r["rapport"] == "a_jour"
    assert apres.get(f"/api/audits/{e['id']}/fichier").content[:2] == b"PK"
    assert apres.get(f"/api/audits/{e['id']}/rapport").status_code == 200

    assert apres.delete(f"/api/audits/{e['id']}").json()["ok"]
    assert apres.get("/api/audits").json()["audits"] == []
    assert apres.get(f"/api/audits/{e['id']}").status_code == 404
    assert not (historique_isole / e["id"]).exists()


def test_historique_desactive(ref, monkeypatch, audit_xlsx):
    monkeypatch.setenv("AUDIT_ERGO_HISTORIQUE", "0")
    client = nouvelle_app(ref, monkeypatch)
    e = deposer(client, audit_xlsx([CONSTAT_VALIDE])).json()
    assert e["persistant"] is False
    assert not client.get("/api/audits").json()["persistant"]


def test_identifiants_refuses(tmp_path):
    h = Historique(tmp_path)
    assert h.charger("../secret") is None
    h.supprimer("..")  # sans effet
    assert tmp_path.exists()


def test_comparaison(ref, monkeypatch, audit_xlsx):
    client = nouvelle_app(ref, monkeypatch)
    avant = deposer(client, audit_xlsx([CONSTAT_VALIDE, {**CONSTAT_VALIDE, "ecran": "Panier", "gravite": 4}],
                                       nom="v1.xlsx")).json()
    apres = deposer(client, audit_xlsx([{**CONSTAT_VALIDE, "gravite": 2}], nom="v2.xlsx")).json()
    c = client.get(f"/api/comparaison?a={avant['id']}&b={apres['id']}").json()
    assert c["a"]["nb_problemes"] == 2 and c["b"]["nb_problemes"] == 1
    assert c["a"]["gravites"]["4"] == 1 and c["b"]["gravites"]["2"] == 1
    assert c["a"]["par_categorie"]["GUI"] == 2 and c["b"]["par_categorie"]["GUI"] == 1
    assert c["a"]["maturite_indicative"] < c["b"]["maturite_indicative"]
    assert {x["code"] for x in c["categories"]} == set(ref.categories)
    assert client.get(f"/api/comparaison?a={avant['id']}&b=inconnu").status_code == 404


def test_modifier_rapport(ref, monkeypatch, audit_xlsx, tmp_path):
    client = nouvelle_app(ref, monkeypatch)
    e = deposer(client, audit_xlsx([CONSTAT_VALIDE, {**CONSTAT_VALIDE, "ecran": "Panier", "gravite": 4}])).json()
    attendre(client, client.post(f"/api/audits/{e['id']}/rapport", json={"ia": False, "langue": "fr"}).json())
    url = f"/api/audits/{e['id']}/rapport"
    r = client.patch(url, json={"chemin": "impact", "valeur": "  Les clients abandonnent leur panier.  "}).json()
    assert r["impact"] == "Les clients abandonnent leur panier." and r["modifie"]
    r = client.patch(url, json={"chemin": "points_forts", "valeur": ["Catalogue clair", " ", "Photos"]}).json()
    assert r["points_forts"] == ["Catalogue clair", "Photos"]
    r = client.patch(url, json={"chemin": "themes.0.pourquoi", "valeur": "Le système ne répond pas."}).json()
    assert r["themes"][0]["pourquoi"] == "Le système ne répond pas."
    assert client.patch(url, json={"chemin": "maturite", "valeur": 4}).json()["maturite"] == 4
    for refus in ({"chemin": "faits", "valeur": "x"}, {"chemin": "themes.99.titre", "valeur": "x"},
                  {"chemin": "themes.0.problemes", "valeur": "x"}, {"chemin": "maturite", "valeur": 9}):
        assert client.patch(url, json=refus).status_code == 400

    # Le rapport Word reprend les modifications
    chemin = tmp_path / "rapport.docx"
    chemin.write_bytes(client.get(f"{url}.docx").content)
    texte = "\n".join(p.text for p in Document(chemin).paragraphs)
    assert "Les clients abandonnent leur panier." in texte and "Le système ne répond pas." in texte

    # Une décision sur l'audit garde le rapport modifié, signalé comme à régénérer
    e = attendre(client, client.post(f"/api/audits/{e['id']}/ia", json={"langue": "fr"}).json())
    assert e["rapport"] == "perime"
    assert client.get(url).json()["impact"] == "Les clients abandonnent leur panier."
