"""Conversion des objets de `audit_ergo` en JSON pour l'interface : libellés résolus dans la langue choisie."""
from dataclasses import asdict
from datetime import date, datetime

from audit_ergo.i18n import GRAVITES, TYPES_RECO, libelle_gravite, lire_gravite, t
from audit_ergo.lecture import LIBELLES, libelle_champ
from audit_ergo.rapport import EFFORTS, HORIZONS, IMPACTS, L, MATURITES, MODELE
from audit_ergo.suggestion import ErreurSuggestion, libelle_reco, libelle_verdict


def valeur(v):
    """Valeur de cellule lisible en JSON : dates au format jj/mm/aaaa, nombres entiers sans « .0 »."""
    if isinstance(v, (datetime, date)):
        return v.strftime("%d/%m/%Y")
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    return str(v)


# --- Référentiel -------------------------------------------------------------------------------------

def critere(ref, code, lg):
    c = ref.criteres[code]
    return {"code": code, "libelle": ref.libelle_critere(code, lg), "nom": c["name"], "nom_fr": c["label_fr"],
            "categorie": c["categorie"], "definition": c.get("definition", ""),
            "checklist": [q["q"] for q in c.get("checklist", [])]}


def referentiel(ref, lg):
    return {
        "version": ref.version,
        "categories": [{"code": code, "libelle": ref.libelle_categorie(code, lg), "definition": c.get("definition", "")}
                       for code, c in ref.categories.items()],
        "criteres": [critere(ref, code, lg) for code in ref.criteres],
        "nb_regles": len(ref.regles),
        "gravites": [{"niveau": g, "libelle": v[lg], "definition": v[f"def_{lg}"]} for g, v in GRAVITES.items()],
        "types_reco": [{"cle": k, "libelle": v[lg]} for k, v in TYPES_RECO.items()],
        "champs": {champ: libelle_champ(champ, lg) for champ in LIBELLES},
    }


# --- Suggestion de l'IA ------------------------------------------------------------------------------

def suggestion(s, ref, lg):
    if isinstance(s, ErreurSuggestion):
        return {"erreur": str(s)}
    d = asdict(s)
    d.pop("usage", None)
    d.update({
        "critere": critere(ref, s.code, lg),
        "categorie_libelle": ref.libelle_categorie(ref.criteres[s.code]["categorie"], lg),
        "secondaires": [{**v, "libelle": ref.libelle_critere(v["code"], lg)} for v in s.secondaires],
        "alternatives": [{**v, "libelle": ref.libelle_critere(v["code"], lg)} for v in s.alternatives],
        "confiance_libelle": t(f"confiance.{s.confiance}", lg),
        "verdict_libelle": libelle_verdict(s.verdict, lg).lstrip("✓✗ "),
        "reco_statut_libelle": libelle_reco(s.reco_statut, lg).lstrip("✓✗ "),
        "gravite_libelle": libelle_gravite(s.gravite, lg) if s.gravite else "",
        "type_reco_libelle": TYPES_RECO[s.type_reco][lg] if s.type_reco else "",
        "critere_designer_libelle": ref.libelle_critere(s.critere_designer, lg) if s.critere_designer else "",
        "ligne_excel": s.ligne_excel(ref, lg),
        "justification_critere": s.justification_critere,
        "reco_a_retenir": s.reco_a_retenir,
    })
    return d


# --- Audit relu --------------------------------------------------------------------------------------

def anomalie(a):
    return {"niveau": a.niveau, "code": a.code, "message": a.message, "ligne": a.ligne, "constat": a.constat,
            "champ": a.champ}


