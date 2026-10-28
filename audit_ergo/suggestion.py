"""Suggestions de l'IA (modèle Mistral local) à partir d'un constat : critère, recommandation, gravité.

Principe : AUCUNE donnée ne quitte le poste du designer. L'IA est un modèle installé sur le poste
(Ollama, LM Studio, llama.cpp…) qui expose une API compatible OpenAI (/v1/chat/completions) sur
localhost. L'application refuse toute autre adresse, sauf autorisation explicite (serveur interne).

Configuration (environnement ou fichier .env à la racine du dépôt, voir .env.exemple) :
- API_BASE        : adresse du serveur local (défaut : http://localhost:11434/v1, celle d'Ollama) ;
- AUDIT_ERGO_MODELE : nom du modèle sur ce serveur (défaut : mistral-small) ;
- API_KEY         : facultative en local ;
- CA_BUNDLE       : certificats (PEM), seulement pour un serveur interne en HTTPS ;
- AUDIT_ERGO_RESEAU_AUTORISE=1 : autorise une adresse qui n'est pas locale (ex. serveur GPU interne).
"""
import ipaddress
import json
import os
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from .cache import CacheSuggestions
from .i18n import GRAVITES, TYPES_RECO, langue_defaut, t

FICHIER_ENV = Path(__file__).resolve().parent.parent / ".env"
CONFIANCES = ["haute", "moyenne", "faible"]
VERDICTS = ["confirme", "a_revoir", "incorrect", "non_fourni"]
STATUTS_RECO = ["bonne", "a_ameliorer", "hors_sujet", "non_fournie"]
ADRESSE_DEFAUT = "http://localhost:11434/v1"
NOMS_LANGUE = {"fr": "français", "en": "anglais"}


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
MODELE = os.environ.get("AUDIT_ERGO_MODELE", "mistral-small")
MAX_TOKENS = int(os.environ.get("AUDIT_ERGO_MAX_TOKENS", "4000"))
# Basse : un même constat doit donner la même réponse d'un designer à l'autre
TEMPERATURE = float(os.environ.get("AUDIT_ERGO_TEMPERATURE", "0.2"))
# Un modèle local traite en général une requête à la fois : en lancer plusieurs ne fait que les ralentir
PARALLELE = max(1, int(os.environ.get("AUDIT_ERGO_PARALLELE", "1")))
DELAI = float(os.environ.get("AUDIT_ERGO_DELAI", "600"))  # secondes : un modèle local sur CPU peut être lent


def _env(*noms):
    return next((os.environ[n].strip() for n in noms if os.environ.get(n, "").strip()), None)


def adresse_api():
    charger_env()
    return _env("API_BASE") or ADRESSE_DEFAUT


def ia_configuree():
    """L'IA est utilisable dès qu'une adresse est connue (celle d'Ollama par défaut) : pas de clé en local."""
    charger_env()
    return os.environ.get("AUDIT_ERGO_IA", "1") != "0"


def est_locale(adresse):
    """True si l'adresse désigne ce poste (localhost, 127.0.0.0/8, ::1)."""
    hote = (urlparse(adresse).hostname or "").lower()
    if hote in ("localhost", "localhost.localdomain") or hote.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(hote).is_loopback
    except ValueError:
        return False


def verifier_adresse(adresse):
    """Refuse toute adresse qui ferait sortir les données du poste, sauf autorisation explicite."""
    if urlparse(adresse).scheme not in ("http", "https") or not urlparse(adresse).hostname:
        raise ErreurSuggestion(f"API_BASE invalide : « {adresse} » (attendu : http://localhost:11434/v1).")
    if not est_locale(adresse) and os.environ.get("AUDIT_ERGO_RESEAU_AUTORISE") != "1":
        raise ErreurSuggestion(
            f"API_BASE ({adresse}) n'est pas une adresse locale : les constats quitteraient le poste. "
            "Utilisez le modèle installé sur ce poste (ex. http://localhost:11434/v1), ou, pour un serveur "
            "interne validé par votre organisation, ajoutez AUDIT_ERGO_RESEAU_AUTORISE=1 dans le fichier .env.")


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


