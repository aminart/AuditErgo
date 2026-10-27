"""Cache local des réponses de l'IA : un constat déjà analysé n'est pas refacturé.

La clé est une empreinte de la requête complète (constat, écran, critère du designer, contexte, modèle,
format, consignes et référentiel). Toute modification du référentiel ou du prompt change donc la clé :
les anciennes réponses ne sont plus utilisées, sans rien avoir à vider.

Emplacement : .cache/suggestions.sqlite à la racine du dépôt, ou le chemin indiqué par AUDIT_ERGO_CACHE.
AUDIT_ERGO_CACHE=0 désactive le cache. Le cache est « au mieux » : une erreur de lecture ou d'écriture
n'empêche jamais l'analyse.
"""
import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

CHEMIN_DEFAUT = Path(__file__).resolve().parent.parent / ".cache" / "suggestions.sqlite"
DESACTIVE = {"0", "non", "false", "off"}


class CacheSuggestions:
    def __init__(self, chemin):
        self.chemin = Path(chemin)
        self._verrou = threading.Lock()

    @classmethod
    def defaut(cls):
        """Cache configuré par AUDIT_ERGO_CACHE, ou None s'il est désactivé."""
        valeur = os.environ.get("AUDIT_ERGO_CACHE", "").strip()
        if valeur.lower() in DESACTIVE:
            return None
        return cls(Path(valeur).expanduser() if valeur else CHEMIN_DEFAUT)

    @staticmethod
    def cle(fmt, requete):
        brut = json.dumps({"format": fmt, "requete": requete}, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(brut.encode("utf-8")).hexdigest()

    def _connexion(self):
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        cx = sqlite3.connect(self.chemin, timeout=10)
        cx.execute("CREATE TABLE IF NOT EXISTS suggestions "
                   "(cle TEXT PRIMARY KEY, contenu TEXT NOT NULL, cree_le TEXT NOT NULL)")
        return cx

    def lire(self, cle):
        try:
            with self._verrou, self._connexion() as cx:
                ligne = cx.execute("SELECT contenu FROM suggestions WHERE cle = ?", (cle,)).fetchone()
            return json.loads(ligne[0]) if ligne else None
        except (sqlite3.Error, OSError, json.JSONDecodeError):
            return None

    def ecrire(self, cle, contenu):
        try:
            with self._verrou, self._connexion() as cx:
                cx.execute("INSERT OR REPLACE INTO suggestions VALUES (?, ?, ?)",
                           (cle, json.dumps(contenu, ensure_ascii=False), datetime.now().isoformat(timespec="seconds")))
        except (sqlite3.Error, OSError):
            pass

    def taille(self):
        if not self.chemin.exists():
            return 0
        try:
            with self._verrou, self._connexion() as cx:
                return cx.execute("SELECT COUNT(*) FROM suggestions").fetchone()[0]
        except (sqlite3.Error, OSError):
            return 0

    def vider(self):
        """Supprime toutes les réponses mémorisées ; renvoie leur nombre."""
        n = self.taille()
        try:
            with self._verrou, self._connexion() as cx:
                cx.execute("DELETE FROM suggestions")
        except (sqlite3.Error, OSError):
            return 0
        return n
