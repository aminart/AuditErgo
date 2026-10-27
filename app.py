"""Interface web : streamlit run app.py"""
import streamlit as st

st.set_page_config(page_title="Audit ergonomique assisté", page_icon="🔍", layout="wide")

from interface.commun import barre_laterale, referentiel  # noqa: E402

barre_laterale(referentiel())
st.navigation([
    st.Page("interface/suggestion.py", title="Suggérer un critère", icon="🎯", default=True),
    st.Page("interface/relecture.py", title="Relire un audit", icon="🔍"),
]).run()
