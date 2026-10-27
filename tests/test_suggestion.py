"""Tests du moteur de suggestion, avec un faux client à la place de l'API (aucune clé nécessaire)."""
import json
from types import SimpleNamespace

import anthropic
import httpx2 as httpx  # client HTTP utilisé par le SDK anthropic 2.x
import pytest
from openpyxl import load_workbook

from audit_ergo import relire
from audit_ergo.suggestion import ErreurSuggestion, construire_requete, suggerer, verifier_audit
from audit_ergo.lecture import lire_audit
from conftest import CONSTAT_VALIDE


def reponse_ia(code="GUI-03", **modif):
    data = {
        "critere_principal": {"code": code, "confiance": "haute", "justification": "Réaction après l'action.",
                              "regle": "R1", "question_checklist": "Is information displayed during the loading?"},
        "criteres_secondaires": [{"code": "ERR-01", "justification": "Double clic possible."}],
        "alternatives": [{"code": "GUI-01", "pourquoi_pas": "Concerne l'avant de l'action."}],
        "question_a_se_poser": "",
        "precisions_manquantes": [],
        "verdict_designer": {"statut": "a_revoir", "commentaire": "GUI-01 décrit l'avant de l'action."},
    }
    data.update(modif)
    return data


class FauxClient:
    """Imite client.beta.messages.create : renvoie les réponses données, dans l'ordre (ou lève l'exception)."""

    def __init__(self, *reponses, stop_reason="end_turn"):
        self.reponses, self.appels, self.stop_reason = list(reponses), [], stop_reason
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **requete):
        self.appels.append(requete)
        r = self.reponses.pop(0) if len(self.reponses) > 1 else self.reponses[0]
        if isinstance(r, Exception):
            raise r
        return SimpleNamespace(
            stop_reason=self.stop_reason,
            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=json.dumps(r))],
            usage=SimpleNamespace(input_tokens=100, output_tokens=50, cache_read_input_tokens=9000,
                                  cache_creation_input_tokens=0),
        )


def erreur_api(cls, status):
    reponse = httpx.Response(status, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    return cls("erreur", response=reponse, body=None)


def test_requete(ref):
    req = construire_requete(ref, "  Aucun indicateur de chargement.  ", "Paiement", "GUI-01 – Incitation",
                             {"produit": "Boutique", "cible": None})
    assert req["model"] == "claude-opus-5-5"
    referentiel = req["system"][1]
    assert referentiel["cache_control"] == {"type": "ephemeral"}
    assert all(code in referentiel["text"] for code in ref.criteres)
    assert all(f"## {r} –" in referentiel["text"] for r in ref.regles)
    message = req["messages"][0]["content"]
    assert "Constat : Aucun indicateur de chargement." in message
    assert "Écran / page : Paiement" in message and "produit = Boutique" in message and "cible" not in message
    assert "Critère choisi par le designer : GUI-01" in message
    schema = req["output_config"]["format"]["schema"]
    assert schema["properties"]["critere_principal"]["properties"]["code"]["enum"] == list(ref.criteres)
    assert req["fallbacks"] == "default" and req["betas"] == ["server-side-fallback-2026-07-01"]
    # Le bloc mis en cache ne dépend pas du constat : il est identique d'un appel à l'autre
    autre = construire_requete(ref, "Autre constat.")
    assert autre["system"] == req["system"]


def test_requete_constat_vide(ref):
    with pytest.raises(ErreurSuggestion):
        construire_requete(ref, "   ")


def test_suggestion(ref):
    client = FauxClient(reponse_ia(criteres_secondaires=[
        {"code": "ERR-01", "justification": "x"}, {"code": "GUI-03", "justification": "doublon du principal"}]))
    s = suggerer(client, ref, "Aucun indicateur après le clic.", critere_designer="GUI-01")
    assert s.code == "GUI-03" and s.verdict == "a_revoir" and s.critere_designer == "GUI-01"
    assert [x["code"] for x in s.secondaires] == ["ERR-01"]  # le principal n'est pas répété en secondaire
    assert s.usage["cache_lu"] == 9000
    assert s.ligne_excel(ref) == "GUI-03 – Feedback immédiat (Immediate Feedback) | Secondaires : ERR-01 | Règle : R1"


def test_sans_critere_designer_pas_de_verdict(ref):
    s = suggerer(FauxClient(reponse_ia()), ref, "Aucun indicateur après le clic.")
    assert s.verdict == "non_fourni" and s.commentaire_verdict == ""


@pytest.mark.parametrize("client, message", [
    (None, "Aucune clé"),
    (FauxClient(reponse_ia(code="XYZ-99")), "absents du référentiel"),
    (FauxClient({"autre": 1}), "incomplète"),
    (FauxClient(reponse_ia(), stop_reason="refusal"), "refusé"),
    (FauxClient(reponse_ia(), stop_reason="max_tokens"), "tronquée"),
    (FauxClient(erreur_api(anthropic.AuthenticationError, 401)), "Clé d'API refusée"),
    (FauxClient(erreur_api(anthropic.RateLimitError, 429)), "Limite de requêtes"),
    (FauxClient(erreur_api(anthropic.InternalServerError, 500)), r"Erreur du service \(500\)"),
])
def test_erreurs(ref, client, message):
    with pytest.raises(ErreurSuggestion, match=message):
        suggerer(client, ref, "Aucun indicateur après le clic.")


def test_verifier_audit_et_export(audit_xlsx, ref, tmp_path):
    autre = {**CONSTAT_VALIDE, "ecran": "Panier", "critere": "GUI-01 – Incitation (Prompting)"}
    chemin = audit_xlsx([CONSTAT_VALIDE, autre, {**CONSTAT_VALIDE, "ecran": "Compte"}])
    client = FauxClient(reponse_ia(verdict_designer={"statut": "confirme", "commentaire": "OK"}),
                        erreur_api(anthropic.RateLimitError, 429),
                        reponse_ia(verdict_designer={"statut": "a_revoir", "commentaire": "Avant/après."}))
    vus = []
    audit, _, _, sortie, ia = relire(chemin, tmp_path / "relu.xlsx", ref, client,
                                     progression=lambda fait, total: vus.append((fait, total)))
    assert len(client.appels) == 3 and vus[-1] == (3, 3)
    assert ia[5].verdict == "confirme"
    assert sum(isinstance(r, ErreurSuggestion) for r in ia.values()) == 1  # une erreur n'arrête pas les autres
    contexte_envoye = client.appels[0]["messages"][0]["content"]
    assert "produit = Produit test" in contexte_envoye

    ws = load_workbook(sortie)["Audit"]
    entetes = [c.value for c in ws[3]]
    assert entetes[-3:] == ["IA : critère suggéré", "IA : verdict", "IA : justification"]
    col = entetes.index("IA : verdict") + 1
    assert ws.cell(row=5, column=col).value == "✓ Confirmé"
    assert "Erreur" in [ws.cell(row=r, column=col).value for r in (6, 7)]
    assert str(ws.cell(row=5, column=col - 1).value).startswith("GUI-03 –")


def test_verifier_audit_vide(audit_xlsx, ref):
    assert verifier_audit(FauxClient(reponse_ia()), ref, lire_audit(audit_xlsx([]))) == {}

