"""Lecture d'un audit Excel rempli par un designer.

La lecture est tolérante : l'onglet et la ligne d'en-tête sont recherchés, et les colonnes sont reconnues
par leur nom même si le designer les a déplacées ou légèrement renommées.
"""
from dataclasses import dataclass, field

from openpyxl import load_workbook

from .referentiel import normaliser

# Champ interne -> noms de colonnes acceptés (comparés après normalisation), en français, en anglais et
# tels qu'ils figurent dans le template d'origine (« Heuristic_Evaluation_template.xlsx »)
COLONNES = {
    "id": ["id", "identifiant", "n", "numero"],
    "ecran": ["ecran page", "ecran", "page", "ecran vue", "ecran emplacement", "emplacement", "location",
              "screen", "screen location", "screen page"],
    "parcours": ["parcours tache", "parcours", "parcours cas d usage", "cas d usage", "workflow use cases",
                 "workflow use case", "workflow", "use case", "use cases"],
    "tache": ["tache", "taches", "task", "tasks"],
    "date": ["date"],
    "capture": ["capture", "capture fichier ou lien", "captures", "screenshot", "screenshots"],
    "type": ["type", "type de constat", "finding type"],
    "constat": ["constat", "description", "probleme", "observation", "finding", "issue", "findings"],
    "categorie": ["categorie", "criteria", "category", "criteria category"],
    "critere": ["critere principal", "critere", "critere ergonomique", "sub criteria", "sub criterion",
                "subcriteria", "subcriterion", "main criterion"],
    "secondaires": ["criteres secondaires", "criteres secondaires codes separes par", "secondary criteria"],
    "regle": ["regle de departage", "regle", "tie break rule", "rule"],
    "justification": ["justification du critere", "justification", "justification critere", "pourquoi ce critere",
                      "criterion justification", "rationale"],
    "gravite": ["gravite", "gravite 0 4", "severite", "severity"],
    "frequence": ["frequence", "frequency"],
    "impact": ["impact"],
    "type_reco": ["type de recommandation", "type of ux recommendation", "type of recommendation",
                  "recommendation type"],
    "recommandation": ["recommandation", "recommandation si probleme", "recommandations", "preconisation",
                       "detail of ux recommendation", "ux recommendation", "recommendation", "recommendations"],
    "priorite": ["priorite", "priority"],
    "statut_maquette": ["statut maquette", "mock up solution status", "mock up status", "mockup status"],
    "statut": ["statut", "status"],
    "controle": ["controle", "check"],
}
# Le type est facultatif : sans colonne Type (template d'origine), un constat est un problème
OBLIGATOIRES = ["ecran", "constat", "categorie", "critere", "gravite", "recommandation"]
LIBELLES = {
    "ecran": ("Écran / Emplacement", "Screen / Location"), "parcours": ("Parcours / Cas d'usage", "Workflow / Use case"),
    "tache": ("Tâche", "Task"), "date": ("Date", "Date"), "capture": ("Capture", "Screenshot"), "type": ("Type", "Type"),
    "constat": ("Constat", "Finding"), "categorie": ("Catégorie", "Criteria"),
    "critere": ("Critère principal", "Sub-criterion"), "secondaires": ("Critères secondaires", "Secondary criteria"),
    "regle": ("Règle de départage", "Tie-break rule"), "justification": ("Justification du critère", "Criterion justification"),
    "gravite": ("Gravité", "Severity"), "frequence": ("Fréquence", "Frequency"), "impact": ("Impact", "Impact"),
    "type_reco": ("Type de recommandation", "Type of UX recommendation"),
    "recommandation": ("Recommandation", "Detail of UX recommendation"), "priorite": ("Priorité", "Priority"),
    "statut_maquette": ("Statut maquette", "Mock-up status"), "statut": ("Statut", "Status"),
    "controle": ("Contrôle", "Check"),
}


def libelle_champ(champ, langue="fr"):
    paire = LIBELLES.get(champ)
    return (paire[1] if langue == "en" else paire[0]) if paire else champ


CHAMPS_CONTEXTE = {
    "produit": ["produit interface auditee", "audited product interface"],
    "version_produit": ["version url ou build", "version url or build"],
    "client": ["client equipe", "client team"],
    "cible": ["cible utilisateurs", "target users"],
    "plateforme": ["plateforme", "platform"],
    "contexte_usage": ["contexte d usage", "context of use"],
    "parcours": ["parcours audites", "audited journeys"],
    "designer": ["designer"],
    "date": ["date de l audit", "audit date"],
    "langue": ["langue", "language"],
    "version_template": ["version du template", "template version"],
    "version_referentiel": ["version du referentiel", "referential version"],
}
CONTEXTE_OBLIGATOIRE = ["produit", "cible", "plateforme", "parcours", "designer", "date"]


