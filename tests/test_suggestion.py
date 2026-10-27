"""Tests du moteur de suggestion, avec un faux client à la place de l'API (aucune clé nécessaire)."""
import json
from pathlib import Path
from types import SimpleNamespace

import anthropic
import httpx2 as httpx  # client HTTP utilisé par les SDK anthropic et openai
import pytest
from openpyxl import load_workbook

from audit_ergo import relire
from audit_ergo.suggestion import (ClientIA, ErreurSuggestion, client_ou_none, construire_requete,
                                   construire_requete_openai, suggerer, verifier_audit)
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



@pytest.fixture
def env_vide(monkeypatch):
    for nom in ("API_KEY", "API_BASE", "CA_BUNDLE", "API_FORMAT", "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL"):
        monkeypatch.delenv(nom, raising=False)
    monkeypatch.setattr("audit_ergo.suggestion.FICHIER_ENV", Path("/inexistant/.env"))
    monkeypatch.setattr("audit_ergo.suggestion.charger_env.__defaults__", (Path("/inexistant/.env"),))
    return monkeypatch


def test_configuration_sans_cle(env_vide):
    assert client_ou_none() is None


def test_configuration_par_defaut_anthropic(env_vide):
    env_vide.setenv("API_KEY", "cle-test")
    client = client_ou_none()
    assert client.format == "anthropic" and client.sdk.api_key == "cle-test"


@pytest.mark.parametrize("adresse", ["https://passerelle.exemple.fr/v1", "https://passerelle.exemple.fr/v1/",
                                     "https://passerelle.exemple.fr/v1/chat/completions"])
def test_configuration_passerelle_openai(env_vide, adresse):
    env_vide.setenv("API_KEY", "cle-test")
    env_vide.setenv("API_BASE", adresse)  # API_BASE renseigné => format OpenAI par défaut
    client = client_ou_none()
    assert client.format == "openai" and client.sdk.api_key == "cle-test"
    assert str(client.sdk.base_url) == "https://passerelle.exemple.fr/v1/"


def test_configuration_format_explicite(env_vide):
    env_vide.setenv("API_KEY", "cle-test")
    env_vide.setenv("API_BASE", "https://passerelle.exemple.fr/anthropic")
    env_vide.setenv("API_FORMAT", "Anthropic")
    client = client_ou_none()
    assert client.format == "anthropic"
    assert str(client.sdk.base_url).startswith("https://passerelle.exemple.fr/anthropic")
    env_vide.setenv("API_FORMAT", "mistral")
    with pytest.raises(ErreurSuggestion, match="API_FORMAT"):
        client_ou_none()
    env_vide.setenv("API_FORMAT", "openai")
    env_vide.delenv("API_BASE")
    with pytest.raises(ErreurSuggestion, match="API_BASE est obligatoire"):
        client_ou_none()


def test_anthropic_base_url_garde_le_format_anthropic(env_vide):
    """ANTHROPIC_BASE_URL (souvent défini par d'autres outils) ne doit pas basculer en format OpenAI."""
    env_vide.setenv("API_KEY", "cle-test")
    env_vide.setenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    client = client_ou_none()
    assert client.format == "anthropic" and str(client.sdk.base_url).startswith("https://api.anthropic.com")


def test_configuration_noms_anthropic_acceptes(env_vide):
    env_vide.setenv("ANTHROPIC_API_KEY", "ancienne")
    assert client_ou_none().sdk.api_key == "ancienne"
    env_vide.setenv("API_KEY", "nouvelle")  # API_KEY est prioritaire
    assert client_ou_none().sdk.api_key == "nouvelle"


