"""Lance l'application : python -m serveur [--port 8501] [--sans-navigateur]

Le serveur n'écoute que sur ce poste (127.0.0.1) et ouvre l'application dans le navigateur.
"""
import argparse
import threading
import time
import webbrowser

import uvicorn

from .api import WEB, creer_app


def main():
    parser = argparse.ArgumentParser(description="Audit ergonomique assisté")
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--sans-navigateur", action="store_true", help="ne pas ouvrir le navigateur")
    args = parser.parse_args()
    adresse = f"http://localhost:{args.port}"
    if not (WEB / "index.html").exists():
        print("Interface introuvable (web/dist) : compilez-la avec « npm run build » dans le dossier web.")
    if not args.sans_navigateur:
        threading.Thread(target=lambda: (time.sleep(2), webbrowser.open(adresse)), daemon=True).start()
    print(f"Application : {adresse} (accessible depuis ce poste seulement)")
    uvicorn.run(creer_app(), host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
