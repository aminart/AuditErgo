"""Ligne de commande : python3 -m audit_ergo AUDIT.xlsx [-o SORTIE.xlsx] [--json]"""
import argparse
import json
import sys
from dataclasses import asdict

from . import ErreurLecture, relire
from .controles import NIVEAUX
from .export import LIBELLE_NIVEAU


def main(argv=None):
    parser = argparse.ArgumentParser(prog="audit_ergo", description="Relecture automatique d'un audit ergonomique.")
    parser.add_argument("audit", help="fichier Excel rempli par le designer")
    parser.add_argument("-o", "--sortie", help="fichier annoté à produire (défaut : <audit>_relu.xlsx)")
    parser.add_argument("--json", action="store_true", help="afficher le résultat en JSON")
    args = parser.parse_args(argv)

    try:
        audit, anomalies, synthese, sortie = relire(args.audit, args.sortie)
    except (ErreurLecture, FileNotFoundError) as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"synthese": asdict(synthese), "anomalies": [asdict(a) for a in anomalies],
                          "sortie": str(sortie)}, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"{synthese.nb_constats} constats lus (onglet « {audit.onglet} »)")
        for niveau in NIVEAUX:
            liste = [a for a in anomalies if a.niveau == niveau]
            if liste:
                print(f"\n{LIBELLE_NIVEAU[niveau]} ({len(liste)})")
                for a in liste:
                    lieu = f"ligne {a.ligne} [{a.constat}]" if a.ligne else "fichier"
                    print(f"  - {lieu} : {a.message}")
        print("\n" + ("✓ Prêt pour la relecture des critères" if synthese.pret
                      else f"⚠ {synthese.nb_bloquants} anomalie(s) bloquante(s) à corriger"))
        print(f"Fichier annoté : {sortie}")
    return 0 if synthese.pret else 1


if __name__ == "__main__":
    sys.exit(main())
