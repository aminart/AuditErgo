"""Vue d'ensemble de l'audit : couverture du référentiel, gravités, conformité."""
from collections import Counter
from dataclasses import dataclass

from .controles import AVERTISSEMENT, BLOQUANT
from .i18n import GRAVITES, lire_gravite, lire_type

RECOMMANDES = ["parcours", "tache", "capture", "type_reco"]  # champs facultatifs du template


@dataclass
class Synthese:
    nb_constats: int
    nb_problemes: int
    nb_points_forts: int
    gravites: dict  # niveau (1 à 4) -> nombre de problèmes
    par_critere: dict  # code -> nombre de constats (critère principal)
    secondaires: dict  # code -> nombre de mentions en critère secondaire
    non_couverts: list  # codes jamais cités
    categories_non_couvertes: list
    conformes: int  # constats sans aucune anomalie bloquante
    sans_remarque: int  # constats sans aucune anomalie
    completude_recommandee: float  # part des champs recommandés remplis
    nb_bloquants: int
    nb_avertissements: int

    @property
    def pret(self):
        return self.nb_bloquants == 0


def synthetiser(audit, anomalies, ref):
    constats = audit.constats
    problemes = [c for c in constats if lire_type(c["type"]) != "point_fort"]
    par_critere = Counter(code for c in constats if (code := ref.trouver_critere(c["critere"])))
    secondaires = Counter(code for c in constats for code in ref.codes_mentionnes(c["secondaires"])[0])
    cites = set(par_critere) | set(secondaires)
    gravites = Counter(g for c in problemes if (g := lire_gravite(c["gravite"])) is not None)

    lignes_bloquees = {a.ligne for a in anomalies if a.niveau == BLOQUANT and a.ligne}
    lignes_remarques = {a.ligne for a in anomalies if a.ligne}
    remplis = sum(1 for c in constats for champ in RECOMMANDES if c[champ] not in (None, ""))

    return Synthese(
        nb_constats=len(constats),
        nb_problemes=len(problemes),
        nb_points_forts=len(constats) - len(problemes),
        gravites={g: gravites.get(g, 0) for g in GRAVITES},
        par_critere=dict(sorted(par_critere.items())),
        secondaires=dict(sorted(secondaires.items())),
        non_couverts=[code for code in ref.criteres if code not in cites],
        categories_non_couvertes=[cat for cat in ref.categories
                                  if not any(ref.criteres[c]["categorie"] == cat for c in cites)],
        conformes=sum(1 for c in constats if c.ligne not in lignes_bloquees),
        sans_remarque=sum(1 for c in constats if c.ligne not in lignes_remarques),
        completude_recommandee=remplis / (len(constats) * len(RECOMMANDES)) if constats else 0.0,
        nb_bloquants=sum(1 for a in anomalies if a.niveau == BLOQUANT),
        nb_avertissements=sum(1 for a in anomalies if a.niveau == AVERTISSEMENT),
    )
