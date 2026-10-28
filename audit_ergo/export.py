"""Export : le fichier du designer, annoté (et complété), avec deux onglets de relecture en plus.

Les annotations sont rédigées dans la langue choisie dans l'application (`langue`).
"""
from datetime import date

from openpyxl import load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .controles import AVERTISSEMENT, BLOQUANT, INFO, NIVEAUX
from .i18n import GRAVITES, ajouter, libelle_gravite, lire_gravite, t
from .lecture import libelle_champ

FONT = "Arial"
NAVY = "1F3864"
COULEURS = {BLOQUANT: "F8CBAD", AVERTISSEMENT: "FFE699", INFO: "DDEBF7"}
COULEURS_VERDICT = {"confirme": "E2EFDA", "a_revoir": "FFE699", "incorrect": "F8CBAD", "non_fourni": "EDEDED"}
COULEURS_RECO = {"bonne": "E2EFDA", "a_ameliorer": "FFE699", "hors_sujet": "F8CBAD", "non_fournie": "EDEDED"}
VIOLET = "E4DFEC"  # cellule complétée par l'application : à valider par le designer
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")

# Les en-têtes ajoutés commencent par « Relecture » / « Review » ou « IA » / « AI » : la lecture d'un fichier
# déjà relu les ignore (voir lecture.py)
ajouter({
    "onglet.synthese": {"fr": "Relecture – Synthèse", "en": "Review – Summary"},
    "onglet.anomalies": {"fr": "Relecture – Anomalies", "en": "Review – Issues"},
    "col.niveau": {"fr": "Relecture : niveau", "en": "Review: level"},
    "col.remarques": {"fr": "Relecture : remarques", "en": "Review: remarks"},
    "col.ia_critere": {"fr": "IA : critère suggéré", "en": "AI: suggested sub-criterion"},
    "col.ia_verdict": {"fr": "IA : verdict critère", "en": "AI: sub-criterion verdict"},
    "col.ia_justification": {"fr": "IA : justification critère", "en": "AI: sub-criterion justification"},
    "col.ia_reco": {"fr": "IA : recommandation", "en": "AI: recommendation"},
    "col.ia_avis_reco": {"fr": "IA : avis recommandation", "en": "AI: recommendation review"},
    "col.ia_gravite": {"fr": "IA : gravité", "en": "AI: severity"},
    "col.ia_remarques": {"fr": "IA : remarques", "en": "AI: remarks"},
    "niveau.bloquant": {"fr": "Bloquant", "en": "Blocking"},
    "niveau.avertissement": {"fr": "Avertissement", "en": "Warning"},
    "niveau.info": {"fr": "Info", "en": "Info"},
    "conforme": {"fr": "✓ Conforme", "en": "✓ Compliant"},
    "propose_rempli": {"fr": "Proposé (cellule remplie)", "en": "Proposed (cell filled)"},
    "proposee_remplie": {"fr": "Proposée (cellule remplie)", "en": "Proposed (cell filled)"},
    "erreur": {"fr": "Erreur", "en": "Error"},
    "confiance": {"fr": "confiance {niveau}", "en": "{niveau} confidence"},
    "vous": {"fr": "vous : {valeur}", "en": "you: {valeur}"},
    "sur_critere": {"fr": "Sur le critère choisi : {texte}", "en": "On the chosen sub-criterion: {texte}"},
    "rem.gravite": {"fr": "Gravité : {texte}", "en": "Severity: {texte}"},
    "rem.complementaires": {"fr": "Recommandations complémentaires : {texte}", "en": "Additional recommendations: {texte}"},
    "rem.question": {"fr": "À se demander : {texte}", "en": "To consider: {texte}"},
    "rem.preciser": {"fr": "À préciser : {texte}", "en": "To clarify: {texte}"},
    "comm.ia": {"fr": "Proposé par l'IA, à valider.", "en": "Proposed by the AI, to be validated."},
    "comm.auto": {"fr": "Complété automatiquement, à vérifier.", "en": "Filled automatically, to be checked."},
    "comm.auteur_completion": {"fr": "Complétion automatique", "en": "Automatic completion"},
    "comm.auteur_relecture": {"fr": "Relecture automatique", "en": "Automatic review"},
    "syn.titre": {"fr": "Relecture automatique de l'audit", "en": "Automatic audit review"},
    "syn.sous_titre_completion": {"fr": "{n} cellule(s) complétée(s) automatiquement, en violet dans l'onglet « {onglet} » : à valider.",
                                  "en": "{n} cell(s) filled automatically, in purple in the “{onglet}” sheet: to be validated."},
    "syn.sous_titre": {"fr": "Contrôles de forme.", "en": "Form checks."},
    "syn.pret": {"fr": "✓ Prêt pour la relecture des critères", "en": "✓ Ready for criteria review"},
    "syn.bloquants": {"fr": "⚠ {n} anomalie(s) bloquante(s) à corriger", "en": "⚠ {n} blocking issue(s) to fix"},
    "syn.contexte": {"fr": "Contexte", "en": "Context"},
    "syn.produit": {"fr": "Produit", "en": "Product"},
    "syn.designer": {"fr": "Designer", "en": "Designer"},
    "syn.plateforme": {"fr": "Plateforme", "en": "Platform"},
    "syn.date": {"fr": "Date de l'audit", "en": "Audit date"},
    "syn.non_renseigne": {"fr": "(non renseigné)", "en": "(not provided)"},
    "syn.indicateurs": {"fr": "Indicateurs", "en": "Indicators"},
    "syn.constats": {"fr": "Constats", "en": "Findings"},
    "syn.problemes": {"fr": "dont problèmes / points forts", "en": "of which issues / strengths"},
    "syn.conformes": {"fr": "Constats sans anomalie bloquante", "en": "Findings without blocking issue"},
    "syn.sans_remarque": {"fr": "Constats sans aucune remarque", "en": "Findings without any remark"},
    "syn.anomalies": {"fr": "Anomalies bloquantes / avertissements", "en": "Blocking issues / warnings"},
    "syn.facultatifs": {"fr": "Champs facultatifs remplis", "en": "Optional fields filled"},
    "syn.cites": {"fr": "Critères cités (sur {n})", "en": "Sub-criteria used (out of {n})"},
    "syn.completees": {"fr": "Cellules complétées par l'IA (en violet, à valider)", "en": "Cells filled by the AI (purple, to validate)"},
    "syn.completees_val": {"fr": "{n} sur {c} constat(s)", "en": "{n} across {c} finding(s)"},
    "syn.gravites": {"fr": "Gravité des problèmes", "en": "Issue severity"},
    "syn.libelle": {"fr": "Libellé", "en": "Label"},
    "syn.nombre": {"fr": "Nombre", "en": "Count"},
    "syn.couverture": {"fr": "Couverture du référentiel", "en": "Referential coverage"},
    "syn.critere": {"fr": "Critère", "en": "Sub-criterion"},
    "syn.principal": {"fr": "Principal", "en": "Main"},
    "syn.secondaire": {"fr": "Secondaire", "en": "Secondary"},
    "syn.note_couverture": {"fr": "En rouge : critères jamais cités. Ce n'est pas forcément une erreur, mais à vérifier avec la checklist du critère.",
                            "en": "In red: sub-criteria never used. Not necessarily an error, but worth checking against the criterion's checklist."},
    "ano.entetes": {"fr": "Niveau|Ligne|Constat|Champ|Code|Message", "en": "Level|Row|Finding|Field|Code|Message"},
})


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
            cell = ws.cell(row=audit.ligne_entete, column=col, value=libelle_champ(champ, audit.langue))
            cell.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor=NAVY)
            cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
            ws.column_dimensions[get_column_letter(col)].width = 45 if champ == "recommandation" else 24
            audit.colonnes[champ] = col


