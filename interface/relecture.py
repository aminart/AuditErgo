"""Page « Relire un audit » : contrôles de forme, puis vérification des critères par l'IA (facultative)."""
import hashlib
import tempfile
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import streamlit as st

from audit_ergo import ErreurLecture, relire
from audit_ergo.controles import AVERTISSEMENT, BLOQUANT, INFO
from audit_ergo.export import LIBELLE_NIVEAU
from audit_ergo.lecture import LIBELLES
from audit_ergo.suggestion import LIBELLE_RECO, LIBELLE_VERDICT, ErreurSuggestion
from interface.commun import client, libelle_critere, referentiel

ICONES = {BLOQUANT: "🔴", AVERTISSEMENT: "🟠", INFO: "🔵"}
ICONES_VERDICT = {"confirme": "🟢", "a_revoir": "🟠", "incorrect": "🔴", "non_fourni": "⚪"}
ICONES_RECO = {"bonne": "🟢", "a_ameliorer": "🟠", "hors_sujet": "🔴", "non_fournie": "⚪"}
CHAMPS_IA = {"critere": "critère", "categorie": "catégorie", "recommandation": "recommandation",
             "gravite": "gravité", "secondaires": "critères secondaires", "regle": "règle", "type": "type"}

ref = referentiel()

st.title("🔍 Relire un audit")
st.write("Déposez l'audit Excel, même partiellement rempli : les constats suffisent. L'outil vérifie la forme "
         "de chaque constat et renvoie le fichier annoté. Avec une clé d'API, l'IA **complète** les cellules "
         "vides (catégorie, critère, recommandation, gravité…) et **corrige** ce que vous avez déjà saisi, "
         "sans jamais l'écraser : ses propositions apparaissent en violet et dans les colonnes « IA : … ».")
fichier = st.file_uploader("Audit à relire (.xlsx)", type=["xlsx"])
if not fichier:
    st.stop()


def lancer(contenu, nom, avec_ia, forcer=False, remplir=True):
    """Relecture complète, conservée en session : l'IA n'est appelée qu'à la demande, pas à chaque clic."""
    barre = st.progress(0.0, "Analyse des constats par l'IA…") if avec_ia else None

    def progression(fait, total):
        barre.progress(fait / total, f"Analyse des constats par l'IA : {fait}/{total}")

    with tempfile.TemporaryDirectory() as tmp:
        entree = Path(tmp) / nom
        entree.write_bytes(contenu)
        audit, anomalies, synthese, sortie, ia = relire(entree, Path(tmp) / f"{entree.stem}_relu.xlsx", ref,
                                                        client() if avec_ia else None,
                                                        progression if avec_ia else None, forcer, remplir)
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
if not etat or etat["empreinte"] != empreinte:
    try:
        st.session_state["relecture"] = etat = {"empreinte": empreinte, **lancer(contenu, fichier.name, False)}
    except ErreurLecture as e:
        st.error(f"Impossible de lire ce fichier : {e}")
        st.stop()
    except Exception as e:  # fichier corrompu, protégé par mot de passe…
        st.error(f"Le fichier n'a pas pu être ouvert ({type(e).__name__}). Vérifiez qu'il s'agit d'un .xlsx valide.")
        st.stop()

audit, anomalies, synthese, ia = etat["audit"], etat["anomalies"], etat["synthese"], etat["ia"]

nb_completes = sum(len(a) for a in audit.completions.values())
if synthese.pret:
    st.success("✓ Aucune anomalie bloquante" + (" après complétion par l'IA." if nb_completes else "."))
else:
    st.error(f"⚠ {synthese.nb_bloquants} anomalie(s) bloquante(s) à corriger.")
champs_vides = {a.champ for a in anomalies if a.code == "CHAMP_VIDE"} & {"critere", "categorie", "recommandation",
                                                                          "gravite", "type"}
if ia is None and champs_vides:
    st.info("Des constats n'ont pas encore de " + ", ".join(CHAMPS_IA[c] for c in sorted(champs_vides))
            + " : « Compléter et corriger avec l'IA » peut les remplir pour vous.")
if nb_completes:
    st.info(f"**{nb_completes} cellule(s) complétée(s)** pour {len(audit.completions)} constat(s) : elles sont "
            "en violet dans le fichier, avec l'explication en commentaire. Relisez-les et validez-les.")

