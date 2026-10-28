"""Génère le template Excel des designers, en français et en anglais, à partir de referentiel/referentiel.json.

Usage : python3 scripts/build_template.py  (depuis le dossier du dépôt)
Sorties : template/Audit_ergonomique_FR.xlsx et template/Ergonomic_audit_EN.xlsx

Version 2 : reprend le template d'origine (Heuristic_Evaluation_template.xlsx) — ses colonnes de suivi
(cas d'usage, tâche, type de recommandation, statut maquette, statut), son échelle de gravité à 4 niveaux
et son onglet de résultats — en corrigeant ses défauts, et y ajoute les colonnes du standard commun.
"""
import json
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from audit_ergo.i18n import GRAVITES, STATUTS_MAQUETTE, TYPES, TYPES_RECO  # noqa: E402
from audit_ergo.referentiel import Referentiel  # noqa: E402

SORTIES = {"fr": ROOT / "template" / "Audit_ergonomique_FR.xlsx", "en": ROOT / "template" / "Ergonomic_audit_EN.xlsx"}
TEMPLATE_VERSION = "2.0"
N_ROWS = 300  # lignes de constats préparées
HEADER_ROW, EXAMPLE_ROW, FIRST_ROW = 3, 4, 5
LAST_ROW = FIRST_ROW + N_ROWS - 1

FONT = "Arial"
NAVY = "1F3864"
INPUT_FILL = PatternFill("solid", fgColor="FFF9E5")
AUTO_FILL = PatternFill("solid", fgColor="EDEDED")
HEADER_FILL = PatternFill("solid", fgColor=NAVY)
OPTIONAL_HEADER_FILL = PatternFill("solid", fgColor="5B7DB1")
SUIVI_HEADER_FILL = PatternFill("solid", fgColor="7F7F7F")
EXAMPLE_FONT = Font(name=FONT, size=10, italic=True, color="7F7F7F")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
COULEURS_GRAVITE = {1: "C6EFCE", 2: "FFE699", 3: "F4B183", 4: "FF7C80"}
PLATEFORMES = {"fr": ["Web desktop", "Web responsive / mobile", "Application mobile", "Logiciel métier", "Borne / autre"],
               "en": ["Desktop web", "Responsive / mobile web", "Mobile app", "Business software", "Kiosk / other"]}

# (champ, en-tête fr, en-tête en, largeur, rôle) ; rôle : "obligatoire", "conseille", "suivi" ou "auto"
COLONNES = [
    ("id", "ID", "ID", 9, "auto"),
    ("parcours", "Parcours / Cas d'usage", "Workflow / Use case", 18, "conseille"),
    ("tache", "Tâche", "Task", 16, "conseille"),
    ("ecran", "Écran / Emplacement *", "Screen / Location *", 18, "obligatoire"),
    ("capture", "Capture", "Screenshot", 16, "conseille"),
    ("type", "Type", "Type", 12, "conseille"),
    ("constat", "Constat *", "Finding *", 45, "obligatoire"),
    ("categorie", "Catégorie *", "Criteria *", 24, "obligatoire"),
    ("critere", "Critère principal *", "Sub-criterion *", 36, "obligatoire"),
    ("secondaires", "Critères secondaires (codes séparés par ;)", "Secondary criteria (codes separated by ;)", 18,
     "conseille"),
    ("regle", "Règle de départage", "Tie-break rule", 11, "conseille"),
    ("justification", "Justification du critère", "Criterion justification", 36, "conseille"),
    ("gravite", "Gravité * (si problème)", "Severity * (if issue)", 12, "obligatoire"),
    ("type_reco", "Type de recommandation", "Type of UX recommendation", 16, "conseille"),
    ("recommandation", "Recommandation * (si problème)", "Detail of UX recommendation * (if issue)", 45, "obligatoire"),
    ("statut_maquette", "Statut maquette", "Mock-up status", 14, "suivi"),
    ("statut", "Statut", "Status", 14, "suivi"),
    ("controle", "Contrôle", "Check", 30, "auto"),
]
COL = {champ: i + 1 for i, (champ, *_) in enumerate(COLONNES)}


def L(champ):
    return get_column_letter(COL[champ])


