"""Génère le template Excel que remplissent les designers, à partir de referentiel/referentiel.json.

Usage : python3 scripts/build_template.py  (depuis le dossier du dépôt)
Sortie : template/Audit_ergonomique_template.xlsx
"""
import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "template" / "Audit_ergonomique_template.xlsx"
TEMPLATE_VERSION = "1.0"
N_ROWS = 200  # lignes de constats préparées

FONT = "Arial"
NAVY = "1F3864"
INPUT_FILL = PatternFill("solid", fgColor="FFF9E5")
AUTO_FILL = PatternFill("solid", fgColor="EDEDED")
HEADER_FILL = PatternFill("solid", fgColor=NAVY)
OPTIONAL_HEADER_FILL = PatternFill("solid", fgColor="5B7DB1")
EXAMPLE_FONT = Font(name=FONT, size=10, italic=True, color="7F7F7F")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")

TYPES = ["Problème", "Point fort"]
FREQUENCES = ["Rare", "Occasionnelle", "Systématique"]
IMPACTS = ["Faible", "Moyen", "Fort"]
PRIORITES = ["P1", "P2", "P3"]
PLATEFORMES = ["Web desktop", "Web responsive / mobile", "Application mobile", "Logiciel métier", "Borne / autre"]
GRAVITE = [
    (0, "Pas un problème", "Désaccord avec un critère sans impact sur l'utilisabilité.", "–"),
    (1, "Cosmétique", "Gêne esthétique ou mineure ; à corriger si le temps le permet.", "P3"),
    (2, "Mineur", "Gêne ponctuelle, l'utilisateur contourne facilement le problème.", "P3 ou P2"),
    (3, "Majeur", "L'utilisateur est ralenti, se trompe ou a besoin d'aide.", "P2 ou P1"),
    (4, "Bloquant", "La tâche ne peut pas être accomplie. À corriger avant mise en production.", "P1"),
]

# (en-tête, largeur, obligatoire, saisie par le designer)
COLUMNS = [
    ("ID", 9, False, False),
    ("Écran / Page *", 18, True, True),
    ("Parcours / Tâche", 18, False, True),
    ("Capture (fichier ou lien)", 18, False, True),
    ("Type *", 12, True, True),
    ("Constat *", 45, True, True),
    ("Catégorie *", 26, True, True),
    ("Critère principal *", 38, True, True),
    ("Critères secondaires (codes séparés par ;)", 20, False, True),
    ("Règle de départage", 12, False, True),
    ("Gravité (0-4) *", 10, True, True),
    ("Fréquence", 14, False, True),
    ("Impact", 10, False, True),
    ("Recommandation * (si Problème)", 45, True, True),
    ("Priorité", 9, False, True),
    ("Contrôle", 30, False, False),
]
def key(header):
    return header.split(" *")[0].split(" (")[0]


COL = {key(name): i + 1 for i, (name, *_) in enumerate(COLUMNS)}
HEADER_ROW, EXAMPLE_ROW, FIRST_ROW = 3, 4, 5
LAST_ROW = FIRST_ROW + N_ROWS - 1


def letter(name):
    from openpyxl.utils import get_column_letter
    return get_column_letter(COL[name])


def cat_label(cat):
    return f"{cat['code']} – {cat['label_fr']}"


def crit_label(c):
    return f"{c['code']} – {c['label_fr']} ({c['name']})"


def style_header(ws, row, headers, fills=None):
    for i, h in enumerate(headers, 1):
        cell = ws.cell(row=row, column=i, value=h)
        cell.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
        cell.fill = fills[i - 1] if fills else HEADER_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        cell.border = BORDER


def set_font(ws):
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is not None and cell.font.name != FONT:
                f = cell.font
                cell.font = Font(name=FONT, size=f.size or 10, bold=f.bold, italic=f.italic, color=f.color)


def add_name(wb, name, ref):
    wb.defined_names[name] = DefinedName(name, attr_text=ref)


