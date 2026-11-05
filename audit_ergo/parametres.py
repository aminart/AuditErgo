"""Paramètres de connexion au modèle : enregistrés depuis l'écran Réglages, ou fournis par le fichier .env.

Même fonctionnement que SpecGen :
- l'écran Réglages enregistre l'adresse, la clé, le modèle et le délai dans le dossier de l'utilisateur
  (%APPDATA%\\AuditErgo sous Windows), avec le certificat importé (ca.crt) ;
- la clé est chiffrée avec le compte Windows (DPAPI) et n'est jamais renvoyée en clair à l'interface ;
- une variable de l'environnement ou du fichier .env est prioritaire, champ par champ (déploiement sur
  plusieurs postes) : API_BASE, API_KEY, CA_BUNDLE, AUDIT_ERGO_MODELE, AUDIT_ERGO_DELAI.

Contrairement à SpecGen, la clé et le certificat sont facultatifs (Ollama ou LM Studio sur le poste n'en
demandent pas) et l'adresse d'Ollama sert par défaut : l'IA fonctionne sans aucune configuration.
Ce module ne lit pas lui-même le fichier .env : suggestion.charger_env() le charge dans l'environnement.
"""
from __future__ import annotations

import base64
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ADRESSE_DEFAUT = "http://localhost:11434/v1"
MODELE_DEFAUT = "mistral-small"
DELAI_DEFAUT = 600.0  # secondes : un modèle local sur CPU peut être lent
NOM_CERTIFICAT = "ca.crt"

# Champ -> variable d'environnement (ou du .env) qui le remplace
VARIABLES = {
    "api_base": "API_BASE",
    "api_key": "API_KEY",
    "ca_bundle": "CA_BUNDLE",
    "model": "AUDIT_ERGO_MODELE",
    "timeout": "AUDIT_ERGO_DELAI",
}


def dossier_config() -> Path:
    """Dossier de l'utilisateur où l'écran Réglages enregistre les paramètres."""
    if autre := os.environ.get("AUDIT_ERGO_CONFIG", "").strip():
        return Path(autre).expanduser()
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "AuditErgo"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "audit-ergo"


def _fichier() -> Path:
    return dossier_config() / "config.json"


def chemin_certificat() -> Path:
    return dossier_config() / NOM_CERTIFICAT


@dataclass
class Parametres:
    api_base: str
    api_key: str
    ca_bundle: str
    model: str
    timeout: float
    depuis_env: list[str] = field(default_factory=list)