TXT = {
    "fr": {
        "onglets": {"aide": "Mode d'emploi", "contexte": "Contexte", "audit": "Audit", "resultats": "Résultats",
                    "criteres": "Critères", "regles": "Règles de départage", "gravite": "Gravité", "listes": "Listes"},
        "titre_audit": "Audit ergonomique : constats",
        "legende_audit": ("Une ligne par constat. Jaune pâle = à remplir ; gris = automatique. * = obligatoire. "
                          "En-têtes gris = suivi. La ligne 4 est un exemple. Voir « Mode d'emploi »."),
        "ctrl": {"champs": "⚠ Champ obligatoire manquant", "hors_cat": "⚠ Critère hors catégorie",
                 "grav_reco": "⚠ Gravité ou recommandation manquante", "court": "⚠ Constat trop court", "ok": "✓ OK"},
        "aide": [
            ("Audit ergonomique : mode d'emploi", "titre"),
            (f"Template v{TEMPLATE_VERSION} · référentiel v{{ref}}", "petit"),
            ("", None),
            ("Étapes", "section"),
            ("1. Onglet « Contexte » : décrire le produit audité, la cible et la plateforme.", None),
            ("2. Onglet « Audit » : une ligne par constat (problème ou point fort). La ligne grisée en italique est un "
             "exemple : la laisser telle quelle. Sans type, un constat est considéré comme un problème.", None),
            ("3. Choisir la Catégorie, puis le Critère principal : la liste des critères dépend de la catégorie.", None),
            ("4. En cas d'hésitation entre deux critères, consulter l'onglet « Règles de départage », indiquer la "
             "règle appliquée et justifier le choix en une phrase (colonne « Justification du critère »).", None),
            ("5. Noter la gravité (Faible, Moyenne, Élevée, Critique) selon l'onglet « Gravité ». Toujours rédiger "
             "une recommandation pour un problème.", None),
            ("6. Vérifier la colonne « Contrôle » : elle doit afficher ✓ OK avant de rendre l'audit. L'onglet "
             "« Résultats » se met à jour tout seul.", None),
            ("7. L'application « Audit ergonomique assisté » peut compléter les cellules vides (en violet, à valider) "
             "et proposer des corrections : il suffit de lui donner ce fichier, même avec les seuls constats.", None),
            ("", None),
            ("Code couleur", "section"),
            ("Fond jaune pâle : cellules à remplir. Fond gris : cellules calculées (ID, Contrôle), ne pas modifier.", None),
            ("En-tête bleu foncé avec * : obligatoire. Bleu clair : conseillé. Gris : suivi du projet (maquette, statut).",
             None),
            ("", None),
            ("Bonnes pratiques de rédaction", "section"),
            ("Constat : factuel, observable et localisé. « Sur l'écran Panier, le bouton Valider reste actif pendant le "
             "chargement » plutôt que « le panier est confus ».", None),
            ("Critère : choisir la CAUSE du problème, pas son symptôme. Les autres critères touchés vont dans "
             "« Critères secondaires ».", None),
            ("Recommandation : spécifique (nomme l'élément), actionnable, vérifiable, et si possible appuyée sur une "
             "norme (WCAG, guidelines de la plateforme).", None),
            ("", None),
            ("Note : les définitions et checklists des critères sont en anglais, comme le référentiel d'origine.", "petit"),
        ],
        "contexte": [("Produit / interface auditée *", ""), ("Version, URL ou build", ""), ("Client / équipe", ""),
                     ("Cible utilisateurs *", ""), ("Plateforme *", "PLATEFORME"), ("Contexte d'usage", ""),
                     ("Parcours audités *", ""), ("Designer *", ""), ("Date de l'audit *", "DATE"), ("Langue", "fr"),
                     ("Version du template", TEMPLATE_VERSION), ("Version du référentiel", "REF")],
        "titre_contexte": "Contexte de l'audit",
        "note_contexte": "Les champs marqués * sont obligatoires. Langue et versions sont remplies automatiquement.",
        "exemple": {"parcours": "Commander un produit", "tache": "Payer", "ecran": "Panier – étape Paiement",
                    "capture": "paiement_01.png", "constat": "Après un clic sur « Payer », aucun indicateur de "
                    "chargement n'apparaît pendant environ 5 secondes ; le bouton reste actif et des utilisateurs "
                    "cliquent plusieurs fois.",
                    "justification": "Le problème porte sur la réponse du système APRÈS l'action (R1). Checklist : "
                                     "« Is information displayed during the loading of an action? »",
                    "recommandation": "Afficher un indicateur de chargement dans le bouton « Payer » dès le clic et "
                                      "désactiver le bouton jusqu'à la réponse du serveur, pour éviter les doubles "
                                      "paiements."},
        "resultats": {"titre": "Résultats de l'audit (calculés automatiquement)",
                      "entete": ["Code", "Critère"] + [GRAVITES[g]["fr"] for g in GRAVITES] + ["Total problèmes",
                                                                                          "Points forts"],
                      "total": "Total", "par_cat": ["Code", "Catégorie", "Constats"],
                      "note": "Comptage d'après les colonnes « Critère principal », « Gravité » et « Type » de l'onglet "
                              "Audit. Un constat sans type compte comme un problème."},
        "criteres_entete": ["Code", "Catégorie", "Critère", "Nom anglais", "Sources", "Définition (anglais)",
                            "Questions de checklist (anglais)"],
        "proposee": " [proposée]",
        "regles_titre": "Règles de départage : comment choisir entre deux critères proches",
        "regles_entete": ["Règle", "Thème", "Question à se poser", "Si le problème concerne…", "Critère", "Exemple"],
        "gravite_titre": "Échelle de gravité",
        "gravite_entete": ["Niveau", "Libellé", "Description"],
        "gravite_note": "La gravité combine la fréquence (le problème arrive-t-il souvent ?), l'impact (est-il facile à "
                        "surmonter ?) et la persistance (l'utilisateur le rencontre-t-il à chaque fois ?).",
        "aide_saisie": {"type": "Problème ou Point fort (vide = problème).",
                        "categorie": "Choisir la catégorie avant le critère.",
                        "critere": "La liste dépend de la catégorie choisie.",
                        "regle": "Voir l'onglet « Règles de départage ».",
                        "gravite": "Voir l'onglet « Gravité ».",
                        "erreur": "Choisir une valeur dans la liste."},
    },
    "en": {
        "onglets": {"aide": "How to use", "contexte": "Context", "audit": "Audit", "resultats": "Results",
                    "criteres": "Criteria", "regles": "Tie-break rules", "gravite": "Severity", "listes": "Lists"},
        "titre_audit": "Ergonomic audit: findings",
        "legende_audit": ("One row per finding. Pale yellow = to fill in; grey = automatic. * = required. Grey headers "
                          "= project tracking. Row 4 is an example. See “How to use”."),
        "ctrl": {"champs": "⚠ Required field missing", "hors_cat": "⚠ Sub-criterion outside its criteria",
                 "grav_reco": "⚠ Severity or recommendation missing", "court": "⚠ Finding too short", "ok": "✓ OK"},
        "aide": [
            ("Ergonomic audit: how to use", "titre"),
            (f"Template v{TEMPLATE_VERSION} · referential v{{ref}}", "petit"),
            ("", None),
            ("Steps", "section"),
            ("1. “Context” sheet: describe the audited product, the target users and the platform.", None),
            ("2. “Audit” sheet: one row per finding (issue or strength). The greyed italic row is an example: leave it "
             "as is. Without a type, a finding is considered an issue.", None),
            ("3. Choose the Criteria, then the Sub-criterion: the sub-criteria list depends on the criteria.", None),
            ("4. When hesitating between two sub-criteria, check the “Tie-break rules” sheet, enter the rule applied "
             "and justify the choice in one sentence (“Criterion justification” column).", None),
            ("5. Rate the severity (Low, Medium, High, Critical) using the “Severity” sheet. Always write a "
             "recommendation for an issue.", None),
            ("6. Check the “Check” column: it must show ✓ OK before handing in the audit. The “Results” sheet updates "
             "automatically.", None),
            ("7. The “Ergonomic audit assistant” application can fill in empty cells (in purple, to be validated) and "
             "suggest corrections: just give it this file, even with the findings only.", None),
            ("", None),
            ("Colour code", "section"),
            ("Pale yellow: cells to fill in. Grey: calculated cells (ID, Check), do not edit.", None),
            ("Dark blue header with *: required. Light blue: recommended. Grey: project tracking (mock-up, status).",
             None),
            ("", None),
            ("Writing good practice", "section"),
            ("Finding: factual, observable and located. “On the Cart screen, the Confirm button stays active while "
             "loading” rather than “the cart is confusing”.", None),
            ("Sub-criterion: choose the CAUSE of the problem, not its symptom. Other affected criteria go in "
             "“Secondary criteria”.", None),
            ("Recommendation: specific (names the element), actionable, verifiable, and if possible based on a standard "
             "(WCAG, platform guidelines).", None),
        ],
        "contexte": [("Audited product / interface *", ""), ("Version, URL or build", ""), ("Client / team", ""),
                     ("Target users *", ""), ("Platform *", "PLATEFORME"), ("Context of use", ""),
                     ("Audited journeys *", ""), ("Designer *", ""), ("Audit date *", "DATE"), ("Language", "en"),
                     ("Template version", TEMPLATE_VERSION), ("Referential version", "REF")],
        "titre_contexte": "Audit context",
        "note_contexte": "Fields marked * are required. Language and versions are filled in automatically.",
        "exemple": {"parcours": "Order a product", "tache": "Pay", "ecran": "Cart – Payment step",
                    "capture": "payment_01.png", "constat": "After clicking “Pay”, no loading indicator appears for "
                    "about 5 seconds; the button stays active and some users click several times.",
                    "justification": "The problem is the system's response AFTER the action (R1). Checklist: "
                                     "“Is information displayed during the loading of an action?”",
                    "recommandation": "Show a loading indicator in the “Pay” button as soon as it is clicked and "
                                      "disable the button until the server responds, to avoid double payments."},
        "resultats": {"titre": "Audit results (calculated automatically)",
                      "entete": ["Code", "Sub-criterion"] + [GRAVITES[g]["en"] for g in GRAVITES] + ["Total issues",
                                                                                              "Strengths"],
                      "total": "Total", "par_cat": ["Code", "Criteria", "Findings"],
                      "note": "Counted from the “Sub-criterion”, “Severity” and “Type” columns of the Audit sheet. "
                              "A finding without a type counts as an issue."},
        "criteres_entete": ["Code", "Criteria", "Sub-criterion", "French name", "Sources", "Definition",
                            "Checklist questions"],
        "proposee": " [proposed]",
        "regles_titre": "Tie-break rules: how to choose between two close sub-criteria",
        "regles_entete": ["Rule", "Theme", "Question to ask", "If the problem is about…", "Sub-criterion", "Example"],
        "gravite_titre": "Severity scale",
        "gravite_entete": ["Level", "Label", "Description"],
        "gravite_note": "Severity combines frequency (does the problem happen often?), impact (is it easy to overcome?) "
                        "and persistence (does the user meet it every time?).",
        "aide_saisie": {"type": "Issue or Strength (empty = issue).", "categorie": "Choose the criteria first.",
                        "critere": "The list depends on the chosen criteria.", "regle": "See the “Tie-break rules” sheet.",
                        "gravite": "See the “Severity” sheet.", "erreur": "Choose a value from the list."},
    },
}


