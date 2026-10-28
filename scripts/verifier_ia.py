"""Vérifie que le modèle répond (utilisé par start.bat ; n'empêche jamais le lancement).

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
    import openai

    try:
        modeles = [m.id for m in client.models.list()]
    except openai.NotFoundError:  # passerelle sans /v1/models : elle répond, on ne peut pas lister
        print(f"IA : le serveur {adresse_api()} répond (modèle « {MODELE} »).")
        return
    except openai.AuthenticationError:
        print(f"IA : clé refusée par {adresse_api()} : vérifiez API_KEY dans .env.")
        return
    except Exception as e:
        print(f"IA : le modèle ne répond pas à {adresse_api()} ({type(e).__name__} : {e}).")
        print("     Vérifiez API_BASE, API_KEY et CA_BUNDLE dans .env ; l'application démarre quand même.")
        return
    if any(m == MODELE or m.split(":")[0] == MODELE for m in modeles):
        print(f"IA : modèle « {MODELE} » prêt ({adresse_api()}).")
    else:
        print(f"IA : le modèle « {MODELE} » n'est pas proposé. Disponibles : {', '.join(modeles) or 'aucun'}.")
        print("     Corrigez AUDIT_ERGO_MODELE dans .env.")


if __name__ == "__main__":
    main()
