"""Page « Relire un audit » : contrôles de forme, puis complétion et correction par l'IA locale (facultative)."""
import hashlib
import tempfile
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import streamlit as st

from audit_ergo import ErreurLecture, generer_rapport, relire
from audit_ergo.controles import AVERTISSEMENT, BLOQUANT, INFO
from audit_ergo.i18n import GRAVITES, libelle_gravite, t
from audit_ergo.lecture import libelle_champ
from audit_ergo.suggestion import ErreurSuggestion, libelle_reco, libelle_verdict
from interface.commun import XLSX, client, langue, referentiel

ref = referentiel()
lg = langue()
ICONES = {BLOQUANT: "🔴", AVERTISSEMENT: "🟠", INFO: "🔵"}
ICONES_VERDICT = {"confirme": "🟢", "a_revoir": "🟠", "incorrect": "🔴", "non_fourni": "⚪"}
ICONES_RECO = {"bonne": "🟢", "a_ameliorer": "🟠", "hors_sujet": "🔴", "non_fournie": "⚪"}
TXT = {
    "titre": ("🔍 Relire un audit", "🔍 Review an audit"),
    "intro": ("Déposez l'audit Excel, même partiellement rempli : les constats suffisent. Le template d'origine est "
              "accepté aussi. L'outil vérifie la forme de chaque constat et renvoie le fichier annoté. L'IA locale "
              "**complète** les cellules vides (catégorie, critère, recommandation, gravité…) et **corrige** ce que "
              "vous avez déjà saisi, sans jamais l'écraser : ses propositions apparaissent en violet et dans les "
              "colonnes « IA : … ».",
              "Drop the Excel audit, even partly filled: the findings are enough. The original template is accepted "
              "too. The tool checks each finding and returns the annotated file. The local AI **fills in** empty cells "
              "(criteria, sub-criterion, recommendation, severity…) and **corrects** what you already entered, never "
              "overwriting it: its proposals appear in purple and in the “AI: …” columns."),
    "fichier": ("Audit à relire (.xlsx)", "Audit to review (.xlsx)"),
    "progression": ("Analyse des constats par le modèle local : {f}/{n}", "Local model analysing findings: {f}/{n}"),
    "illisible": ("Impossible de lire ce fichier : {e}", "Cannot read this file: {e}"),
    "corrompu": ("Le fichier n'a pas pu être ouvert ({e}). Vérifiez qu'il s'agit d'un .xlsx valide.",
                 "The file could not be opened ({e}). Check that it is a valid .xlsx file."),
    "pret": ("✓ Aucune anomalie bloquante.", "✓ No blocking issue."),
    "pret_ia": ("✓ Aucune anomalie bloquante après complétion par l'IA.", "✓ No blocking issue after AI completion."),
    "bloquants": ("⚠ {n} anomalie(s) bloquante(s) à corriger.", "⚠ {n} blocking issue(s) to fix."),
    "vides": ("Des constats n'ont pas encore de {liste} : « Compléter et corriger avec l'IA » peut les remplir pour vous.",
              "Some findings have no {liste} yet: “Complete and correct with the AI” can fill them in for you."),
    "completes": ("**{n} cellule(s) complétée(s)** pour {c} constat(s) : elles sont en violet dans le fichier, avec "
                  "l'explication en commentaire. Relisez-les et validez-les.",
                  "**{n} cell(s) filled in** for {c} finding(s): they are purple in the file, with the explanation in "
                  "a comment. Review and validate them."),
    "telecharger": ("📥 Télécharger l'audit annoté", "📥 Download the annotated audit"),
    "telecharger_complete": ("📥 Télécharger l'audit complété", "📥 Download the completed audit"),
    "remplir": ("Remplir les cellules vides avec les propositions de l'IA",
                "Fill empty cells with the AI's proposals"),
    "remplir_aide": ("Décoché : l'IA donne seulement son avis, dans les colonnes « IA : … ».",
                     "Unchecked: the AI only gives its opinion, in the “AI: …” columns."),
    "bouton_ia": ("🎯 Compléter et corriger avec l'IA ({n} constat(s))",
                  "🎯 Complete and correct with the AI ({n} finding(s))"),
    "duree": ("Le modèle local traite un constat à la fois : comptez de quelques secondes à une minute par constat "
              "selon le poste.", "The local model processes one finding at a time: allow a few seconds to a minute "
              "per finding depending on the computer."),
    "sans_ia": ("IA indisponible : voir la barre latérale.", "AI unavailable: see the sidebar."),
    "ia_faite": ("Analyse par l'IA faite : avis et propositions dans les colonnes « IA : … » du fichier.",
                 "AI analysis done: opinions and proposals in the “AI: …” columns of the file."),
    "depuis_cache": (" {n} constat(s) repris du cache.", " {n} finding(s) from cache."),
    "refaire": ("Refaire l'analyse IA sans le cache", "Redo the AI analysis without the cache"),
    "contexte_vide": ("Onglet « Contexte » non renseigné", "“Context” sheet not filled in"),
    "m.constats": ("Constats", "Findings"),
    "m.types": ("{p} problème(s) · {f} point(s) fort(s)", "{p} issue(s) · {f} strength(s)"),
    "m.conformes": ("Sans anomalie bloquante", "Without blocking issue"),
    "m.sans_remarque": ("Sans aucune remarque", "Without any remark"),
    "m.facultatifs": ("Champs facultatifs remplis", "Optional fields filled"),
    "m.facultatifs_aide": ("Parcours, tâche, capture, type de recommandation.",
                           "Workflow, task, screenshot, type of recommendation."),
    "m.cites": ("Critères cités", "Sub-criteria used"),
    "o.anomalies": ("Anomalies", "Issues"), "o.couverture": ("Couverture du référentiel", "Referential coverage"),
    "o.gravite": ("Gravité", "Severity"), "o.ia": ("Analyse IA", "AI analysis"),
    "aucune_anomalie": ("Aucune anomalie détectée.", "No issue found."),
    "niveaux": ("Niveaux affichés", "Levels shown"),
    "c.niveau": ("Niveau", "Level"), "c.ligne": ("Ligne", "Row"), "c.constat": ("Constat", "Finding"),
    "c.champ": ("Champ", "Field"), "c.message": ("Message", "Message"), "c.code": ("Code", "Code"),
    "c.critere": ("Critère", "Sub-criterion"), "c.principal": ("Principal", "Main"),
    "c.secondaire": ("Secondaire", "Secondary"), "c.proposition": ("Proposition IA", "AI proposal"),
    "c.reco": ("Recommandation", "Recommendation"), "c.reco_ia": ("Recommandation IA", "AI recommendation"),
    "c.gravite_ia": ("Gravité IA", "AI severity"), "c.explication": ("Explication", "Explanation"),
    "couverture_intro": ("Nombre de constats par critère. Un critère jamais cité n'est pas forcément une erreur, mais "
                         "mérite un passage sur sa checklist.", "Number of findings per sub-criterion. A sub-criterion "
                         "never used is not necessarily an error, but deserves a look at its checklist."),
    "jamais": ("Jamais cités : {liste}", "Never used: {liste}"),
    "problemes": ("Problèmes", "Issues"),
    "resume_ia": ("{n} constat(s) analysé(s) · **{c} critère(s) à revoir** · **{r} recommandation(s) à améliorer**",
                  "{n} finding(s) analysed · **{c} sub-criteria to review** · **{r} recommendation(s) to improve**"),
    "erreurs": (" · {n} erreur(s)", " · {n} error(s)"),
    "rempli_ia": ("🟣 Rempli par l'IA", "🟣 Filled by the AI"),
    "redigee_ia": ("🟣 Rédigée par l'IA", "🟣 Written by the AI"),
    "erreur": ("⚠ Erreur", "⚠ Error"),
    "technique": ("Détail technique", "Technical details"),
    "r.titre": ("📄 Rapport Word de synthèse", "📄 Summary report (Word)"),
    "r.intro": ("Rapport à remettre à l'équipe produit : synthèse générale et maturité UX, problèmes principaux "
                "regroupés par thématique, grands chantiers UX/UI hiérarchisés, quick wins et suites à moyen et long "
                "terme. Les chiffres sont calculés à partir de l'audit ; l'IA rédige les analyses.",
                "Report for the product team: executive summary and UX maturity, main issues grouped by theme, "
                "prioritised UX/UI initiatives, quick wins and medium to long-term next steps. Figures are computed "
                "from the audit; the AI writes the analysis."),
    "r.avant_ia": ("Conseil : lancez d'abord « Compléter et corriger avec l'IA », pour que le rapport parte d'un "
                   "audit complet (critères, gravités, recommandations).",
                   "Tip: run “Complete and correct with the AI” first, so that the report starts from a complete "
                   "audit (criteria, severities, recommendations)."),
    "r.bouton": ("Générer le rapport", "Generate the report"),
    "r.progression": ("Rédaction du rapport par l'IA : étape {f}/{n}", "AI writing the report: step {f}/{n}"),
    "r.sans_ia": ("Rapport produit sans IA : les faits sont complets, les passages surlignés en jaune sont à rédiger.",
                  "Report produced without AI: facts are complete, passages highlighted in yellow are to be written."),
    "r.erreur": ("L'IA n'a pas pu tout rédiger ({e}) : les passages surlignés en jaune sont à rédiger.",
                 "The AI could not write everything ({e}): passages highlighted in yellow are to be written."),
    "r.ok": ("Rapport rédigé avec l'IA : relisez-le avant de le diffuser.",
             "Report drafted with the AI: review it before sharing."),
    "r.telecharger": ("📥 Télécharger le rapport Word", "📥 Download the Word report"),
}
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
CHAMPS_VIDES = ["type", "categorie", "critere", "gravite", "recommandation"]