def entete(ws, row, valeurs, fills=None):
    for i, v in enumerate(valeurs, 1):
        cell = ws.cell(row=row, column=i, value=v)
        cell.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
        cell.fill = fills[i - 1] if fills else HEADER_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        cell.border = BORDER


def cellule(ws, row, col, valeur, gras=False, taille=9):
    c = ws.cell(row=row, column=col, value=valeur)
    c.alignment = WRAP
    c.border = BORDER
    c.font = Font(name=FONT, size=taille, bold=gras)
    return c


def nommer(wb, nom, ref):
    wb.defined_names[nom] = DefinedName(nom, attr_text=ref)


def feuille_listes(wb, ref, lg, tx):
    ws = wb.create_sheet(tx["onglets"]["listes"])
    ws.sheet_state = "hidden"
    listes = {
        "L_CAT": [ref.libelle_categorie(c, lg) for c in ref.categories],
        "L_TYPE": [v[lg] for v in TYPES.values()],
        "L_GRAV": [v[lg] for v in GRAVITES.values()],
        "L_TYPE_RECO": [v[lg] for v in TYPES_RECO.values()],
        "L_MAQUETTE": [v[lg] for v in STATUTS_MAQUETTE.values()],
        "L_REGLE": list(ref.regles),
        "L_PLATEFORME": PLATEFORMES[lg],
    }
    for cat in ref.categories:  # une liste de critères par catégorie, pour la liste déroulante dépendante
        listes[f"L_{cat}"] = [ref.libelle_critere(c, lg) for c, v in ref.criteres.items() if v["categorie"] == cat]
    titre = f"'{ws.title}'" if " " in ws.title else ws.title
    for i, (nom, valeurs) in enumerate(listes.items(), 1):
        lettre = get_column_letter(i)
        ws.cell(row=1, column=i, value=nom).font = Font(name=FONT, bold=True)
        for j, v in enumerate(valeurs, 2):
            ws.cell(row=j, column=i, value=v)
        nommer(wb, nom, f"{titre}!${lettre}$2:${lettre}${len(valeurs) + 1}")


