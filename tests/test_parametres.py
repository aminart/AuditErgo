"""Paramètres de connexion de l'écran Réglages (même fonctionnement que SpecGen) : enregistrement, clé jamais
renvoyée, .env prioritaire champ par champ, certificat importé, test de connexion avec diagnostic."""
import datetime as dt
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient

from audit_ergo import parametres
from audit_ergo.suggestion import client_ou_none, connexion
from serveur import api


@pytest.fixture
def env_vide(monkeypatch):
    for nom in parametres.VARIABLES.values():
        monkeypatch.delenv(nom, raising=False)
    monkeypatch.delenv("AUDIT_ERGO_IA", raising=False)
    monkeypatch.setattr("audit_ergo.suggestion.charger_env.__defaults__", (parametres.dossier_config() / "absent.env",))
    return monkeypatch


@pytest.fixture
def client(ref, env_vide):
    return TestClient(api.creer_app(ref))


def certificat_pem(jours=30):
    cle = ec.generate_private_key(ec.SECP256R1())
    nom = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Autorite interne test")])
    maintenant = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(nom).issuer_name(nom).public_key(cle.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(maintenant - dt.timedelta(days=1))
            .not_valid_after(maintenant + dt.timedelta(days=jours)).sign(cle, hashes.SHA256()))
    return cert.public_bytes(Encoding.PEM)


def test_sans_reglage_ollama_local_par_defaut(client):
    p = connexion()
    assert (p.api_base, p.model, p.api_key, p.ca_bundle) == (parametres.ADRESSE_DEFAUT, "mistral-small", "", "")
    publics = client.get("/api/settings").json()
    assert publics["saved"] is False and publics["active"] is True and publics["certificate"] is None


def test_enregistrer_sans_jamais_renvoyer_la_cle(client):
    cle = "sk-passerelle-1234567890ABCD"
    r = client.put("/api/settings", json={"api_base": "https://passerelle.interne/v1", "api_key": cle,
                                          "model": "mistral-large", "timeout": 120}).json()
    assert r["saved"] and r["has_api_key"] and r["api_key_hint"] == "ABCD"
    assert cle not in json.dumps(r) and cle not in json.dumps(client.get("/api/settings").json())
    assert cle not in (parametres.dossier_config() / "config.json").read_text(encoding="utf-8")
    p = connexion()
    assert (p.api_base, p.api_key, p.model, p.timeout) == ("https://passerelle.interne/v1", cle, "mistral-large", 120)
    # Le client du modèle utilise les paramètres enregistrés, et la barre latérale les affiche
    assert str(client_ou_none().base_url) == "https://passerelle.interne/v1/" and client_ou_none().api_key == cle
    ia = client.get("/api/config").json()["ia"]
    assert ia["modele"] == "mistral-large" and ia["hote"] == "passerelle.interne" and ia["cle"] is True


def test_cle_gardee_ou_effacee(client):
    client.put("/api/settings", json={"api_base": "http://localhost:1234/v1", "api_key": "cle-longue-1234"})
    client.put("/api/settings", json={"api_base": "http://localhost:1234/v1", "api_key": None})
    assert connexion().api_key == "cle-longue-1234"
    client.put("/api/settings", json={"api_base": "http://localhost:1234/v1", "api_key": ""})
    assert connexion().api_key == "" and client.get("/api/settings").json()["has_api_key"] is False


def test_env_prioritaire_champ_par_champ(client, env_vide):
    client.put("/api/settings", json={"api_base": "http://localhost:1234/v1", "model": "modele-ecran"})
    env_vide.setenv("API_BASE", "https://depuis-le-env.interne/v1")
    publics = client.get("/api/settings").json()
    assert publics["api_base"] == "https://depuis-le-env.interne/v1" and publics["env_fields"] == ["api_base"]
    assert publics["model"] == "modele-ecran"


def test_certificat_importe(client):
    r = client.post("/api/settings/certificate", files={"file": ("autorite.crt", certificat_pem(30))})
    assert r.status_code == 200
    certificat = r.json()["certificate"]
    assert certificat["name"] == "autorite.crt" and certificat["expires_at"] and certificat["imported_at"]
    assert connexion().ca_bundle == str(parametres.chemin_certificat())
    assert parametres.chemin_certificat().read_bytes().startswith(b"-----BEGIN CERTIFICATE-----")


def test_certificat_invalide_refuse(client):
    r = client.post("/api/settings/certificate?langue=en", files={"file": ("faux.crt", b"pas un certificat")})
    assert r.status_code == 422 and "not a valid certificate" in r.json()["detail"]
    assert connexion().ca_bundle == ""


def test_effacer(client):
    client.put("/api/settings", json={"api_base": "http://localhost:1234/v1", "api_key": "cle-longue-1234"})
    client.post("/api/settings/certificate", files={"file": ("a.crt", certificat_pem())})
    r = client.delete("/api/settings").json()
    assert r["saved"] is False and r["has_api_key"] is False and r["certificate"] is None
    assert connexion().api_base == parametres.ADRESSE_DEFAUT


@pytest.fixture
def serveur_ollama():
    """Serveur local qui liste ses modèles comme Ollama (GET /v1/models)."""
    class Serveur(BaseHTTPRequestHandler):
        def do_GET(self):
            brut = json.dumps({"object": "list", "data": [{"id": "mistral-small:latest", "object": "model"},
                                                          {"id": "llama3:8b", "object": "model"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(brut)))
            self.end_headers()
            self.wfile.write(brut)

        def log_message(self, *args):
            pass

    serveur = HTTPServer(("127.0.0.1", 0), Serveur)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{serveur.server_port}/v1"
    serveur.shutdown()


def test_tester_modele_disponible(client, serveur_ollama):
    r = client.post("/api/settings/test", json={"api_base": serveur_ollama, "model": "mistral-small"}).json()
    assert r["ok"] is True and r["title"] == "Connexion opérationnelle" and r["model"] == "mistral-small" and r["at"]
    # Le dernier test est gardé pour l'écran, mais les valeurs testées ne sont pas enregistrées
    publics = client.get("/api/settings").json()
    assert publics["last_test"]["ok"] is True and publics["saved"] is False


def test_tester_modele_absent(client, serveur_ollama):
    r = client.post("/api/settings/test?langue=en", json={"api_base": serveur_ollama, "model": "qwen"}).json()
    assert r["ok"] is False and r["field"] == "model"
    assert "mistral-small:latest" in r["message"] and "ollama pull qwen" in r["message"]


def test_tester_serveur_injoignable(client):
    r = client.post("/api/settings/test", json={"api_base": "http://127.0.0.1:9/v1"}).json()
    assert r["ok"] is False and r["field"] == "api_base" and "injoignable" in r["title"]


def test_tester_adresse_invalide(client):
    r = client.post("/api/settings/test", json={"api_base": "localhost"}).json()
    assert r["ok"] is False and r["field"] == "api_base"
