"""Suggestion de critères par l'IA (Claude) à partir d'un constat.

Configuration lue dans l'environnement ou dans un fichier .env à la racine du dépôt (voir .env.exemple) :
- API_KEY    : clé d'API (obligatoire pour utiliser l'IA) ;
- API_BASE   : adresse de la passerelle (ex. https://passerelle.exemple.fr/v1) ; vide = API Anthropic ;
- CA_BUNDLE  : chemin d'un fichier de certificats (PEM) si la passerelle ou le proxy utilise une autorité
               de certification interne ;
- API_FORMAT : « openai » (endpoint /v1/chat/completions) ou « anthropic » (endpoint /v1/messages).
               Par défaut : openai si API_BASE est renseigné, anthropic sinon (y compris quand seule la
               variable ANTHROPIC_BASE_URL est définie).
Sans clé, `client_ou_none()` renvoie None et l'interface l'indique au lieu d'appeler l'API.
"""
import json
import os
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from .cache import CacheSuggestions

FICHIER_ENV = Path(__file__).resolve().parent.parent / ".env"
CONFIANCES = ["haute", "moyenne", "faible"]
VERDICTS = ["confirme", "a_revoir", "incorrect", "non_fourni"]
STATUTS_RECO = ["bonne", "a_ameliorer", "hors_sujet", "non_fournie"]
LIBELLE_RECO = {"bonne": "✓ Bonne", "a_ameliorer": "À améliorer", "hors_sujet": "✗ Hors sujet",
                "non_fournie": "Non fournie"}
LIBELLE_VERDICT = {"confirme": "✓ Confirmé", "a_revoir": "À revoir", "incorrect": "✗ Incorrect",
                   "non_fourni": "Non fourni"}


class ErreurSuggestion(Exception):
    """Erreur à afficher telle quelle à l'utilisateur."""


def charger_env(chemin=FICHIER_ENV):
    """Charge les variables d'un fichier .env simple (CLE=valeur) sans écraser l'environnement existant."""
    if not chemin.exists():
        return
    # utf-8-sig : le Bloc-notes de Windows peut ajouter un BOM en tête de fichier
    for ligne in chemin.read_text(encoding="utf-8-sig").splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith("#") and "=" in ligne:
            cle, valeur = ligne.split("=", 1)
            os.environ.setdefault(cle.strip(), valeur.strip().strip('"').strip("'"))


charger_env()  # avant de lire la configuration ci-dessous, pour qu'elle puisse venir du .env
MODELE = os.environ.get("AUDIT_ERGO_MODELE", "claude-opus-5-5")
EFFORT = os.environ.get("AUDIT_ERGO_EFFORT", "medium")
MAX_TOKENS = int(os.environ.get("AUDIT_ERGO_MAX_TOKENS", "16000"))
# Format anthropic uniquement : relance sur un autre modèle si un filtre de sécurité refuse la requête
FALLBACK = os.environ.get("AUDIT_ERGO_FALLBACK", "1") != "0"
FORMATS = ("openai", "anthropic")


@dataclass
class ClientIA:
    format: str  # "openai" ou "anthropic"
    sdk: object  # openai.OpenAI ou anthropic.Anthropic


def _env(*noms):
    """Première variable renseignée parmi `noms` (les noms ANTHROPIC_* restent acceptés)."""
    return next((os.environ[n].strip() for n in noms if os.environ.get(n, "").strip()), None)


def cle_disponible():
    charger_env()
    return bool(_env("API_KEY", "ANTHROPIC_API_KEY"))


def adresse_api():
    charger_env()
    return _env("API_BASE", "ANTHROPIC_BASE_URL")


def format_api():
    charger_env()
    # Seul API_BASE (la variable de cette application) implique le format OpenAI ; ANTHROPIC_BASE_URL,
    # souvent défini par d'autres outils, désigne une adresse au format Anthropic
    fmt = (_env("API_FORMAT") or ("openai" if _env("API_BASE") else "anthropic")).lower()
    if fmt not in FORMATS:
        raise ErreurSuggestion(f"API_FORMAT : « {fmt} » inconnu (valeurs possibles : openai, anthropic).")
    return fmt


