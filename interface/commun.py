"""Éléments partagés par les pages de l'interface."""
from pathlib import Path

import streamlit as st

from audit_ergo import Referentiel
from audit_ergo.cache import CacheSuggestions
from audit_ergo.suggestion import ErreurSuggestion, adresse_api, cle_disponible, client_ou_none, format_api

TEMPLATE = Path(__file__).resolve().parent.parent / "template" / "Audit_ergonomique_template.xlsx"
CLE_SESSION = "cle_api_saisie"


@st.cache_resource
def referentiel():
    return Referentiel.charger()


def client():
    """Client Anthropic (clé du .env / de l'environnement, sinon clé saisie dans la barre latérale), ou None."""
    try:
        return client_ou_none(st.session_state.get(CLE_SESSION) or None)
    except ErreurSuggestion as e:  # CA_BUNDLE introuvable ou illisible
        st.error(str(e))
        return None


def barre_laterale(ref):
    with st.sidebar:
        st.caption(f"Référentiel v{ref.version} · {len(ref.criteres)} critères · {len(ref.regles)} règles de départage")
        st.download_button("Télécharger le template vierge", TEMPLATE.read_bytes(), TEMPLATE.name,
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.divider()
        st.subheader("IA")
        if cle_disponible():
            st.success("Clé d'API configurée.")
            try:
                st.caption(f"API : {adresse_api() or 'Anthropic'} · format {format_api()}")
            except ErreurSuggestion as e:
                st.error(str(e))
        else:
            st.text_input("Clé d'API Anthropic", type="password", key=CLE_SESSION,
                          help="Utilisée seulement pendant cette session, jamais enregistrée. Pour ne plus la "
                               "saisir, renseignez API_KEY dans le fichier .env (voir .env.exemple).")
            if not st.session_state.get(CLE_SESSION):
                st.info("Sans clé, les contrôles de forme fonctionnent ; les suggestions de critères sont "
                        "désactivées.")
        cache = CacheSuggestions.defaut()
        if cache:
            n = cache.taille()
            st.caption(f"{n} réponse(s) de l'IA mémorisée(s) : un constat déjà analysé n'est pas refacturé.")
            if n and st.button("Vider le cache de l'IA"):
                cache.vider()
                st.rerun()


def libelle_critere(ref, code):
    c = ref.criteres[code]
    return f"{code} – {c['label_fr']} ({c['name']})"
