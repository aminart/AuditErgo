"""Contrat du portail : /health, --port, --no-browser et --version, communs aux applications de la suite."""
import socket

import pytest
from fastapi.testclient import TestClient

from serveur import APP_ID, PORT_DEFAUT, VERSION, api
from serveur import __main__ as lanceur


def test_health_repond_sans_ia(ref, monkeypatch):
    monkeypatch.setenv("AUDIT_ERGO_HISTORIQUE", "0")
    r = TestClient(api.creer_app(ref)).get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "app": APP_ID, "name": "Audit ergonomique", "version": VERSION}


def test_port_reserve():
    assert PORT_DEFAUT == 8501


def test_option_version(capsys):
    with pytest.raises(SystemExit) as fin:
        lanceur.main(["--version"])
    assert fin.value.code == 0
    assert VERSION in capsys.readouterr().out


def test_port_pris_par_une_autre_application(monkeypatch, capsys):
    with socket.socket() as autre:
        autre.bind(("127.0.0.1", 0))
        autre.listen()
        port = autre.getsockname()[1]
        lance = []
        monkeypatch.setattr(lanceur.uvicorn, "run", lambda *a, **k: lance.append(k))
        with pytest.raises(SystemExit) as fin:
            lanceur.main(["--port", str(port), "--no-browser"])
    assert fin.value.code == 2
    assert not lance
    assert str(port) in capsys.readouterr().err


@pytest.mark.parametrize("option", ["--no-browser", "--sans-navigateur"])
def test_sans_navigateur(monkeypatch, option):
    with socket.socket() as sonde:
        sonde.bind(("127.0.0.1", 0))
        port = sonde.getsockname()[1]
    lance, ouvert = [], []
    monkeypatch.setattr(lanceur.uvicorn, "run", lambda app, **k: lance.append(k))
    monkeypatch.setattr(lanceur.webbrowser, "open", ouvert.append)
    lanceur.main(["--port", str(port), option])
    assert lance == [{"host": "127.0.0.1", "port": port, "log_level": "warning"}]
    assert not ouvert
