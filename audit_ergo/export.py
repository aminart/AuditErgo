"""Export : le fichier du designer, annoté, avec deux onglets de relecture en plus."""
from datetime import date

from openpyxl import load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .controles import AVERTISSEMENT, BLOQUANT, INFO, NIVEAUX
from .lecture import LIBELLES

FONT = "Arial"
NAVY = "1F3864"
COULEURS = {BLOQUANT: "F8CBAD", AVERTISSEMENT: "FFE699", INFO: "DDEBF7"}
LIBELLE_NIVEAU = {BLOQUANT: "Bloquant", AVERTISSEMENT: "Avertissement", INFO: "Info"}
ONGLET_SYNTHESE, ONGLET_ANOMALIES = "Relecture – Synthèse", "Relecture – Anomalies"
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")


def _entete(ws, row, valeurs, largeurs=None):
    for i, v in enumerate(valeurs, 1):
        cell = ws.cell(row=row, column=i, value=v)
        cell.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        cell.border = BORDER
        if largeurs:
            ws.column_dimensions[get_column_letter(i)].width = largeurs[i - 1]


def _ligne(ws, row, valeurs, fill=None, bold=False):
    for i, v in enumerate(valeurs, 1):
        cell = ws.cell(row=row, column=i, value=v)
        cell.font = Font(name=FONT, size=10, bold=bold and i == 1)
        cell.alignment = WRAP
        cell.border = BORDER
        if fill:
            cell.fill = PatternFill("solid", fgColor=fill)


COLONNES_RELECTURE = [("Relecture : niveau", 14), ("Relecture : remarques", 60)]
COLONNES_IA = [("IA : critère suggéré", 32), ("IA : verdict critère", 16), ("IA : recommandation", 50),
               ("IA : avis recommandation", 30), ("IA : gravité", 16), ("IA : justification", 60)]
COULEURS_VERDICT = {"confirme": "E2EFDA", "a_revoir": "FFE699", "incorrect": "F8CBAD", "non_fourni": "EDEDED"}
COULEURS_RECO = {"bonne": "E2EFDA", "a_ameliorer": "FFE699", "hors_sujet": "F8CBAD", "non_fournie": "EDEDED"}
VIOLET = "E4DFEC"  # cellule complétée par l'application : à valider par le designer
LIBELLES_GRAVITE = ["Pas un problème", "Cosmétique", "Mineur", "Majeur", "Bloquant"]


def _commenter(cell, texte, auteur):
    """Ajoute un commentaire, à la suite de celui qui existe déjà le cas échéant."""
    if cell.comment:
        texte = f"{cell.comment.text}\n\n{texte}"
    cell.comment = Comment(texte, auteur, width=340, height=140)


def _ajouter_colonnes_manquantes(ws, audit):
    """Crée les colonnes que la complétion a dû ajouter (fichier sans colonne Recommandation, par ex.)."""
    for champ, col in list(audit.colonnes.items()):
        if col is None:
            col = ws.max_column + 1
            cell = ws.cell(row=audit.ligne_entete, column=col, value=LIBELLES[champ])
            cell.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor=NAVY)
            cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
            ws.column_dimensions[get_column_letter(col)].width = 45 if champ == "recommandation" else 24
            audit.colonnes[champ] = col


def _ecrire_completions(ws, audit):
    from .completion import IA

    for ligne, ajouts in audit.completions.items():
        for champ, (valeur, origine, explication) in ajouts.items():
            cell = ws.cell(row=ligne, column=audit.colonnes[champ], value=valeur)
            cell.fill = PatternFill("solid", fgColor=VIOLET)
            cell.font = Font(name=FONT, size=10, italic=True)
            cell.alignment = WRAP
            entete = "Proposé par l'IA, à valider." if origine == IA else "Complété automatiquement, à vérifier."
            _commenter(cell, f"{entete}\n{explication}", "Complétion automatique")


