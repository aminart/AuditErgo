"""Complétion d'un audit : remplit les cellules vides avec les propositions de l'IA.

Règle d'or : une cellule remplie par le designer n'est JAMAIS modifiée. Ses choix sont évalués à part
(colonnes « IA : … » et commentaires) ; seules les cellules vides reçoivent une proposition, signalée
comme « à valider ».

Les valeurs écrites dans les cellules suivent la langue du fichier (pour rester cohérentes avec ses listes
déroulantes) ; les explications suivent la langue choisie dans l'application.
"""
from .i18n import TYPES, TYPES_RECO, ajouter, libelle_gravite, lire_type, t
from .suggestion import ErreurSuggestion

IA, AUTO = "ia", "auto"  # origine d'une valeur : proposée par l'IA, ou déduite sans IA
# Champs remplis seulement si le fichier a déjà la colonne (on n'ajoute pas ces colonnes à un fichier libre)
SI_COLONNE = {"type", "type_reco"}

ajouter({
    "compl.type": {"fr": "Type par défaut : un constat sans type est considéré comme un problème.",
                   "en": "Default type: a finding without a type is considered an issue."},
    "compl.categorie_designer": {"fr": "Catégorie déduite du critère choisi.",
                                 "en": "Criteria deduced from the chosen sub-criterion."},
    "compl.critere": {"fr": "Critère proposé par l'IA (confiance {confiance}) : {justification}",
                      "en": "Sub-criterion proposed by the AI ({confiance} confidence): {justification}"},
    "compl.categorie": {"fr": "Catégorie du critère proposé par l'IA.", "en": "Criteria of the AI's sub-criterion."},
    "compl.regle": {"fr": "Règle de départage appliquée par l'IA.", "en": "Tie-break rule applied by the AI."},
    "compl.secondaires": {"fr": "Critères secondaires proposés par l'IA.", "en": "Secondary criteria proposed by the AI."},
    "compl.justification": {"fr": "Justification rédigée par l'IA.", "en": "Justification written by the AI."},
    "compl.gravite": {"fr": "Gravité proposée par l'IA : {justification}", "en": "Severity proposed by the AI: {justification}"},
    "compl.recommandation": {"fr": "Recommandation rédigée par l'IA.", "en": "Recommendation written by the AI."},
    "compl.type_reco": {"fr": "Type de recommandation proposé par l'IA.", "en": "Type of recommendation proposed by the AI."},
})


def _vide(valeur):
    return valeur is None or str(valeur).strip() == ""


def completer(audit, ia, ref, langue="fr"):
    """Remplit, dans `audit`, les champs vides à partir des suggestions `ia` ({ligne: Suggestion | erreur}).

    Renvoie {ligne: {champ: (valeur, origine, explication)}} et l'enregistre dans `audit.completions`.
    Les colonnes absentes du fichier (ex. pas de colonne Recommandation) sont ajoutées à `audit.colonnes`
    avec la valeur None : l'export les crée.
    """
    lf = audit.langue  # langue des valeurs écrites dans le fichier
    completions = {}
    for c in audit.constats:
        if _vide(c["constat"]):
            continue
        ajouts = {}

        def remplir(champ, valeur, origine, explication):
            if champ in SI_COLONNE and champ not in audit.colonnes:
                return
            if _vide(c[champ]) and not _vide(valeur):
                ajouts[champ] = (valeur, origine, explication)
                c.valeurs[champ] = valeur

        remplir("type", TYPES["probleme"][lf], AUTO, t("compl.type", langue))
        est_probleme = lire_type(c["type"]) != "point_fort"

        critere_designer = ref.trouver_critere(c["critere"])
        if critere_designer:  # catégorie déduite du critère choisi par le designer : pas besoin de l'IA
            remplir("categorie", ref.libelle_categorie(ref.criteres[critere_designer]["categorie"], lf), AUTO,
                    t("compl.categorie_designer", langue))

        res = ia.get(c.ligne)
        if res is not None and not isinstance(res, ErreurSuggestion):
            if not critere_designer and _vide(c["critere"]):
                remplir("critere", ref.libelle_critere(res.code, lf), IA,
                        t("compl.critere", langue, confiance=t(f"confiance.{res.confiance}", langue),
                          justification=res.justification))
                remplir("categorie", ref.libelle_categorie(ref.criteres[res.code]["categorie"], lf), IA,
                        t("compl.categorie", langue))
                if res.regle != "aucune":
                    remplir("regle", res.regle, IA, t("compl.regle", langue))
                if res.secondaires:
                    remplir("secondaires", " ; ".join(x["code"] for x in res.secondaires), IA,
                            t("compl.secondaires", langue))
            # Justification : seulement pour un critère proposé par l'IA ou un critère du designer qu'elle
            # confirme ; jamais pour un critère qu'elle juge à revoir
            if "critere" in ajouts or (critere_designer and res.verdict == "confirme"
                                       and critere_designer == res.code):
                remplir("justification", res.justification_critere, IA, t("compl.justification", langue))
            if est_probleme and res.gravite is not None:
                remplir("gravite", libelle_gravite(res.gravite, lf), IA,
                        t("compl.gravite", langue, justification=res.justification_gravite))
            if est_probleme and res.reco_proposee:
                remplir("recommandation", res.reco_proposee, IA, t("compl.recommandation", langue))
            if est_probleme and res.type_reco:
                remplir("type_reco", TYPES_RECO[res.type_reco][lf], IA, t("compl.type_reco", langue))

        for champ in ajouts:
            audit.colonnes.setdefault(champ, None)
        if ajouts:
            completions[c.ligne] = ajouts
    audit.completions = completions
    return completions
