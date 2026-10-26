"""Lecture d'un audit Excel rempli par un designer.

La lecture est tolérante : l'onglet et la ligne d'en-tête sont recherchés, et les colonnes sont reconnues
par leur nom même si le designer les a déplacées ou légèrement renommées.
"""
from dataclasses import dataclass, field

from openpyxl import load_workbook

from .referentiel import normaliser

# Champ interne -> noms de colonnes acceptés (comparés après normalisation)
COLONNES = {
    "id": ["id", "identifiant", "n", "numero"],
    "ecran": ["ecran page", "ecran", "page", "ecran vue"],
    "parcours": ["parcours tache", "parcours", "tache"],
    "capture": ["capture", "capture fichier ou lien", "captures", "screenshot"],
    "type": ["type", "type de constat"],
    "constat": ["constat", "description", "probleme", "observation"],
    "categorie": ["categorie"],
    "critere": ["critere principal", "critere", "critere ergonomique"],
    "secondaires": ["criteres secondaires", "criteres secondaires codes separes par"],
    "regle": ["regle de departage", "regle"],
    "gravite": ["gravite", "gravite 0 4", "severite"],
    "frequence": ["frequence"],
    "impact": ["impact"],
    "recommandation": ["recommandation", "recommandation si probleme", "recommandations", "preconisation"],
    "priorite": ["priorite"],
    "controle": ["controle"],
}
OBLIGATOIRES = ["ecran", "type", "constat", "categorie", "critere", "gravite", "recommandation"]
LIBELLES = {
    "ecran": "Écran / Page", "parcours": "Parcours / Tâche", "capture": "Capture", "type": "Type",
    "constat": "Constat", "categorie": "Catégorie", "critere": "Critère principal",
    "secondaires": "Critères secondaires", "regle": "Règle de départage", "gravite": "Gravité",
    "frequence": "Fréquence", "impact": "Impact", "recommandation": "Recommandation", "priorite": "Priorité",
}
CHAMPS_CONTEXTE = {
    "produit": "produit interface auditee",
    "version_produit": "version url ou build",
    "client": "client equipe",
    "cible": "cible utilisateurs",
    "plateforme": "plateforme",
    "contexte_usage": "contexte d usage",
    "parcours": "parcours audites",
    "designer": "designer",
    "date": "date de l audit",
    "version_template": "version du template",
    "version_referentiel": "version du referentiel",
}
CONTEXTE_OBLIGATOIRE = ["produit", "cible", "plateforme", "parcours", "designer", "date"]


def nom_colonne(entete):
    """Champ interne correspondant à un en-tête, ou None."""
    n = normaliser(str(entete).replace("*", ""))
    for champ, variantes in COLONNES.items():
        if n in variantes:
            return champ
    # En-tête enrichi (« Gravité (0-4) * ») : on retire le contenu entre parenthèses
    n = normaliser(str(entete).split("(")[0].replace("*", ""))
    for champ, variantes in COLONNES.items():
        if n in variantes:
            return champ
    return None


@dataclass
class Constat:
    ligne: int
    valeurs: dict

    def __getitem__(self, champ):
        v = self.valeurs.get(champ)
        return v.strip() if isinstance(v, str) else v

    @property
    def ref(self):
        return self["id"] or f"ligne {self.ligne}"


@dataclass
class Audit:
    chemin: str
    onglet: str
    ligne_entete: int
    colonnes: dict  # champ -> numéro de colonne
    constats: list
    contexte: dict = field(default_factory=dict)
    colonnes_inconnues: list = field(default_factory=list)

    @property
    def colonnes_manquantes(self):
        return [c for c in OBLIGATOIRES if c not in self.colonnes]


class ErreurLecture(Exception):
    pass


def _trouver_entete(ws, max_lignes=15):
    meilleur = (0, None)
    for r in range(1, min(ws.max_row, max_lignes) + 1):
        trouves = sum(1 for c in ws[r] if c.value and nom_colonne(c.value))
        if trouves > meilleur[0]:
            meilleur = (trouves, r)
    return meilleur[1] if meilleur[0] >= 3 else None


def _lire_contexte(wb):
    if "Contexte" not in wb.sheetnames:
        return {}
    ws = wb["Contexte"]
    par_libelle = {v: k for k, v in CHAMPS_CONTEXTE.items()}
    contexte = {}
    for row in ws.iter_rows(min_col=1, max_col=2):
        libelle, valeur = row[0].value, row[1].value
        champ = par_libelle.get(normaliser(str(libelle or "").replace("*", "")))
        if champ:
            contexte[champ] = valeur.strip() if isinstance(valeur, str) else valeur
    return contexte


def lire_audit(chemin):
    # data_only : on lit les valeurs affichées (l'ID et le Contrôle sont des formules)
    wb = load_workbook(chemin, data_only=True)
    candidats = (["Audit"] if "Audit" in wb.sheetnames else []) + [n for n in wb.sheetnames if n != "Audit"]
    for nom in candidats:
        ws = wb[nom]
        entete = _trouver_entete(ws)
        if entete:
            break
    else:
        raise ErreurLecture("Aucun onglet ne contient de ligne d'en-tête reconnaissable (Constat, Critère, Gravité…).")

    colonnes, inconnues = {}, []
    for cell in ws[entete]:
        if cell.value is None:
            continue
        if normaliser(str(cell.value)).startswith("relecture"):
            continue  # colonnes ajoutées par une relecture précédente
        champ = nom_colonne(cell.value)
        if champ and champ not in colonnes:
            colonnes[champ] = cell.column
        elif not champ:
            inconnues.append(str(cell.value))

    constats = []
    for r in range(entete + 1, ws.max_row + 1):
        valeurs = {champ: ws.cell(row=r, column=col).value for champ, col in colonnes.items()}
        if str(valeurs.get("id") or "").strip().upper() == "EXEMPLE":
            continue
        if not any(v not in (None, "") for k, v in valeurs.items() if k not in ("id", "controle")):
            continue
        constats.append(Constat(ligne=r, valeurs=valeurs))

    return Audit(chemin=str(chemin), onglet=ws.title, ligne_entete=entete, colonnes=colonnes,
                 constats=constats, contexte=_lire_contexte(wb), colonnes_inconnues=inconnues)