def _annoter_audit(ws, audit, anomalies, ref, ia=None):
    par_ligne = {}
    for a in anomalies:
        if a.ligne:
            par_ligne.setdefault(a.ligne, []).append(a)

    _ajouter_colonnes_manquantes(ws, audit)
    _ecrire_completions(ws, audit)

    # Une relecture précédente a pu déjà ajouter ces colonnes : on les réutilise
    existantes = {cell.value: cell.column for cell in ws[audit.ligne_entete] if cell.value}
    prochaine = ws.max_column + 1
    cols = {}
    for titre, largeur in COLONNES_RELECTURE + (COLONNES_IA if ia is not None else []):
        if titre in existantes:
            cols[titre] = existantes[titre]
        else:
            cols[titre], prochaine = prochaine, prochaine + 1
        cell = ws.cell(row=audit.ligne_entete, column=cols[titre], value=titre)
        cell.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="7030A0" if titre.startswith("Relecture") else "2E75B6")
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        ws.column_dimensions[get_column_letter(cols[titre])].width = largeur
        for r in range(audit.ligne_entete + 1, ws.max_row + 1):
            ws.cell(row=r, column=cols[titre]).value = None
    col_niveau, col_remarques = cols["Relecture : niveau"], cols["Relecture : remarques"]

    if ia is not None:
        _colonnes_ia(ws, audit, ref, ia, cols)

    for c in audit.constats:
        liste = par_ligne.get(c.ligne, [])
        pire = min((NIVEAUX.index(a.niveau) for a in liste), default=None)
        niveau = NIVEAUX[pire] if pire is not None else None
        cell = ws.cell(row=c.ligne, column=col_niveau, value=LIBELLE_NIVEAU[niveau] if niveau else "✓ Conforme")
        cell.fill = PatternFill("solid", fgColor=COULEURS[niveau] if niveau else "E2EFDA")
        cell.font = Font(name=FONT, size=10, bold=True)
        cell.alignment = WRAP
        remarques = "\n".join(f"• {a.message}" for a in liste)
        r = ws.cell(row=c.ligne, column=col_remarques, value=remarques or None)
        r.font = Font(name=FONT, size=10)
        r.alignment = WRAP

        # Surligne chaque cellule fautive, avec le détail en commentaire
        par_champ = {}
        for a in liste:
            if a.champ in audit.colonnes:
                par_champ.setdefault(a.champ, []).append(a)
        for champ, liste_champ in par_champ.items():
            cible = ws.cell(row=c.ligne, column=audit.colonnes[champ])
            pire = NIVEAUX[min(NIVEAUX.index(a.niveau) for a in liste_champ)]
            cible.fill = PatternFill("solid", fgColor=COULEURS[pire])
            _commenter(cible, "\n".join(a.message for a in liste_champ), "Relecture automatique")


def _colonnes_ia(ws, audit, ref, ia, cols):
    from .controles import _gravite
    from .suggestion import LIBELLE_RECO, LIBELLE_VERDICT, ErreurSuggestion

    for c in audit.constats:
        res = ia.get(c.ligne)
        if res is None:
            continue
        crit, verdict, reco, avis, grav, justif = (ws.cell(row=c.ligne, column=cols[t]) for t, _ in COLONNES_IA)
        for cell in (crit, verdict, reco, avis, grav, justif):
            cell.font = Font(name=FONT, size=10)
            cell.alignment = WRAP
        if isinstance(res, ErreurSuggestion):
            verdict.value, justif.value = "Erreur", str(res)
            continue
        completes = audit.completions.get(c.ligne, {})

        crit.value = res.ligne_excel(ref)
        if res.critere_designer:
            statut = res.verdict
            verdict.value = LIBELLE_VERDICT[statut]
        else:
            statut = "non_fourni"
            verdict.value = "Proposé (cellule remplie)" if "critere" in completes else LIBELLE_VERDICT[statut]
        if res.confiance != "haute":
            verdict.value += f" · confiance {res.confiance}"
        verdict.fill = PatternFill("solid", fgColor=COULEURS_VERDICT[statut])

        reco.value = res.reco_a_retenir or None
        if res.reco_statut != "non_fournie":
            avis.value = LIBELLE_RECO[res.reco_statut] + (f" : {res.reco_commentaire}" if res.reco_commentaire else "")
            avis.fill = PatternFill("solid", fgColor=COULEURS_RECO[res.reco_statut])
        elif "recommandation" in completes:
            avis.value = "Proposée (cellule remplie)"

        if res.gravite is not None:
            grav.value = f"{res.gravite} – {LIBELLES_GRAVITE[res.gravite]}"
            g_designer = _gravite(c["gravite"]) if "gravite" not in completes else None
            if g_designer is not None and g_designer != res.gravite:
                grav.value += f" (vous : {g_designer})"
                if abs(g_designer - res.gravite) >= 2:
                    grav.fill = PatternFill("solid", fgColor=COULEURS_VERDICT["a_revoir"])

        details = [res.justification]
        if res.commentaire_verdict:
            details.append(f"Sur le critère choisi : {res.commentaire_verdict}")
        if res.question_checklist:
            details.append(f"Checklist : {res.question_checklist}")
        if res.justification_gravite:
            details.append(f"Gravité : {res.justification_gravite}")
        if res.reco_complementaires:
            details.append("Recommandations complémentaires : " + " ; ".join(res.reco_complementaires))
        if res.question_a_se_poser:
            details.append(f"À se demander : {res.question_a_se_poser}")
        if res.precisions_manquantes:
            details.append("À préciser : " + " ; ".join(res.precisions_manquantes))
        justif.value = "\n".join(details)