def test_configuration_ca_bundle(env_vide, tmp_path):
    import certifi

    env_vide.setenv("API_KEY", "cle-test")
    env_vide.setenv("CA_BUNDLE", certifi.where())
    assert client_ou_none() is not None
    env_vide.setenv("API_BASE", "https://passerelle.exemple.fr/v1")
    assert client_ou_none().format == "openai"  # le certificat s'applique aussi au client OpenAI

    env_vide.setenv("CA_BUNDLE", str(tmp_path / "absent.pem"))
    with pytest.raises(ErreurSuggestion, match="introuvable"):
        client_ou_none()

    faux = tmp_path / "faux.pem"
    faux.write_text("pas un certificat")
    env_vide.setenv("CA_BUNDLE", str(faux))
    with pytest.raises(ErreurSuggestion, match="illisible"):
        client_ou_none()


# --- Format OpenAI (/v1/chat/completions) ---------------------------------------------------------------

class FauxOpenAI:
    """Imite client.chat.completions.create d'un SDK OpenAI pointé vers une passerelle."""

    def __init__(self, *reponses, finish_reason="stop", refuse_response_format=False):
        self.reponses, self.appels = list(reponses), []
        self.finish_reason, self.refuse_response_format = finish_reason, refuse_response_format
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **requete):
        import openai

        self.appels.append(requete)
        if self.refuse_response_format and "response_format" in requete:
            reponse = httpx.Response(400, request=httpx.Request("POST", "https://gw/v1/chat/completions"))
            raise openai.BadRequestError("response_format json_schema is not supported", response=reponse, body=None)
        r = self.reponses.pop(0) if len(self.reponses) > 1 else self.reponses[0]
        if isinstance(r, Exception):
            raise r
        contenu = r if isinstance(r, str) else json.dumps(r)
        return SimpleNamespace(
            choices=[SimpleNamespace(finish_reason=self.finish_reason,
                                     message=SimpleNamespace(content=contenu, refusal=None))],
            usage=SimpleNamespace(prompt_tokens=9000, completion_tokens=400,
                                  prompt_tokens_details=SimpleNamespace(cached_tokens=8000)),
        )


def openai_client(*reponses, **kw):
    return ClientIA("openai", FauxOpenAI(*reponses, **kw))


def test_requete_openai(ref):
    req = construire_requete_openai(ref, "Aucun indicateur.", "Paiement", "GUI-01 – Incitation")
    systeme, utilisateur = req["messages"]
    assert systeme["role"] == "system" and utilisateur["role"] == "user"
    assert all(code in systeme["content"] for code in ref.criteres)
    assert '"enum"' in systeme["content"]  # schéma aussi décrit dans les consignes
    assert "Critère choisi par le designer : GUI-01" in utilisateur["content"]
    assert req["response_format"]["json_schema"]["schema"]["properties"]["critere_principal"]
    assert "betas" not in req and "fallbacks" not in req and "output_config" not in req
    assert construire_requete_openai(ref, "Autre.")["messages"][0] == systeme  # en-tête stable (cache)


def test_suggestion_openai(ref):
    client = openai_client(reponse_ia())
    s = suggerer(client, ref, "Aucun indicateur après le clic.", critere_designer="GUI-01")
    assert s.code == "GUI-03" and s.verdict == "a_revoir"
    assert s.usage == {"entree": 9000, "sortie": 400, "cache_lu": 8000, "cache_ecrit": 0}


def test_openai_reponse_entouree_de_texte(ref):
    texte = "Voici l'analyse :\n```json\n" + json.dumps(reponse_ia()) + "\n```"
    assert suggerer(openai_client(texte), ref, "Aucun indicateur après le clic.").code == "GUI-03"


def test_openai_passerelle_sans_response_format(ref):
    faux = FauxOpenAI(reponse_ia(), refuse_response_format=True)
    s = suggerer(ClientIA("openai", faux), ref, "Aucun indicateur après le clic.")
    assert s.code == "GUI-03"
    assert len(faux.appels) == 2 and "response_format" not in faux.appels[1]


