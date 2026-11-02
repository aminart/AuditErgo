"""Historique des audits : chaque audit déposé est enregistré sur ce poste et se rouvre après un redémarrage.

Emplacement : `.donnees/audits/` à la racine de l'application (ignoré par Git), ou le dossier indiqué par
AUDIT_ERGO_HISTORIQUE. AUDIT_ERGO_HISTORIQUE=0 désactive l'enregistrement : les audits sont alors gardés dans
un dossier temporaire, supprimé à l'arrêt de l'application.

Un audit = un dossier : le fichier déposé, le fichier annoté, `etat.pkl` (relecture, avis de l'IA, décisions du
designer, rapport) et `resume.json` (ce qu'affiche la liste, lisible sans ouvrir l'état).
L'état est enregistré avec pickle : il n'est lu que depuis ce dossier, écrit par l'application elle-même.
"""
import atexit
import json
import os
import pickle
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

RACINE_DEFAUT = Path(__file__).resolve().parent.parent / ".donnees" / "audits"
DESACTIVE = {"0", "non", "false", "off"}
VERSION = 1
CHAMPS = ["nom", "langue", "audit", "anomalies", "synthese", "ia", "nom_sortie", "rapport", "rapport_perime", "cree"]


def maintenant():
    return datetime.now().isoformat(timespec="seconds")


class Historique:
    def __init__(self, racine=None, persistant=True):
        if not persistant:
            racine = Path(tempfile.mkdtemp(prefix="audit_ergo_"))
            atexit.register(shutil.rmtree, racine, ignore_errors=True)
        self.racine = Path(racine or RACINE_DEFAUT)
        self.persistant = persistant

    @classmethod
    def defaut(cls):
        valeur = os.environ.get("AUDIT_ERGO_HISTORIQUE", "").strip()
        if valeur.lower() in DESACTIVE:
            return cls(persistant=False)
        return cls(Path(valeur).expanduser() if valeur else None)

    def dossier(self, id_):
        if not id_.isalnum():  # identifiant produit par l'application (uuid hexadécimal)
            raise KeyError(id_)
        d = self.racine / id_
        d.mkdir(parents=True, exist_ok=True)
        return d

    def enregistrer(self, session, resume):
        d = self.dossier(session.id)
        etat = {"version": VERSION, **{c: getattr(session, c) for c in CHAMPS}}
        temporaire = d / "etat.pkl.tmp"
        temporaire.write_bytes(pickle.dumps(etat))
        temporaire.replace(d / "etat.pkl")  # écriture atomique : un arrêt brutal ne corrompt pas l'état
        (d / "resume.json").write_text(json.dumps({**resume, "id": session.id, "cree": session.cree,
                                                   "modifie": maintenant()}, ensure_ascii=False), encoding="utf-8")

    def charger(self, id_):
        """État enregistré ({champ: valeur}), ou None si l'audit n'existe pas ou est illisible."""
        try:
            chemin = self.racine / id_ / "etat.pkl"
            if not id_.isalnum() or not chemin.exists():
                return None
            etat = pickle.loads(chemin.read_bytes())
            return etat if etat.get("version") == VERSION else None
        except Exception:  # noqa: BLE001 : fichier abîmé, version incompatible…
            return None

    def lister(self):
        """Résumés des audits enregistrés, le plus récemment modifié d'abord."""
        resumes = []
        if not self.racine.exists():
            return resumes
        for d in self.racine.iterdir():
            try:
                resumes.append(json.loads((d / "resume.json").read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        return sorted(resumes, key=lambda r: r.get("modifie", ""), reverse=True)

    def supprimer(self, id_):
        if id_.isalnum():
            shutil.rmtree(self.racine / id_, ignore_errors=True)
