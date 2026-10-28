"""Éléments partagés par les pages de l'interface : langue, référentiel, modèle local, barre latérale."""
import os
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

from audit_ergo import Referentiel
from audit_ergo.cache import CacheSuggestions
from audit_ergo.i18n import LANGUES, langue_defaut
from audit_ergo.suggestion import MODELE, ErreurSuggestion, adresse_api, client_ou_none, est_locale, ia_configuree

RACINE = Path(__file__).resolve().parent.parent
TEMPLATES = {"fr": RACINE / "template" / "Audit_ergonomique_FR.xlsx", "en": RACINE / "template" / "Ergonomic_audit_EN.xlsx"}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

TEXTES = {
    "langue": ("Langue", "Language"),
    "page.suggestion": ("Suggérer un critère", "Suggest a criterion"),
    "page.relecture": ("Relire un audit", "Review an audit"),
    "referentiel": ("Référentiel v{v} · {n} critères · {r} règles de départage",
                    "Referential v{v} · {n} sub-criteria · {r} tie-break rules"),
    "template": ("Télécharger le template vierge", "Download the blank template"),
    "ia": ("IA", "AI"),
    "ia.modele": ("Modèle : **{m}**", "Model: **{m}**"),
    "ia.connexion": ("`API_BASE` : {a}  \n`API_KEY` : {k}  \n`CA_BUNDLE` : {c}",
                     "`API_BASE`: {a}  \n`API_KEY`: {k}  \n`CA_BUNDLE`: {c}"),
    "ia.cle_oui": ("renseignée", "set"), "ia.cle_non": ("non renseignée", "not set"),
    "ia.ca_non": ("non renseigné", "not set"),
    "ia.local": ("🔒 Modèle sur ce poste : aucune donnée n'en sort.", "🔒 Model on this computer: no data leaves it."),
    "ia.distant": ("Les constats sont envoyés au serveur {h}.", "Findings are sent to server {h}."),
    "ia.tester": ("Tester la connexion", "Test the connection"),
    "ia.ok": ("Modèle disponible.", "Model available."),
    "ia.cle": ("Clé refusée par le serveur : vérifiez API_KEY dans .env.", "Key refused by the server: check API_KEY in .env."),
    "ia.absent": ("Le serveur répond, mais le modèle « {m} » n'y est pas installé. Modèles disponibles : {liste}. "
                  "Corrigez AUDIT_ERGO_MODELE dans .env, ou installez-le (« ollama pull {m} »).",
                  "The server answers, but model “{m}” is not installed. Available models: {liste}. Fix "
                  "AUDIT_ERGO_MODELE in .env, or install it (“ollama pull {m}”)."),
    "ia.injoignable": ("Le modèle ne répond pas à {a}. Vérifiez API_BASE, API_KEY et CA_BUNDLE dans .env, "
                       "ou lancez Ollama (ou LM Studio) s'il est sur ce poste.",
                       "The model does not answer at {a}. Check API_BASE, API_KEY and CA_BUNDLE in .env, "
                       "or start Ollama (or LM Studio) if it runs on this computer."),
    "ia.desactivee": ("IA désactivée (AUDIT_ERGO_IA=0) : seuls les contrôles de forme sont disponibles.",
                      "AI disabled (AUDIT_ERGO_IA=0): only form checks are available."),
    "cache": ("{n} réponse(s) de l'IA mémorisée(s) : un constat déjà analysé n'est pas recalculé.",
              "{n} AI answer(s) stored: a finding already analysed is not recomputed."),
    "cache.vider": ("Vider le cache de l'IA", "Clear the AI cache"),
}


def langue():
    return st.session_state.get("langue") or langue_defaut()


def tr(cle, **valeurs):
    """Texte de l'interface dans la langue choisie."""
    fr, en = TEXTES[cle]
    texte = en if langue() == "en" else fr
    return texte.format(**valeurs) if valeurs else texte


@st.cache_resource
def referentiel():
    return Referentiel.charger()


def client():
    """Client du modèle local, ou None (IA désactivée ou configuration refusée, avec un message)."""
    try:
        return client_ou_none()
    except ErreurSuggestion as e:  # API_BASE mal formée, CA_BUNDLE invalide…
        st.error(str(e))
        return None


def _tester_connexion():
    cl = client()
    if cl is None:
        return
    import openai

    try:
        modeles = [m.id for m in cl.models.list()]
    except openai.NotFoundError:  # passerelle sans /v1/models : elle répond, mais ne liste pas ses modèles
        st.success(tr("ia.ok"))
        return
    except openai.AuthenticationError:
        st.error(tr("ia.cle"))
        return
    except Exception as e:  # serveur injoignable, certificat refusé…
        st.error(tr("ia.injoignable", a=adresse_api()) + f"  \n`{type(e).__name__} : {e}`")
        return
    # Ollama nomme les modèles « nom:étiquette » ; « mistral-small » désigne « mistral-small:latest »
    if any(m == MODELE or m.split(":")[0] == MODELE for m in modeles):
        st.success(tr("ia.ok"))
    else:
        st.warning(tr("ia.absent", m=MODELE, liste=", ".join(modeles) or "—"))


def barre_laterale(ref):
    with st.sidebar:
        st.selectbox(tr("langue"), list(LANGUES), format_func=LANGUES.get, key="langue",
                     index=list(LANGUES).index(langue()))
        st.caption(tr("referentiel", v=ref.version, n=len(ref.criteres), r=len(ref.regles)))
        modele = TEMPLATES[langue()]
        st.download_button(tr("template"), modele.read_bytes(), modele.name, mime=XLSX)
        st.divider()
        st.subheader(tr("ia"))
        if not ia_configuree():
            st.info(tr("ia.desactivee"))
            return
        st.caption(tr("ia.modele", m=MODELE))
        cle, ca = os.environ.get("API_KEY", "").strip(), os.environ.get("CA_BUNDLE", "").strip()
        st.caption(tr("ia.connexion", a=adresse_api(), k=tr("ia.cle_oui") if cle else tr("ia.cle_non"),
                      c=Path(ca).name if ca else tr("ia.ca_non")))
        adresse = adresse_api()
        st.caption(tr("ia.local") if est_locale(adresse) else tr("ia.distant", h=urlparse(adresse).hostname))
        if st.button(tr("ia.tester")):
            _tester_connexion()
        cache = CacheSuggestions.defaut()
        if cache:
            n = cache.taille()
            st.caption(tr("cache", n=n))
            if n and st.button(tr("cache.vider")):
                cache.vider()
                st.rerun()