def feuille_aide(wb, ref, tx):
    ws = wb.active
    ws.title = tx["onglets"]["aide"]
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 115
    styles = {"titre": Font(name=FONT, size=16, bold=True, color=NAVY), "section": Font(name=FONT, size=12, bold=True,
              color=NAVY), "petit": Font(name=FONT, size=9, italic=True, color="7F7F7F"), None: Font(name=FONT, size=10)}
    for i, (texte, style) in enumerate(tx["aide"], 1):
        c = ws.cell(row=i, column=2, value=texte.replace("{ref}", ref.version))
        c.font = styles[style]
        c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.sheet_view.showGridLines = False


def feuille_contexte(wb, ref, lg, tx):
    from datetime import date  # noqa: F401  (date laissée vide : le designer la saisit)

    ws = wb.create_sheet(tx["onglets"]["contexte"])
    ws.column_dimensions["A"].width = 32
    ws.column_dimensions["B"].width = 70
    ws["A1"] = tx["titre_contexte"]
    ws["A1"].font = Font(name=FONT, size=14, bold=True, color=NAVY)
    for i, (libelle, valeur) in enumerate(tx["contexte"], 3):
        a = cellule(ws, i, 1, libelle, gras=True, taille=10)
        auto = valeur not in ("", "PLATEFORME", "DATE")
        b = cellule(ws, i, 2, ref.version if valeur == "REF" else (valeur if auto else None), taille=10)
        b.fill = AUTO_FILL if auto else INPUT_FILL
        del a
        if valeur == "PLATEFORME":
            dv = DataValidation(type="list", formula1="L_PLATEFORME", allow_blank=True)
            ws.add_data_validation(dv)
            dv.add(b)
        if valeur == "DATE":
            b.number_format = "DD/MM/YYYY" if lg == "fr" else "YYYY-MM-DD"
    ws.cell(row=len(tx["contexte"]) + 4, column=1, value=tx["note_contexte"]).font = EXAMPLE_FONT