def sheet_listes(wb, ref):
    ws = wb.create_sheet("Listes")
    ws.sheet_state = "hidden"
    lists = {
        "L_CAT": [cat_label(c) for c in ref["grid"]],
        "L_TYPE": TYPES,
        "L_GRAV": [g[0] for g in GRAVITE],
        "L_FREQ": FREQUENCES,
        "L_IMPACT": IMPACTS,
        "L_PRIO": PRIORITES,
        "L_REGLE": [r["id"] for r in ref["regles_departage"]["regles"]],
        "L_PLATEFORME": PLATEFORMES,
    }
    # Une liste de critères par catégorie, nommée L_<code> pour la liste déroulante dépendante
    for cat in ref["grid"]:
        lists[f"L_{cat['code']}"] = [crit_label(c) for c in cat["criteria"]]
    from openpyxl.utils import get_column_letter
    for i, (name, values) in enumerate(lists.items(), 1):
        col = get_column_letter(i)
        ws.cell(row=1, column=i, value=name).font = Font(name=FONT, bold=True)
        for j, v in enumerate(values, 2):
            ws.cell(row=j, column=i, value=v)
        add_name(wb, name, f"Listes!${col}$2:${col}${len(values) + 1}")


def sheet_mode_emploi(wb, ref):
    ws = wb.active
    ws.title = "Mode d'emploi"
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 110
    lines = [
        ("Audit ergonomique : mode d'emploi", Font(name=FONT, size=16, bold=True, color=NAVY)),
        (f"Template v{TEMPLATE_VERSION} · référentiel v{ref['version']}", Font(name=FONT, size=9, italic=True, color="7F7F7F")),
        ("", None),
        ("Étapes", Font(name=FONT, size=12, bold=True, color=NAVY)),
        ("1. Onglet « Contexte » : décrire le produit audité, la cible et la plateforme.", None),
        ("2. Onglet « Audit » : une ligne par constat (problème ou point fort). La ligne grisée en italique est un exemple : la laisser telle quelle.", None),
        ("3. Choisir d'abord la Catégorie, puis le Critère principal : la liste des critères dépend de la catégorie choisie.", None),
        ("4. En cas d'hésitation entre deux critères, consulter l'onglet « Règles de départage » et indiquer la règle appliquée.", None),
        ("5. Noter la gravité de 0 à 4 selon l'onglet « Gravité ». Toujours rédiger une recommandation pour un problème.", None),
        ("6. Vérifier la colonne « Contrôle » : elle doit afficher ✓ OK sur chaque ligne avant de rendre l'audit.", None),
        ("", None),
        ("Code couleur", Font(name=FONT, size=12, bold=True, color=NAVY)),
        ("Fond jaune pâle : cellules à remplir.", None),
        ("Fond gris : cellules calculées automatiquement (ID, Contrôle), ne pas modifier.", None),
        ("En-tête bleu foncé avec * : colonne obligatoire. En-tête bleu clair : colonne recommandée.", None),
        ("", None),
        ("Bonnes pratiques de rédaction", Font(name=FONT, size=12, bold=True, color=NAVY)),
        ("Constat : factuel, observable et localisé. « Sur l'écran Panier, le bouton Valider reste actif pendant le chargement » plutôt que « le panier est confus ».", None),
        ("Critère : choisir la CAUSE du problème, pas son symptôme. Les autres critères touchés vont dans « Critères secondaires ».", None),
        ("Recommandation : spécifique (nomme l'élément), actionnable, vérifiable, et si possible appuyée sur une norme (WCAG, guidelines de la plateforme).", None),
        ("", None),
        ("Les autres onglets", Font(name=FONT, size=12, bold=True, color=NAVY)),
        ("« Critères » : définition et checklist de chaque critère. Les questions marquées [proposée] sont en cours de validation.", None),
        ("« Règles de départage » : comment choisir entre deux critères proches.", None),
        ("« Gravité » : échelle de gravité commune à tous les audits.", None),
    ]
    for i, (text, font) in enumerate(lines, 1):
        cell = ws.cell(row=i, column=2, value=text)
        cell.font = font or Font(name=FONT, size=10)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.sheet_view.showGridLines = False