def _ecrire_completions(ws, audit, langue):
    from .completion import IA

    for ligne, ajouts in audit.completions.items():
        for champ, (valeur, origine, explication) in ajouts.items():
            cell = ws.cell(row=ligne, column=audit.colonnes[champ], value=valeur)
            cell.fill = PatternFill("solid", fgColor=VIOLET)
            cell.font = Font(name=FONT, size=10, italic=True)
            cell.alignment = WRAP
            entete = t("comm.ia" if origine == IA else "comm.auto", langue)
            _commenter(cell, f"{entete}\n{explication}", t("comm.auteur_completion", langue))


def _colonnes_relecture(langue, avec_ia):
    cols = [("col.niveau", 14), ("col.remarques", 60)]
    if avec_ia:
        cols += [("col.ia_critere", 32), ("col.ia_verdict", 16), ("col.ia_justification", 50), ("col.ia_reco", 50),
                 ("col.ia_avis_reco", 30), ("col.ia_gravite", 16), ("col.ia_remarques", 50)]
    return [(cle, t(cle, langue), largeur) for cle, largeur in cols]


def _annoter_audit(ws, audit, anomalies, ref, ia, langue):
    par_ligne = {}
    for a in anomalies:
        if a.ligne:
            par_ligne.setdefault(a.ligne, []).append(a)

    _ajouter_colonnes_manquantes(ws, audit)
    _ecrire_completions(ws, audit, langue)

    # Une relecture précédente (dans l'une ou l'autre langue) a pu ajouter ces colonnes : on les réutilise
    titres_connus = {t(cle, l): cle for cle, _, _ in _colonnes_relecture("fr", True) for l in ("fr", "en")}
    existantes = {titres_connus[c.value]: c.column for c in ws[audit.ligne_entete] if c.value in titres_connus}
    prochaine = ws.max_column + 1
    cols = {}
    for cle, titre, largeur in _colonnes_relecture(langue, ia is not None):
        if cle in existantes:
            cols[cle] = existantes[cle]
        else:
            cols[cle], prochaine = prochaine, prochaine + 1
        cell = ws.cell(row=audit.ligne_entete, column=cols[cle], value=titre)
        cell.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="7030A0" if cle in ("col.niveau", "col.remarques") else "2E75B6")
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        ws.column_dimensions[get_column_letter(cols[cle])].width = largeur
        for r in range(audit.ligne_entete + 1, ws.max_row + 1):
            ws.cell(row=r, column=cols[cle]).value = None

    if ia is not None:
        _colonnes_ia(ws, audit, ref, ia, cols, langue)

    for c in audit.constats:
        liste = par_ligne.get(c.ligne, [])
        pire = min((NIVEAUX.index(a.niveau) for a in liste), default=None)
        niveau = NIVEAUX[pire] if pire is not None else None
        cell = ws.cell(row=c.ligne, column=cols["col.niveau"],
                       value=t(f"niveau.{niveau}", langue) if niveau else t("conforme", langue))
        cell.fill = PatternFill("solid", fgColor=COULEURS[niveau] if niveau else "E2EFDA")
        cell.font = Font(name=FONT, size=10, bold=True)
        cell.alignment = WRAP
        remarques = "\n".join(f"• {a.message}" for a in liste)
        r = ws.cell(row=c.ligne, column=cols["col.remarques"], value=remarques or None)
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
            _commenter(cible, "\n".join(a.message for a in liste_champ), t("comm.auteur_relecture", langue))