def formule_controle(r, tx):
    c = {k: f"{L(k)}{r}" for k in COL}
    point_fort = TYPES["point_fort"]["fr" if tx is TXT["fr"] else "en"]
    m = tx["ctrl"]
    return (f'=IF({c["constat"]}="","",'
            f'IF(OR({c["ecran"]}="",{c["categorie"]}="",{c["critere"]}=""),"{m["champs"]}",'
            f'IF(LEFT({c["critere"]},3)<>LEFT({c["categorie"]},3),"{m["hors_cat"]}",'
            f'IF(AND({c["type"]}<>"{point_fort}",OR({c["gravite"]}="",{c["recommandation"]}="")),"{m["grav_reco"]}",'
            f'IF(LEN({c["constat"]})<20,"{m["court"]}","{m["ok"]}")))))')


def feuille_audit(wb, ref, lg, tx):
    ws = wb.create_sheet(tx["onglets"]["audit"])
    ws["A1"] = tx["titre_audit"]
    ws["A1"].font = Font(name=FONT, size=14, bold=True, color=NAVY)
    ws["A2"] = tx["legende_audit"]
    ws["A2"].font = Font(name=FONT, size=9, italic=True, color="595959")

    remplissages = {"obligatoire": HEADER_FILL, "conseille": OPTIONAL_HEADER_FILL, "suivi": SUIVI_HEADER_FILL,
                    "auto": HEADER_FILL}
    entete(ws, HEADER_ROW, [fr if lg == "fr" else en for _, fr, en, _, _ in COLONNES],
           [remplissages[role] for *_, role in COLONNES])
    ws.row_dimensions[HEADER_ROW].height = 45
    for champ, _, _, largeur, _ in COLONNES:
        ws.column_dimensions[L(champ)].width = largeur

    ex = tx["exemple"]
    exemple = {**ex, "id": "EXEMPLE" if lg == "fr" else "EXAMPLE", "type": TYPES["probleme"][lg],
               "categorie": ref.libelle_categorie("GUI", lg), "critere": ref.libelle_critere("GUI-03", lg),
               "secondaires": "ERR-01", "regle": "R1", "gravite": GRAVITES[3][lg], "type_reco": TYPES_RECO["design"][lg],
               "statut_maquette": STATUTS_MAQUETTE["a_maquetter"][lg]}
    for champ, *_ in COLONNES:
        c = ws.cell(row=EXAMPLE_ROW, column=COL[champ], value=exemple.get(champ))
        c.font, c.fill, c.alignment, c.border = EXAMPLE_FONT, AUTO_FILL, WRAP, BORDER
    ws.cell(row=EXAMPLE_ROW, column=COL["controle"], value=formule_controle(EXAMPLE_ROW, tx))

    for r in range(FIRST_ROW, LAST_ROW + 1):
        for champ, *_, role in COLONNES:
            c = ws.cell(row=r, column=COL[champ])
            c.fill = AUTO_FILL if role == "auto" else INPUT_FILL
            c.alignment, c.border, c.font = WRAP, BORDER, Font(name=FONT, size=10)
        ws.cell(row=r, column=COL["id"], value=f'=IF({L("constat")}{r}="","","F-"&TEXT(ROW()-{EXAMPLE_ROW},"000"))')
        ws.cell(row=r, column=COL["controle"], value=formule_controle(r, tx))

    plage = lambda champ: f"{L(champ)}{EXAMPLE_ROW}:{L(champ)}{LAST_ROW}"  # noqa: E731
    aide = tx["aide_saisie"]
    for champ, formule, message in [
        ("type", "L_TYPE", aide["type"]), ("categorie", "L_CAT", aide["categorie"]),
        ("critere", f'INDIRECT("L_"&LEFT(${L("categorie")}{EXAMPLE_ROW},3))', aide["critere"]),
        ("regle", "L_REGLE", aide["regle"]), ("gravite", "L_GRAV", aide["gravite"]),
        ("type_reco", "L_TYPE_RECO", None), ("statut_maquette", "L_MAQUETTE", None),
    ]:
        dv = DataValidation(type="list", formula1=formule, allow_blank=True, showErrorMessage=True,
                            errorTitle="⚠", error=aide["erreur"])
        if message:
            dv.promptTitle, dv.prompt, dv.showInputMessage = "ℹ", message, True
        ws.add_data_validation(dv)
        dv.add(plage(champ))

    premier = f"{L('controle')}{EXAMPLE_ROW}"
    ws.conditional_formatting.add(plage("controle"), FormulaRule(
        formula=[f'LEFT({premier},1)="⚠"'], fill=PatternFill("solid", fgColor="FCE4D6"), font=Font(color="C00000", bold=True)))
    ws.conditional_formatting.add(plage("controle"), FormulaRule(
        formula=[f'LEFT({premier},1)="✓"'], fill=PatternFill("solid", fgColor="E2EFDA"), font=Font(color="375623")))
    for g, couleur in COULEURS_GRAVITE.items():
        ws.conditional_formatting.add(plage("gravite"), CellIsRule(
            operator="equal", formula=[f'"{GRAVITES[g][lg]}"'], fill=PatternFill("solid", fgColor=couleur)))

    ws.freeze_panes = ws.cell(row=EXAMPLE_ROW, column=COL["constat"])
    ws.auto_filter.ref = f"A{HEADER_ROW}:{L('controle')}{LAST_ROW}"
    ws.print_title_rows = f"{HEADER_ROW}:{HEADER_ROW}"


