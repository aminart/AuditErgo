"""Tests du moteur de suggestion, avec un faux serveur local (aucun modèle ni réseau nécessaire)."""
import json
from pathlib import Path
from types import SimpleNamespace

import httpx2 as httpx  # client HTTP utilisé par le SDK openai
import openai
import pytest
from openpyxl import load_workbook

from audit_ergo import relire
from audit_ergo.lecture import lire_audit
from audit_ergo.suggestion import (ADRESSE_DEFAUT, ErreurSuggestion, client_ou_none, construire_requete, est_locale,
                                   suggerer, verifier_audit)
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
    """Imite client.chat.completions.create d'un serveur local (Ollama, LM Studio…).

    Renvoie les réponses données dans l'ordre (la dernière est répétée) ; une exception est levée telle quelle.
    """

    def __init__(self, *reponses, finish_reason="stop", refuse_response_format=False, prompt_tokens=None):
        self.reponses, self.appels = list(reponses), []
        self.finish_reason, self.refuse_response_format = finish_reason, refuse_response_format
        self.prompt_tokens = prompt_tokens
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **requete):
        self.appels.append(requete)
        if self.refuse_response_format and "response_format" in requete:
            raise erreur_api(openai.BadRequestError, 400, "response_format json_schema is not supported")
        r = self.reponses.pop(0) if len(self.reponses) > 1 else self.reponses[0]
        if isinstance(r, Exception):
            raise r
        contenu = r if isinstance(r, str) else json.dumps(r)
        taille = sum(len(m["content"]) for m in requete["messages"]) // 4  # contexte suffisant par défaut
        return SimpleNamespace(
            choices=[SimpleNamespace(finish_reason=self.finish_reason,
                                     message=SimpleNamespace(content=contenu, refusal=None))],
            usage=SimpleNamespace(prompt_tokens=self.prompt_tokens or taille, completion_tokens=400),
        )


def erreur_api(cls, status, message="erreur"):
    reponse = httpx.Response(status, request=httpx.Request("POST", "http://localhost:11434/v1/chat/completions"))
    return cls(message, response=reponse, body=None)


def message_utilisateur(client, i=0):
    return client.appels[i]["messages"][-1]["content"]


# --- Requête ---------------------------------------------------------------------------------------------