def _base_url(adresse):
    """Le SDK ajoute lui-même /chat/completions : on l'enlève si l'adresse le contient déjà."""
    adresse = adresse.rstrip("/")
    for suffixe in ("/chat/completions", "/completions"):
        if adresse.endswith(suffixe):
            return adresse[: -len(suffixe)]
    return adresse


def client_ou_none(api_key=None):
    """Client pour le modèle local, ou None si l'IA est désactivée (AUDIT_ERGO_IA=0).

    Lève ErreurSuggestion si l'adresse n'est pas locale (sans autorisation) ou si CA_BUNDLE est invalide.
    """
    if not ia_configuree():
        return None
    adresse = adresse_api()
    verifier_adresse(adresse)
    import openai

    # trust_env=False : jamais de proxy, même si HTTPS_PROXY est défini sur le poste ; la connexion va
    # directement au serveur local
    options = {"trust_env": False, "timeout": DELAI}
    if contexte_ssl := _contexte_ssl():
        options["verify"] = contexte_ssl
    return openai.OpenAI(api_key=api_key or _env("API_KEY") or "local", base_url=_base_url(adresse),
                         max_retries=1, http_client=openai.DefaultHttpxClient(**options))


# --- Prompt -----------------------------------------------------------------------------------------

def _texte_referentiel(ref):
    """Référentiel complet en texte, identique d'un appel à l'autre (les serveurs locaux réutilisent alors
    le début du prompt déjà calculé, ce qui accélère nettement les appels suivants)."""
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


ECHELLE = "\n".join(f"{g} = {v['fr']} / {v['en']} : {v['def_fr']}" for g, v in GRAVITES.items())

CONSIGNES = f"""Tu assistes des UX designers qui réalisent des audits ergonomiques heuristiques. \
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
8. Propose une recommandation spécifique (nomme l'élément à modifier), actionnable (une équipe peut \
l'implémenter sans réinterpréter), qui traite la cause, vérifiable, et appuyée sur une norme ou un usage \
reconnu quand c'est pertinent (WCAG, guidelines de la plateforme). Une à trois phrases.
9. Si le designer a rédigé une recommandation, évalue-la : « bonne » si elle remplit ces conditions, \
« a_ameliorer » si elle est juste mais incomplète ou vague (donne alors une version améliorée qui garde \
son intention), « hors_sujet » si elle ne traite pas le problème. Sinon, « non_fournie ».
10. Ajoute au besoin une ou deux recommandations complémentaires, sinon aucune.
11. Indique le type de recommandation : design, test (test utilisateur), formation ou procedure.

Gravité (échelle à 4 niveaux) :
{ECHELLE}
12. Estime la gravité d'après la fréquence, l'impact et la persistance du problème, en une phrase de \
justification. Si le designer a indiqué une gravité différente, explique l'écart.

N'utilise que les codes du référentiel. Réponds de façon concise et factuelle."""