def feuille_resultats(wb, ref, lg, tx):
    """Comptage par critère et par gravité : corrige l'onglet « Results » d'origine (22 critères sur 24, plages
    incohérentes, sous-critères comparés avec leur retour à la ligne)."""
    ws = wb.create_sheet(tx["onglets"]["resultats"])
    res = tx["resultats"]
    audit = f"'{tx['onglets']['audit']}'" if " " in tx["onglets"]["audit"] else tx["onglets"]["audit"]
    plage = lambda champ: f"{audit}!${L(champ)}${FIRST_ROW}:${L(champ)}${LAST_ROW}"  # noqa: E731
    ws["A1"] = res["titre"]
    ws["A1"].font = Font(name=FONT, size=14, bold=True, color=NAVY)
    entete(ws, 3, res["entete"])
    for col, largeur in zip("ABCDEFGH", (9, 44, 11, 11, 11, 11, 14, 12)):
        ws.column_dimensions[col].width = largeur
    point_fort = TYPES["point_fort"][lg]
    r = 4
    for code in ref.criteres:
        cellule(ws, r, 1, code, gras=True)
        cellule(ws, r, 2, ref.libelle_critere(code, lg).split(" – ", 1)[1])
        for i, g in enumerate(GRAVITES, 3):
            cellule(ws, r, i, f'=COUNTIFS({plage("critere")},"{code}*",{plage("gravite")},"{GRAVITES[g][lg]}",'
                              f'{plage("type")},"<>{point_fort}")')
        cellule(ws, r, 7, f"=SUM(C{r}:F{r})", gras=True)
        cellule(ws, r, 8, f'=COUNTIFS({plage("critere")},"{code}*",{plage("type")},"{point_fort}")')
        r += 1
    cellule(ws, r, 1, res["total"], gras=True)
    cellule(ws, r, 2, "")
    for col in "CDEFGH":
        cellule(ws, r, "ABCDEFGH".index(col) + 1, f"=SUM({col}4:{col}{r - 1})", gras=True)
    for i, g in enumerate(GRAVITES, 3):
        ws.cell(row=3, column=i).fill = PatternFill("solid", fgColor=COULEURS_GRAVITE[g])
        ws.cell(row=3, column=i).font = Font(name=FONT, size=10, bold=True, color="000000")
    ws.conditional_formatting.add(f"G4:G{r - 1}", CellIsRule(operator="greaterThan", formula=["0"],
                                                             fill=PatternFill("solid", fgColor="FCE4D6")))

    r += 2
    for i, v in enumerate(res["par_cat"], 1):
        c = ws.cell(row=r, column=i, value=v)
        c.font, c.fill, c.border = Font(name=FONT, size=10, bold=True, color="FFFFFF"), HEADER_FILL, BORDER
    for code in ref.categories:
        r += 1
        cellule(ws, r, 1, code, gras=True)
        cellule(ws, r, 2, ref.libelle_categorie(code, lg).split(" – ", 1)[1])
        cellule(ws, r, 3, f'=COUNTIF({plage("critere")},"{code}-*")')
    ws.cell(row=r + 2, column=1, value=res["note"]).font = EXAMPLE_FONT
    ws.freeze_panes = "C4"