def _colonnes_ia(ws, audit, ref, ia, cols, langue):
    from .suggestion import ErreurSuggestion, libelle_reco, libelle_verdict

    for c in audit.constats:
        res = ia.get(c.ligne)
        if res is None:
            continue
        cellules = {cle: ws.cell(row=c.ligne, column=cols[cle]) for cle in cols if cle.startswith("col.ia_")}
        for cell in cellules.values():
            cell.font = Font(name=FONT, size=10)
            cell.alignment = WRAP
        if isinstance(res, ErreurSuggestion):
            cellules["col.ia_verdict"].value = t("erreur", langue)
            cellules["col.ia_remarques"].value = str(res)
            continue
        completes = audit.completions.get(c.ligne, {})

        cellules["col.ia_critere"].value = res.ligne_excel(ref, langue)
        verdict = cellules["col.ia_verdict"]
        if res.critere_designer:
            statut = res.verdict
            verdict.value = libelle_verdict(statut, langue)
        else:
            statut = "non_fourni"
            verdict.value = t("propose_rempli", langue) if "critere" in completes else libelle_verdict(statut, langue)
        if res.confiance != "haute":
            verdict.value += " · " + t("confiance", langue, niveau=t(f"confiance.{res.confiance}", langue))
        verdict.fill = PatternFill("solid", fgColor=COULEURS_VERDICT[statut])

        justif = res.justification_critere
        if res.commentaire_verdict:
            justif += "\n" + t("sur_critere", langue, texte=res.commentaire_verdict)
        cellules["col.ia_justification"].value = justif

        cellules["col.ia_reco"].value = res.reco_a_retenir or None
        avis = cellules["col.ia_avis_reco"]
        if res.reco_statut != "non_fournie":
            avis.value = libelle_reco(res.reco_statut, langue) + (f" : {res.reco_commentaire}" if res.reco_commentaire else "")
            avis.fill = PatternFill("solid", fgColor=COULEURS_RECO[res.reco_statut])
        elif "recommandation" in completes:
            avis.value = t("proposee_remplie", langue)

        if res.gravite is not None:
            grav = cellules["col.ia_gravite"]
            grav.value = f"{res.gravite} – {libelle_gravite(res.gravite, langue)}"
            g_designer = lire_gravite(c["gravite"]) if "gravite" not in completes else None
            if g_designer is not None and g_designer != res.gravite:
                grav.value += f" ({t('vous', langue, valeur=libelle_gravite(g_designer, langue))})"
                if abs(g_designer - res.gravite) >= 2:
                    grav.fill = PatternFill("solid", fgColor=COULEURS_VERDICT["a_revoir"])

        details = []
        if res.justification_gravite:
            details.append(t("rem.gravite", langue, texte=res.justification_gravite))
        if res.reco_complementaires:
            details.append(t("rem.complementaires", langue, texte=" ; ".join(res.reco_complementaires)))
        if res.question_a_se_poser:
            details.append(t("rem.question", langue, texte=res.question_a_se_poser))
        if res.precisions_manquantes:
            details.append(t("rem.preciser", langue, texte=" ; ".join(res.precisions_manquantes)))
        cellules["col.ia_remarques"].value = "\n".join(details) or None


