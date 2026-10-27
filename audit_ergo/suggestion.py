"""Suggestion de critères par l'IA (Claude) à partir d'un constat.

La clé d'API est lue dans la variable d'environnement ANTHROPIC_API_KEY, ou dans un fichier .env
à la racine du dépôt (voir .env.exemple). Sans clé, `client_ou_none()` renvoie None et l'interface
l'indique au lieu d'appeler l'API.
"""
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

FICHIER_ENV = Path(__file__).resolve().parent.parent / ".env"
CONFIANCES = ["haute", "moyenne", "faible"]
VERDICTS = ["confirme", "a_revoir", "incorrect", "non_fourni"]
LIBELLE_VERDICT = {"confirme": "✓ Confirmé", "a_revoir": "À revoir", "incorrect": "✗ Incorrect",
                   "non_fourni": "Non fourni"}


class ErreurSuggestion(Exception):
    """Erreur à afficher telle quelle à l'utilisateur."""


def charger_env(chemin=FICHIER_ENV):
    """Charge les variables d'un fichier .env simple (CLE=valeur) sans écraser l'environnement existant."""
    if not chemin.exists():
        return
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith("#") and "=" in ligne:
            cle, valeur = ligne.split("=", 1)
            os.environ.setdefault(cle.strip(), valeur.strip().strip('"').strip("'"))


charger_env()  # avant de lire la configuration ci-dessous, pour qu'elle puisse venir du .env
MODELE = os.environ.get("AUDIT_ERGO_MODELE", "claude-opus-5-5")
EFFORT = os.environ.get("AUDIT_ERGO_EFFORT", "medium")
# Relance automatique sur un autre modèle si un filtre de sécurité refuse la requête (désactivable)
FALLBACK = os.environ.get("AUDIT_ERGO_FALLBACK", "1") != "0"


def cle_disponible():
    charger_env()
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def client_ou_none(api_key=None):
    """Client Anthropic prêt à l'emploi, ou None si aucune clé n'est configurée."""
    charger_env()
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    import anthropic
    return anthropic.Anthropic(api_key=api_key, max_retries=3)


# --- Prompt -----------------------------------------------------------------------------------------

def _texte_referentiel(ref):
    """Référentiel complet en texte. Identique d'un appel à l'autre : il est mis en cache côté API."""
    lignes = [f"# Référentiel d'évaluation ergonomique (version {ref.version})", ""]
    for cat in ref.data["grid"]:
        lignes += [f"## {cat['code']} – {cat['label_fr']} ({cat['label']})", cat["definition"], ""]
        for c in cat["criteria"]:
            lignes += [f"### {c['code']} – {c['label_fr']} ({c['name']})", f"Définition : {c['definition']}"]
            if c.get("note"):
                lignes.append(f"Note : {c['note']}")
            if c["checklist"]:
                lignes.append("Checklist :")
                lignes += [f"- {q['q']}" for q in c["checklist"]]
            lignes.append("")
    regles = ref.data["regles_departage"]
    lignes += ["# Règles de départage", ""]
    lignes += [f"- {p}" for p in regles["principes"]] + [""]
    for r in regles["regles"]:
        lignes += [f"## {r['id']} – {r['theme']}", f"Question : {r['question']}"]
        for cas in r["cas"]:
            lignes.append(f"- Si : {cas['si']} → {cas['critere']} (exemple : {cas['exemple']})")
        lignes.append("")
    return "\n".join(lignes)


CONSIGNES = """Tu assistes des UX designers qui réalisent des audits ergonomiques heuristiques. \
Pour chaque constat, tu proposes le critère du référentiel ci-dessous qui correspond le mieux, \
afin que tous les designers classent les problèmes de la même façon.

Méthode :
1. Identifie la CAUSE du problème décrit, pas son symptôme. Le critère principal correspond à cette cause.
2. Si deux critères sont proches, applique la règle de départage concernée et cite-la.
3. Appuie-toi sur la définition du critère et, si possible, cite mot pour mot la question de checklist \
qui s'applique (en anglais, telle qu'elle figure dans le référentiel).
4. Ajoute des critères secondaires seulement s'ils sont réellement touchés (zéro, un ou deux en général).
5. Propose une ou deux alternatives plausibles et explique pourquoi elles ne sont pas retenues.
6. Si le constat est trop vague pour trancher, mets la confiance à « faible », indique la question à \
poser au designer et ce qu'il faudrait préciser.
7. Si le designer a indiqué un critère, donne un verdict : « confirme » s'il correspond, « a_revoir » \
s'il est défendable mais qu'un autre est meilleur, « incorrect » s'il ne correspond pas. Sinon, \
« non_fourni ».

N'utilise que les codes du référentiel. Réponds en français, de façon concise et factuelle."""