def test_openai_reponse_partielle_normalisee(ref):
    """Sans schéma strict, la passerelle peut renvoyer une réponse incomplète : elle est normalisée."""
    minimale = {"critere_principal": {"code": "GUI-03", "justification": "Après l'action.", "confiance": "élevée",
                                      "regle": "R99"}}
    s = suggerer(openai_client(minimale), ref, "Aucun indicateur après le clic.")
    assert (s.code, s.confiance, s.regle, s.secondaires, s.verdict) == ("GUI-03", "faible", "aucune", [], "non_fourni")
    with pytest.raises(ErreurSuggestion, match="verdict"):
        suggerer(openai_client(minimale), ref, "Aucun indicateur après le clic.", critere_designer="GUI-01")


def erreur_openai(cls, status):
    reponse = httpx.Response(status, request=httpx.Request("POST", "https://gw/v1/chat/completions"))
    return cls("erreur", response=reponse, body=None)


def test_openai_erreurs(ref):
    import openai

    cas = [
        (openai_client("pas du json"), "illisible"),
        (openai_client(""), "vide"),
        (openai_client(reponse_ia(), finish_reason="length"), "tronquée"),
        (openai_client(reponse_ia(), finish_reason="content_filter"), "refusé"),
        (openai_client(erreur_openai(openai.AuthenticationError, 401)), "Clé d'API refusée"),
        (openai_client(erreur_openai(openai.NotFoundError, 404)), "AUDIT_ERGO_MODELE"),
        (openai_client(erreur_openai(openai.BadRequestError, 400)), "Requête refusée"),
    ]
    for client, message in cas:
        with pytest.raises(ErreurSuggestion, match=message):
            suggerer(client, ref, "Aucun indicateur après le clic.")


def test_bout_en_bout_passerelle_openai_locale(env_vide, ref):
    """Vrai appel HTTP vers une fausse passerelle locale au format OpenAI : URL, en-têtes et corps réels."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    recus = []

    class Passerelle(BaseHTTPRequestHandler):
        def do_POST(self):
            corps = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            recus.append({"chemin": self.path, "auth": self.headers.get("Authorization"), "corps": corps})
            if "response_format" in corps:  # cette passerelle ne connaît pas response_format
                self._repondre(400, {"error": {"message": "Unsupported parameter: response_format"}})
            else:
                self._repondre(200, {"id": "x", "object": "chat.completion", "model": corps["model"],
                                     "choices": [{"index": 0, "finish_reason": "stop",
                                                  "message": {"role": "assistant",
                                                              "content": json.dumps(reponse_ia())}}],
                                     "usage": {"prompt_tokens": 9000, "completion_tokens": 300}})

        def _repondre(self, code, data):
            brut = json.dumps(data).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(brut)))
            self.end_headers()
            self.wfile.write(brut)

        def log_message(self, *args):
            pass

    serveur = HTTPServer(("127.0.0.1", 0), Passerelle)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    try:
        env_vide.setenv("NO_PROXY", "127.0.0.1")
        env_vide.setenv("API_KEY", "cle-passerelle")
        env_vide.setenv("API_BASE", f"http://127.0.0.1:{serveur.server_port}/v1/chat/completions")
        s = suggerer(client_ou_none(), ref, "Aucun indicateur après le clic.", "Paiement", "GUI-01")
    finally:
        serveur.shutdown()

    assert s.code == "GUI-03" and s.verdict == "a_revoir" and s.usage["entree"] == 9000
    assert [r["chemin"] for r in recus] == ["/v1/chat/completions"] * 2  # 2e essai sans response_format
    assert recus[0]["auth"] == "Bearer cle-passerelle"
    assert recus[1]["corps"]["messages"][0]["role"] == "system"
    assert "response_format" not in recus[1]["corps"]


def test_env_enregistre_par_le_bloc_notes(env_vide, tmp_path):
    """Un .env enregistré avec un BOM (Bloc-notes de Windows) et des fins de ligne CRLF est bien lu."""
    from audit_ergo.suggestion import charger_env

    fichier = tmp_path / ".env"
    fichier.write_bytes("API_KEY=cle-bloc-notes\r\nAPI_BASE=\r\n".encode("utf-8-sig"))
    charger_env(fichier)
    assert client_ou_none().sdk.api_key == "cle-bloc-notes"
