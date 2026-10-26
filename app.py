"""Interface web de relecture : streamlit run app.py"""
import tempfile
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import streamlit as st

from audit_ergo import ErreurLecture, Referentiel, relire
from audit_ergo.controles import AVERTISSEMENT, BLOQUANT, INFO
from audit_ergo.export import LIBELLE_NIVEAU
from audit_ergo.lecture import LIBELLES

TEMPLATE = Path(__file__).parent / "template" / "Audit_ergonomique_template.xlsx"
ICONES = {BLOQUANT: "🔴", AVERTISSEMENT: "🟠", INFO: "🔵"}

st.set_page_config(page_title="Relecture d'audit ergonomique", page_icon="🔍", layout="wide")


@st.cache_resource
def referentiel():
    return Referentiel.charger()


ref = referentiel()

with st.sidebar:
    st.header("Relecture d'audit")
    st.write("Déposez l'audit Excel rempli. L'outil vérifie la forme de chaque constat et renvoie le fichier "
             "annoté : cellules surlignées, commentaires et deux onglets de synthèse.")
    st.caption(f"Référentiel v{ref.version} · {len(ref.criteres)} critères · {len(ref.regles)} règles de départage")
    st.download_button("Télécharger le template vierge", TEMPLATE.read_bytes(), TEMPLATE.name,
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.info("Version 1 : contrôles de forme uniquement. La vérification des critères par l'IA arrivera "
            "dans la version suivante.")

st.title("🔍 Relecture d'audit ergonomique")
fichier = st.file_uploader("Audit à relire (.xlsx)", type=["xlsx"])
if not fichier:
    st.stop()

with tempfile.TemporaryDirectory() as tmp:
    entree = Path(tmp) / fichier.name
    entree.write_bytes(fichier.getvalue())
    try:
        audit, anomalies, synthese, sortie = relire(entree, Path(tmp) / f"{entree.stem}_relu.xlsx", ref)
    except ErreurLecture as e:
        st.error(f"Impossible de lire ce fichier : {e}")
        st.stop()
    except Exception as e:  # fichier corrompu, protégé par mot de passe…
        st.error(f"Le fichier n'a pas pu être ouvert ({type(e).__name__}). Vérifiez qu'il s'agit d'un .xlsx valide.")
        st.stop()
    resultat = Path(sortie).read_bytes()

if synthese.pret:
    st.success("✓ Aucune anomalie bloquante : l'audit est prêt pour la relecture des critères.")
else:
    st.error(f"⚠ {synthese.nb_bloquants} anomalie(s) bloquante(s) à corriger.")

st.download_button("📥 Télécharger l'audit annoté", resultat, Path(sortie).name, type="primary",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

ctx = audit.contexte
st.caption(" · ".join(str(v) for v in (ctx.get("produit"), ctx.get("designer"), ctx.get("plateforme")) if v)
           or "Onglet « Contexte » non renseigné")

n = synthese.nb_constats or 1
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Constats", synthese.nb_constats)
c1.caption(f"{synthese.nb_problemes} problème(s) · {synthese.nb_points_forts} point(s) fort(s)")
c2.metric("Sans anomalie bloquante", f"{synthese.conformes / n:.0%}")
c3.metric("Sans aucune remarque", f"{synthese.sans_remarque / n:.0%}")
c4.metric("Champs complétés", f"{synthese.completude_recommandee:.0%}")
c5.metric("Critères cités", f"{len(ref.criteres) - len(synthese.non_couverts)} / {len(ref.criteres)}")

onglet_anomalies, onglet_couverture, onglet_gravite = st.tabs(["Anomalies", "Couverture du référentiel", "Gravité"])

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

with st.expander("Détail technique"):
    st.json({"onglet": audit.onglet, "ligne_entete": audit.ligne_entete,
             "colonnes_reconnues": list(audit.colonnes), "colonnes_ignorees": audit.colonnes_inconnues,
             "synthese": asdict(synthese)}, expanded=False)
