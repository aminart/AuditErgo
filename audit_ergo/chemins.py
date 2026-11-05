"""Emplacements des fichiers, valables depuis les sources ET depuis l'exécutable AuditErgo.exe (PyInstaller).

| Quoi | Depuis les sources | Depuis l'exe |
|---|---|---|
| Ressources en lecture (interface, templates, référentiel, VERSION) | racine du dépôt | dans l'exe |
| Fichier .env facultatif | racine du dépôt | à côté de AuditErgo.exe |
| Données écrites (cache des réponses, historique des audits) | .cache/ et .donnees/ du dépôt | %APPDATA%\\AuditErgo |

Depuis l'exe, le dossier de l'exe peut être en lecture seule (Program Files, partage réseau) : rien n'y est écrit.
"""
import sys
from pathlib import Path

from . import parametres

RACINE_DEPOT = Path(__file__).resolve().parent.parent


def empaquete() -> bool:
    """True quand l'application tourne depuis AuditErgo.exe."""
    return bool(getattr(sys, "frozen", False))


def ressources() -> Path:
    """Fichiers livrés avec l'application, en lecture seule."""
    return Path(getattr(sys, "_MEIPASS")) if empaquete() else RACINE_DEPOT


def dossier_app() -> Path:
    """Dossier que voit l'utilisateur : celui de l'exe, ou la racine du dépôt. Accueille le .env facultatif."""
    return Path(sys.executable).resolve().parent if empaquete() else RACINE_DEPOT


def cache_defaut() -> Path:
    if empaquete():
        return parametres.dossier_config() / "cache" / "suggestions.sqlite"
    return RACINE_DEPOT / ".cache" / "suggestions.sqlite"


def historique_defaut() -> Path:
    if empaquete():
        return parametres.dossier_config() / "audits"
    return RACINE_DEPOT / ".donnees" / "audits"


def version() -> str:
    """Numéro de version : fichier VERSION à la racine (source unique, embarqué dans l'exe)."""
    try:
        return (ressources() / "VERSION").read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"