def _onglet_synthese(wb, audit, synthese, ref, langue):
    ws = wb.create_sheet(t("onglet.synthese", langue), 0)
    ws.sheet_view.showGridLines = False
    for col, largeur in zip("ABCD", (42, 50, 14, 14)):
        ws.column_dimensions[col].width = largeur
    ws["A1"] = t("syn.titre", langue)
    ws["A1"].font = Font(name=FONT, size=16, bold=True, color=NAVY)
    nb_completes = sum(len(a) for a in audit.completions.values())
    ws["A2"] = (f"v{ref.version} · {date.today():%d/%m/%Y}. "
                + (t("syn.sous_titre_completion", langue, n=nb_completes, onglet=audit.onglet) if nb_completes
                   else t("syn.sous_titre", langue)))
    ws["A2"].font = Font(name=FONT, size=9, italic=True, color="7F7F7F")

    ws["A4"] = t("syn.pret", langue) if synthese.pret else t("syn.bloquants", langue, n=synthese.nb_bloquants)
    ws["A4"].font = Font(name=FONT, size=13, bold=True, color="375623" if synthese.pret else "C00000")

    ctx = audit.contexte
    date_audit = ctx.get("date")
    infos = [(t("syn.produit", langue), ctx.get("produit")), (t("syn.designer", langue), ctx.get("designer")),
             (t("syn.plateforme", langue), ctx.get("plateforme")),
             (t("syn.date", langue), date_audit.strftime("%d/%m/%Y") if hasattr(date_audit, "strftime") else date_audit)]
    n = synthese.nb_constats or 1
    indicateurs = [
        (t("syn.constats", langue), synthese.nb_constats),
        (t("syn.problemes", langue), f"{synthese.nb_problemes} / {synthese.nb_points_forts}"),
        (t("syn.conformes", langue), f"{synthese.conformes} ({synthese.conformes / n:.0%})"),
        (t("syn.sans_remarque", langue), f"{synthese.sans_remarque} ({synthese.sans_remarque / n:.0%})"),
        (t("syn.anomalies", langue), f"{synthese.nb_bloquants} / {synthese.nb_avertissements}"),
        (t("syn.facultatifs", langue), f"{synthese.completude_recommandee:.0%}"),
        (t("syn.cites", langue, n=len(ref.criteres)), f"{len(ref.criteres) - len(synthese.non_couverts)}"),
    ] + ([(t("syn.completees", langue), t("syn.completees_val", langue, n=nb_completes, c=len(audit.completions)))]
         if nb_completes else [])
    r = 6
    _entete(ws, r, [t("syn.contexte", langue), ""])
    for k, v in infos:
        r += 1
        _ligne(ws, r, [k, v if v not in (None, "") else t("syn.non_renseigne", langue)], bold=True)
    r += 2
    _entete(ws, r, [t("syn.indicateurs", langue), ""])
    for k, v in indicateurs:
        r += 1
        _ligne(ws, r, [k, v], bold=True)

    r += 2
    _entete(ws, r, [t("syn.gravites", langue), t("syn.libelle", langue), t("syn.nombre", langue)])
    for g in sorted(GRAVITES, reverse=True):
        r += 1
        _ligne(ws, r, [g, libelle_gravite(g, langue), synthese.gravites[g]])

    r += 2
    _entete(ws, r, [t("syn.couverture", langue), t("syn.critere", langue), t("syn.principal", langue),
                    t("syn.secondaire", langue)])
    for code in ref.criteres:
        r += 1
        p, s = synthese.par_critere.get(code, 0), synthese.secondaires.get(code, 0)
        _ligne(ws, r, [code, ref.libelle_critere(code, langue).split(" – ", 1)[1], p, s],
               fill=None if p or s else "FCE4D6")
    r += 1
    ws.cell(row=r, column=1, value=t("syn.note_couverture", langue)).font = \
        Font(name=FONT, size=9, italic=True, color="7F7F7F")


