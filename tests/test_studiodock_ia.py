"""Connexion et modèle réglés dans Studio Dock (Réglages › Modèles d'IA), communs à toutes les apps de la suite."""
import base64
import json

import pytest
from fastapi.testclient import TestClient

from audit_ergo import parametres, studiodock_ia


def ecrire(defaut=None, apps=None):
    dossier = studiodock_ia.dossier()
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "connexions.json").write_text(json.dumps({
        "format": 1,
        "connections": [
            {"id": "sd1", "name": "Passerelle", "provider": "openai", "api_base": "https://llm.interne/v1",
             "api_key": {"scheme": "plain", "data": base64.b64encode(b"sk-dock-ABCD1234").decode()},
             "models": ["mistral-large", "mistral-small"]},
            {"id": "sd2", "name": "Ollama (ce poste)", "provider": "ollama", "api_base": "http://localhost:11434/v1",
             "models": ["qwen3:8b"], "context_tokens": 4096},
        ],
        "default": defaut, "apps": apps or {},
    }), encoding="utf-8")


@pytest.fixture(autouse=True)
def sans_env(monkeypatch):
    for nom in ("API_BASE", "API_KEY", "CA_BUNDLE"):
        monkeypatch.delenv(nom, raising=False)


def test_studio_dock_fournit_la_connexion():
    parametres.enregistrer("https://propre.exemple/v1", "sk-propre", "modele-propre", 300)
    ecrire({"connection": "sd1", "model": "mistral-small"}, {"audit-ergo": {"connection": "sd2", "model": "qwen3:8b"}})
    p = parametres.effectifs()
    assert (p.source, p.api_base, p.model, p.api_key) == ("studiodock", "http://localhost:11434/v1", "qwen3:8b", "")
    publics = parametres.publics()
    assert publics["source"] == "studiodock" and publics["studiodock"] == {"name": "Ollama (ce poste)"}
    # Enregistrer depuis l'écran : seul le délai change, la connexion propre reste intacte
    parametres.enregistrer("https://ignore/v1", "ignore", "ignore", 450)
    donnees = parametres.enregistres()
    assert (donnees["api_base"], donnees["model"], donnees["timeout"]) == ("https://propre.exemple/v1", "modele-propre", 450)
    assert parametres.cle_enregistree() == "sk-propre"


def test_modele_par_defaut_avec_cle():
    ecrire({"connection": "sd1", "model": "mistral-small"})
    p = parametres.effectifs()
    assert (p.api_key, p.model) == ("sk-dock-ABCD1234", "mistral-small")
    assert "sk-dock" not in json.dumps(parametres.publics())


def test_configuration_propre_et_env(monkeypatch):
    ecrire({"connection": "sd1", "model": "mistral-small"}, {"audit-ergo": {"own": True}})
    p = parametres.effectifs()
    assert (p.source, p.api_base) == ("app", parametres.ADRESSE_DEFAUT)
    assert parametres.publics()["studiodock_own"]
    ecrire({"connection": "sd1", "model": "mistral-small"})
    monkeypatch.setenv("API_BASE", "https://env.exemple/v1")
    assert parametres.effectifs().source == "app"


def test_test_de_connexion(ref, monkeypatch):
    from serveur import api

    ecrire({"connection": "sd1", "model": "mistral-small"})
    app = api.creer_app(ref)
    monkeypatch.setattr(api, "client_ou_none", lambda *a, **k: None)
    client = TestClient(app)
    r = client.post("/api/settings/test", json={"api_base": "", "model": "autre"}).json()
    # Le test part vers la connexion de Studio Dock, pas vers les valeurs du formulaire
    assert r["model"] == "mistral-small"
    lu = client.get("/api/settings").json()
    assert lu["source"] == "studiodock" and lu["model"] == "mistral-small"
