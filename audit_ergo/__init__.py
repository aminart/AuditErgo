"""Relecture automatique des audits ergonomiques."""
from pathlib import Path

from .controles import controler
from .export import exporter
from .lecture import ErreurLecture, lire_audit
from .referentiel import Referentiel
from .suggestion import verifier_audit
from .synthese import synthetiser

__all__ = ["relire", "Referentiel", "ErreurLecture"]


def relire(chemin, sortie=None, ref=None, client=None, progression=None, forcer=False):
    """Lit un audit, le contrôle et écrit le fichier annoté.

    Avec un `client` (ClientIA), chaque constat est aussi soumis à l'IA pour vérifier le critère choisi ;
    les constats déjà analysés sont repris du cache local, sauf `forcer=True`.
    Renvoie (audit, anomalies, synthese, sortie, ia) ; `ia` vaut None sans client.
    """
    ref = ref or Referentiel.charger()
    audit = lire_audit(chemin)
    anomalies = controler(audit, ref)
    synthese = synthetiser(audit, anomalies, ref)
    ia = verifier_audit(client, ref, audit, progression, forcer=forcer) if client is not None else None
    if sortie is None:
        p = Path(chemin)
        sortie = p.with_name(f"{p.stem}_relu{p.suffix}")
    exporter(audit, anomalies, synthese, ref, sortie, ia)
    return audit, anomalies, synthese, sortie, ia