def _contexte_ssl():
    """Contexte SSL construit à partir de CA_BUNDLE, ou None si la variable est vide."""
    ca = _env("CA_BUNDLE")
    if not ca:
        return None
    chemin = Path(ca).expanduser()
    if not chemin.is_file():
        raise ErreurSuggestion(f"CA_BUNDLE : fichier introuvable ({chemin}).")
    try:
        return ssl.create_default_context(cafile=str(chemin))
    except (ssl.SSLError, OSError) as e:
        raise ErreurSuggestion(f"CA_BUNDLE : fichier de certificats illisible ({chemin}) : {e}") from e


def _base_openai(adresse):
    """Le SDK OpenAI ajoute lui-même /chat/completions : on l'enlève si l'adresse le contient déjà."""
    adresse = adresse.rstrip("/")
    for suffixe in ("/chat/completions", "/completions"):
        if adresse.endswith(suffixe):
            return adresse[: -len(suffixe)]
    return adresse


def client_ou_none(api_key=None):
    """ClientIA prêt à l'emploi, ou None si aucune clé n'est configurée.

    Lève ErreurSuggestion si la configuration est invalide (CA_BUNDLE, API_FORMAT, API_BASE manquant).
    """
    charger_env()
    api_key = api_key or _env("API_KEY", "ANTHROPIC_API_KEY")
    if not api_key:
        return None
    fmt, base, contexte_ssl = format_api(), adresse_api(), _contexte_ssl()

    if fmt == "openai":
        if not base:
            raise ErreurSuggestion("API_BASE est obligatoire avec le format OpenAI (adresse de la passerelle).")
        import openai

        options = {"api_key": api_key, "base_url": _base_openai(base), "max_retries": 3}
        if contexte_ssl:
            options["http_client"] = openai.DefaultHttpxClient(verify=contexte_ssl)
        return ClientIA("openai", openai.OpenAI(**options))

    import anthropic

    options = {"api_key": api_key, "max_retries": 3}
    if base:
        options["base_url"] = base
    if contexte_ssl:
        options["http_client"] = anthropic.DefaultHttpxClient(verify=contexte_ssl)
    return ClientIA("anthropic", anthropic.Anthropic(**options))


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
Pour chaque constat, tu proposes le critère du référentiel ci-dessous qui correspond le mieux, une \
recommandation et une gravité, afin que tous les designers produisent des audits du même niveau.

Critère :
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

Recommandation :
8. Propose une recommandation qui est spécifique (nomme l'élément à modifier), actionnable (une équipe \
peut l'implémenter sans réinterpréter), qui traite la cause, qui est vérifiable, et qui s'appuie sur une \
norme ou un usage reconnu quand c'est pertinent (WCAG, guidelines de la plateforme). Une à trois phrases.
9. Si le designer a rédigé une recommandation, évalue-la : « bonne » si elle remplit ces conditions, \
« a_ameliorer » si elle est juste mais incomplète ou vague (donne alors une version améliorée qui garde \
son intention), « hors_sujet » si elle ne traite pas le problème. Sinon, « non_fournie ».
10. Ajoute au besoin une ou deux recommandations complémentaires (autres pistes utiles), sinon aucune.

