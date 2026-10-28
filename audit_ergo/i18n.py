"""Textes en français et en anglais, échelles et listes communes au template, à l'application et à l'IA.

`t(cle, langue, **valeurs)` renvoie le texte traduit ; une clé absente dans une langue retombe sur le
français, puis sur la clé elle-même (jamais d'erreur à l'affichage).
"""
import os

from .referentiel import normaliser

LANGUES = {"fr": "Français", "en": "English"}


def langue_defaut():
    langue = os.environ.get("AUDIT_ERGO_LANGUE", "fr").strip().lower()[:2]
    return langue if langue in LANGUES else "fr"


# --- Échelle de gravité : celle du template d'origine (4 niveaux) -------------------------------------

GRAVITES = {
    1: {"fr": "Faible", "en": "Low",
        "def_fr": "Problème non critique ou question générale sur le produit.",
        "def_en": "Non-critical problems or general questions about the product."},
    2: {"fr": "Moyenne", "en": "Medium",
        "def_fr": "Problème non critique et limité (pas de perte de données ni de panne) ; un contournement simple "
                  "existe.",
        "def_en": "A non-critical, limited problem (no data lost or system failure); a simple workaround exists."},
    3: {"fr": "Élevée", "en": "High",
        "def_fr": "Problème sérieux qui gêne l'utilisation ou empêche de poursuivre la tâche normalement ; "
                  "le contournement est difficile.",
        "def_en": "A serious condition that impairs the operation, or continued operation; the workaround is "
                  "difficult."},
    4: {"fr": "Critique", "en": "Critical",
        "def_fr": "La tâche ne peut pas être accomplie (blocage, perte de données) : à corriger avant la mise en "
                  "production.",
        "def_en": "The task cannot be completed (blocking, data loss): must be fixed before release."},
}
_ALIAS_GRAVITE = {normaliser(v[l]): g for g, v in GRAVITES.items() for l in ("fr", "en")}
_ALIAS_GRAVITE.update({"elevee": 3, "haute": 3, "critique": 4, "bloquant": 4, "mineur": 2, "majeur": 3,
                       "faible": 1, "basse": 1, "moyen": 2, "eleve": 3})


def lire_gravite(valeur):
    """Niveau 1 à 4 à partir de « 3 », 3, « High », « Élevée », « 3 – Élevée »… ; None si illisible."""
    if valeur is None or str(valeur).strip() == "":
        return None
    if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
        return int(valeur) if float(valeur).is_integer() and 1 <= valeur <= 4 else None
    texte = normaliser(valeur)
    if texte[:1].isdigit():
        n = int(texte.split()[0]) if texte.split()[0].isdigit() else None
        return n if n in GRAVITES else None
    return _ALIAS_GRAVITE.get(texte)


def libelle_gravite(niveau, langue="fr"):
    return GRAVITES[niveau][langue] if niveau in GRAVITES else ""


# --- Listes du template ------------------------------------------------------------------------------

TYPES = {"probleme": {"fr": "Problème", "en": "Issue"}, "point_fort": {"fr": "Point fort", "en": "Strength"}}
_ALIAS_TYPE = {"probleme": "probleme", "issue": "probleme", "problem": "probleme", "point fort": "point_fort",
               "strength": "point_fort", "positive": "point_fort", "good practice": "point_fort"}

TYPES_RECO = {"design": {"fr": "Design", "en": "Design"}, "test": {"fr": "Test utilisateur", "en": "User test"},
              "formation": {"fr": "Formation", "en": "Training"}, "procedure": {"fr": "Procédure", "en": "Procedure"}}
STATUTS_MAQUETTE = {"a_faire": {"fr": "À faire", "en": "To do"}, "a_maquetter": {"fr": "À maquetter", "en": "To mock up"},
                    "maquette": {"fr": "Maquetté", "en": "Mocked up"}, "planifie": {"fr": "Planifié", "en": "Planned"},
                    "implemente": {"fr": "Implémenté", "en": "Implemented"}}


def lire_type(valeur):
    """« probleme », « point_fort » ou None, quelle que soit la langue de saisie."""
    return _ALIAS_TYPE.get(normaliser(valeur or ""))


def lire_type_reco(valeur):
    n = normaliser(valeur or "")
    for cle, v in TYPES_RECO.items():
        if n in (cle, normaliser(v["fr"]), normaliser(v["en"])) or (cle == "test" and n.startswith("test")):
            return cle
    return None


# --- Textes ------------------------------------------------------------------------------------------

TEXTES = {
    # Verdicts de l'IA
    "verdict.confirme": {"fr": "✓ Confirmé", "en": "✓ Confirmed"},
    "verdict.a_revoir": {"fr": "À revoir", "en": "To review"},
    "verdict.incorrect": {"fr": "✗ Incorrect", "en": "✗ Incorrect"},
    "verdict.non_fourni": {"fr": "Non fourni", "en": "Not provided"},
    "reco.bonne": {"fr": "✓ Bonne", "en": "✓ Good"},
    "reco.a_ameliorer": {"fr": "À améliorer", "en": "To improve"},
    "reco.hors_sujet": {"fr": "✗ Hors sujet", "en": "✗ Off topic"},
    "reco.non_fournie": {"fr": "Non fournie", "en": "Not provided"},
    "confiance.haute": {"fr": "haute", "en": "high"},
    "confiance.moyenne": {"fr": "moyenne", "en": "medium"},
    "confiance.faible": {"fr": "faible", "en": "low"},
}


def t(cle, langue="fr", **valeurs):
    entree = TEXTES.get(cle, {})
    texte = entree.get(langue) or entree.get("fr") or cle
    return texte.format(**valeurs) if valeurs else texte


def ajouter(textes):
    """Permet à chaque module de déclarer ses propres textes : ajouter({"cle": {"fr": ..., "en": ...}})."""
    TEXTES.update(textes)