def etat_audit(session, ref):
    """Tout ce que l'interface affiche pour un audit relu."""
    audit, lg, ia = session.audit, session.langue, session.ia
    par_ligne = {}
    for a in session.anomalies:
        if a.ligne:
            par_ligne.setdefault(a.ligne, []).append(anomalie(a))
    constats = []
    for c in audit.constats:
        completes = audit.completions.get(c.ligne, {})
        constats.append({
            "ligne": c.ligne, "ref": str(c.ref),
            "valeurs": {champ: valeur(v) for champ, v in c.valeurs.items()},
            "gravite": lire_gravite(c["gravite"]),
            "critere_code": ref.trouver_critere(c["critere"]),
            "completions": {champ: {"valeur": valeur(v), "origine": origine, "explication": explication}
                            for champ, (v, origine, explication) in completes.items()},
            "anomalies": par_ligne.get(c.ligne, []),
            "ia": suggestion(ia[c.ligne], ref, lg) if ia and c.ligne in ia else None,
        })
    s = session.synthese
    ok = [r for r in (ia or {}).values() if not isinstance(r, ErreurSuggestion)]
    return {
        "id": session.id, "nom": session.nom, "nom_sortie": session.nom_sortie, "langue": lg,
        "audit": {"onglet": audit.onglet, "ligne_entete": audit.ligne_entete, "langue_fichier": audit.langue,
                  "colonnes_reconnues": list(audit.colonnes), "colonnes_ignorees": audit.colonnes_inconnues,
                  "colonnes_manquantes": audit.colonnes_manquantes,
                  "contexte": {k: valeur(v) for k, v in audit.contexte.items()}},
        "constats": constats,
        "anomalies": [anomalie(a) for a in session.anomalies],
        "synthese": {**asdict(s), "pret": s.pret, "gravites": {str(k): v for k, v in s.gravites.items()}},
        "ia": None if ia is None else {
            "analyses": len(ok), "erreurs": len(ia) - len(ok),
            "depuis_cache": sum(1 for r in ok if r.depuis_cache),
            "criteres_a_revoir": sum(1 for r in ok if r.verdict in ("a_revoir", "incorrect")),
            "recos_a_ameliorer": sum(1 for r in ok if r.reco_statut in ("a_ameliorer", "hors_sujet")),
        },
        "nb_completions": sum(len(a) for a in audit.completions.values()),
        "a_valider": sum(1 for a in audit.completions.values() for (_, o, _) in a.values() if o != "valide"),
        "rapport": "aucun" if session.rapport is None else "perime" if session.rapport_perime else "a_jour",
        "cree": session.cree,
    }


# --- Rapport de synthèse -----------------------------------------------------------------------------

def _probleme(p, ref, lg):
    return {"cle": p.cle, "ref": p.ref, "ecran": p.ecran, "constat": p.constat, "critere": p.critere,
            "critere_libelle": ref.libelle_critere(p.critere, lg) if p.critere else "",
            "gravite": p.gravite, "recommandation": p.recommandation,
            "type_reco": TYPES_RECO[p.type_reco][lg] if p.type_reco else ""}


def _theme(th, ref, lg):
    return {"titre": th.titre, "description": th.description, "pourquoi": th.pourquoi,
            "consequences": th.consequences, "problemes": [p.cle for p in th.problemes], "ecrans": th.ecrans,
            "gravite_max": th.gravite_max, "poids": th.poids, "recurrent": th.recurrent,
            "criteres": [{"code": c, "libelle": ref.libelle_critere(c, lg)} for c in th.criteres]}


def rapport(r, ref):
    lg, f = r.langue, r.faits
    gravites = {str(k): v for k, v in f.gravites.items() if k is not None}
    if f.gravites.get(None):
        gravites["aucune"] = f.gravites[None]
    return {
        "langue": lg, "ia": r.ia, "erreur": r.erreur, "modele": MODELE, "modifie": getattr(r, "modifie", False),
        "libelles": {cle: (en if lg == "en" else fr) for cle, (fr, en) in L.items()},
        "maturites": [{"niveau": n, "libelle": m[lg], "definition": m[f"def_{lg}"]} for n, m in MATURITES.items()],
        "gravites": [{"niveau": g, "libelle": v[lg], "definition": v[f"def_{lg}"]} for g, v in GRAVITES.items()],
        "impacts": IMPACTS, "efforts": EFFORTS, "horizons": HORIZONS,
        "faits": {
            "contexte": {k: valeur(v) for k, v in f.contexte.items() if valeur(v) not in (None, "")},
            "problemes": [_probleme(p, ref, lg) for p in f.problemes],
            "points_forts": [{"ref": str(a), "ecran": e, "constat": c} for a, e, c in f.points_forts],
            "gravites": gravites, "ecrans": f.ecrans, "graves": f.graves,
            "version_referentiel": f.version_referentiel, "maturite_indicative": f.maturite_indicative,
        },
        "resume": r.resume, "maturite": r.maturite, "maturite_justification": r.maturite_justification,
        "points_forts": r.points_forts, "faiblesses": r.faiblesses, "recurrents": r.recurrents, "impact": r.impact,
        "themes": [_theme(th, ref, lg) for th in r.themes],
        "cas_isoles": [r.themes.index(th) for th in r.cas_isoles],
        "recommandations": [{"titre": c.titre, "objectif": c.objectif, "importance": c.importance,
                             "benefices": c.benefices, "problemes_resolus": c.problemes_resolus,
                             "themes": [r.themes.index(th) for th in c.themes if th in r.themes],
                             "nb_problemes": sum(len(th.problemes) for th in c.themes),
                             "impact": c.impact, "effort": c.effort, "pistes": c.pistes}
                            for c in r.recommandations],
        "quick_wins": [{"titre": q.titre, "description": q.description, "valeur": q.valeur,
                        "problemes": [p.cle for p in q.problemes]} for q in r.quick_wins],
        "quick_wins_candidats": r.quick_wins_candidats,
        "suites": [{"titre": s.titre, "horizon": s.horizon, "description": s.description} for s in r.suites],
        "demarche": r.demarche,
    }