def sheet_contexte(wb, ref):
    ws = wb.create_sheet("Contexte")
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 70
    ws["A1"] = "Contexte de l'audit"
    ws["A1"].font = Font(name=FONT, size=14, bold=True, color=NAVY)
    fields = [
        ("Produit / interface auditée *", ""),
        ("Version, URL ou build", ""),
        ("Client / équipe", ""),
        ("Cible utilisateurs *", ""),
        ("Plateforme *", ""),
        ("Contexte d'usage", ""),
        ("Parcours audités *", ""),
        ("Designer *", ""),
        ("Date de l'audit *", ""),
        ("Version du template", TEMPLATE_VERSION),
        ("Version du référentiel", ref["version"]),
    ]
    for i, (label, value) in enumerate(fields, 3):
        a, b = ws.cell(row=i, column=1, value=label), ws.cell(row=i, column=2, value=value)
        a.font = Font(name=FONT, size=10, bold=True)
        b.font = Font(name=FONT, size=10)
        b.fill = AUTO_FILL if value else INPUT_FILL
        a.border = b.border = BORDER
        b.alignment = WRAP
        if label.startswith("Plateforme"):
            dv = DataValidation(type="list", formula1="L_PLATEFORME", allow_blank=True)
            ws.add_data_validation(dv)
            dv.add(b)
        if label.startswith("Date"):
            b.number_format = "DD/MM/YYYY"
    ws.cell(row=len(fields) + 4, column=1,
            value="Les champs marqués * sont obligatoires. Les versions sont remplies automatiquement.").font = EXAMPLE_FONT


def control_formula(r):
    c = {k: f"{letter(k)}{r}" for k in COL}
    grav = f"({c['Gravité']}+0)"
    return (
        f'=IF({c["Constat"]}="","",'
        f'IF(OR({c["Écran / Page"]}="",{c["Type"]}="",{c["Catégorie"]}="",{c["Critère principal"]}="",{c["Gravité"]}=""),'
        f'"⚠ Champ obligatoire manquant",'
        f'IF(LEFT({c["Critère principal"]},3)<>LEFT({c["Catégorie"]},3),"⚠ Critère hors catégorie",'
        f'IF(AND({c["Type"]}="Problème",{c["Recommandation"]}=""),"⚠ Recommandation manquante",'
        f'IF(AND({c["Priorité"]}<>"",OR(AND({grav}>=3,{c["Priorité"]}="P3"),AND({grav}<=1,{c["Priorité"]}="P1"))),'
        f'"⚠ Priorité incohérente avec la gravité",'
        f'IF(LEN({c["Constat"]})<20,"⚠ Constat trop court","✓ OK"))))))'
    )