def feuille_criteres(wb, ref, lg, tx):
    ws = wb.create_sheet(tx["onglets"]["criteres"])
    entete(ws, 1, tx["criteres_entete"])
    for i, largeur in enumerate([9, 22, 30, 30, 18, 60, 80], 1):
        ws.column_dimensions[get_column_letter(i)].width = largeur
    r = 2
    for cat in ref.data["grid"]:
        for c in cat["criteria"]:
            questions = "\n".join(f"• {q['q']}" + (tx["proposee"] if q["statut"] == "proposee" else "")
                                  for q in c["checklist"]) or "—"
            nom, autre = (c["label_fr"], c["name"]) if lg == "fr" else (c["name"], c["label_fr"])
            for i, v in enumerate([c["code"], ref.libelle_categorie(cat["code"], lg), nom, autre,
                                   ", ".join(c["sources"]), c["definition"], questions], 1):
                cellule(ws, r, i, v, gras=(i == 1))
            r += 1
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = f"A1:G{r - 1}"


def feuille_regles(wb, ref, lg, tx):
    ws = wb.create_sheet(tx["onglets"]["regles"])
    ws["A1"] = tx["regles_titre"]
    ws["A1"].font = Font(name=FONT, size=14, bold=True, color=NAVY)
    regles = ref.data["regles_departage"]
    suffixe = "_en" if lg == "en" else ""
    principes = regles.get(f"principes{suffixe}") or regles["principes"]
    for i, p in enumerate(principes, 2):
        ws.cell(row=i, column=1, value=f"• {p}").font = Font(name=FONT, size=10)
    debut = len(principes) + 3
    entete(ws, debut, tx["regles_entete"])
    for i, largeur in enumerate([8, 22, 45, 55, 12, 50], 1):
        ws.column_dimensions[get_column_letter(i)].width = largeur
    r = debut + 1
    for regle in regles["regles"]:
        for k, cas in enumerate(regle["cas"]):
            valeurs = [regle["id"], regle.get(f"theme{suffixe}", regle["theme"]),
                       regle.get(f"question{suffixe}", regle["question"]), cas.get(f"si{suffixe}", cas["si"]),
                       cas["critere"], cas.get(f"exemple{suffixe}", cas["exemple"])]
            for i, v in enumerate(valeurs, 1):
                cellule(ws, r, i, v if (k == 0 or i > 3) else None, gras=(i in (1, 5)))
            r += 1
        if len(regle["cas"]) > 1:
            for col in (1, 2, 3):
                ws.merge_cells(start_row=r - len(regle["cas"]), end_row=r - 1, start_column=col, end_column=col)
    ws.freeze_panes = ws.cell(row=debut + 1, column=1)


