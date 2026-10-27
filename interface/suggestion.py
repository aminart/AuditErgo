"""Page « Suggérer un critère » : un constat en entrée, les critères adéquats en sortie."""
import streamlit as st

from audit_ergo.suggestion import LIBELLE_VERDICT, ErreurSuggestion, suggerer
from interface.commun import client, libelle_critere, referentiel

ref = referentiel()
AUCUN = "— Aucun, je veux une proposition —"
BADGE_CONFIANCE = {"haute": ":green-badge[Confiance haute]", "moyenne": ":orange-badge[Confiance moyenne]",
                   "faible": ":red-badge[Confiance faible]"}

st.title("🎯 Suggérer un critère")
st.write("Décrivez un constat : l'IA propose le critère du référentiel qui correspond, explique pourquoi en "
         "s'appuyant sur les définitions, les checklists et les règles de départage, et signale ce qu'il "
         "faudrait préciser.")

cl = client()
if cl is None:
    st.warning("Aucune clé d'API : saisissez-la dans la barre latérale ou dans le fichier .env.")

with st.form("constat"):
    constat = st.text_area("Constat *", height=110, placeholder="Ex. : Après un clic sur « Payer », aucun indicateur "
                           "de chargement n'apparaît pendant 5 secondes ; le bouton reste actif.")
    col1, col2 = st.columns(2)
    ecran = col1.text_input("Écran / page", placeholder="Ex. : Paiement")
    choix = col2.selectbox("Critère que vous envisagez (facultatif, pour le faire vérifier)",
                           [AUCUN] + [libelle_critere(ref, c) for c in ref.criteres])
    with st.expander("Contexte du produit (facultatif, améliore la pertinence)"):
        c1, c2, c3 = st.columns(3)
        contexte = {"produit": c1.text_input("Produit"), "cible": c2.text_input("Cible utilisateurs"),
                    "plateforme": c3.text_input("Plateforme")}
    envoye = st.form_submit_button("Proposer les critères", type="primary", disabled=cl is None)

if envoye:
    if not constat.strip():
        st.error("Le constat est vide.")
    else:
        critere = None if choix == AUCUN else choix.split(" – ")[0]
        with st.spinner("Analyse du constat…"):
            try:
                s = suggerer(cl, ref, constat, ecran or None, critere, contexte)
                st.session_state.setdefault("historique", []).insert(0, (constat, ecran, s))
            except ErreurSuggestion as e:
                st.error(str(e))


def afficher(s):
    c = ref.criteres[s.code]
    st.subheader(f"{s.code} – {c['label_fr']}")
    st.caption(f"{c['name']} · catégorie {ref.categories[c['categorie']]['label_fr']}")
    st.markdown(BADGE_CONFIANCE[s.confiance] + (f" :blue-badge[Règle {s.regle}]" if s.regle != "aucune" else ""))
    st.write(s.justification)
    if s.question_checklist:
        st.markdown(f"**Question de checklist :** _{s.question_checklist}_")

    if s.critere_designer:
        message = f"**Votre choix ({s.critere_designer}) : {LIBELLE_VERDICT[s.verdict]}**\n\n{s.commentaire_verdict}"
        {"confirme": st.success, "a_revoir": st.warning}.get(s.verdict, st.error)(message)

    parties = []
    if s.question_a_se_poser:
        parties.append(f"**À se demander :** {s.question_a_se_poser}")
    if s.precisions_manquantes:
        parties.append("**Pour trancher, préciser :**\n" + "\n".join(f"- {p}" for p in s.precisions_manquantes))
    if parties:
        st.info("\n\n".join(parties))

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Critères secondaires**")
        if s.secondaires:
            for x in s.secondaires:
                st.markdown(f"- **{libelle_critere(ref, x['code'])}** : {x['justification']}")
        else:
            st.caption("Aucun.")
    with col2:
        st.markdown("**Critères envisagés puis écartés**")
        if s.alternatives:
            for x in s.alternatives:
                st.markdown(f"- **{libelle_critere(ref, x['code'])}** : {x['pourquoi_pas']}")
        else:
            st.caption("Aucun.")

    st.markdown("**À coller dans l'audit**")
    st.code(s.ligne_excel(ref), language=None)
    with st.expander(f"Définition et checklist de {s.code}"):
        st.write(c["definition"])
        for q in c["checklist"]:
            st.markdown(f"- {q['q']}")


historique = st.session_state.get("historique", [])
if historique:
    constat_, ecran_, s = historique[0]
    st.divider()
    afficher(s)
    if len(historique) > 1:
        st.divider()
        st.markdown("**Constats précédents (cette session)**")
        for constat_, ecran_, s in historique[1:]:
            with st.expander(f"{s.code} · {(ecran_ + ' · ') if ecran_ else ''}{constat_[:90]}"):
                afficher(s)