def x(cle, **valeurs):
    fr, en = TXT[cle]
    texte = en if lg == "en" else fr
    return texte.format(**valeurs) if valeurs else texte


st.title(x("titre"))
st.write(x("intro"))
fichier = st.file_uploader(x("fichier"), type=["xlsx"])
if not fichier:
    st.stop()


def lancer(contenu, nom, avec_ia, forcer=False, remplir=True):
    """Relecture complète, conservée en session : l'IA n'est appelée qu'à la demande, pas à chaque clic."""
    barre = st.progress(0.0, x("progression", f=0, n="…")) if avec_ia else None

    def progression(fait, total):
        barre.progress(fait / total, x("progression", f=fait, n=total))

    with tempfile.TemporaryDirectory() as tmp:
        entree = Path(tmp) / nom
        entree.write_bytes(contenu)
        audit, anomalies, synthese, sortie, ia = relire(entree, Path(tmp) / f"{entree.stem}_relu.xlsx", ref,
                                                        client() if avec_ia else None,
                                                        progression if avec_ia else None, forcer, remplir, lg)
        resultat = Path(sortie).read_bytes()
    if audit.completions:
        sortie = Path(sortie).with_name(Path(sortie).name.replace("_relu", "_complete"))
    if barre:
        barre.empty()
    return {"audit": audit, "anomalies": anomalies, "synthese": synthese, "nom_sortie": Path(sortie).name,
            "fichier": resultat, "ia": ia}