def _schema(ref):
    codes = list(ref.criteres)
    regles = list(ref.regles) + ["aucune"]
    code = {"type": "string", "enum": codes}
    return {
        "type": "object",
        "properties": {
            "critere_principal": {
                "type": "object",
                "properties": {
                    "code": code,
                    "confiance": {"type": "string", "enum": CONFIANCES},
                    "justification": {"type": "string"},
                    "regle": {"type": "string", "enum": regles},
                    "question_checklist": {"type": "string"},
                },
                "required": ["code", "confiance", "justification", "regle", "question_checklist"],
                "additionalProperties": False,
            },
            "criteres_secondaires": {
                "type": "array",
                "items": {"type": "object", "properties": {"code": code, "justification": {"type": "string"}},
                          "required": ["code", "justification"], "additionalProperties": False},
            },
            "alternatives": {
                "type": "array",
                "items": {"type": "object",
                          "properties": {"code": code, "pourquoi_pas": {"type": "string"}},
                          "required": ["code", "pourquoi_pas"], "additionalProperties": False},
            },
            "question_a_se_poser": {"type": "string"},
            "precisions_manquantes": {"type": "array", "items": {"type": "string"}},
            "verdict_designer": {
                "type": "object",
                "properties": {"statut": {"type": "string", "enum": VERDICTS}, "commentaire": {"type": "string"}},
                "required": ["statut", "commentaire"],
                "additionalProperties": False,
            },
        },
        "required": ["critere_principal", "criteres_secondaires", "alternatives", "question_a_se_poser",
                     "precisions_manquantes", "verdict_designer"],
        "additionalProperties": False,
    }


def construire_requete(ref, constat, ecran=None, critere_designer=None, contexte=None):
    """Paramètres de l'appel API. Séparé de l'appel pour pouvoir être testé sans clé."""
    if not constat or not str(constat).strip():
        raise ErreurSuggestion("Le constat est vide.")
    contexte = {k: v for k, v in (contexte or {}).items() if v}
    parties = [f"Constat : {str(constat).strip()}"]
    if ecran:
        parties.append(f"Écran / page : {ecran}")
    if contexte:
        parties.append("Contexte de l'audit : " + " ; ".join(f"{k} = {v}" for k, v in contexte.items()))
    if critere_designer:
        parties.append(f"Critère choisi par le designer : {critere_designer}")
    else:
        parties.append("Le designer n'a pas indiqué de critère.")
    requete = {
        "model": MODELE,
        "max_tokens": 16000,  # inclut la réflexion du modèle : une limite basse tronquerait la réponse
        "system": [
            {"type": "text", "text": CONSIGNES},
            # Bloc stable et volumineux : mis en cache pour ne le payer qu'une fois par série d'appels
            {"type": "text", "text": _texte_referentiel(ref), "cache_control": {"type": "ephemeral"}},
        ],
        "messages": [{"role": "user", "content": "\n".join(parties)}],
        "output_config": {"effort": EFFORT, "format": {"type": "json_schema", "schema": _schema(ref)}},
    }
    if FALLBACK:
        requete.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    return requete


# --- Résultat ---------------------------------------------------------------------------------------

@dataclass
class Suggestion:
    code: str
    confiance: str
    justification: str
    regle: str
    question_checklist: str
    secondaires: list = field(default_factory=list)  # [{"code", "justification"}]
    alternatives: list = field(default_factory=list)  # [{"code", "pourquoi_pas"}]
    question_a_se_poser: str = ""
    precisions_manquantes: list = field(default_factory=list)
    verdict: str = "non_fourni"
    commentaire_verdict: str = ""
    critere_designer: str | None = None  # code du critère choisi par le designer, s'il y en a un
    usage: dict = field(default_factory=dict)

    def ligne_excel(self, ref):
        """Texte prêt à coller dans le template."""
        c = ref.criteres[self.code]
        txt = f"{c['code']} – {c['label_fr']} ({c['name']})"
        if self.secondaires:
            txt += " | Secondaires : " + " ; ".join(s["code"] for s in self.secondaires)
        if self.regle != "aucune":
            txt += f" | Règle : {self.regle}"
        return txt


