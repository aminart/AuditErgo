"""Éléments partagés par les pages de l'interface."""
from pathlib import Path

import streamlit as st

from audit_ergo import Referentiel
from audit_ergo.suggestion import cle_disponible, client_ou_none

TEMPLATE = Path(__file__).resolve().parent.parent / "template" / "Audit_ergonomique_template.xlsx"
CLE_SESSION = "cle_api_saisie"


@st.cache_resource
def referentiel():
    return Referentiel.charger()


def client():
    """Client Anthropic (clé du .env / de l'environnement, sinon clé saisie dans la barre latérale), ou None."""
    return client_ou_none(st.session_state.get(CLE_SESSION) or None)


def barre_laterale(ref):
    with st.sidebar:
        st.caption(f"Référentiel v{ref.version} · {len(ref.criteres)} critères · {len(ref.regles)} règles de départage")
        st.download_button("Télécharger le template vierge", TEMPLATE.read_bytes(), TEMPLATE.name,
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.divider()
        st.subheader("IA")
        if cle_disponible():
            st.success("Clé d'API configurée.")
        else:
            st.text_input("Clé d'API Anthropic", type="password", key=CLE_SESSION,
                          help="Utilisée seulement pendant cette session, jamais enregistrée. Pour ne plus la "
                               "saisir, placez-la dans le fichier .env (voir .env.exemple).")
            if not st.session_state.get(CLE_SESSION):
                st.info("Sans clé, les contrôles de forme fonctionnent ; les suggestions de critères sont "
                        "désactivées.")


def libelle_critere(ref, code):
    c = ref.criteres[code]
    return f"{code} – {c['label_fr']} ({c['name']})"