contenu = fichier.getvalue()
empreinte = hashlib.sha256(contenu).hexdigest()
etat = st.session_state.get("relecture")
# La langue fait partie de l'empreinte : changer de langue relance les contrôles (sans IA) dans la bonne langue
if not etat or etat["empreinte"] != (empreinte, lg):
    try:
        st.session_state["relecture"] = etat = {"empreinte": (empreinte, lg), **lancer(contenu, fichier.name, False)}
    except ErreurLecture as e:
        st.error(x("illisible", e=e))
        st.stop()
    except Exception as e:  # fichier corrompu, protégé par mot de passe…
        st.error(x("corrompu", e=type(e).__name__))
        st.stop()

audit, anomalies, synthese, ia = etat["audit"], etat["anomalies"], etat["synthese"], etat["ia"]

nb_completes = sum(len(a) for a in audit.completions.values())
if synthese.pret:
    st.success(x("pret_ia") if nb_completes else x("pret"))
else:
    st.error(x("bloquants", n=synthese.nb_bloquants))
champs_vides = [c for c in CHAMPS_VIDES if any(a.code == "CHAMP_VIDE" and a.champ == c for a in anomalies)]
if ia is None and champs_vides:
    st.info(x("vides", liste=", ".join(libelle_champ(c, lg).lower() for c in champs_vides)))