Gravité (échelle de Nielsen) : 0 pas un problème, 1 cosmétique, 2 mineur (gêne ponctuelle), \
3 majeur (l'utilisateur est ralenti ou se trompe), 4 bloquant (la tâche ne peut pas être accomplie). \
11. Estime la gravité d'après la fréquence, l'impact et la persistance du problème, en une phrase de \
justification. Si le designer a indiqué une gravité très différente, explique l'écart.

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
            "recommandation": {
                "type": "object",
                "properties": {
                    "proposee": {"type": "string"},
                    "avis_designer": {
                        "type": "object",
                        "properties": {"statut": {"type": "string", "enum": STATUTS_RECO},
                                       "commentaire": {"type": "string"},
                                       "version_amelioree": {"type": "string"}},
                        "required": ["statut", "commentaire", "version_amelioree"],
                        "additionalProperties": False,
                    },
                    "complementaires": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["proposee", "avis_designer", "complementaires"],
                "additionalProperties": False,
            },
            "gravite": {
                "type": "object",
                "properties": {"valeur": {"type": "integer", "enum": [0, 1, 2, 3, 4]},
                               "justification": {"type": "string"}},
                "required": ["valeur", "justification"],
                "additionalProperties": False,
            },
        },
        "required": ["critere_principal", "criteres_secondaires", "alternatives", "question_a_se_poser",
                     "precisions_manquantes", "verdict_designer", "recommandation", "gravite"],
        "additionalProperties": False,
    }


def _message(constat, ecran=None, critere_designer=None, contexte=None, recommandation_designer=None,
             gravite_designer=None):
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
    if recommandation_designer and str(recommandation_designer).strip():
        parties.append(f"Recommandation rédigée par le designer : {str(recommandation_designer).strip()}")
    else:
        parties.append("Le designer n'a pas rédigé de recommandation.")
    if gravite_designer is not None and str(gravite_designer).strip() != "":
        parties.append(f"Gravité indiquée par le designer : {gravite_designer}")
    return "\n".join(parties)


def construire_requete(ref, constat, ecran=None, critere_designer=None, contexte=None, recommandation_designer=None,
                       gravite_designer=None):
    """Paramètres de l'appel au format Anthropic (/v1/messages). Testable sans clé."""
    requete = {
        "model": MODELE,
        "max_tokens": MAX_TOKENS,  # inclut la réflexion du modèle : une limite basse tronquerait la réponse
        "system": [
            {"type": "text", "text": CONSIGNES},
            # Bloc stable et volumineux : mis en cache pour ne le payer qu'une fois par série d'appels
            {"type": "text", "text": _texte_referentiel(ref), "cache_control": {"type": "ephemeral"}},
        ],
        "messages": [{"role": "user", "content": _message(constat, ecran, critere_designer, contexte, recommandation_designer,
                                                         gravite_designer)}],
        "output_config": {"effort": EFFORT, "format": {"type": "json_schema", "schema": _schema(ref)}},
    }
    if FALLBACK:
        requete.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    return requete


def construire_requete_openai(ref, constat, ecran=None, critere_designer=None, contexte=None, recommandation_designer=None,
                              gravite_designer=None):
    """Paramètres de l'appel au format OpenAI (/v1/chat/completions). Testable sans clé.

    Le schéma est à la fois demandé via response_format et décrit dans les consignes, car toutes les
    passerelles ne transmettent pas response_format.
    """
    schema = _schema(ref)
    consigne_json = ("Réponds uniquement avec un objet JSON valide, sans texte autour ni bloc de code, "
                     "conforme à ce schéma JSON :\n" + json.dumps(schema, ensure_ascii=False))
    return {
        "model": MODELE,
        "max_tokens": MAX_TOKENS,
        "messages": [
            # Contenu stable en tête : les passerelles qui gèrent un cache de prompt peuvent le réutiliser
            {"role": "system", "content": f"{CONSIGNES}\n\n{_texte_referentiel(ref)}\n\n{consigne_json}"},
            {"role": "user", "content": _message(constat, ecran, critere_designer, contexte, recommandation_designer,
                                                         gravite_designer)},
        ],
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": "suggestion_critere", "strict": True, "schema": schema}},
    }


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
    reco_proposee: str = ""  # recommandation rédigée par l'IA
    reco_statut: str = "non_fournie"  # avis sur la recommandation du designer (STATUTS_RECO)
    reco_commentaire: str = ""
    reco_amelioree: str = ""  # version améliorée de la recommandation du designer, si utile
    reco_complementaires: list = field(default_factory=list)
    gravite: int | None = None  # gravité estimée par l'IA (0 à 4)
    justification_gravite: str = ""
    usage: dict = field(default_factory=dict)
    depuis_cache: bool = False  # True : réponse reprise du cache local, sans nouvel appel (ni coût)

    def ligne_excel(self, ref):
        """Texte prêt à coller dans le template."""
        c = ref.criteres[self.code]
        txt = f"{c['code']} – {c['label_fr']} ({c['name']})"
        if self.secondaires:
            txt += " | Secondaires : " + " ; ".join(s["code"] for s in self.secondaires)
        if self.regle != "aucune":
            txt += f" | Règle : {self.regle}"
        return txt

    @property
    def reco_a_retenir(self):
        """Recommandation à proposer : la version améliorée de celle du designer si elle existe, sinon celle de l'IA."""
        return self.reco_amelioree or self.reco_proposee


