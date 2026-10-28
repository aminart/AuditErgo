"""Page « Suggérer un critère » : un constat en entrée ; critère, recommandation et gravité en sortie."""
import streamlit as st

from audit_ergo.i18n import GRAVITES, TYPES_RECO, libelle_gravite, t
from audit_ergo.suggestion import ErreurSuggestion, libelle_reco, libelle_verdict, suggerer
from interface.commun import client, langue, referentiel

ref = referentiel()
lg = langue()
TXT = {
    "titre": ("🎯 Suggérer un critère", "🎯 Suggest a criterion"),
    "intro": ("Décrivez un constat : l'IA locale propose le critère du référentiel qui correspond (en s'appuyant sur les "
              "définitions, les checklists et les règles de départage), une recommandation et une gravité. Si vous "
              "indiquez vos propres choix, elle les vérifie.",
              "Describe a finding: the local AI proposes the matching sub-criterion of the referential (based on the "
              "definitions, checklists and tie-break rules), a recommendation and a severity. If you enter your own "
              "choices, it checks them."),
    "sans_ia": ("IA indisponible : voir la barre latérale.", "AI unavailable: see the sidebar."),
    "constat": ("Constat *", "Finding *"),
    "constat_ex": ("Ex. : Après un clic sur « Payer », aucun indicateur de chargement n'apparaît pendant 5 secondes ; "
                   "le bouton reste actif.", "E.g.: After clicking “Pay”, no loading indicator appears for 5 seconds; "
                   "the button stays active."),
    "ecran": ("Écran / emplacement", "Screen / location"),
    "ecran_ex": ("Ex. : Paiement", "E.g.: Payment"),
    "critere": ("Critère que vous envisagez (facultatif, pour le faire vérifier)",
                "Sub-criterion you are considering (optional, to have it checked)"),
    "aucun": ("— Aucun, je veux une proposition —", "— None, I want a proposal —"),
    "reco": ("Votre recommandation (facultatif, pour la faire vérifier ou améliorer)",
             "Your recommendation (optional, to have it checked or improved)"),
    "gravite": ("Gravité que vous envisagez (facultatif)", "Severity you are considering (optional)"),
    "non_renseignee": ("— Non renseignée —", "— Not set —"),
    "contexte": ("Contexte du produit (facultatif, améliore la pertinence)",
                 "Product context (optional, improves relevance)"),
    "produit": ("Produit", "Product"), "cible": ("Cible utilisateurs", "Target users"),
    "plateforme": ("Plateforme", "Platform"),
    "forcer": ("Nouvelle analyse, même si ce constat a déjà été analysé",
               "New analysis, even if this finding was already analysed"),
    "forcer_aide": ("Par défaut, une réponse déjà obtenue pour exactement le même constat est reprise sans "
                    "recalcul.", "By default, an answer already obtained for exactly the same finding is reused."),
    "proposer": ("Proposer", "Suggest"),
    "vide": ("Le constat est vide.", "The finding is empty."),
    "attente": ("Analyse du constat par le modèle local… (cela peut prendre une à deux minutes)",
                "The local model is analysing the finding… (this can take a minute or two)"),
    "confiance": ("Confiance {n}", "{n} confidence"),
    "regle": ("Règle {r}", "Rule {r}"),
    "cache": ("Repris du cache", "From cache"),
    "categorie": ("catégorie {c}", "criteria {c}"),
    "checklist": ("**Question de checklist :** _{q}_", "**Checklist question:** _{q}_"),
    "votre_choix": ("Votre choix ({c}) : {v}", "Your choice ({c}): {v}"),
    "a_se_demander": ("**À se demander :** {q}", "**To consider:** {q}"),
    "preciser": ("**Pour trancher, préciser :**", "**To decide, clarify:**"),
    "secondaires": ("**Critères secondaires**", "**Secondary criteria**"),
    "ecartes": ("**Critères envisagés puis écartés**", "**Sub-criteria considered and rejected**"),
    "aucun_critere": ("Aucun.", "None."),
    "titre_reco": ("#### Recommandation", "#### Recommendation"),
    "votre_reco": ("Votre recommandation : {v}", "Your recommendation: {v}"),
    "reco_amelioree": ("**Version améliorée de votre recommandation**", "**Improved version of your recommendation**"),
    "reco_ia": ("**Recommandation proposée par l'IA**", "**Recommendation proposed by the AI**"),
    "reco_autre": ("**Autre formulation proposée par l'IA**", "**Alternative wording proposed by the AI**"),
    "type_reco": ("Type : {t}", "Type: {t}"),
    "pistes": ("**Pistes complémentaires**", "**Additional ideas**"),
    "titre_gravite": ("#### Gravité proposée : {g}", "#### Proposed severity: {g}"),
    "a_coller": ("**À coller dans l'audit**", "**To paste into the audit**"),
    "col_critere": ("Critère principal", "Sub-criterion"),
    "col_justification": ("Justification du critère", "Criterion justification"),
    "definition": ("Définition et checklist de {c}", "Definition and checklist of {c}"),
    "precedents": ("**Constats précédents (cette session)**", "**Previous findings (this session)**"),
}


def x(cle, **valeurs):
    fr, en = TXT[cle]
    texte = en if lg == "en" else fr
    return texte.format(**valeurs) if valeurs else texte


BADGES = {"haute": "green", "moyenne": "orange", "faible": "red"}
GRAVITES_LISTE = [x("non_renseignee")] + [f"{g} – {libelle_gravite(g, lg)}" for g in GRAVITES]

st.title(x("titre"))
st.write(x("intro"))

cl = client()
if cl is None:
    st.warning(x("sans_ia"))