def test_requete(ref):
    req = construire_requete(ref, "  Aucun indicateur de chargement.  ", "Paiement", "GUI-01 – Incitation",
                             {"produit": "Boutique", "cible": None}, "Ajouter un loader.", 2)
    systeme, utilisateur = req["messages"]
    assert systeme["role"] == "system" and utilisateur["role"] == "user"
    assert all(code in systeme["content"] for code in ref.criteres)
    assert all(f"## {r} –" in systeme["content"] for r in ref.regles)
    assert "Critical" in systeme["content"] and "Faible" in systeme["content"]  # échelle à 4 niveaux
    assert '"enum"' in systeme["content"]  # schéma aussi décrit dans les consignes
    u = utilisateur["content"]
    assert "Constat : Aucun indicateur de chargement." in u and "Écran / page : Paiement" in u
    assert "produit = Boutique" in u and "cible" not in u
    assert "Critère choisi par le designer : GUI-01" in u
    assert "Recommandation rédigée par le designer : Ajouter un loader." in u
    assert "Gravité indiquée par le designer : 2 (Moyenne)" in u
    assert "en français" in u
    schema = req["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["critere_principal"]["properties"]["code"]["enum"] == list(ref.criteres)
    assert schema["properties"]["gravite"]["properties"]["valeur"]["enum"] == [1, 2, 3, 4]
    assert req["temperature"] <= 0.3  # réponses stables d'un designer à l'autre
    # Le début du prompt ne dépend pas du constat : le serveur local le réutilise d'un appel à l'autre
    assert construire_requete(ref, "Autre constat.")["messages"][0] == systeme


def test_requete_en_anglais(ref):
    assert "en anglais" in construire_requete(ref, "x", langue="en")["messages"][-1]["content"]


def test_requete_constat_vide(ref):
    with pytest.raises(ErreurSuggestion):
        construire_requete(ref, "   ")


# --- Réponse ---------------------------------------------------------------------------------------------

def test_suggestion(ref):
    client = FauxClient(reponse_ia(criteres_secondaires=[
        {"code": "ERR-01", "justification": "x"}, {"code": "GUI-03", "justification": "doublon du principal"}]))
    s = suggerer(client, ref, "Aucun indicateur après le clic.", critere_designer="GUI-01")
    assert s.code == "GUI-03" and s.verdict == "a_revoir" and s.critere_designer == "GUI-01"
    assert [x["code"] for x in s.secondaires] == ["ERR-01"]  # le principal n'est pas répété en secondaire
    assert s.ligne_excel(ref) == "GUI-03 – Feedback immédiat (Immediate Feedback) | Secondaires : ERR-01 | Règle : R1"
    assert s.ligne_excel(ref, "en") == "GUI-03 – Immediate Feedback | Secondary : ERR-01 | Rule : R1"


def test_sans_critere_designer_pas_de_verdict(ref):
    s = suggerer(FauxClient(reponse_ia()), ref, "Aucun indicateur après le clic.")
    assert s.verdict == "non_fourni" and s.commentaire_verdict == ""


def test_reponse_entouree_de_texte(ref):
    texte = "Voici l'analyse :\n```json\n" + json.dumps(reponse_ia()) + "\n```"
    assert suggerer(FauxClient(texte), ref, "Aucun indicateur après le clic.").code == "GUI-03"


def test_serveur_sans_response_format(ref):
    client = FauxClient(reponse_ia(), refuse_response_format=True)
    assert suggerer(client, ref, "Aucun indicateur après le clic.").code == "GUI-03"
    assert len(client.appels) == 2 and "response_format" not in client.appels[1]


def test_reponse_partielle_normalisee(ref):
    """Un modèle local peut renvoyer une réponse incomplète : elle est normalisée."""
    minimale = {"critere_principal": {"code": "GUI-03", "justification": "Après l'action.", "confiance": "élevée",
                                      "regle": "R99"}, "gravite": {"valeur": 0}}
    s = suggerer(FauxClient(minimale), ref, "Aucun indicateur après le clic.")
    assert (s.code, s.confiance, s.regle, s.secondaires, s.verdict, s.gravite) == \
        ("GUI-03", "faible", "aucune", [], "non_fourni", None)  # gravité 0 : hors de l'échelle 1-4
    with pytest.raises(ErreurSuggestion, match="verdict"):
        suggerer(FauxClient(minimale), ref, "Aucun indicateur après le clic.", critere_designer="GUI-01")


def test_contexte_tronque_detecte(ref):
    """Ollama coupe sans prévenir ce qui dépasse sa fenêtre de contexte : l'application doit le dire."""
    with pytest.raises(ErreurSuggestion, match="OLLAMA_CONTEXT_LENGTH"):
        suggerer(FauxClient(reponse_ia(), prompt_tokens=2048), ref, "Aucun indicateur après le clic.")


@pytest.mark.parametrize("client, message", [
    (None, "IA désactivée"),
    (FauxClient(reponse_ia(code="XYZ-99")), "absents du référentiel"),
    (FauxClient({"autre": 1}), "incomplète"),
    (FauxClient("pas du json"), "illisible"),
    (FauxClient(""), "vide"),
    (FauxClient(reponse_ia(), finish_reason="length"), "tronquée"),
    (FauxClient(reponse_ia(), finish_reason="content_filter"), "refusé"),
    (FauxClient(openai.APIConnectionError(request=httpx.Request("POST", "http://localhost:11434"))), "ne répond pas"),
    (FauxClient(erreur_api(openai.NotFoundError, 404)), "ollama pull"),
    (FauxClient(erreur_api(openai.BadRequestError, 400)), "Requête refusée"),
    (FauxClient(erreur_api(openai.InternalServerError, 500)), r"Erreur du serveur local \(500\)"),
])
def test_erreurs(ref, client, message):
    with pytest.raises(ErreurSuggestion, match=message):
        suggerer(client, ref, "Aucun indicateur après le clic.")


# --- Audit complet ---------------------------------------------------------------------------------------

def test_verifier_audit_et_export(audit_xlsx, ref, tmp_path):
    autre = {**CONSTAT_VALIDE, "ecran": "Panier", "critere": "GUI-01 – Incitation (Prompting)"}
    chemin = audit_xlsx([CONSTAT_VALIDE, autre, {**CONSTAT_VALIDE, "ecran": "Compte"}])
    client = FauxClient(reponse_ia(verdict_designer={"statut": "confirme", "commentaire": "OK"}),
                        erreur_api(openai.InternalServerError, 500),
                        reponse_ia(verdict_designer={"statut": "a_revoir", "commentaire": "Avant/après."}))
    vus = []
    audit, _, _, sortie, ia = relire(chemin, tmp_path / "relu.xlsx", ref, client,
                                     progression=lambda fait, total: vus.append((fait, total)))
    assert len(client.appels) == 3 and vus[-1] == (3, 3)
    assert sum(isinstance(r, ErreurSuggestion) for r in ia.values()) == 1  # une erreur n'arrête pas les autres
    assert "produit = Produit test" in message_utilisateur(client)

    ws = load_workbook(sortie)["Audit"]
    entetes = [c.value for c in ws[3]]
    assert entetes[-7:] == ["IA : critère suggéré", "IA : verdict critère", "IA : justification critère",
                            "IA : recommandation", "IA : avis recommandation", "IA : gravité", "IA : remarques"]
    col = entetes.index("IA : verdict critère") + 1
    verdicts = [ws.cell(row=r, column=col).value for r in (5, 6, 7)]
    assert "✓ Confirmé" in verdicts and "Erreur" in verdicts


def test_export_en_anglais(audit_xlsx, ref, tmp_path):
    client = FauxClient(reponse_ia(verdict_designer={"statut": "confirme", "commentaire": "OK"}))
    _, anomalies, _, sortie, _ = relire(audit_xlsx([CONSTAT_VALIDE]), tmp_path / "en.xlsx", ref, client, langue="en")
    wb = load_workbook(sortie)
    assert wb.sheetnames[:2] == ["Review – Summary", "Review – Issues"]
    assert "AI: sub-criterion verdict" in [c.value for c in wb["Audit"][3]]
    assert "en anglais" in message_utilisateur(client)  # l'IA rédige en anglais
    # Relire en français un fichier relu en anglais ne duplique pas les colonnes de relecture
    _, _, _, sortie_fr, _ = relire(sortie, tmp_path / "fr.xlsx", ref, client, langue="fr")
    entetes = [c.value for c in load_workbook(sortie_fr)["Audit"][3] if c.value]
    assert len(entetes) == len(set(entetes)) and "AI: sub-criterion verdict" not in entetes


def test_verifier_audit_vide(audit_xlsx, ref):
    assert verifier_audit(FauxClient(reponse_ia()), ref, lire_audit(audit_xlsx([]))) == {}


# --- Configuration : tout reste sur le poste ------------------------------------------------------------

@pytest.fixture
def env_vide(monkeypatch):
    for nom in ("API_KEY", "API_BASE", "CA_BUNDLE", "AUDIT_ERGO_RESEAU_AUTORISE", "AUDIT_ERGO_IA"):
        monkeypatch.delenv(nom, raising=False)
    monkeypatch.setattr("audit_ergo.suggestion.FICHIER_ENV", Path("/inexistant/.env"))
    monkeypatch.setattr("audit_ergo.suggestion.charger_env.__defaults__", (Path("/inexistant/.env"),))
    return monkeypatch


def test_configuration_par_defaut_ollama_local(env_vide):
    client = client_ou_none()
    assert str(client.base_url) == ADRESSE_DEFAUT + "/" and client.api_key == "local"


@pytest.mark.parametrize("adresse", ["http://localhost:1234/v1", "http://127.0.0.1:11434/v1/chat/completions",
                                     "http://[::1]:8080/v1", "http://localhost:11434/v1/"])
def test_adresses_locales_acceptees(env_vide, adresse):
    env_vide.setenv("API_BASE", adresse)
    assert client_ou_none() is not None


@pytest.mark.parametrize("adresse", ["https://api.mistral.ai/v1", "https://api.openai.com/v1",
                                     "http://192.168.1.20:11434/v1", "http://serveur-gpu.interne/v1"])
def test_adresses_distantes_refusees(env_vide, adresse):
    env_vide.setenv("API_BASE", adresse)
    assert not est_locale(adresse)
    with pytest.raises(ErreurSuggestion, match="quitteraient le poste"):
        client_ou_none()
    env_vide.setenv("AUDIT_ERGO_RESEAU_AUTORISE", "1")  # serveur interne validé par l'organisation
    assert client_ou_none() is not None


def test_ia_desactivee(env_vide):
    env_vide.setenv("AUDIT_ERGO_IA", "0")
    assert client_ou_none() is None


def test_adresse_invalide(env_vide):
    env_vide.setenv("API_BASE", "localhost")
    with pytest.raises(ErreurSuggestion, match="invalide"):
        client_ou_none()


def test_configuration_ca_bundle(env_vide, tmp_path):
    import certifi

    env_vide.setenv("CA_BUNDLE", certifi.where())
    assert client_ou_none() is not None
    env_vide.setenv("CA_BUNDLE", str(tmp_path / "absent.pem"))
    with pytest.raises(ErreurSuggestion, match="introuvable"):
        client_ou_none()
    faux = tmp_path / "faux.pem"
    faux.write_text("pas un certificat")
    env_vide.setenv("CA_BUNDLE", str(faux))
    with pytest.raises(ErreurSuggestion, match="illisible"):
        client_ou_none()


def test_env_enregistre_par_le_bloc_notes(env_vide, tmp_path):
    """Un .env enregistré avec un BOM (Bloc-notes de Windows) et des fins de ligne CRLF est bien lu."""
    from audit_ergo.suggestion import charger_env

    fichier = tmp_path / ".env"
    fichier.write_bytes("API_BASE=http://localhost:1234/v1\r\nAPI_KEY=cle-lm-studio\r\n".encode("utf-8-sig"))
    charger_env(fichier)
    client = client_ou_none()
    assert client.api_key == "cle-lm-studio" and str(client.base_url).startswith("http://localhost:1234")


def test_bout_en_bout_serveur_local_sans_proxy(env_vide, ref):
    """Vrai appel HTTP vers un faux serveur local, alors qu'un proxy est configuré sur le poste : la requête
    doit aller directement au serveur local, jamais passer par le proxy."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    recus = []

    class Serveur(BaseHTTPRequestHandler):
        def do_POST(self):
            corps = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            recus.append({"chemin": self.path, "auth": self.headers.get("Authorization"), "corps": corps})
            if "response_format" in corps:  # ce serveur ne connaît pas response_format
                self._repondre(400, {"error": {"message": "Unsupported parameter: response_format"}})
            else:
                taille = sum(len(m["content"]) for m in corps["messages"]) // 4
                self._repondre(200, {"id": "x", "object": "chat.completion", "model": corps["model"],
                                     "choices": [{"index": 0, "finish_reason": "stop",
                                                  "message": {"role": "assistant",
                                                              "content": json.dumps(reponse_ia())}}],
                                     "usage": {"prompt_tokens": taille, "completion_tokens": 300}})

        def _repondre(self, code, data):
            brut = json.dumps(data).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(brut)))
            self.end_headers()
            self.wfile.write(brut)

        def log_message(self, *args):
            pass

    serveur = HTTPServer(("127.0.0.1", 0), Serveur)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    try:
        # Un proxy injoignable : si la requête l'utilisait, elle échouerait
        env_vide.setenv("HTTP_PROXY", "http://proxy-inexistant.invalid:3128")
        env_vide.setenv("HTTPS_PROXY", "http://proxy-inexistant.invalid:3128")
        env_vide.setenv("ALL_PROXY", "http://proxy-inexistant.invalid:3128")
        env_vide.delenv("NO_PROXY", raising=False)
        env_vide.delenv("no_proxy", raising=False)
        env_vide.setenv("API_BASE", f"http://127.0.0.1:{serveur.server_port}/v1/chat/completions")
        s = suggerer(client_ou_none(), ref, "Aucun indicateur après le clic.", "Paiement", "GUI-01")
    finally:
        serveur.shutdown()

    assert s.code == "GUI-03" and s.verdict == "a_revoir"
    assert [r["chemin"] for r in recus] == ["/v1/chat/completions"] * 2  # 2e essai sans response_format
    assert recus[0]["auth"] == "Bearer local"
    assert recus[1]["corps"]["model"] and recus[1]["corps"]["temperature"] <= 0.3