def sheet_audit(wb, ref):
    ws = wb.create_sheet("Audit")
    ws["A1"] = "Audit ergonomique : constats"
    ws["A1"].font = Font(name=FONT, size=14, bold=True, color=NAVY)
    ws["A2"] = ("Une ligne par constat. Jaune pâle = à remplir ; gris = automatique. "
                "* = obligatoire. La ligne 4 est un exemple. Voir l'onglet « Mode d'emploi ».")
    ws["A2"].font = Font(name=FONT, size=9, italic=True, color="595959")

    fills = [HEADER_FILL if req else OPTIONAL_HEADER_FILL for _, _, req, _ in COLUMNS]
    style_header(ws, HEADER_ROW, [h for h, *_ in COLUMNS], fills)
    ws.row_dimensions[HEADER_ROW].height = 42
    from openpyxl.utils import get_column_letter
    for i, (_, width, _, _) in enumerate(COLUMNS, 1):
        ws.column_dimensions[get_column_letter(i)].width = width

    gui = next(c for c in ref["grid"] if c["code"] == "GUI")
    feedback = next(c for c in gui["criteria"] if c["code"] == "GUI-03")
    example = {
        "ID": "EXEMPLE",
        "Écran / Page": "Panier – étape Paiement",
        "Parcours / Tâche": "Commander un produit",
        "Capture": "paiement_01.png",
        "Type": "Problème",
        "Constat": "Après un clic sur « Payer », aucun indicateur de chargement n'apparaît pendant environ 5 secondes ; "
                   "le bouton reste actif et des utilisateurs cliquent plusieurs fois.",
        "Catégorie": cat_label(gui),
        "Critère principal": crit_label(feedback),
        "Critères secondaires": "ERR-01",
        "Règle de départage": "R1",
        "Gravité": 3,
        "Fréquence": "Systématique",
        "Impact": "Fort",
        "Recommandation": "Afficher un indicateur de chargement dans le bouton « Payer » dès le clic et désactiver le "
                          "bouton jusqu'à la réponse du serveur, pour éviter les doubles paiements.",
        "Priorité": "P1",
    }
    for i, (header, *_) in enumerate(COLUMNS, 1):
        cell = ws.cell(row=EXAMPLE_ROW, column=i, value=example.get(key(header)))
        cell.font = EXAMPLE_FONT
        cell.fill = AUTO_FILL
        cell.alignment = WRAP
        cell.border = BORDER
    ws.cell(row=EXAMPLE_ROW, column=COL["Contrôle"], value=control_formula(EXAMPLE_ROW))

    for r in range(FIRST_ROW, LAST_ROW + 1):
        for i, (_, _, _, is_input) in enumerate(COLUMNS, 1):
            cell = ws.cell(row=r, column=i)
            cell.fill = INPUT_FILL if is_input else AUTO_FILL
            cell.alignment = WRAP
            cell.border = BORDER
            cell.font = Font(name=FONT, size=10)
        ws.cell(row=r, column=COL["ID"], value=f'=IF({letter("Constat")}{r}="","","F-"&TEXT(ROW()-{EXAMPLE_ROW},"000"))')
        ws.cell(row=r, column=COL["Contrôle"], value=control_formula(r))

    rng = lambda name: f"{letter(name)}{EXAMPLE_ROW}:{letter(name)}{LAST_ROW}"
    validations = [
        ("Type", "L_TYPE", "Choisir Problème ou Point fort."),
        ("Catégorie", "L_CAT", "Choisir la catégorie avant le critère."),
        ("Critère principal", f'INDIRECT("L_"&LEFT(${letter("Catégorie")}{EXAMPLE_ROW},3))',
         "La liste dépend de la catégorie choisie."),
        ("Règle de départage", "L_REGLE", "Voir l'onglet « Règles de départage »."),
        ("Gravité", "L_GRAV", "0 à 4, voir l'onglet « Gravité »."),
        ("Fréquence", "L_FREQ", None),
        ("Impact", "L_IMPACT", None),
        ("Priorité", "L_PRIO", None),
    ]
    for name, formula, prompt in validations:
        dv = DataValidation(type="list", formula1=formula, allow_blank=True, showErrorMessage=True,
                            errorTitle="Valeur non valide", error="Choisir une valeur dans la liste.")
        if prompt:
            dv.promptTitle, dv.prompt, dv.showInputMessage = name, prompt, True
        ws.add_data_validation(dv)
        dv.add(rng(name))

    ctrl = rng("Contrôle")
    first_ctrl = f"{letter('Contrôle')}{EXAMPLE_ROW}"
    ws.conditional_formatting.add(ctrl, FormulaRule(formula=[f'LEFT({first_ctrl},1)="⚠"'],
                                                    fill=PatternFill("solid", fgColor="FCE4D6"),
                                                    font=Font(color="C00000", bold=True)))
    ws.conditional_formatting.add(ctrl, FormulaRule(formula=[f'LEFT({first_ctrl},1)="✓"'],
                                                    fill=PatternFill("solid", fgColor="E2EFDA"),
                                                    font=Font(color="375623")))
    grav = rng("Gravité")
    for value, color in [(4, "FF7C80"), (3, "F4B183"), (2, "FFE699")]:
        ws.conditional_formatting.add(grav, CellIsRule(operator="equal", formula=[str(value)],
                                                       fill=PatternFill("solid", fgColor=color)))

    ws.freeze_panes = ws.cell(row=EXAMPLE_ROW, column=COL["Type"])
    ws.auto_filter.ref = f"A{HEADER_ROW}:{letter('Contrôle')}{LAST_ROW}"


def sheet_criteres(wb, ref):
    ws = wb.create_sheet("Critères")
    headers = ["Code", "Catégorie", "Critère", "Nom français", "Sources", "Définition", "Questions de checklist"]
    widths = [9, 22, 28, 28, 18, 60, 80]
    style_header(ws, 1, headers)
    from openpyxl.utils import get_column_letter
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    r = 2
    for cat in ref["grid"]:
        for c in cat["criteria"]:
            questions = "\n".join(
                f"• {q['q']}" + (" [proposée]" if q["statut"] == "proposee" else "") for q in c["checklist"]
            ) or "(aucune question)"
            values = [c["code"], cat_label(cat), c["name"], c["label_fr"], ", ".join(c["sources"]),
                      c["definition"], questions]
            for i, v in enumerate(values, 1):
                cell = ws.cell(row=r, column=i, value=v)
                cell.alignment = WRAP
                cell.border = BORDER
                cell.font = Font(name=FONT, size=9, bold=(i == 1))
            r += 1
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = f"A1:G{r - 1}"