if nb_completes:
    st.info(x("completes", n=nb_completes, c=len(audit.completions)))

col_dl, col_ia = st.columns([1, 2])
col_dl.download_button(x("telecharger_complete") if nb_completes else x("telecharger"), etat["fichier"],
                       etat["nom_sortie"], type="primary", mime=XLSX)
with col_ia:
    if ia is None:
        cl = client()
        n_constats = sum(1 for c in audit.constats if c["constat"])
        remplir = st.checkbox(x("remplir"), value=True, help=x("remplir_aide"))
        if st.button(x("bouton_ia", n=n_constats), disabled=cl is None, help=None if cl else x("sans_ia")):
            st.session_state["relecture"] = {"empreinte": (empreinte, lg),
                                             **lancer(contenu, fichier.name, True, remplir=remplir)}
            st.rerun()
        st.caption(x("duree"))
    else:
        caches = sum(1 for r in ia.values() if not isinstance(r, ErreurSuggestion) and r.depuis_cache)
        st.caption(x("ia_faite") + (x("depuis_cache", n=caches) if caches else ""))
        if caches and st.button(x("refaire")):
            st.session_state["relecture"] = {"empreinte": (empreinte, lg),
                                             **lancer(contenu, fichier.name, True, forcer=True)}
            st.rerun()

st.divider()
st.subheader(x("r.titre"))
st.write(x("r.intro"))
if ia is None:
    st.caption(x("r.avant_ia"))
# Le rapport correspond à un état de l'audit : il est à refaire après une complétion par l'IA
cle_rapport = (empreinte, lg, ia is not None)
rapport = st.session_state.get("rapport")
if st.button(x("r.bouton")):
    barre = st.progress(0.0, x("r.progression", f=0, n=2))
    r, octets = generer_rapport(audit, ref, None, client(), lg,
                                progression=lambda fait, total: barre.progress(fait / total,
                                                                               x("r.progression", f=fait, n=total)))
    barre.empty()
    st.session_state["rapport"] = rapport = {"cle": cle_rapport, "octets": octets, "ia": r.ia, "erreur": r.erreur}
if rapport and rapport["cle"] == cle_rapport:
    if rapport["erreur"]:
        st.warning(x("r.erreur", e=rapport["erreur"]))
    elif rapport["ia"]:
        st.success(x("r.ok"))
    else:
        st.info(x("r.sans_ia"))
    st.download_button(x("r.telecharger"), rapport["octets"], f"{Path(fichier.name).stem}_rapport.docx",
                       mime=DOCX, type="primary")
st.divider()

ctx = audit.contexte
st.caption(" · ".join(str(v) for v in (ctx.get("produit"), ctx.get("designer"), ctx.get("plateforme")) if v)
           or x("contexte_vide"))

n = synthese.nb_constats or 1
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric(x("m.constats"), synthese.nb_constats)
c1.caption(x("m.types", p=synthese.nb_problemes, f=synthese.nb_points_forts))
c2.metric(x("m.conformes"), f"{synthese.conformes / n:.0%}")
c3.metric(x("m.sans_remarque"), f"{synthese.sans_remarque / n:.0%}")
c4.metric(x("m.facultatifs"), f"{synthese.completude_recommandee:.0%}", help=x("m.facultatifs_aide"))
c5.metric(x("m.cites"), f"{len(ref.criteres) - len(synthese.non_couverts)} / {len(ref.criteres)}")

onglets = [x("o.anomalies"), x("o.couverture"), x("o.gravite")] + ([x("o.ia")] if ia is not None else [])
onglet_anomalies, onglet_couverture, onglet_gravite, *onglet_ia = st.tabs(onglets)

