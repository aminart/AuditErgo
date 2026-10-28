"""Cache local des réponses de l'IA."""
import copy

import pytest

from audit_ergo import Referentiel, relire
from audit_ergo.cache import CacheSuggestions
from audit_ergo.suggestion import ErreurSuggestion, suggerer
from conftest import CONSTAT_VALIDE
from test_suggestion import FauxClient, erreur_api, reponse_ia

CONSTAT = "Aucun indicateur de chargement après le clic sur Payer."


def test_meme_constat_repris_du_cache(ref):
    client = FauxClient(reponse_ia())
    premiere = suggerer(client, ref, CONSTAT, "Paiement")
    seconde = suggerer(client, ref, CONSTAT, "Paiement")
    assert len(client.appels) == 1
    assert not premiere.depuis_cache and seconde.depuis_cache
    assert seconde.code == premiere.code and seconde.justification == premiere.justification
    assert seconde.usage == {}  # aucun coût


def test_forcer_refait_l_appel(ref):
    client = FauxClient(reponse_ia())
    suggerer(client, ref, CONSTAT)
    s = suggerer(client, ref, CONSTAT, forcer=True)
    assert len(client.appels) == 2 and not s.depuis_cache
    suggerer(client, ref, CONSTAT)
    assert len(client.appels) == 2  # la nouvelle réponse a remplacé l'ancienne dans le cache


@pytest.mark.parametrize("variante", [
    {"constat": CONSTAT + " "  "Le bouton reste actif."},
    {"ecran": "Panier"},
    {"critere_designer": "GUI-01"},
    {"contexte": {"produit": "Autre produit"}},
])
def test_toute_difference_refait_l_appel(ref, variante):
    client = FauxClient(reponse_ia())
    base = {"constat": CONSTAT, "ecran": "Paiement", "critere_designer": None, "contexte": None}
    suggerer(client, ref, **base)
    suggerer(client, ref, **{**base, **variante})
    assert len(client.appels) == 2


def test_referentiel_modifie_invalide_le_cache(ref):
    client = FauxClient(reponse_ia())
    suggerer(client, ref, CONSTAT)
    data = copy.deepcopy(ref.data)
    data["grid"][0]["criteria"][0]["definition"] += " (modifiée)"
    suggerer(client, Referentiel(data), CONSTAT)
    assert len(client.appels) == 2


def test_langue_differente_refait_l_appel(ref):
    client = FauxClient(reponse_ia())
    suggerer(client, ref, CONSTAT, langue="fr")
    suggerer(client, ref, CONSTAT, langue="en")
    assert len(client.appels) == 2


def test_erreurs_et_reponses_invalides_non_memorisees(ref):
    import openai

    client = FauxClient(erreur_api(openai.InternalServerError, 500), reponse_ia(code="XYZ-99"), reponse_ia())
    for _ in range(2):
        with pytest.raises(ErreurSuggestion):
            suggerer(client, ref, CONSTAT)
    assert not suggerer(client, ref, CONSTAT).depuis_cache
    assert len(client.appels) == 3


def test_cache_desactive(ref, monkeypatch):
    monkeypatch.setenv("AUDIT_ERGO_CACHE", "0")
    client = FauxClient(reponse_ia())
    suggerer(client, ref, CONSTAT)
    suggerer(client, ref, CONSTAT)
    assert len(client.appels) == 2 and CacheSuggestions.defaut() is None


def test_fichier_de_cache_corrompu_sans_consequence(ref, cache_isole):
    cache_isole.parent.mkdir(parents=True)
    cache_isole.write_text("pas une base sqlite")
    client = FauxClient(reponse_ia())
    assert suggerer(client, ref, CONSTAT).code == "GUI-03"
    assert suggerer(client, ref, CONSTAT).code == "GUI-03"
    assert len(client.appels) == 2  # cache inutilisable : on appelle l'API, sans planter


def test_taille_et_vider(ref, cache_isole):
    cache = CacheSuggestions(cache_isole)
    assert cache.taille() == 0
    suggerer(FauxClient(reponse_ia()), ref, CONSTAT)
    suggerer(FauxClient(reponse_ia()), ref, CONSTAT, "Panier")
    assert cache.taille() == 2
    assert cache.vider() == 2 and cache.taille() == 0


def test_relecture_d_audit_deux_fois(audit_xlsx, ref, tmp_path):
    chemin = audit_xlsx([CONSTAT_VALIDE, {**CONSTAT_VALIDE, "ecran": "Compte"}])
    client = FauxClient(reponse_ia())
    relire(chemin, tmp_path / "a.xlsx", ref, client)
    assert len(client.appels) == 2
    _, _, _, _, ia = relire(chemin, tmp_path / "b.xlsx", ref, client)
    assert len(client.appels) == 2  # seconde relecture : tout vient du cache
    assert all(s.depuis_cache for s in ia.values())
    relire(chemin, tmp_path / "c.xlsx", ref, client, forcer=True)
    assert len(client.appels) == 4