with st.form("constat"):
    constat = st.text_area(x("constat"), height=110, placeholder=x("constat_ex"))
    col1, col2 = st.columns(2)
    ecran = col1.text_input(x("ecran"), placeholder=x("ecran_ex"))
    choix = col2.selectbox(x("critere"), [x("aucun")] + [ref.libelle_critere(c, lg) for c in ref.criteres])
    reco_designer = st.text_area(x("reco"), height=70)
    gravite_choisie = st.selectbox(x("gravite"), GRAVITES_LISTE)
    with st.expander(x("contexte")):
        c1, c2, c3 = st.columns(3)
        contexte = {"produit": c1.text_input(x("produit")), "cible": c2.text_input(x("cible")),
                    "plateforme": c3.text_input(x("plateforme"))}
    forcer = st.checkbox(x("forcer"), help=x("forcer_aide"))
    envoye = st.form_submit_button(x("proposer"), type="primary", disabled=cl is None)

if envoye:
    if not constat.strip():
        st.error(x("vide"))
    else:
        critere = None if choix == x("aucun") else choix.split(" – ")[0]
        gravite = None if gravite_choisie == GRAVITES_LISTE[0] else int(gravite_choisie[0])
        with st.spinner(x("attente")):
            try:
                s = suggerer(cl, ref, constat, ecran or None, critere, contexte, forcer=forcer,
                             recommandation_designer=reco_designer or None, gravite_designer=gravite, langue=lg)
                st.session_state.setdefault("historique", []).insert(0, (constat, ecran, s))
            except ErreurSuggestion as e:
                st.error(str(e))


def afficher(s):
    c = ref.criteres[s.code]
    st.subheader(ref.libelle_critere(s.code, lg).split(" (")[0])
    st.caption(f"{c['name'] if lg == 'fr' else c['label_fr']} · "
               + x("categorie", c=ref.libelle_categorie(c["categorie"], lg).split(" – ")[1]))
    badges = f":{BADGES[s.confiance]}-badge[{x('confiance', n=t(f'confiance.{s.confiance}', lg))}]"
    if s.regle != "aucune":
        badges += f" :blue-badge[{x('regle', r=s.regle)}]"
    if s.depuis_cache:
        badges += f" :gray-badge[{x('cache')}]"
    st.markdown(badges)
    st.write(s.justification)
    if s.question_checklist:
        st.markdown(x("checklist", q=s.question_checklist))

    if s.critere_designer:
        message = f"**{x('votre_choix', c=s.critere_designer, v=libelle_verdict(s.verdict, lg))}**\n\n{s.commentaire_verdict}"
        {"confirme": st.success, "a_revoir": st.warning}.get(s.verdict, st.error)(message)

    parties = []
    if s.question_a_se_poser:
        parties.append(x("a_se_demander", q=s.question_a_se_poser))
    if s.precisions_manquantes:
        parties.append(x("preciser") + "\n" + "\n".join(f"- {p}" for p in s.precisions_manquantes))
    if parties:
        st.info("\n\n".join(parties))

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(x("secondaires"))
        for v in s.secondaires:
            st.markdown(f"- **{ref.libelle_critere(v['code'], lg)}** : {v['justification']}")
        if not s.secondaires:
            st.caption(x("aucun_critere"))
    with col2:
        st.markdown(x("ecartes"))
        for v in s.alternatives:
            st.markdown(f"- **{ref.libelle_critere(v['code'], lg)}** : {v['pourquoi_pas']}")
        if not s.alternatives:
            st.caption(x("aucun_critere"))

    st.markdown(x("titre_reco"))
    if s.reco_statut != "non_fournie":
        message = f"**{x('votre_reco', v=libelle_reco(s.reco_statut, lg))}**" + (
            f"\n\n{s.reco_commentaire}" if s.reco_commentaire else "")
        {"bonne": st.success, "a_ameliorer": st.warning}.get(s.reco_statut, st.error)(message)
    if s.reco_amelioree:
        st.markdown(x("reco_amelioree"))
        st.code(s.reco_amelioree, language=None, wrap_lines=True)
    if s.reco_proposee and s.reco_statut != "bonne":
        st.markdown(x("reco_autre") if s.reco_amelioree else x("reco_ia"))
        st.code(s.reco_proposee, language=None, wrap_lines=True)
    if s.type_reco:
        st.caption(x("type_reco", t=TYPES_RECO[s.type_reco][lg]))
    if s.reco_complementaires:
        st.markdown(x("pistes") + "\n" + "\n".join(f"- {v}" for v in s.reco_complementaires))

    if s.gravite is not None:
        st.markdown(x("titre_gravite", g=f"{s.gravite} – {libelle_gravite(s.gravite, lg)}"))
        st.write(s.justification_gravite)

    st.markdown(x("a_coller"))
    st.caption(x("col_critere"))
    st.code(s.ligne_excel(ref, lg), language=None)
    if not s.critere_designer or s.verdict == "confirme":
        st.caption(x("col_justification"))
        st.code(s.justification_critere, language=None, wrap_lines=True)
    with st.expander(x("definition", c=s.code)):
        st.write(c["definition"])
        for q in c["checklist"]:
            st.markdown(f"- {q['q']}")


historique = st.session_state.get("historique", [])
if historique:
    st.divider()
    afficher(historique[0][2])
    if len(historique) > 1:
        st.divider()
        st.markdown(x("precedents"))
        for constat_, ecran_, s in historique[1:]:
            with st.expander(f"{s.code} · {(ecran_ + ' · ') if ecran_ else ''}{constat_[:90]}"):
                afficher(s)