# --- Chiffrement de la clé ---------------------------------------------------------------------------

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _dpapi(donnees: bytes, chiffrer: bool) -> bytes:
        tampon = ctypes.create_string_buffer(donnees, len(donnees))
        entree = _Blob(len(donnees), ctypes.cast(tampon, ctypes.POINTER(ctypes.c_char)))
        sortie = _Blob()
        if chiffrer:
            ok = ctypes.windll.crypt32.CryptProtectData(ctypes.byref(entree), "AuditErgo", None, None, None, 0, ctypes.byref(sortie))
        else:
            ok = ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(entree), None, None, None, None, 0, ctypes.byref(sortie))
        if not ok:
            raise ctypes.WinError()
        try:
            return ctypes.string_at(sortie.pbData, sortie.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(sortie.pbData)

    def _chiffrer(valeur: str) -> dict[str, str]:
        return {"scheme": "dpapi", "data": base64.b64encode(_dpapi(valeur.encode("utf-8"), True)).decode("ascii")}

else:
    # Développement sous Linux / macOS : pas de coffre du système branché, la clé est seulement encodée.
    def _chiffrer(valeur: str) -> dict[str, str]:
        return {"scheme": "plain", "data": base64.b64encode(valeur.encode("utf-8")).decode("ascii")}


def _dechiffrer(stocke: dict[str, str] | None) -> str:
    if not stocke:
        return ""
    brut = base64.b64decode(stocke["data"])
    if stocke.get("scheme") == "dpapi":
        if sys.platform != "win32":
            return ""
        return _dpapi(brut, False).decode("utf-8")
    return brut.decode("utf-8")


# --- Paramètres enregistrés --------------------------------------------------------------------------

def enregistres() -> dict[str, Any]:
    try:
        return json.loads(_fichier().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _ecrire(donnees: dict[str, Any]) -> None:
    dossier_config().mkdir(parents=True, exist_ok=True)
    _fichier().write_text(json.dumps(donnees, ensure_ascii=False, indent=2), encoding="utf-8")


def cle_enregistree() -> str:
    try:
        return _dechiffrer(enregistres().get("api_key"))
    except OSError:
        return ""  # chiffrée par un autre compte Windows : considérée comme absente


def enregistrer(api_base: str, api_key: str | None, model: str, timeout: float) -> None:
    """`api_key` None garde la clé enregistrée ; une chaîne vide l'efface."""
    donnees = enregistres()
    donnees.update({"api_base": api_base.strip(), "model": model.strip() or MODELE_DEFAUT, "timeout": timeout})
    if api_key is not None:
        donnees["api_key"] = _chiffrer(api_key.strip()) if api_key.strip() else None
    _ecrire(donnees)


def enregistrer_test(resultat: dict[str, Any]) -> None:
    donnees = enregistres()
    donnees["last_test"] = resultat
    _ecrire(donnees)


def effacer() -> None:
    for chemin in (_fichier(), chemin_certificat()):
        chemin.unlink(missing_ok=True)


def importer_certificat(nom: str, contenu: bytes) -> dict[str, Any]:
    """Vérifie un .crt (PEM ou DER, éventuellement une chaîne) et l'enregistre au format PEM."""
    from cryptography import x509
    from cryptography.hazmat.primitives.serialization import Encoding

    try:
        certificats = x509.load_pem_x509_certificates(contenu)
    except ValueError:
        try:
            certificats = [x509.load_der_x509_certificate(contenu)]
        except ValueError as e:
            raise ValueError("Ce fichier n'est pas un certificat valide (.crt au format PEM ou DER attendu).") from e
    dossier_config().mkdir(parents=True, exist_ok=True)
    chemin_certificat().write_bytes(b"".join(c.public_bytes(Encoding.PEM) for c in certificats))
    infos = {
        "name": nom,
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": min(c.not_valid_after_utc for c in certificats).isoformat(),
    }
    donnees = enregistres()
    donnees["certificate"] = infos
    donnees.pop("last_test", None)
    _ecrire(donnees)
    return infos


# --- Paramètres effectifs : environnement / .env d'abord, puis l'écran Réglages ------------------------

def _env(champ: str) -> str:
    return os.environ.get(VARIABLES[champ], "").strip()


def effectifs() -> Parametres:
    donnees = enregistres()
    depuis_env = [champ for champ in VARIABLES if _env(champ)]
    certificat = str(chemin_certificat()) if donnees.get("certificate") and chemin_certificat().is_file() else ""
    delai = _env("timeout") or donnees.get("timeout")
    try:
        delai = float(delai) if delai else DELAI_DEFAUT
    except ValueError:
        delai = DELAI_DEFAUT
    return Parametres(
        api_base=_env("api_base") or donnees.get("api_base") or ADRESSE_DEFAUT,
        api_key=_env("api_key") or cle_enregistree(),
        ca_bundle=_env("ca_bundle") or certificat,
        model=_env("model") or donnees.get("model") or MODELE_DEFAUT,
        timeout=delai,
        depuis_env=depuis_env,
    )


def publics(chemin_env: Path | None = None) -> dict[str, Any]:
    """Ce que l'écran Réglages peut afficher : jamais la clé elle-même."""
    donnees = enregistres()
    p = effectifs()
    if "ca_bundle" in p.depuis_env:
        certificat = {"name": Path(p.ca_bundle).name}
    else:
        certificat = donnees.get("certificate") if p.ca_bundle else None
    return {
        # Rien d'enregistré ni de fourni par le .env : l'IA tourne sur les valeurs par défaut (Ollama local)
        "saved": bool(donnees.get("api_base")) or bool(p.depuis_env),
        "env_fields": p.depuis_env,
        "env_file": str(chemin_env) if chemin_env and chemin_env.is_file() else None,
        "storage_dir": str(dossier_config()),
        "api_base": p.api_base,
        "default_api_base": ADRESSE_DEFAUT,
        "has_api_key": bool(p.api_key),
        "api_key_hint": p.api_key[-4:] if len(p.api_key) >= 8 else "",
        "certificate": certificat,
        "model": p.model,
        "timeout": p.timeout,
        "last_test": donnees.get("last_test"),
    }
