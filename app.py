"""Interface web : streamlit run app.py (servie uniquement sur ce poste, voir .streamlit/config.toml)"""
import streamlit as st

st.set_page_config(page_title="Audit ergonomique assisté", page_icon="🔍", layout="wide")

from interface.commun import barre_laterale, referentiel, tr  # noqa: E402

barre_laterale(referentiel())
st.navigation([
    st.Page("interface/suggestion.py", title=tr("page.suggestion"), icon="🎯", default=True),
    st.Page("interface/relecture.py", title=tr("page.relecture"), icon="🔍"),
]).run()