def interpreter(ref, data, critere_designer=None, usage=None):
    """Valide la réponse JSON du modèle et la convertit en Suggestion."""
    try:
        p = data["critere_principal"]
        codes = [p["code"]] + [x["code"] for x in data["criteres_secondaires"] + data["alternatives"]]
    except (KeyError, TypeError) as e:
        raise ErreurSuggestion(f"Réponse de l'IA incomplète ({e}).") from e
    inconnus = [c for c in codes if c not in ref.criteres]
    if inconnus:
        raise ErreurSuggestion(f"L'IA a proposé des codes absents du référentiel : {', '.join(inconnus)}.")
    secondaires = [s for s in data["criteres_secondaires"] if s["code"] != p["code"]]
    alternatives = [a for a in data["alternatives"] if a["code"] != p["code"]]
    verdict = data["verdict_designer"]["statut"] if critere_designer else "non_fourni"
    return Suggestion(
        code=p["code"], confiance=p["confiance"], justification=p["justification"], regle=p["regle"],
        question_checklist=p["question_checklist"], secondaires=secondaires, alternatives=alternatives,
        question_a_se_poser=data["question_a_se_poser"], precisions_manquantes=data["precisions_manquantes"],
        verdict=verdict, commentaire_verdict=data["verdict_designer"]["commentaire"] if critere_designer else "",
        critere_designer=critere_designer, usage=usage or {},
    )


def suggerer(client, ref, constat, ecran=None, critere_designer=None, contexte=None):
    """Appelle Claude et renvoie une Suggestion. `critere_designer` est un code du référentiel (ou None)."""
    import anthropic

    if client is None:
        raise ErreurSuggestion("Aucune clé d'API configurée (variable ANTHROPIC_API_KEY ou fichier .env).")
    libelle = None
    if critere_designer:
        c = ref.criteres[critere_designer]
        libelle = f"{c['code']} – {c['label_fr']} ({c['name']})"
    requete = construire_requete(ref, constat, ecran, libelle, contexte)
    try:
        reponse = client.beta.messages.create(**requete)
    except anthropic.AuthenticationError as e:
        raise ErreurSuggestion("Clé d'API refusée : vérifiez ANTHROPIC_API_KEY.") from e
    except anthropic.PermissionDeniedError as e:
        raise ErreurSuggestion("Cette clé d'API n'a pas accès au modèle demandé.") from e
    except anthropic.NotFoundError as e:
        raise ErreurSuggestion(f"Modèle introuvable : {MODELE} (variable AUDIT_ERGO_MODELE).") from e
    except anthropic.RateLimitError as e:
        raise ErreurSuggestion("Limite de requêtes atteinte : réessayez dans une minute.") from e
    except anthropic.BadRequestError as e:
        raise ErreurSuggestion(f"Requête refusée par l'API : {e.message}") from e
    except anthropic.APIStatusError as e:
        raise ErreurSuggestion(f"Erreur du service ({e.status_code}) : réessayez plus tard.") from e
    except anthropic.APIConnectionError as e:
        raise ErreurSuggestion("Connexion à l'API impossible : vérifiez votre accès Internet.") from e

    if reponse.stop_reason == "refusal":
        raise ErreurSuggestion("L'IA a refusé de traiter ce constat. Reformulez-le ou classez-le manuellement.")
    if reponse.stop_reason == "max_tokens":
        raise ErreurSuggestion("Réponse de l'IA tronquée : réessayez.")
    texte = next((b.text for b in reponse.content if b.type == "text"), None)
    try:
        data = json.loads(texte)
    except (TypeError, json.JSONDecodeError) as e:
        raise ErreurSuggestion("Réponse de l'IA illisible : réessayez.") from e
    u = reponse.usage
    usage = {"entree": u.input_tokens, "sortie": u.output_tokens,
             "cache_lu": getattr(u, "cache_read_input_tokens", 0) or 0,
             "cache_ecrit": getattr(u, "cache_creation_input_tokens", 0) or 0}
    return interpreter(ref, data, critere_designer, usage)


def verifier_audit(client, ref, audit, progression=None, paralleles=4):
    """Suggestion pour chaque constat de l'audit. Renvoie {ligne: Suggestion | ErreurSuggestion}."""
    contexte = {k: audit.contexte.get(k) for k in ("produit", "cible", "plateforme", "contexte_usage")}
    a_traiter = [c for c in audit.constats if c["constat"]]
    resultats = {}

    def une(c):
        try:
            return suggerer(client, ref, c["constat"], c["ecran"], ref.trouver_critere(c["critere"]), contexte)
        except ErreurSuggestion as e:
            return e

    if not a_traiter:
        return resultats
    # Le premier appel écrit le référentiel en cache ; les suivants, en parallèle, le relisent
    resultats[a_traiter[0].ligne] = une(a_traiter[0])
    if progression:
        progression(1, len(a_traiter))
    with ThreadPoolExecutor(max_workers=paralleles) as pool:
        futures = {pool.submit(une, c): c.ligne for c in a_traiter[1:]}
        for i, f in enumerate(as_completed(futures), 2):
            resultats[futures[f]] = f.result()
            if progression:
                progression(i, len(a_traiter))
    return resultats
