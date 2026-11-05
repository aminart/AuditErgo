"""Lance l'application : python -m serveur [--port 8501] [--no-browser] [--version]

Le serveur n'écoute que sur ce poste (127.0.0.1) et ouvre l'application dans le navigateur.

Contrat commun aux applications de la suite (lancement par le portail) :
- --port N : port imposé ; s'il est pris par une autre application, échec explicite (code 2) ;
- --no-browser : ne pas ouvrir le navigateur ;
- --version : affiche la version ;
- GET /health : {"status": "ok", "app": "audit-ergo", "name": ..., "version": ...}.
"""
import argparse
import json
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

import uvicorn

from . import APP_ID, APP_NOM, PORT_DEFAUT, VERSION

HOTE = "127.0.0.1"


def _deja_lancee(port):
    """Vrai si cette application répond déjà sur ce port."""
    try:
        with urllib.request.urlopen(f"http://{HOTE}:{port}/health", timeout=1) as r:
            return r.status == 200 and json.loads(r.read()).get("app") == APP_ID
    except (OSError, ValueError):
        return False


def _port_libre(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sonde:
        return sonde.connect_ex((HOTE, port)) != 0


def _ouvrir_quand_prete(adresse, port):
    for _ in range(60):
        if _deja_lancee(port):
            webbrowser.open(adresse)
            return
        time.sleep(0.5)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m serveur", description=APP_NOM)
    parser.add_argument("--port", type=int, default=PORT_DEFAUT, help=f"port d'écoute (défaut {PORT_DEFAUT})")
    parser.add_argument("--no-browser", "--sans-navigateur", dest="sans_navigateur", action="store_true",
                        help="ne pas ouvrir le navigateur (lancement par le portail)")
    parser.add_argument("--version", action="version", version=f"{APP_NOM} {VERSION}")
    args = parser.parse_args(argv)
    adresse = f"http://localhost:{args.port}"

    if _deja_lancee(args.port):
        print(f"L'application est déjà lancée : {adresse}")
        if not args.sans_navigateur:
            webbrowser.open(adresse)
        return
    if not _port_libre(args.port):
        print(f"Le port {args.port} est déjà utilisé par une autre application : impossible de démarrer.",
              file=sys.stderr)
        sys.exit(2)

    from .api import WEB, creer_app  # après les vérifications : le chargement du référentiel prend un instant

    if not (WEB / "index.html").exists():
        print("Interface introuvable (web/dist) : compilez-la avec « npm run build » dans le dossier web.")
    if not args.sans_navigateur:
        threading.Thread(target=_ouvrir_quand_prete, args=(adresse, args.port), daemon=True).start()
    print(f"{APP_NOM} {VERSION}")
    print(f"Application : {adresse} (accessible depuis ce poste seulement)")
    uvicorn.run(creer_app(), host=HOTE, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