# En-têtes propres à l'anglais : servent à deviner la langue d'un fichier sans onglet Contexte
ENTETES_ANGLAIS = {"severity", "sub criteria", "sub criterion", "finding", "location", "screen location",
                   "detail of ux recommendation", "criteria", "workflow use cases", "workflow use case", "tasks",
                   "task", "tie break rule", "criterion justification", "secondary criteria", "mock up solution status"}


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
        return self["id"] or f"#{self.ligne}"


@dataclass
class Audit:
    chemin: str
    onglet: str
    ligne_entete: int
    colonnes: dict  # champ -> numéro de colonne
    constats: list
    contexte: dict = field(default_factory=dict)
    colonnes_inconnues: list = field(default_factory=list)
    completions: dict = field(default_factory=dict)  # {ligne: {champ: (valeur, origine, explication)}}
    langue: str = "fr"  # langue du fichier (en-têtes, listes) : les valeurs complétées la suivent

    @property
    def colonnes_manquantes(self):
        return [c for c in OBLIGATOIRES if c not in self.colonnes]


class ErreurLecture(Exception):
    pass


def _trouver_entete(ws, max_lignes=15):
    """(score, ligne) de la ligne d'en-tête : celle qui contient le plus de colonnes reconnues.

    Il en faut au moins trois, ou une colonne « Constat » (un simple tableau de constats suffit :
    l'IA peut compléter le reste). Renvoie (0, None) si aucune ligne ne convient.
    """
    meilleur = (0, None)
    for r in range(1, min(ws.max_row, max_lignes) + 1):
        champs = [nom_colonne(c.value) for c in ws[r] if c.value]
        score = sum(1 for ch in champs if ch) + (2 if "constat" in champs else 0)
        if score > meilleur[0]:
            meilleur = (score, r)
    return meilleur if meilleur[0] >= 3 else (0, None)


def _lire_contexte(wb):
    if "Contexte" not in wb.sheetnames:
        return {}
    ws = wb["Contexte"]
    par_libelle = {variante: k for k, variantes in CHAMPS_CONTEXTE.items() for variante in variantes}
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
    # Onglet « Audit » du template en priorité ; sinon l'onglet dont l'en-tête est le mieux reconnu.
    # Les onglets ajoutés par une relecture précédente (« Relecture – … ») sont ignorés.
    candidats = [n for n in wb.sheetnames if not normaliser(n).startswith(("relecture", "review"))]
    scores = {n: _trouver_entete(wb[n]) for n in candidats}
    nom = "Audit" if scores.get("Audit", (0, None))[1] else max(candidats, key=lambda n: scores[n][0], default=None)
    if nom is None or not scores[nom][1]:
        raise ErreurLecture("Aucun onglet ne contient de ligne d'en-tête reconnaissable (Constat, Critère, Gravité…).")
    ws, entete = wb[nom], scores[nom][1]

    colonnes, inconnues = {}, []
    for cell in ws[entete]:
        if cell.value is None:
            continue
        if normaliser(str(cell.value)).startswith(("relecture", "ia ", "review", "ai ")):
            continue  # colonnes ajoutées par une relecture précédente
        champ = nom_colonne(cell.value)
        if champ and champ not in colonnes:
            colonnes[champ] = cell.column
        elif not champ:
            inconnues.append(str(cell.value))

    # Cellules fusionnées (ex. un même cas d'usage sur plusieurs lignes) : la valeur vaut pour chaque ligne
    fusions = {}
    for plage in ws.merged_cells.ranges:
        if plage.min_row > entete:
            haut_gauche = ws.cell(row=plage.min_row, column=plage.min_col).value
            for r in range(plage.min_row, plage.max_row + 1):
                for col in range(plage.min_col, plage.max_col + 1):
                    fusions[(r, col)] = haut_gauche

    constats = []
    for r in range(entete + 1, ws.max_row + 1):
        propres = {champ: ws.cell(row=r, column=col).value for champ, col in colonnes.items()}
        if str(propres.get("id") or "").strip().upper() in ("EXEMPLE", "EXAMPLE"):
            continue
        # Une ligne n'est un constat que si elle a un contenu propre (pas seulement une cellule fusionnée)
        if not any(v not in (None, "") for k, v in propres.items()
                   if k not in ("id", "controle") and (r, colonnes[k]) not in fusions):
            continue
        valeurs = {champ: fusions.get((r, colonnes[champ]), v) for champ, v in propres.items()}
        constats.append(Constat(ligne=r, valeurs=valeurs))

    contexte = _lire_contexte(wb)
    langue = str(contexte.get("langue") or "").strip().lower()[:2]
    if langue not in ("fr", "en"):
        entetes = {normaliser(str(c.value).split("(")[0].replace("*", "")) for c in ws[entete] if c.value}
        langue = "en" if entetes & ENTETES_ANGLAIS else "fr"
    return Audit(chemin=str(chemin), onglet=ws.title, ligne_entete=entete, colonnes=colonnes,
                 constats=constats, contexte=contexte, colonnes_inconnues=inconnues, langue=langue)