def _schema(ref):
    codes = list(ref.criteres)
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
                    "regle": {"type": "string", "enum": list(ref.regles) + ["aucune"]},
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
                "items": {"type": "object", "properties": {"code": code, "pourquoi_pas": {"type": "string"}},
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
                    "type": {"type": "string", "enum": list(TYPES_RECO)},
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
                "required": ["proposee", "type", "avis_designer", "complementaires"],
                "additionalProperties": False,
            },
            "gravite": {
                "type": "object",
                "properties": {"valeur": {"type": "integer", "enum": list(GRAVITES)},
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
    if gravite_designer in GRAVITES:
        parties.append(f"Gravité indiquée par le designer : {gravite_designer} "
                       f"({GRAVITES[gravite_designer]['fr']})")
    return "\n".join(parties)


def construire_requete(ref, constat, ecran=None, critere_designer=None, contexte=None, recommandation_designer=None,
                       gravite_designer=None, langue="fr"):
    """Paramètres de l'appel (/v1/chat/completions). Testable sans serveur.

    Le schéma est à la fois demandé via response_format et décrit dans les consignes, car tous les
    serveurs locaux ne respectent pas response_format.
    """
    schema = _schema(ref)
    consigne_json = ("Réponds uniquement avec un objet JSON valide, sans texte autour ni bloc de code, "
                     "conforme à ce schéma JSON :\n" + json.dumps(schema, ensure_ascii=False))
    consigne_langue = (f"Rédige tous les textes de la réponse (justifications, recommandations, commentaires) "
                       f"en {NOMS_LANGUE.get(langue, 'français')}. Les codes et les valeurs imposées par le "
                       f"schéma restent tels quels.")
    return {
        "model": MODELE,
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE,
        "messages": [
            # Contenu stable en tête : le serveur local réutilise ce début de prompt d'un appel à l'autre
            {"role": "system", "content": f"{CONSIGNES}\n\n{_texte_referentiel(ref)}\n\n{consigne_json}"},
            {"role": "user", "content": _message(constat, ecran, critere_designer, contexte,
                                                 recommandation_designer, gravite_designer)
                                        + f"\n\n{consigne_langue}"},
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
    type_reco: str | None = None  # clé de TYPES_RECO
    reco_statut: str = "non_fournie"  # avis sur la recommandation du designer (STATUTS_RECO)
    reco_commentaire: str = ""
    reco_amelioree: str = ""  # version améliorée de la recommandation du designer, si utile
    reco_complementaires: list = field(default_factory=list)
    gravite: int | None = None  # gravité estimée par l'IA (1 à 4)
    justification_gravite: str = ""
    usage: dict = field(default_factory=dict)
    depuis_cache: bool = False  # True : réponse reprise du cache local, sans nouvel appel

    def ligne_excel(self, ref, langue="fr"):
        """Texte prêt à coller dans le template."""
        txt = ref.libelle_critere(self.code, langue)
        if self.secondaires:
            txt += " | " + ("Secondary" if langue == "en" else "Secondaires") + " : " + \
                   " ; ".join(s["code"] for s in self.secondaires)
        if self.regle != "aucune":
            txt += f" | {'Rule' if langue == 'en' else 'Règle'} : {self.regle}"
        return txt

    @property
    def justification_critere(self):
        """Justification du critère principal, prête à figurer dans l'audit : raison, règle et checklist."""
        txt = self.justification.strip()
        if self.regle != "aucune":
            txt += f" ({self.regle})"
        if self.question_checklist:
            txt += f" Checklist : « {self.question_checklist.strip()} »"
        return txt

    @property
    def reco_a_retenir(self):
        """Recommandation à proposer : la version améliorée de celle du designer si elle existe, sinon celle de l'IA."""
        return self.reco_amelioree or self.reco_proposee


def interpreter(ref, data, critere_designer=None, usage=None, avec_reco_designer=False):
    """Valide la réponse JSON du modèle et la convertit en Suggestion.

    Un modèle local ne respecte pas toujours le schéma : tout est donc revérifié ici.
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

    reco = data.get("recommandation") if isinstance(data.get("recommandation"), dict) else {}
    suggestion.reco_proposee = str(reco.get("proposee") or "").strip()
    suggestion.type_reco = reco.get("type") if reco.get("type") in TYPES_RECO else None
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
        if valeur in GRAVITES:
            suggestion.gravite = valeur
            suggestion.justification_gravite = str(grav.get("justification") or "").strip()
    except (TypeError, ValueError):
        pass
    return suggestion


# --- Appel ------------------------------------------------------------------------------------------

def _erreur_api(e):
    """Traduit une exception du SDK en message lisible, avec la marche à suivre pour un modèle local."""
    import openai

    adresse = adresse_api()
    if isinstance(e, openai.APIConnectionError):
        return ErreurSuggestion(
            f"Le modèle local ne répond pas à {adresse}. Vérifiez qu'il est lancé (Ollama : application "
            "ouverte, ou « ollama serve ») et que API_BASE est correct.")
    if isinstance(e, openai.NotFoundError):
        return ErreurSuggestion(
            f"Modèle « {MODELE} » introuvable sur {adresse}. Vérifiez AUDIT_ERGO_MODELE (Ollama : « ollama list » "
            f"affiche les modèles installés ; « ollama pull {MODELE} » l'installe).")
    if isinstance(e, (openai.AuthenticationError, openai.PermissionDeniedError)):
        return ErreurSuggestion("Le serveur local refuse la clé : vérifiez API_KEY (souvent inutile en local).")
    if isinstance(e, openai.BadRequestError):
        return ErreurSuggestion(f"Requête refusée par le serveur local : {e.message}")
    if isinstance(e, openai.APITimeoutError):
        return ErreurSuggestion(f"Le modèle local n'a pas répondu en {DELAI:.0f} s : augmentez AUDIT_ERGO_DELAI ou "
                                "utilisez un modèle plus léger.")
    if isinstance(e, openai.APIStatusError):
        return ErreurSuggestion(f"Erreur du serveur local ({e.status_code}) : {e.message}")
    raise e


def _extraire_json(texte):
    """JSON de la réponse, même entouré de texte ou d'un bloc ```json."""
    if not texte:
        raise ErreurSuggestion("Réponse de l'IA vide : réessayez.")
    debut, fin = texte.find("{"), texte.rfind("}")
    try:
        return json.loads(texte[debut:fin + 1] if debut != -1 and fin > debut else texte)
    except json.JSONDecodeError as e:
        raise ErreurSuggestion("Réponse de l'IA illisible (JSON invalide) : réessayez, ou utilisez un modèle "
                               "plus grand.") from e


def _verifier_contexte(requete, prompt_tokens):
    """Détecte un prompt tronqué : un serveur local (Ollama) coupe sans prévenir ce qui dépasse sa fenêtre de
    contexte, et le modèle répond alors sans avoir lu le référentiel."""
    if not prompt_tokens:
        return
    estimation = sum(len(m["content"]) for m in requete["messages"]) / 4.5  # ~4,5 caractères par token
    if prompt_tokens < 0.6 * estimation:
        raise ErreurSuggestion(
            f"Le modèle local n'a lu que {prompt_tokens} tokens sur environ {estimation:.0f} : sa fenêtre de "
            "contexte est trop petite et le référentiel a été tronqué. Augmentez-la à 16384 au moins "
            "(Ollama : variable d'environnement OLLAMA_CONTEXT_LENGTH=16384 puis redémarrer Ollama ; "
            "LM Studio : réglage « Context Length » du modèle).")


def _appeler(client, requete):
    import openai

    try:
        try:
            reponse = client.chat.completions.create(**requete)
        except openai.BadRequestError as e:
            # Serveur ou modèle qui n'accepte pas response_format : on réessaie sans (le schéma reste décrit
            # dans les consignes, et la réponse est validée ensuite)
            if "response_format" not in str(e) and "json_schema" not in str(e):
                raise
            reponse = client.chat.completions.create(**{k: v for k, v in requete.items() if k != "response_format"})
    except openai.APIError as e:
        raise _erreur_api(e) from e
    if not reponse.choices:
        raise ErreurSuggestion("Réponse de l'IA vide : réessayez.")
    u = reponse.usage
    _verifier_contexte(requete, getattr(u, "prompt_tokens", 0) if u else 0)
    choix = reponse.choices[0]
    if choix.finish_reason == "content_filter" or getattr(choix.message, "refusal", None):
        raise ErreurSuggestion("L'IA a refusé de traiter ce constat. Reformulez-le ou classez-le manuellement.")
    if choix.finish_reason == "length":
        raise ErreurSuggestion("Réponse de l'IA tronquée : augmentez AUDIT_ERGO_MAX_TOKENS ou réessayez.")
    usage = {"entree": getattr(u, "prompt_tokens", 0) or 0, "sortie": getattr(u, "completion_tokens", 0) or 0}
    return _extraire_json(choix.message.content), usage


DEFAUT = object()  # cache par défaut (CacheSuggestions.defaut())


def suggerer(client, ref, constat, ecran=None, critere_designer=None, contexte=None, cache=DEFAUT, forcer=False,
             recommandation_designer=None, gravite_designer=None, langue=None):
    """Interroge le modèle local et renvoie une Suggestion.

    `critere_designer` est un code du référentiel (ou None) ; `recommandation_designer` et `gravite_designer`
    (1 à 4), facultatifs, sont évalués par l'IA. Les textes de la réponse sont rédigés dans `langue`.
    Une réponse déjà obtenue pour la même requête est reprise du cache local (sauf `forcer=True`) ;
    `cache=None` désactive le cache.
    """
    if client is None:
        raise ErreurSuggestion("IA désactivée (AUDIT_ERGO_IA=0 dans le fichier .env).")
    langue = langue or langue_defaut()
    libelle = ref.libelle_critere(critere_designer) if critere_designer else None
    requete = construire_requete(ref, constat, ecran, libelle, contexte, recommandation_designer, gravite_designer,
                                 langue)
    avec_reco = bool(recommandation_designer and str(recommandation_designer).strip())

    cache = CacheSuggestions.defaut() if cache is DEFAUT else cache
    cle = cache.cle("local", requete) if cache else None
    if cache and not forcer and (memorise := cache.lire(cle)):
        try:
            suggestion = interpreter(ref, memorise["data"], critere_designer, avec_reco_designer=avec_reco)
            suggestion.depuis_cache = True
            return suggestion
        except (ErreurSuggestion, KeyError, TypeError):
            pass  # entrée illisible : on refait l'appel

    data, usage = _appeler(client, requete)
    suggestion = interpreter(ref, data, critere_designer, usage, avec_reco)  # valide avant de mémoriser
    if cache:
        cache.ecrire(cle, {"data": data, "usage": usage})
    return suggestion


def verifier_audit(client, ref, audit, progression=None, paralleles=None, forcer=False, langue=None):
    """Suggestion pour chaque constat de l'audit. Renvoie {ligne: Suggestion | ErreurSuggestion}.

    Les constats déjà analysés sont repris du cache local, sauf `forcer=True`.
    """
    from .i18n import lire_gravite

    cache = CacheSuggestions.defaut()
    contexte = {k: audit.contexte.get(k) for k in ("produit", "cible", "plateforme", "contexte_usage")}
    a_traiter = [c for c in audit.constats if c["constat"]]
    resultats = {}

    def une(c):
        try:
            return suggerer(client, ref, c["constat"], c["ecran"], ref.trouver_critere(c["critere"]), contexte,
                            cache, forcer, c["recommandation"], lire_gravite(c["gravite"]), langue)
        except ErreurSuggestion as e:
            return e

    with ThreadPoolExecutor(max_workers=paralleles or PARALLELE) as pool:
        futures = {pool.submit(une, c): c.ligne for c in a_traiter}
        for i, f in enumerate(as_completed(futures), 1):
            resultats[futures[f]] = f.result()
            if progression:
                progression(i, len(a_traiter))
    return resultats


def libelle_verdict(statut, langue="fr"):
    return t(f"verdict.{statut}", langue)


def libelle_reco(statut, langue="fr"):
    return t(f"reco.{statut}", langue)