def interpreter(ref, data, critere_designer=None, usage=None, avec_reco_designer=False):
    """Valide la réponse JSON du modèle et la convertit en Suggestion.

    Le format OpenAI ne garantit pas toujours le respect du schéma : tout est donc revérifié ici.
    """
    try:
        p = data["critere_principal"]
        secondaires = [{"code": x["code"], "justification": str(x["justification"])}
                       for x in data.get("criteres_secondaires") or []]
        alternatives = [{"code": x["code"], "pourquoi_pas": str(x["pourquoi_pas"])}
                        for x in data.get("alternatives") or []]
        verdict = data.get("verdict_designer") or {}
        suggestion = Suggestion(
            code=p["code"],
            confiance=p.get("confiance") if p.get("confiance") in CONFIANCES else "faible",
            justification=str(p["justification"]),
            regle=p.get("regle") if p.get("regle") in ref.regles else "aucune",
            question_checklist=str(p.get("question_checklist") or ""),
            question_a_se_poser=str(data.get("question_a_se_poser") or ""),
            precisions_manquantes=[str(x) for x in data.get("precisions_manquantes") or []],
            critere_designer=critere_designer, usage=usage or {},
        )
    except (KeyError, TypeError, AttributeError) as e:
        raise ErreurSuggestion(f"Réponse de l'IA incomplète ({e}).") from e
    codes = [suggestion.code] + [x["code"] for x in secondaires + alternatives]
    inconnus = [c for c in codes if c not in ref.criteres]
    if inconnus:
        raise ErreurSuggestion(f"L'IA a proposé des codes absents du référentiel : {', '.join(map(str, inconnus))}.")
    suggestion.secondaires = [x for x in secondaires if x["code"] != suggestion.code]
    suggestion.alternatives = [x for x in alternatives if x["code"] != suggestion.code]
    if critere_designer:
        if verdict.get("statut") not in ("confirme", "a_revoir", "incorrect"):
            raise ErreurSuggestion("Réponse de l'IA incomplète (verdict sur le choix du designer manquant).")
        suggestion.verdict, suggestion.commentaire_verdict = verdict["statut"], str(verdict.get("commentaire") or "")

    # Recommandation et gravité : complétées si présentes (une passerelle peut ne pas respecter le schéma)
    reco = data.get("recommandation") if isinstance(data.get("recommandation"), dict) else {}
    suggestion.reco_proposee = str(reco.get("proposee") or "").strip()
    suggestion.reco_complementaires = [str(x).strip() for x in reco.get("complementaires") or [] if str(x).strip()]
    avis = reco.get("avis_designer") if isinstance(reco.get("avis_designer"), dict) else {}
    if avec_reco_designer and avis.get("statut") in ("bonne", "a_ameliorer", "hors_sujet"):
        suggestion.reco_statut = avis["statut"]
        suggestion.reco_commentaire = str(avis.get("commentaire") or "").strip()
        if avis["statut"] != "bonne":
            suggestion.reco_amelioree = str(avis.get("version_amelioree") or "").strip()
    grav = data.get("gravite") if isinstance(data.get("gravite"), dict) else {}
    try:
        valeur = int(grav.get("valeur"))
        if 0 <= valeur <= 4:
            suggestion.gravite = valeur
            suggestion.justification_gravite = str(grav.get("justification") or "").strip()
    except (TypeError, ValueError):
        pass
    return suggestion