with onglet_anomalies:
    if not anomalies:
        st.write(x("aucune_anomalie"))
    else:
        niveaux = st.multiselect(x("niveaux"), [BLOQUANT, AVERTISSEMENT, INFO], default=[BLOQUANT, AVERTISSEMENT, INFO],
                                 format_func=lambda niv: t(f"niveau.{niv}", lg))
        lignes = [{x("c.niveau"): f"{ICONES[a.niveau]} {t(f'niveau.{a.niveau}', lg)}", x("c.ligne"): a.ligne,
                   x("c.constat"): a.constat, x("c.champ"): libelle_champ(a.champ, lg) if a.champ else "",
                   x("c.message"): a.message} for a in anomalies if a.niveau in niveaux]
        st.dataframe(pd.DataFrame(lignes), hide_index=True, use_container_width=True,
                     column_config={x("c.message"): st.column_config.TextColumn(width="large")})

with onglet_couverture:
    st.write(x("couverture_intro"))
    lignes = [{x("c.code"): code, x("c.critere"): ref.libelle_critere(code, lg).split(" – ", 1)[1],
               x("c.principal"): synthese.par_critere.get(code, 0), x("c.secondaire"): synthese.secondaires.get(code, 0)}
              for code in ref.criteres]
    st.dataframe(pd.DataFrame(lignes), hide_index=True, use_container_width=True)
    if synthese.non_couverts:
        st.warning(x("jamais", liste=", ".join(ref.libelle_critere(c, lg) for c in synthese.non_couverts)))

with onglet_gravite:
    index = [f"{g} – {libelle_gravite(g, lg)}" for g in GRAVITES]
    st.bar_chart(pd.DataFrame({x("problemes"): [synthese.gravites[g] for g in GRAVITES]}, index=index))

if onglet_ia:
    with onglet_ia[0]:
        ok = [r for r in ia.values() if not isinstance(r, ErreurSuggestion)]
        a_revoir = [r for r in ok if r.verdict in ("a_revoir", "incorrect")]
        recos = [r for r in ok if r.reco_statut in ("a_ameliorer", "hors_sujet")]
        st.write(x("resume_ia", n=len(ok), c=len(a_revoir), r=len(recos))
                 + (x("erreurs", n=len(ia) - len(ok)) if len(ok) < len(ia) else ""))
        par_ligne = {c.ligne: c for c in audit.constats}
        lignes = []
        for ligne, r in sorted(ia.items()):
            c = par_ligne[ligne]
            completes = audit.completions.get(ligne, {})
            if isinstance(r, ErreurSuggestion):
                lignes.append({x("c.ligne"): ligne, x("c.constat"): c.ref, x("c.critere"): x("erreur"),
                               x("c.proposition"): str(r)})
                continue
            if "critere" in completes:
                critere = x("rempli_ia")
            else:
                critere = f"{ICONES_VERDICT[r.verdict]} {libelle_verdict(r.verdict, lg).lstrip('✓✗ ')}"
            if "recommandation" in completes:
                reco = x("redigee_ia")
            elif r.reco_statut != "non_fournie":
                reco = f"{ICONES_RECO[r.reco_statut]} {libelle_reco(r.reco_statut, lg).lstrip('✓✗ ')}"
            else:
                reco = ""
            lignes.append({
                x("c.ligne"): ligne, x("c.constat"): c.ref, x("c.critere"): critere,
                x("c.proposition"): ref.libelle_critere(r.code, lg) + f" ({t(f'confiance.{r.confiance}', lg)})",
                x("c.reco"): reco, x("c.reco_ia"): r.reco_a_retenir,
                x("c.gravite_ia"): libelle_gravite(r.gravite, lg) if r.gravite else "",
                x("c.explication"): r.commentaire_verdict or r.justification,
            })
        st.dataframe(pd.DataFrame(lignes), hide_index=True, use_container_width=True,
                     column_config={x("c.reco_ia"): st.column_config.TextColumn(width="large"),
                                    x("c.explication"): st.column_config.TextColumn(width="large")})

with st.expander(x("technique")):
    st.json({"onglet": audit.onglet, "ligne_entete": audit.ligne_entete, "langue_fichier": audit.langue,
             "colonnes_reconnues": list(audit.colonnes), "colonnes_ignorees": audit.colonnes_inconnues,
             "synthese": asdict(synthese)}, expanded=False)