def sheet_regles(wb, ref):
    ws = wb.create_sheet("Règles de départage")
    ws["A1"] = "Règles de départage : comment choisir entre deux critères proches"
    ws["A1"].font = Font(name=FONT, size=14, bold=True, color=NAVY)
    principes = ref["regles_departage"]["principes"]
    for i, p in enumerate(principes, 2):
        ws.cell(row=i, column=1, value=f"• {p}").font = Font(name=FONT, size=10)
    start = len(principes) + 3
    headers = ["Règle", "Thème", "Question à se poser", "Si le problème concerne…", "Critère", "Exemple"]
    widths = [8, 22, 45, 55, 10, 50]
    style_header(ws, start, headers)
    from openpyxl.utils import get_column_letter
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    r = start + 1
    for regle in ref["regles_departage"]["regles"]:
        for k, cas in enumerate(regle["cas"]):
            values = [regle["id"], regle["theme"], regle["question"], cas["si"], cas["critere"], cas["exemple"]]
            for i, v in enumerate(values, 1):
                cell = ws.cell(row=r, column=i, value=v if (k == 0 or i > 3) else None)
                cell.alignment = WRAP
                cell.border = BORDER
                cell.font = Font(name=FONT, size=9, bold=(i in (1, 5)))
            r += 1
        if len(regle["cas"]) > 1:
            for col in (1, 2, 3):
                ws.merge_cells(start_row=r - len(regle["cas"]), end_row=r - 1, start_column=col, end_column=col)
    ws.freeze_panes = ws.cell(row=start + 1, column=1)


def sheet_gravite(wb):
    ws = wb.create_sheet("Gravité")
    ws["A1"] = "Échelle de gravité (Nielsen)"
    ws["A1"].font = Font(name=FONT, size=14, bold=True, color=NAVY)
    style_header(ws, 3, ["Niveau", "Libellé", "Description", "Priorité conseillée"])
    for i, w in enumerate([9, 18, 70, 18], 1):
        ws.column_dimensions["ABCD"[i - 1]].width = w
    for r, row in enumerate(GRAVITE, 4):
        for i, v in enumerate(row, 1):
            cell = ws.cell(row=r, column=i, value=v)
            cell.alignment = WRAP
            cell.border = BORDER
            cell.font = Font(name=FONT, size=10, bold=(i == 1))
    notes = [
        "La gravité combine la fréquence (le problème arrive-t-il souvent ?), l'impact (est-il facile à surmonter ?) "
        "et la persistance (l'utilisateur le rencontre-t-il à chaque fois ?).",
        "Fréquence : Rare (cas particulier) · Occasionnelle (certains parcours) · Systématique (tous les utilisateurs du parcours).",
        "Impact : Faible (simple gêne) · Moyen (ralentissement, hésitation) · Fort (erreur, abandon, blocage).",
    ]
    for i, n in enumerate(notes, 11):
        cell = ws.cell(row=i, column=1, value=n)
        cell.font = Font(name=FONT, size=10)
        ws.merge_cells(start_row=i, end_row=i, start_column=1, end_column=4)
        cell.alignment = WRAP
        ws.row_dimensions[i].height = 28


def main():
    ref = json.loads((ROOT / "referentiel" / "referentiel.json").read_text(encoding="utf-8"))
    wb = Workbook()
    sheet_mode_emploi(wb, ref)
    sheet_contexte(wb, ref)
    sheet_audit(wb, ref)
    sheet_criteres(wb, ref)
    sheet_regles(wb, ref)
    sheet_gravite(wb)
    sheet_listes(wb, ref)
    for ws in wb.worksheets:
        set_font(ws)
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
    wb.active = wb.sheetnames.index("Audit")
    OUT.parent.mkdir(exist_ok=True)
    wb.save(OUT)
    print(f"Template v{TEMPLATE_VERSION} (référentiel v{ref['version']}) -> {OUT}")


if __name__ == "__main__":
    main()
