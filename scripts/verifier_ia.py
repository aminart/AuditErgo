"""Vérifie que le modèle répond (utilisé par start.bat ; n'empêche jamais le lancement).

Usage : python scripts/verifier_ia.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from audit_ergo.suggestion import ErreurSuggestion, adresse_api, client_ou_none, modele  # noqa: E402


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
        print(f"IA : le serveur {adresse_api()} répond (modèle « {modele()} »).")
        return
    except openai.AuthenticationError:
        print(f"IA : clé refusée par {adresse_api()} : vérifiez la clé d'API dans Réglages (ou API_KEY dans .env).")
        return
    except Exception as e:
        print(f"IA : le modèle ne répond pas à {adresse_api()} ({type(e).__name__} : {e}).")
        print("     Vérifiez la connexion dans Réglages (ou le .env) ; l'application démarre quand même.")
        return
    if any(m == modele() or m.split(":")[0] == modele() for m in modeles):
        print(f"IA : modèle « {modele()} » prêt ({adresse_api()}).")
    else:
        print(f"IA : le modèle « {modele()} » n'est pas proposé. Disponibles : {', '.join(modeles) or 'aucun'}.")
        print("     Corrigez le modèle dans Réglages (options avancées) ou AUDIT_ERGO_MODELE dans .env.")


if __name__ == "__main__":
    main()