def _erreur_api(sdk, e):
    """Traduit une exception du SDK (anthropic ou openai, mêmes noms de classes) en message lisible."""
    base = f" et l'adresse API_BASE ({adresse_api()})." if adresse_api() else "."
    if isinstance(e, sdk.AuthenticationError):
        return ErreurSuggestion("Clé d'API refusée : vérifiez API_KEY.")
    if isinstance(e, sdk.PermissionDeniedError):
        return ErreurSuggestion("Cette clé d'API n'a pas accès au modèle demandé.")
    if isinstance(e, sdk.NotFoundError):
        return ErreurSuggestion(f"Introuvable : vérifiez le modèle ({MODELE}, variable AUDIT_ERGO_MODELE){base}")
    if isinstance(e, sdk.RateLimitError):
        return ErreurSuggestion("Limite de requêtes atteinte : réessayez dans une minute.")
    if isinstance(e, sdk.BadRequestError):
        return ErreurSuggestion(f"Requête refusée par l'API : {e.message}")
    if isinstance(e, sdk.APIStatusError):
        return ErreurSuggestion(f"Erreur du service ({e.status_code}) : réessayez plus tard.")
    if isinstance(e, sdk.APIConnectionError):
        cause = repr(e.__cause__ or e)
        if "CERTIFICATE_VERIFY_FAILED" in cause or "SSL" in cause:
            return ErreurSuggestion("Certificat refusé lors de la connexion à l'API : renseignez CA_BUNDLE avec "
                                    "le fichier de certificats de votre organisation.")
        return ErreurSuggestion(f"Connexion à l'API impossible : vérifiez votre accès réseau{base}")
    raise e


def _extraire_json(texte):
    """JSON de la réponse, même entouré de texte ou d'un bloc ```json (passerelles sans response_format)."""
    if not texte:
        raise ErreurSuggestion("Réponse de l'IA vide : réessayez.")
    debut, fin = texte.find("{"), texte.rfind("}")
    try:
        return json.loads(texte[debut:fin + 1] if debut != -1 and fin > debut else texte)
    except json.JSONDecodeError as e:
        raise ErreurSuggestion("Réponse de l'IA illisible : réessayez.") from e


def _appel_anthropic(sdk, requete):
    import anthropic

    try:
        reponse = sdk.beta.messages.create(**requete)
    except anthropic.APIError as e:
        raise _erreur_api(anthropic, e) from e
    if reponse.stop_reason == "refusal":
        raise ErreurSuggestion("L'IA a refusé de traiter ce constat. Reformulez-le ou classez-le manuellement.")
    if reponse.stop_reason == "max_tokens":
        raise ErreurSuggestion("Réponse de l'IA tronquée : réessayez.")
    texte = next((b.text for b in reponse.content if b.type == "text"), None)
    u = reponse.usage
    usage = {"entree": u.input_tokens, "sortie": u.output_tokens,
             "cache_lu": getattr(u, "cache_read_input_tokens", 0) or 0,
             "cache_ecrit": getattr(u, "cache_creation_input_tokens", 0) or 0}
    return _extraire_json(texte), usage


