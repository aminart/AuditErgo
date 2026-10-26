"""Relecture automatique des audits ergonomiques."""
from pathlib import Path

from .controles import controler
from .export import exporter
from .lecture import ErreurLecture, lire_audit
from .referentiel import Referentiel
from .synthese import synthetiser

__all__ = ["relire", "Referentiel", "ErreurLecture"]


def relire(chemin, sortie=None, ref=None):
    """Lit un audit, le contrôle et écrit le fichier annoté. Renvoie (audit, anomalies, synthese, sortie)."""
    ref = ref or Referentiel.charger()
    audit = lire_audit(chemin)
    anomalies = controler(audit, ref)
    synthese = synthetiser(audit, anomalies, ref)
    if sortie is None:
        p = Path(chemin)
        sortie = p.with_name(f"{p.stem}_relu{p.suffix}")
    exporter(audit, anomalies, synthese, ref, sortie)
    return audit, anomalies, synthese, sortie
