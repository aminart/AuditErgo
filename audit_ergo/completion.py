"""Complétion d'un audit : remplit les cellules vides avec les propositions de l'IA.

Règle d'or : une cellule remplie par le designer n'est JAMAIS modifiée. Ses choix sont évalués à part
(colonnes « IA : … » et commentaires) ; seules les cellules vides reçoivent une proposition, signalée
comme « à valider ».
"""
from .referentiel import normaliser
from .suggestion import ErreurSuggestion

IA, AUTO = "ia", "auto"  # origine d'une valeur : proposée par l'IA, ou déduite sans IA


def _vide(valeur):
    return valeur is None or str(valeur).strip() == ""


def completer(audit, ia, ref):
    """Remplit, dans `audit`, les champs vides à partir des suggestions `ia` ({ligne: Suggestion | erreur}).

    Renvoie {ligne: {champ: (valeur, origine, explication)}} et l'enregistre dans `audit.completions`.
    Les colonnes absentes du fichier (ex. pas de colonne Recommandation) sont ajoutées à `audit.colonnes`
    avec la valeur None : l'export les crée.
    """
    completions = {}
    for c in audit.constats:
        if _vide(c["constat"]):
            continue
        ajouts = {}

        def remplir(champ, valeur, origine, explication):
            if _vide(c[champ]) and not _vide(valeur):
                ajouts[champ] = (valeur, origine, explication)
                c.valeurs[champ] = valeur

        remplir("type", "Problème", AUTO, "Type par défaut : un constat sans type est considéré comme un problème.")
        est_probleme = normaliser(c["type"] or "") != "point fort"

        critere_designer = ref.trouver_critere(c["critere"])
        if critere_designer:  # catégorie déduite du critère choisi par le designer : pas besoin de l'IA
            remplir("categorie", ref.libelle_categorie(ref.criteres[critere_designer]["categorie"]), AUTO,
                    "Catégorie déduite du critère choisi.")

        res = ia.get(c.ligne)
        if res is not None and not isinstance(res, ErreurSuggestion):
            if not critere_designer and _vide(c["critere"]):
                remplir("critere", ref.libelle_critere(res.code), IA,
                        f"Critère proposé par l'IA (confiance {res.confiance}) : {res.justification}")
                remplir("categorie", ref.libelle_categorie(ref.criteres[res.code]["categorie"]), IA,
                        "Catégorie du critère proposé par l'IA.")
                if res.regle != "aucune":
                    remplir("regle", res.regle, IA, "Règle de départage appliquée par l'IA.")
                if res.secondaires:
                    remplir("secondaires", " ; ".join(x["code"] for x in res.secondaires), IA,
                            "Critères secondaires proposés par l'IA.")
            if res.gravite is not None:
                remplir("gravite", res.gravite, IA, f"Gravité proposée par l'IA : {res.justification_gravite}")
            if est_probleme and res.reco_proposee:
                remplir("recommandation", res.reco_proposee, IA, "Recommandation rédigée par l'IA.")

        for champ in ajouts:
            audit.colonnes.setdefault(champ, None)
        if ajouts:
            completions[c.ligne] = ajouts
    audit.completions = completions
    return completions