def _onglet_anomalies(wb, anomalies, langue):
    ws = wb.create_sheet(t("onglet.anomalies", langue), 1)
    _entete(ws, 1, t("ano.entetes", langue).split("|"), [14, 8, 12, 20, 26, 90])
    for i, a in enumerate(anomalies, 2):
        _ligne(ws, i, [t(f"niveau.{a.niveau}", langue), a.ligne, a.constat,
                       libelle_champ(a.champ, langue) if a.champ else None, a.code, a.message],
               fill=COULEURS[a.niveau])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:F{max(len(anomalies) + 1, 2)}"


def exporter(audit, anomalies, synthese, ref, sortie, ia=None, langue="fr"):
    """`ia` : résultats de suggestion.verifier_audit ({ligne: Suggestion | ErreurSuggestion}), ou None."""
    wb = load_workbook(audit.chemin)  # sans data_only : les formules du designer sont conservées
    for nom in [t(cle, l) for cle in ("onglet.synthese", "onglet.anomalies") for l in ("fr", "en")]:
        if nom in wb.sheetnames:
            del wb[nom]
    _annoter_audit(wb[audit.onglet], audit, anomalies, ref, ia, langue)
    _onglet_synthese(wb, audit, synthese, ref, langue)
    _onglet_anomalies(wb, anomalies, langue)
    for ws in wb.worksheets[:2]:
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
    wb.active = 0
    for i, ws in enumerate(wb.worksheets):
        ws.sheet_view.tabSelected = i == 0
    wb.save(sortie)
    return sortie