def _appel_openai(sdk, requete):
    import openai

    try:
        try:
            reponse = sdk.chat.completions.create(**requete)
        except openai.BadRequestError as e:
            # Passerelle ou modèle qui n'accepte pas response_format : on réessaie sans (le schéma reste
            # décrit dans les consignes, et la réponse est validée ensuite)
            if "response_format" not in str(e) and "json_schema" not in str(e):
                raise
            sans = {k: v for k, v in requete.items() if k != "response_format"}
            reponse = sdk.chat.completions.create(**sans)
    except openai.APIError as e:
        raise _erreur_api(openai, e) from e
    if not reponse.choices:
        raise ErreurSuggestion("Réponse de l'IA vide : réessayez.")
    choix = reponse.choices[0]
    if choix.finish_reason == "content_filter" or getattr(choix.message, "refusal", None):
        raise ErreurSuggestion("L'IA a refusé de traiter ce constat. Reformulez-le ou classez-le manuellement.")
    if choix.finish_reason == "length":
        raise ErreurSuggestion("Réponse de l'IA tronquée : augmentez AUDIT_ERGO_MAX_TOKENS ou réessayez.")
    u = reponse.usage
    details = getattr(u, "prompt_tokens_details", None) if u else None
    usage = {"entree": getattr(u, "prompt_tokens", 0) or 0, "sortie": getattr(u, "completion_tokens", 0) or 0,
             "cache_lu": getattr(details, "cached_tokens", 0) or 0, "cache_ecrit": 0}
    return _extraire_json(choix.message.content), usage


DEFAUT = object()  # cache par défaut (CacheSuggestions.defaut())


def suggerer(client, ref, constat, ecran=None, critere_designer=None, contexte=None, cache=DEFAUT, forcer=False,
             recommandation_designer=None, gravite_designer=None):
    """Appelle l'IA et renvoie une Suggestion. `critere_designer` est un code du référentiel (ou None).

    `recommandation_designer` et `gravite_designer` (facultatifs) sont évaluées par l'IA.
    `client` est un ClientIA ; un client Anthropic nu est aussi accepté.
    Une réponse déjà obtenue pour la même requête est reprise du cache local (sauf `forcer=True`) ;
    `cache=None` désactive le cache.
    """
    if client is None:
        raise ErreurSuggestion("Aucune clé d'API configurée (API_KEY dans le fichier .env).")
    fmt, sdk = (client.format, client.sdk) if isinstance(client, ClientIA) else ("anthropic", client)
    libelle = None
    if critere_designer:
        c = ref.criteres[critere_designer]
        libelle = f"{c['code']} – {c['label_fr']} ({c['name']})"
    construire = construire_requete_openai if fmt == "openai" else construire_requete
    requete = construire(ref, constat, ecran, libelle, contexte, recommandation_designer, gravite_designer)
    avec_reco = bool(recommandation_designer and str(recommandation_designer).strip())

    cache = CacheSuggestions.defaut() if cache is DEFAUT else cache
    cle = cache.cle(fmt, requete) if cache else None
    if cache and not forcer and (memorise := cache.lire(cle)):
        try:
            suggestion = interpreter(ref, memorise["data"], critere_designer, avec_reco_designer=avec_reco)
            suggestion.depuis_cache = True
            return suggestion
        except (ErreurSuggestion, KeyError, TypeError):
            pass  # entrée illisible : on refait l'appel

    appel = _appel_openai if fmt == "openai" else _appel_anthropic
    data, usage = appel(sdk, requete)
    suggestion = interpreter(ref, data, critere_designer, usage, avec_reco)  # valide avant de mémoriser
    if cache:
        cache.ecrire(cle, {"data": data, "usage": usage})
    return suggestion


def verifier_audit(client, ref, audit, progression=None, paralleles=4, forcer=False):
    """Suggestion pour chaque constat de l'audit. Renvoie {ligne: Suggestion | ErreurSuggestion}.

    Les constats déjà analysés sont repris du cache local, sauf `forcer=True`.
    """
    cache = CacheSuggestions.defaut()
    contexte = {k: audit.contexte.get(k) for k in ("produit", "cible", "plateforme", "contexte_usage")}
    a_traiter = [c for c in audit.constats if c["constat"]]
    resultats = {}

    def une(c):
        try:
            return suggerer(client, ref, c["constat"], c["ecran"], ref.trouver_critere(c["critere"]), contexte,
                            cache, forcer, c["recommandation"], c["gravite"])
        except ErreurSuggestion as e:
            return e

    if not a_traiter:
        return resultats
    # Le premier appel écrit le référentiel en cache (si l'API le gère) ; les suivants, en parallèle, le relisent
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