col_dl, col_ia = st.columns([1, 2])
col_dl.download_button("📥 Télécharger l'audit " + ("complété" if nb_completes else "annoté"), etat["fichier"],
                       etat["nom_sortie"], type="primary",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
with col_ia:
    if ia is None:
        cl = client()
        n_constats = sum(1 for c in audit.constats if c["constat"])
        remplir = st.checkbox("Remplir les cellules vides avec les propositions de l'IA", value=True,
                              help="Décoché : l'IA donne seulement son avis, dans les colonnes « IA : … ».")
        if st.button(f"🎯 Compléter et corriger avec l'IA ({n_constats} constat(s))", disabled=cl is None,
                     help=None if cl else "Clé d'API requise (barre latérale ou fichier .env)."):
            st.session_state["relecture"] = {"empreinte": empreinte,
                                             **lancer(contenu, fichier.name, True, remplir=remplir)}
            st.rerun()
    else:
        caches = sum(1 for r in ia.values() if not isinstance(r, ErreurSuggestion) and r.depuis_cache)
        st.caption("Analyse par l'IA faite : avis et propositions dans les colonnes « IA : … » du fichier."
                   + (f" {caches} constat(s) repris du cache, sans coût." if caches else ""))
        if caches and st.button("Refaire l'analyse IA sans le cache"):
            st.session_state["relecture"] = {"empreinte": empreinte,
                                             **lancer(contenu, fichier.name, True, forcer=True)}
            st.rerun()

ctx = audit.contexte
st.caption(" · ".join(str(v) for v in (ctx.get("produit"), ctx.get("designer"), ctx.get("plateforme")) if v)
           or "Onglet « Contexte » non renseigné")

n = synthese.nb_constats or 1
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Constats", synthese.nb_constats)
c1.caption(f"{synthese.nb_problemes} problème(s) · {synthese.nb_points_forts} point(s) fort(s)")
c2.metric("Sans anomalie bloquante", f"{synthese.conformes / n:.0%}")
c3.metric("Sans aucune remarque", f"{synthese.sans_remarque / n:.0%}")
c4.metric("Champs facultatifs remplis", f"{synthese.completude_recommandee:.0%}",
          help="Parcours, capture, fréquence, impact, priorité.")
c5.metric("Critères cités", f"{len(ref.criteres) - len(synthese.non_couverts)} / {len(ref.criteres)}")

onglets = ["Anomalies", "Couverture du référentiel", "Gravité"] + (["Analyse IA"] if ia is not None else [])
onglet_anomalies, onglet_couverture, onglet_gravite, *onglet_ia = st.tabs(onglets)

with onglet_anomalies:
    if not anomalies:
        st.write("Aucune anomalie détectée.")
    else:
        niveaux = st.multiselect("Niveaux affichés", [BLOQUANT, AVERTISSEMENT, INFO],
                                 default=[BLOQUANT, AVERTISSEMENT, INFO], format_func=lambda n: LIBELLE_NIVEAU[n])
        lignes = [{"Niveau": f"{ICONES[a.niveau]} {LIBELLE_NIVEAU[a.niveau]}", "Ligne": a.ligne,
                   "Constat": a.constat, "Champ": LIBELLES.get(a.champ, a.champ), "Message": a.message}
                  for a in anomalies if a.niveau in niveaux]
        st.dataframe(pd.DataFrame(lignes), hide_index=True, use_container_width=True,
                     column_config={"Message": st.column_config.TextColumn(width="large")})

with onglet_couverture:
    st.write("Nombre de constats par critère. Un critère jamais cité n'est pas forcément une erreur, "
             "mais mérite un passage sur sa checklist.")
    lignes = [{"Code": code, "Critère": crit["label_fr"],
               "Principal": synthese.par_critere.get(code, 0), "Secondaire": synthese.secondaires.get(code, 0)}
              for code, crit in ref.criteres.items()]
    st.dataframe(pd.DataFrame(lignes), hide_index=True, use_container_width=True)
    if synthese.non_couverts:
        st.warning("Jamais cités : " + ", ".join(f"{c} ({ref.criteres[c]['label_fr']})"
                                                 for c in synthese.non_couverts))

with onglet_gravite:
    libelles = ["0 – Pas un problème", "1 – Cosmétique", "2 – Mineur", "3 – Majeur", "4 – Bloquant"]
    st.bar_chart(pd.DataFrame({"Problèmes": [synthese.gravites[g] for g in range(5)]}, index=libelles))

if onglet_ia:
    with onglet_ia[0]:
        ok = [r for r in ia.values() if not isinstance(r, ErreurSuggestion)]
        a_revoir = [r for r in ok if r.verdict in ("a_revoir", "incorrect")]
        recos = [r for r in ok if r.reco_statut in ("a_ameliorer", "hors_sujet")]
        st.write(f"{len(ok)} constat(s) analysé(s) · **{len(a_revoir)} critère(s) à revoir** · "
                 f"**{len(recos)} recommandation(s) à améliorer**"
                 + (f" · {len(ia) - len(ok)} erreur(s)" if len(ok) < len(ia) else ""))
        par_ligne = {c.ligne: c for c in audit.constats}
        lignes = []
        for ligne, r in sorted(ia.items()):
            c = par_ligne[ligne]
            completes = audit.completions.get(ligne, {})
            if isinstance(r, ErreurSuggestion):
                lignes.append({"Ligne": ligne, "Constat": c.ref, "Critère": "⚠ Erreur", "Proposition IA": str(r)})
                continue
            if "critere" in completes:
                critere = "🟣 Rempli par l'IA"
            else:
                critere = f"{ICONES_VERDICT[r.verdict]} {LIBELLE_VERDICT[r.verdict].lstrip('✓✗ ')}"
            if "recommandation" in completes:
                reco = "🟣 Rédigée par l'IA"
            elif r.reco_statut != "non_fournie":
                reco = f"{ICONES_RECO[r.reco_statut]} {LIBELLE_RECO[r.reco_statut].lstrip('✓✗ ')}"
            else:
                reco = ""
            lignes.append({
                "Ligne": ligne, "Constat": c.ref, "Critère": critere,
                "Proposition IA": libelle_critere(ref, r.code) + f" ({r.confiance})",
                "Recommandation": reco,
                "Recommandation IA": r.reco_a_retenir,
                "Gravité IA": r.gravite,
                "Explication": r.commentaire_verdict or r.justification,
            })
        st.dataframe(pd.DataFrame(lignes), hide_index=True, use_container_width=True,
                     column_config={"Recommandation IA": st.column_config.TextColumn(width="large"),
                                    "Explication": st.column_config.TextColumn(width="large")})

with st.expander("Détail technique"):
    st.json({"onglet": audit.onglet, "ligne_entete": audit.ligne_entete,
             "colonnes_reconnues": list(audit.colonnes), "colonnes_ignorees": audit.colonnes_inconnues,
             "synthese": asdict(synthese)}, expanded=False)
