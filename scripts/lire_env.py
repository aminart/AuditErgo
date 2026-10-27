"""Affiche la valeur d'une variable du fichier .env (utilisé par start.bat).

Usage : python scripts/lire_env.py NOM   -> affiche la valeur, ou rien si elle est absente ou vide.
"""
import sys
from pathlib import Path

ENV = Path(__file__).resolve().parent.parent / ".env"

if __name__ == "__main__":
    if len(sys.argv) != 2 or not ENV.exists():
        sys.exit(0)
    for ligne in ENV.read_text(encoding="utf-8-sig").splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith("#") and "=" in ligne:
            cle, valeur = ligne.split("=", 1)
            if cle.strip() == sys.argv[1]:
                valeur = valeur.strip().strip('"').strip("'")
                if valeur:
                    print(valeur)
                break
