"""Ligne de commande.

Relire un audit :            python3 -m audit_ergo AUDIT.xlsx [-o SORTIE.xlsx] [--ia] [--json]
Suggérer un critère :        python3 -m audit_ergo --suggerer "texte du constat" [--ecran PAGE] [--critere CODE]
"""
import argparse
import json
import sys
from dataclasses import asdict

from . import ErreurLecture, Referentiel, relire
from .controles import NIVEAUX
from .export import LIBELLE_NIVEAU
from .suggestion import LIBELLE_VERDICT, ErreurSuggestion, client_ou_none, suggerer


def afficher_suggestion(s, ref):
    c = ref.criteres[s.code]
    print(f"Critère proposé : {c['code']} – {c['label_fr']} ({c['name']})  [confiance {s.confiance}]")
    print(f"  {s.justification}")
    if s.regle != "aucune":
        print(f"  Règle de départage : {s.regle}")
    if s.question_checklist:
        print(f"  Checklist : {s.question_checklist}")
    for x in s.secondaires:
        print(f"Secondaire : {x['code']} – {ref.criteres[x['code']]['label_fr']} : {x['justification']}")
    for x in s.alternatives:
        print(f"Écarté : {x['code']} – {ref.criteres[x['code']]['label_fr']} : {x['pourquoi_pas']}")
    if s.critere_designer:
        print(f"Choix du designer ({s.critere_designer}) : {LIBELLE_VERDICT[s.verdict]} – {s.commentaire_verdict}")
    if s.question_a_se_poser:
        print(f"À se demander : {s.question_a_se_poser}")
    for p in s.precisions_manquantes:
        print(f"À préciser : {p}")
    print(f"\nÀ coller dans l'audit : {s.ligne_excel(ref)}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="audit_ergo", description="Relecture automatique d'un audit ergonomique.")
    parser.add_argument("audit", nargs="?", help="fichier Excel rempli par le designer")
    parser.add_argument("-o", "--sortie", help="fichier annoté à produire (défaut : <audit>_relu.xlsx)")
    parser.add_argument("--ia", action="store_true", help="vérifier aussi le critère de chaque constat avec l'IA")
    parser.add_argument("--json", action="store_true", help="afficher le résultat en JSON")
    parser.add_argument("--suggerer", metavar="CONSTAT", help="proposer un critère pour un constat (IA)")
    parser.add_argument("--ecran", help="avec --suggerer : écran ou page concerné")
    parser.add_argument("--critere", help="avec --suggerer : critère choisi par le designer, à vérifier")
    args = parser.parse_args(argv)
    if not args.audit and not args.suggerer:
        parser.error("indiquer un fichier d'audit ou --suggerer \"constat\"")

    ref = Referentiel.charger()
    client = None
    if args.ia or args.suggerer:
        try:
            client = client_ou_none()
        except ErreurSuggestion as e:
            print(f"Erreur : {e}", file=sys.stderr)
            return 2
        if client is None:
            print("Erreur : aucune clé d'API. Renseignez API_KEY dans le fichier .env (voir .env.exemple).",
                  file=sys.stderr)
            return 2

    if args.suggerer:
        critere = ref.trouver_critere(args.critere) if args.critere else None
        if args.critere and not critere:
            print(f"Erreur : critère « {args.critere} » inconnu.", file=sys.stderr)
            return 2
        try:
            s = suggerer(client, ref, args.suggerer, args.ecran, critere)
        except ErreurSuggestion as e:
            print(f"Erreur : {e}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(asdict(s), ensure_ascii=False, indent=2))
        else:
            afficher_suggestion(s, ref)
        return 0

    def progression(fait, total):
        print(f"\rIA : {fait}/{total} constats", end="" if fait < total else "\n", file=sys.stderr)

    try:
        audit, anomalies, synthese, sortie, ia = relire(args.audit, args.sortie, ref, client, progression)
    except (ErreurLecture, FileNotFoundError) as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({
            "synthese": asdict(synthese), "anomalies": [asdict(a) for a in anomalies], "sortie": str(sortie),
            "ia": None if ia is None else {ligne: (str(r) if isinstance(r, ErreurSuggestion) else asdict(r))
                                           for ligne, r in ia.items()},
        }, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"{synthese.nb_constats} constats lus (onglet « {audit.onglet} »)")
        for niveau in NIVEAUX:
            liste = [a for a in anomalies if a.niveau == niveau]
            if liste:
                print(f"\n{LIBELLE_NIVEAU[niveau]} ({len(liste)})")
                for a in liste:
                    lieu = f"ligne {a.ligne} [{a.constat}]" if a.ligne else "fichier"
                    print(f"  - {lieu} : {a.message}")
        if ia is not None:
            revoir = [(lg, r) for lg, r in sorted(ia.items())
                      if not isinstance(r, ErreurSuggestion) and r.verdict in ("a_revoir", "incorrect")]
            erreurs = [lg for lg, r in ia.items() if isinstance(r, ErreurSuggestion)]
            print(f"\nIA : {len(revoir)} critère(s) à revoir" + (f", {len(erreurs)} erreur(s)" if erreurs else ""))
            for lg, r in revoir:
                print(f"  - ligne {lg} : {r.critere_designer} → {r.code} ({LIBELLE_VERDICT[r.verdict]}) : "
                      f"{r.commentaire_verdict}")
        print("\n" + ("✓ Prêt pour la relecture des critères" if synthese.pret
                      else f"⚠ {synthese.nb_bloquants} anomalie(s) bloquante(s) à corriger"))
        print(f"Fichier annoté : {sortie}")
    return 0 if synthese.pret else 1


if __name__ == "__main__":
    sys.exit(main())