def _onglet_synthese(wb, audit, synthese, ref):
    ws = wb.create_sheet(ONGLET_SYNTHESE, 0)
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 42
    ws.column_dimensions["B"].width = 50
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 14
    ws["A1"] = "Relecture automatique de l'audit"
    ws["A1"].font = Font(name=FONT, size=16, bold=True, color=NAVY)
    nb_completes = sum(len(a) for a in audit.completions.values())
    ws["A2"] = (f"Référentiel v{ref.version} · {date.today():%d/%m/%Y}. "
                + (f"{nb_completes} cellule(s) complétée(s) automatiquement, en violet dans l'onglet "
                   f"« {audit.onglet} » : à valider." if nb_completes else "Contrôles de forme."))
    ws["A2"].font = Font(name=FONT, size=9, italic=True, color="7F7F7F")

    statut = ("✓ Prêt pour la relecture des critères" if synthese.pret
              else f"⚠ {synthese.nb_bloquants} anomalie(s) bloquante(s) à corriger")
    ws["A4"] = statut
    ws["A4"].font = Font(name=FONT, size=13, bold=True, color="375623" if synthese.pret else "C00000")

    ctx = audit.contexte
    infos = [
        ("Produit", ctx.get("produit")), ("Designer", ctx.get("designer")), ("Plateforme", ctx.get("plateforme")),
        ("Date de l'audit", ctx.get("date").strftime("%d/%m/%Y") if hasattr(ctx.get("date"), "strftime")
         else ctx.get("date")),
    ]
    n = synthese.nb_constats or 1
    indicateurs = [
        ("Constats", synthese.nb_constats),
        ("dont problèmes / points forts", f"{synthese.nb_problemes} / {synthese.nb_points_forts}"),
        ("Constats sans anomalie bloquante", f"{synthese.conformes} ({synthese.conformes / n:.0%})"),
        ("Constats sans aucune remarque", f"{synthese.sans_remarque} ({synthese.sans_remarque / n:.0%})"),
        ("Anomalies bloquantes / avertissements", f"{synthese.nb_bloquants} / {synthese.nb_avertissements}"),
        ("Champs recommandés remplis", f"{synthese.completude_recommandee:.0%}"),
        ("Critères cités (sur 24)", f"{len(ref.criteres) - len(synthese.non_couverts)}"),
    ] + ([("Cellules complétées par l'IA (en violet, à valider)",
           f"{nb_completes} sur {len(audit.completions)} constat(s)")] if nb_completes else [])
    r = 6
    _entete(ws, r, ["Contexte", ""])
    for k, v in infos:
        r += 1
        _ligne(ws, r, [k, v if v not in (None, "") else "(non renseigné)"], bold=True)
    r += 2
    _entete(ws, r, ["Indicateurs", ""])
    for k, v in indicateurs:
        r += 1
        _ligne(ws, r, [k, v], bold=True)

    r += 2
    _entete(ws, r, ["Gravité des problèmes", "Libellé", "Nombre"])
    libelles = ["Pas un problème", "Cosmétique", "Mineur", "Majeur", "Bloquant"]
    for g in range(4, -1, -1):
        r += 1
        _ligne(ws, r, [g, libelles[g], synthese.gravites[g]])

    r += 2
    _entete(ws, r, ["Couverture du référentiel", "Critère", "Principal", "Secondaire"])
    for code, crit in ref.criteres.items():
        r += 1
        p, s = synthese.par_critere.get(code, 0), synthese.secondaires.get(code, 0)
        _ligne(ws, r, [code, f"{crit['label_fr']} ({crit['name']})", p, s], fill=None if p or s else "FCE4D6")
    r += 1
    ws.cell(row=r, column=1, value="En rouge : critères jamais cités. Ce n'est pas forcément une erreur, mais "
                                   "à vérifier avec la checklist du critère.").font = \
        Font(name=FONT, size=9, italic=True, color="7F7F7F")


def _onglet_anomalies(wb, anomalies):
    ws = wb.create_sheet(ONGLET_ANOMALIES, 1)
    _entete(ws, 1, ["Niveau", "Ligne", "Constat", "Champ", "Code", "Message"], [14, 8, 12, 20, 26, 90])
    for i, a in enumerate(anomalies, 2):
        _ligne(ws, i, [LIBELLE_NIVEAU[a.niveau], a.ligne, a.constat, LIBELLES.get(a.champ, a.champ), a.code,
                       a.message],
               fill=COULEURS[a.niveau])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:F{max(len(anomalies) + 1, 2)}"


def exporter(audit, anomalies, synthese, ref, sortie, ia=None):
    """`ia` : résultats de suggestion.verifier_audit ({ligne: Suggestion | ErreurSuggestion}), ou None."""
    wb = load_workbook(audit.chemin)  # sans data_only : les formules du designer sont conservées
    for nom in (ONGLET_SYNTHESE, ONGLET_ANOMALIES):
        if nom in wb.sheetnames:
            del wb[nom]
    _annoter_audit(wb[audit.onglet], audit, anomalies, ref, ia)
    _onglet_synthese(wb, audit, synthese, ref)
    _onglet_anomalies(wb, anomalies)
    for nom in (ONGLET_SYNTHESE, ONGLET_ANOMALIES):
        ws = wb[nom]
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
    wb.active = 0
    for ws in wb.worksheets:
        ws.sheet_view.tabSelected = ws.title == ONGLET_SYNTHESE
    wb.save(sortie)
    return sortie
