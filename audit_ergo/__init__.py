"""Relecture automatique des audits ergonomiques et rapport Word de synthèse."""
from pathlib import Path

from .completion import completer
from .controles import controler
from .export import exporter
from .i18n import langue_defaut
from .lecture import ErreurLecture, lire_audit
from .rapport import generer_rapport
from .referentiel import Referentiel
from .suggestion import verifier_audit
from .synthese import synthetiser

__all__ = ["relire", "generer_rapport", "Referentiel", "ErreurLecture"]


def relire(chemin, sortie=None, ref=None, client=None, progression=None, forcer=False, remplir=True, langue=None):
    """Lit un audit, le contrôle et écrit le fichier annoté.

    Avec un `client` (modèle local), chaque constat est aussi soumis à l'IA : elle vérifie le critère, la
    recommandation et la gravité du designer, et (si `remplir`) complète les cellules vides avec ses
    propositions, sans jamais modifier une cellule déjà remplie. Les constats déjà analysés sont repris
    du cache local, sauf `forcer=True`. Messages, annotations et textes de l'IA sont rédigés dans `langue`.
    Renvoie (audit, anomalies, synthese, sortie, ia) ; `ia` vaut None sans client.
    """
    ref = ref or Referentiel.charger()
    langue = langue or langue_defaut()
    audit = lire_audit(chemin)
    ia = verifier_audit(client, ref, audit, progression, forcer=forcer, langue=langue) if client is not None else None
    if ia is not None and remplir:
        completer(audit, ia, ref, langue)  # avant les contrôles : ils portent sur l'audit complété
    anomalies = controler(audit, ref, langue)
    synthese = synthetiser(audit, anomalies, ref)
    if sortie is None:
        p = Path(chemin)
        sortie = p.with_name(f"{p.stem}_relu{p.suffix}")
    exporter(audit, anomalies, synthese, ref, sortie, ia, langue)
    return audit, anomalies, synthese, sortie, ia
