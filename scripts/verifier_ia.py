"""Vérifie que le modèle local répond (utilisé par start.bat ; n'empêche jamais le lancement).

Usage : python scripts/verifier_ia.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from audit_ergo.suggestion import MODELE, ErreurSuggestion, adresse_api, client_ou_none  # noqa: E402


def main():
    try:
        client = client_ou_none()
    except ErreurSuggestion as e:
        print(f"IA : {e}")
        return
    if client is None:
        print("IA désactivée (AUDIT_ERGO_IA=0) : seuls les contrôles de forme seront disponibles.")
        return
    try:
        modeles = [m.id for m in client.models.list()]
    except Exception:
        print(f"IA : le modèle local ne répond pas à {adresse_api()}.")
        print("     Lancez Ollama (ou LM Studio) pour utiliser les suggestions ; l'application démarre quand même.")
        return
    if any(m == MODELE or m.split(":")[0] == MODELE for m in modeles):
        print(f"IA : modèle local « {MODELE} » prêt ({adresse_api()}). Aucune donnée ne quitte ce poste.")
    else:
        print(f"IA : le modèle « {MODELE} » n'est pas installé. Disponibles : {', '.join(modeles) or 'aucun'}.")
        print(f"     Installez-le (« ollama pull {MODELE} ») ou corrigez AUDIT_ERGO_MODELE dans .env.")


if __name__ == "__main__":
    main()