def feuille_gravite(wb, lg, tx):
    ws = wb.create_sheet(tx["onglets"]["gravite"])
    ws["A1"] = tx["gravite_titre"]
    ws["A1"].font = Font(name=FONT, size=14, bold=True, color=NAVY)
    entete(ws, 3, tx["gravite_entete"])
    for col, largeur in zip("ABC", (9, 16, 90)):
        ws.column_dimensions[col].width = largeur
    for r, g in enumerate(sorted(GRAVITES, reverse=True), 4):
        cellule(ws, r, 1, g, gras=True, taille=10)
        libelle = cellule(ws, r, 2, GRAVITES[g][lg], gras=True, taille=10)
        libelle.fill = PatternFill("solid", fgColor=COULEURS_GRAVITE[g])
        cellule(ws, r, 3, GRAVITES[g][f"def_{lg}"], taille=10)
    c = ws.cell(row=9, column=1, value=tx["gravite_note"])
    c.font, c.alignment = Font(name=FONT, size=10), WRAP
    ws.merge_cells("A9:C9")
    ws.row_dimensions[9].height = 30


def construire(ref, lg):
    tx = TXT[lg]
    wb = Workbook()
    feuille_aide(wb, ref, tx)
    feuille_contexte(wb, ref, lg, tx)
    feuille_audit(wb, ref, lg, tx)
    feuille_resultats(wb, ref, lg, tx)
    feuille_criteres(wb, ref, lg, tx)
    feuille_regles(wb, ref, lg, tx)
    feuille_gravite(wb, lg, tx)
    feuille_listes(wb, ref, lg, tx)
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if c.value is not None and c.font.name != FONT:
                    f = c.font
                    c.font = Font(name=FONT, size=f.size or 10, bold=f.bold, italic=f.italic, color=f.color)
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
    wb.active = wb.sheetnames.index(tx["onglets"]["audit"])
    return wb


def main():
    ref = Referentiel(json.loads((ROOT / "referentiel" / "referentiel.json").read_text(encoding="utf-8")))
    for lg, sortie in SORTIES.items():
        sortie.parent.mkdir(exist_ok=True)
        construire(ref, lg).save(sortie)
        print(f"Template v{TEMPLATE_VERSION} {lg.upper()} (référentiel v{ref.version}) -> {sortie}")


if __name__ == "__main__":
    main()
