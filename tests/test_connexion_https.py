"""Connexion au modèle avec exactement API_BASE, API_KEY et CA_BUNDLE : serveur local en HTTPS, certificat signé
par une autorité interne, clé d'API exigée."""
import json
import shutil
import ssl
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from audit_ergo.suggestion import ErreurSuggestion, client_ou_none, suggerer
from test_suggestion import reponse_ia

pytestmark = pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl absent")
CLE = "cle-du-serveur-mistral"


def _openssl(*args, cwd):
    subprocess.run(["openssl", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture(scope="module")
def certificats(tmp_path_factory):
    """Autorité interne (ca.pem) et certificat du serveur pour localhost, signé par elle. L'autorité n'a pas
    d'extension « key usage », comme beaucoup d'autorités internes d'entreprise (refusée par défaut en Python 3.13)."""
    d = tmp_path_factory.mktemp("pki")
    _openssl("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2", "-subj", "/CN=Autorite interne test",
             "-keyout", "ca.key", "-out", "ca.pem", cwd=d)
    _openssl("req", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=localhost", "-keyout", "serveur.key",
             "-out", "serveur.csr", cwd=d)
    (d / "san.cnf").write_text("subjectAltName=DNS:localhost,IP:127.0.0.1\n")
    _openssl("x509", "-req", "-in", "serveur.csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial",
             "-days", "2", "-extfile", "san.cnf", "-out", "serveur.pem", cwd=d)
    return d


@pytest.fixture
def serveur_https(certificats):
    recus = []

    class Serveur(BaseHTTPRequestHandler):
        def do_POST(self):
            corps = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            recus.append(self.headers.get("Authorization"))
            if self.headers.get("Authorization") != f"Bearer {CLE}":
                return self._repondre(401, {"error": {"message": "invalid api key"}})
            taille = sum(len(m["content"]) for m in corps["messages"]) // 4
            self._repondre(200, {"id": "x", "object": "chat.completion", "model": corps["model"],
                                 "choices": [{"index": 0, "finish_reason": "stop",
                                              "message": {"role": "assistant", "content": json.dumps(reponse_ia())}}],
                                 "usage": {"prompt_tokens": taille, "completion_tokens": 300}})

        def _repondre(self, code, data):
            brut = json.dumps(data).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(brut)))
            self.end_headers()
            self.wfile.write(brut)

        def log_message(self, *args):
            pass

    serveur = HTTPServer(("127.0.0.1", 0), Serveur)
    contexte = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexte.load_cert_chain(certificats / "serveur.pem", certificats / "serveur.key")
    serveur.socket = contexte.wrap_socket(serveur.socket, server_side=True)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    yield f"https://localhost:{serveur.server_port}/v1", recus
    serveur.shutdown()


@pytest.fixture
def env(monkeypatch):
    for nom in ("API_KEY", "API_BASE", "CA_BUNDLE", "AUDIT_ERGO_IA"):
        monkeypatch.delenv(nom, raising=False)
    monkeypatch.setattr("audit_ergo.suggestion.charger_env.__defaults__", (Path("/inexistant/.env"),))
    return monkeypatch


def test_api_base_api_key_ca_bundle(env, serveur_https, certificats, ref):
    adresse, recus = serveur_https
    env.setenv("API_BASE", adresse)
    env.setenv("API_KEY", CLE)
    env.setenv("CA_BUNDLE", str(certificats / "ca.pem"))
    s = suggerer(client_ou_none(), ref, "Aucun indicateur après le clic sur Payer.", cache=None)
    assert s.code == "GUI-03" and recus == [f"Bearer {CLE}"]


def test_sans_ca_bundle_le_certificat_est_refuse(env, serveur_https, ref):
    adresse, _ = serveur_https
    env.setenv("API_BASE", adresse)
    env.setenv("API_KEY", CLE)
    with pytest.raises(ErreurSuggestion, match="CA_BUNDLE"):
        suggerer(client_ou_none(), ref, "Aucun indicateur après le clic sur Payer.", cache=None)


def test_mauvaise_cle_refusee(env, serveur_https, certificats, ref):
    adresse, _ = serveur_https
    env.setenv("API_BASE", adresse)
    env.setenv("API_KEY", "mauvaise-cle")
    env.setenv("CA_BUNDLE", str(certificats / "ca.pem"))
    with pytest.raises(ErreurSuggestion, match="API_KEY"):
        suggerer(client_ou_none(), ref, "Aucun indicateur après le clic sur Payer.", cache=None)


# --- Même connexion configurée depuis l'écran Réglages (certificat importé, clé chiffrée) ------------------

@pytest.fixture
def ecran(env, ref):
    from fastapi.testclient import TestClient

    from serveur import api

    return TestClient(api.creer_app(ref))


def test_ecran_reglages_certificat_importe(ecran, serveur_https, certificats, ref):
    adresse, recus = serveur_https
    ecran.post("/api/settings/certificate", files={"file": ("autorite.crt", (certificats / "ca.pem").read_bytes())})
    r = ecran.post("/api/settings/test", json={"api_base": adresse, "api_key": CLE, "model": "mistral-small"}).json()
    # Serveur sans liste de modèles (GET refusé) : le test passe par un petit appel au modèle
    assert r["ok"] is True, r
    ecran.put("/api/settings", json={"api_base": adresse, "api_key": CLE, "model": "mistral-small"})
    s = suggerer(client_ou_none(), ref, "Aucun indicateur après le clic sur Payer.", cache=None)
    assert s.code == "GUI-03" and recus[-1] == f"Bearer {CLE}"


def test_ecran_reglages_sans_certificat(ecran, serveur_https):
    adresse, _ = serveur_https
    r = ecran.post("/api/settings/test", json={"api_base": adresse, "api_key": CLE}).json()
    assert r["ok"] is False and r["field"] == "certificate"


def test_ecran_reglages_mauvaise_cle(ecran, serveur_https, certificats):
    adresse, _ = serveur_https
    ecran.post("/api/settings/certificate", files={"file": ("autorite.crt", (certificats / "ca.pem").read_bytes())})
    r = ecran.post("/api/settings/test", json={"api_base": adresse, "api_key": "mauvaise-cle"}).json()
    assert r["ok"] is False and r["field"] == "api_key"
