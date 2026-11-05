"""API de l'application : relecture d'un audit, suggestion d'un critère, rapport de synthèse (HTML et Word).

Les audits déposés sont enregistrés sur ce poste (voir `historique.py`) et se rouvrent après un redémarrage.
"""
import io
import threading
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from audit_ergo import ErreurLecture, Referentiel, parametres, relire
from audit_ergo.cache import CacheSuggestions
from audit_ergo.chemins import ressources
from audit_ergo.completion import decider
from audit_ergo.controles import controler
from audit_ergo.export import exporter
from audit_ergo.i18n import LANGUES, langue_defaut
from audit_ergo.rapport import ecrire_docx, faits, maturite_indicative, rediger
from audit_ergo.suggestion import (FICHIER_ENV, ErreurSuggestion, client_ou_none, connexion, est_locale,
                                   ia_configuree, suggerer)
from audit_ergo.synthese import synthetiser

from . import APP_ID, APP_NOM, VERSION
from . import serialisation as ser
from .historique import Historique, maintenant
from .taches import Taches

RACINE = ressources()  # interface et templates : dans le dépôt, ou dans AuditErgo.exe
WEB = RACINE / "web" / "dist"
TEMPLATES = {"fr": RACINE / "template" / "Audit_ergonomique_FR.xlsx", "en": RACINE / "template" / "Ergonomic_audit_EN.xlsx"}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TAILLE_MAX = 30 * 1024 * 1024  # un audit Excel, même avec des captures, reste bien en dessous

MESSAGES = {
    # Test de connexion de l'écran Réglages : (titre, explication) en français puis en anglais
    "ok": ("Connexion opérationnelle", "Connection working"),
    "ok_detail": ("modèle {m}", "model {m}"),
    "configuration": ("Échec de la connexion : paramètres invalides", "Connection failed: invalid settings"),
    "certificat": ("Échec de la connexion : certificat non reconnu", "Connection failed: certificate not recognised"),
    "certificat_detail": ("Le serveur a été joint, mais la connexion sécurisée a été refusée. Importez le certificat (.crt) "
                          "de l'autorité qui a signé celui du serveur, fourni par votre service informatique.",
                          "The server was reached, but the secure connection was refused. Import the certificate (.crt) "
                          "of the authority that signed the server's certificate, provided by your IT department."),
    "delai": ("Échec de la connexion : délai dépassé", "Connection failed: timeout"),
    "delai_detail": ("Le service n'a pas répondu à temps. Vérifiez l'adresse et votre accès au réseau.",
                     "The service did not answer in time. Check the address and your network access."),
    "injoignable": ("Échec de la connexion : serveur injoignable", "Connection failed: server unreachable"),
    "injoignable_detail": ("Aucune réponse de {a}. Vérifiez l'adresse, votre accès au réseau (VPN), ou lancez Ollama "
                           "(ou LM Studio) s'il est sur ce poste.",
                           "No answer from {a}. Check the address, your network access (VPN), or start Ollama "
                           "(or LM Studio) if it runs on this computer."),
    "cle": ("Échec de la connexion : clé API refusée", "Connection failed: API key refused"),
    "cle_detail": ("Le service a refusé la clé API. Vérifiez qu'elle a été copiée en entier et qu'elle est toujours valide.",
                   "The service refused the API key. Check that it was copied in full and is still valid."),
    "introuvable_adresse": ("Échec de la connexion : adresse ou modèle introuvable", "Connection failed: address or model not found"),
    "introuvable_adresse_detail": ("Le service répond, mais l'adresse ou le modèle demandé n'existe pas. Vérifiez l'adresse "
                                   "(elle se termine souvent par /v1) et le modèle.",
                                   "The service answers, but the address or the requested model does not exist. Check the "
                                   "address (it often ends with /v1) and the model."),
    "absent": ("Modèle « {m} » introuvable", "Model “{m}” not found"),
    "absent_detail": ("Le serveur répond, mais ce modèle n'y est pas installé. Modèles disponibles : {liste}. Corrigez le "
                      "modèle (options avancées), ou installez-le (« ollama pull {m} »).",
                      "The server answers, but this model is not installed. Available models: {liste}. Fix the model "
                      "(advanced options), or install it (“ollama pull {m}”)."),
    "erreur_statut": ("Échec de la connexion : erreur {code}", "Connection failed: error {code}"),
    "echec": ("Échec de la connexion", "Connection failed"),
    "desactivee": ("IA désactivée (AUDIT_ERGO_IA=0) : seuls les contrôles de forme sont disponibles.",
                   "AI disabled (AUDIT_ERGO_IA=0): only form checks are available."),
    "certificat_invalide": ("Ce fichier n'est pas un certificat valide (.crt au format PEM ou DER attendu).",
                            "This file is not a valid certificate (.crt in PEM or DER format expected)."),
    "illisible": ("Impossible de lire ce fichier : {e}", "Cannot read this file: {e}"),
    "corrompu": ("Le fichier n'a pas pu être ouvert ({e}). Vérifiez qu'il s'agit d'un .xlsx valide.",
                 "The file could not be opened ({e}). Check that it is a valid .xlsx file."),
    "format": ("Déposez un fichier Excel (.xlsx).", "Drop an Excel file (.xlsx)."),
    "trop_gros": ("Fichier trop volumineux (30 Mo au plus).", "File too large (30 MB at most)."),
    "introuvable": ("Audit introuvable : déposez-le à nouveau.", "Audit not found: drop it again."),
    "sans_ia": ("IA indisponible : vérifiez la connexion au modèle.", "AI unavailable: check the model connection."),
    "vide": ("Le constat est vide.", "The finding is empty."),
    "pas_de_rapport": ("Générez d'abord le rapport.", "Generate the report first."),
}


def message(cle, lg, **valeurs):
    fr, en = MESSAGES[cle]
    texte = en if lg == "en" else fr
    return texte.format(**valeurs) if valeurs else texte


def _langue(lg):
    return lg if lg in LANGUES else langue_defaut()


@dataclass
class Session:
    """Un audit déposé : fichier d'origine, relecture en cours et rapport."""
    id: str
    nom: str
    dossier: Path
    langue: str
    cree: str = ""
    audit: object = None
    anomalies: list = field(default_factory=list)
    synthese: object = None
    ia: dict | None = None
    fichier: bytes = b""
    nom_sortie: str = ""
    rapport: object = None
    rapport_perime: bool = False  # l'audit a changé depuis la génération du rapport
    verrou: threading.RLock = field(default_factory=threading.RLock)

    @property
    def entree(self):
        return self.dossier / self.nom

    @property
    def sortie(self):
        return self.dossier / f"{self.stem}_relu.xlsx"

    @property
    def stem(self):
        return Path(self.nom).stem


# Parties du rapport que le designer peut modifier dans l'application
TEXTES_RAPPORT = {"resume", "maturite_justification", "impact"}
LISTES_RAPPORT = {"points_forts", "faiblesses", "recurrents", "demarche"}
OBJETS_RAPPORT = {"themes": {"titre", "description", "pourquoi", "consequences"},
                  "recommandations": {"titre", "objectif", "importance", "benefices", "problemes_resolus"},
                  "quick_wins": {"titre", "description", "valeur"},
                  "suites": {"titre", "description"}}


def modifier_rapport(r, chemin, valeur):
    """Applique une modification du designer : « resume », « points_forts », « themes.0.description »…"""
    parties = chemin.split(".")
    if len(parties) == 1 and parties[0] in TEXTES_RAPPORT and isinstance(valeur, str):
        setattr(r, parties[0], valeur.strip())
    elif len(parties) == 1 and parties[0] in LISTES_RAPPORT and isinstance(valeur, list):
        setattr(r, parties[0], [str(v).strip() for v in valeur if str(v).strip()])
    elif chemin == "maturite" and valeur in (1, 2, 3, 4, 5):
        r.maturite = valeur
    elif (len(parties) == 3 and parties[0] in OBJETS_RAPPORT and parties[2] in OBJETS_RAPPORT[parties[0]]
          and parties[1].isdigit() and int(parties[1]) < len(getattr(r, parties[0])) and isinstance(valeur, str)):
        setattr(getattr(r, parties[0])[int(parties[1])], parties[2], valeur.strip())
    else:
        raise ValueError(f"Modification refusée : {chemin}")
    r.modifie = True


DELAI_TEST = 30.0  # secondes : le test de l'écran Réglages ne doit pas faire attendre 10 minutes


class DemandeParametres(BaseModel):
    api_base: str = ""
    api_key: str | None = None  # None : garder la clé enregistrée
    model: str = parametres.MODELE_DEFAUT
    timeout: float = Field(default=parametres.DELAI_DEFAUT, ge=10, le=3600)


def creer_app(ref=None, historique=None):
    ref = ref or Referentiel.charger()
    historique = historique or Historique.defaut()
    sessions: dict[str, Session] = {}
    taches = Taches()
    app = FastAPI(title="Audit ergonomique assisté", docs_url=None, redoc_url=None, openapi_url=None)
    # Refuse les requêtes adressées à un autre nom que ce poste (protection contre le « DNS rebinding » :
    # une page web malveillante ne peut pas atteindre l'application par un nom de domaine qui pointe ici)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])

    def client():
        """Client du modèle, ou None (IA désactivée). Lève HTTPException si la configuration est refusée."""
        try:
            return client_ou_none()
        except ErreurSuggestion as e:
            raise HTTPException(400, str(e)) from e

    def session(id_, lg="fr"):
        s = sessions.get(id_)
        if s is None:  # audit d'une séance précédente : rouvert depuis l'historique
            etat = historique.charger(id_)
            if etat is None:
                raise HTTPException(404, message("introuvable", lg))
            s = Session(id=id_, dossier=historique.dossier(id_), **{k: v for k, v in etat.items() if k != "version"})
            s.audit.chemin = str(s.entree)  # le dossier de l'application a pu être déplacé
            if s.sortie.exists():
                s.fichier = s.sortie.read_bytes()
            else:
                recalculer(s, perime=False)
            sessions[id_] = s
        return s

    def resume(s):
        """Ce qu'affiche la liste des audits enregistrés."""
        ctx, syn = s.audit.contexte, s.synthese
        gravites = {int(k): v for k, v in syn.gravites.items()}
        return {
            "nom": s.nom, "produit": ser.valeur(ctx.get("produit")), "designer": ser.valeur(ctx.get("designer")),
            "date": ser.valeur(ctx.get("date")), "plateforme": ser.valeur(ctx.get("plateforme")),
            "nb_constats": syn.nb_constats, "nb_problemes": syn.nb_problemes, "nb_points_forts": syn.nb_points_forts,
            "gravites": {str(k): v for k, v in gravites.items()}, "nb_bloquants": syn.nb_bloquants,
            "maturite_indicative": maturite_indicative(gravites, syn.nb_problemes),
            "ia": s.ia is not None, "rapport": s.rapport is not None,
            "a_valider": sum(1 for a in s.audit.completions.values() for (_, o, _) in a.values() if o != "valide"),
        }

    def sauver(s):
        try:
            historique.enregistrer(s, resume(s))
        except OSError:  # disque plein, droits… : l'audit reste utilisable pendant la séance
            pass

    def etat(s):
        return {**ser.etat_audit(s, ref), "persistant": historique.persistant}

    def recalculer(s, lg=None, perime=True):
        """Contrôles, synthèse et fichier annoté à partir de l'audit en mémoire (sans IA)."""
        s.langue = _langue(lg or s.langue)
        s.anomalies = controler(s.audit, ref, s.langue)
        s.synthese = synthetiser(s.audit, s.anomalies, ref)
        exporter(s.audit, s.anomalies, s.synthese, ref, s.sortie, s.ia, s.langue)
        s.fichier = s.sortie.read_bytes()
        s.nom_sortie = f"{s.stem}_complete.xlsx" if s.audit.completions else f"{s.stem}_relu.xlsx"
        # Le rapport correspond à un état de l'audit : il est gardé (avec les modifications du designer), mais
        # signalé comme à régénérer
        s.rapport_perime = s.rapport_perime or (perime and s.rapport is not None)

    def analyser(s, cl=None, progression=None, forcer=False, remplir=True):
        audit, anomalies, synthese, sortie, ia = relire(s.entree, s.sortie, ref, cl, progression, forcer, remplir,
                                                        s.langue)
        s.audit, s.anomalies, s.synthese, s.ia = audit, anomalies, synthese, ia
        s.fichier = Path(sortie).read_bytes()
        s.nom_sortie = f"{s.stem}_complete.xlsx" if audit.completions else f"{s.stem}_relu.xlsx"
        s.rapport_perime = s.rapport is not None

    # --- Contrat du portail ---------------------------------------------------------------------------

    @app.get("/health")
    def sante():
        """Répond dès que le serveur tourne, que l'IA soit configurée ou non."""
        return {"status": "ok", "app": APP_ID, "name": APP_NOM, "version": VERSION}

    # --- Configuration ---------------------------------------------------------------------------------

    @app.get("/api/config")
    def config(langue: str = ""):
        lg = _langue(langue)
        cache = CacheSuggestions.defaut()
        p = connexion()
        return {
            "langue_defaut": langue_defaut(), "langues": LANGUES,
            "referentiel": ser.referentiel(ref, lg),
            "ia": {"active": ia_configuree(), "modele": p.model, "adresse": p.api_base, "cle": bool(p.api_key),
                   "ca_bundle": Path(p.ca_bundle).name if p.ca_bundle else "", "locale": est_locale(p.api_base),
                   "hote": urlparse(p.api_base).hostname or ""},
            "cache": None if cache is None else cache.taille(),
        }

    # --- Paramètres de connexion au modèle (écran Réglages, comme SpecGen) -----------------------------

    def parametres_publics():
        connexion()  # recharge le .env : une valeur modifiée à la main est prise en compte sans redémarrer
        return {**parametres.publics(FICHIER_ENV), "active": ia_configuree()}

    @app.get("/api/settings")
    def lire_parametres():
        return parametres_publics()

    @app.put("/api/settings")
    def enregistrer_parametres(demande: DemandeParametres):
        parametres.enregistrer(demande.api_base, demande.api_key, demande.model, demande.timeout)
        return parametres_publics()

    @app.delete("/api/settings")
    def effacer_parametres():
        parametres.effacer()
        return parametres_publics()

    @app.post("/api/settings/certificate")
    def importer_certificat(file: UploadFile = File(...), langue: str = ""):
        try:
            parametres.importer_certificat(file.filename or "certificat.crt", file.file.read())
        except ValueError as e:
            raise HTTPException(422, message("certificat_invalide", _langue(langue))) from e
        return parametres_publics()

    @app.post("/api/settings/test")
    def tester_parametres(demande: DemandeParametres, langue: str = ""):
        """Teste les valeurs saisies (pas encore enregistrées) avec le certificat enregistré."""
        lg = _langue(langue)
        en_vigueur = connexion()
        env = en_vigueur.depuis_env
        candidat = replace(
            en_vigueur,
            api_base=en_vigueur.api_base if "api_base" in env else (demande.api_base.strip() or parametres.ADRESSE_DEFAUT),
            api_key=en_vigueur.api_key if demande.api_key is None or "api_key" in env else demande.api_key.strip(),
            model=en_vigueur.model if "model" in env else (demande.model.strip() or parametres.MODELE_DEFAUT),
            timeout=min(en_vigueur.timeout if "timeout" in env else demande.timeout, DELAI_TEST),
        )
        resultat = _tester(candidat, lg)
        resultat.update({"at": datetime.now(timezone.utc).isoformat(), "model": candidat.model})
        if resultat.get("field") != "disabled":
            parametres.enregistrer_test(resultat)
        return resultat

    def _tester(p, lg):
        if not ia_configuree():
            return _echec("disabled", message("desactivee", lg), "", lg)
        try:
            cl = client_ou_none(params=p)
        except ErreurSuggestion as e:
            return _echec("api_base", message("configuration", lg), str(e), lg)
        import openai

        try:
            modeles = [m.id for m in cl.models.list()]
        except (openai.AuthenticationError, openai.PermissionDeniedError) as e:
            return _diagnostic(e, p, lg)
        except openai.APIStatusError:
            # Passerelle sans /v1/models (404, 405, 501…) : elle répond, mais ne liste pas ses modèles.
            # Un petit appel au modèle vérifie l'adresse, la clé et le nom du modèle.
            try:
                cl.chat.completions.create(model=p.model, max_tokens=1, messages=[{"role": "user", "content": "ping"}])
            except Exception as e:  # noqa: BLE001 : diagnostiqué ci-dessous
                return _diagnostic(e, p, lg)
            return _reussite(p, lg)
        except Exception as e:  # noqa: BLE001 : serveur injoignable, certificat refusé, clé refusée…
            return _diagnostic(e, p, lg)
        # Ollama nomme les modèles « nom:étiquette » ; « mistral-small » désigne « mistral-small:latest »
        if any(m == p.model or m.split(":")[0] == p.model for m in modeles):
            return _reussite(p, lg)
        return _echec("model", message("absent", lg, m=p.model),
                      message("absent_detail", lg, m=p.model, liste=", ".join(modeles) or "—"), lg)

    def _reussite(p, lg):
        return {"ok": True, "field": None, "title": message("ok", lg), "message": message("ok_detail", lg, m=p.model)}

    def _echec(champ, titre, explication, lg):
        return {"ok": False, "field": champ, "title": titre, "message": explication}

    def _diagnostic(e, p, lg):
        import ssl

        import openai

        cause, chaine = e, []
        while cause is not None and len(chaine) < 10:
            chaine.append(cause)
            cause = cause.__cause__ or cause.__context__
        if any(isinstance(c, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in str(c) for c in chaine):
            return _echec("certificate", message("certificat", lg), message("certificat_detail", lg), lg)
        if isinstance(e, openai.APITimeoutError):
            return _echec("api_base", message("delai", lg), message("delai_detail", lg), lg)
        if isinstance(e, openai.APIConnectionError):
            return _echec("api_base", message("injoignable", lg), message("injoignable_detail", lg, a=p.api_base), lg)
        if isinstance(e, (openai.AuthenticationError, openai.PermissionDeniedError)):
            return _echec("api_key", message("cle", lg), message("cle_detail", lg), lg)
        if isinstance(e, openai.NotFoundError):
            return _echec("api_base", message("introuvable_adresse", lg), message("introuvable_adresse_detail", lg), lg)
        if isinstance(e, openai.APIStatusError):
            return _echec(None, message("erreur_statut", lg, code=e.status_code), str(e.message), lg)
        return _echec(None, message("echec", lg), f"{type(e).__name__} : {e}", lg)

    @app.delete("/api/cache")
    def vider_cache():
        cache = CacheSuggestions.defaut()
        if cache:
            cache.vider()
        return {"cache": 0 if cache else None}

    @app.get("/api/template")
    def template(langue: str = ""):
        chemin = TEMPLATES[_langue(langue)]
        return FileResponse(chemin, media_type=XLSX, filename=chemin.name)

    # --- Suggérer un critère ---------------------------------------------------------------------------

    class DemandeSuggestion(BaseModel):
        constat: str
        ecran: str = ""
        critere: str = ""
        recommandation: str = ""
        gravite: int | None = None
        contexte: dict = {}
        forcer: bool = False
        langue: str = ""

    @app.post("/api/suggestion")
    def suggestion(d: DemandeSuggestion):
        lg = _langue(d.langue)
        if not d.constat.strip():
            raise HTTPException(400, message("vide", lg))
        cl = client()
        if cl is None:
            raise HTTPException(400, message("sans_ia", lg))
        critere = d.critere if d.critere in ref.criteres else None
        gravite = d.gravite if d.gravite in (1, 2, 3, 4) else None
        contexte = {k: v for k, v in d.contexte.items() if k in ("produit", "cible", "plateforme") and v}

        def executer(tache):
            s = suggerer(cl, ref, d.constat, d.ecran or None, critere, contexte, forcer=d.forcer,
                         recommandation_designer=d.recommandation or None, gravite_designer=gravite, langue=lg)
            return {"suggestion": ser.suggestion(s, ref, lg), "constat": d.constat, "ecran": d.ecran}

        return taches.lancer("suggestion", executer).vue()

    # --- Relire un audit -------------------------------------------------------------------------------

    @app.post("/api/audits")
    async def deposer(fichier: UploadFile = File(...), langue: str = Form("")):
        lg = _langue(langue)
        nom = Path(fichier.filename or "audit.xlsx").name
        if not nom.lower().endswith(".xlsx"):
            raise HTTPException(400, message("format", lg))
        contenu = await fichier.read()
        if len(contenu) > TAILLE_MAX:
            raise HTTPException(413, message("trop_gros", lg))
        id_ = uuid.uuid4().hex
        s = Session(id=id_, nom=nom, dossier=historique.dossier(id_), langue=lg, cree=maintenant())
        s.entree.write_bytes(contenu)
        try:
            analyser(s)
        except ErreurLecture as e:
            historique.supprimer(id_)
            raise HTTPException(400, message("illisible", lg, e=e)) from e
        except Exception as e:  # noqa: BLE001 : fichier corrompu, protégé par mot de passe…
            historique.supprimer(id_)
            raise HTTPException(400, message("corrompu", lg, e=type(e).__name__)) from e
        sessions[s.id] = s
        sauver(s)
        return etat(s)

    @app.get("/api/audits")
    def lister():
        return {"audits": historique.lister(), "persistant": historique.persistant}

    @app.get("/api/audits/{id_}")
    def lire(id_: str, langue: str = ""):
        s = session(id_, _langue(langue))
        with s.verrou:
            if langue and _langue(langue) != s.langue:  # messages et annotations dans la nouvelle langue
                recalculer(s, langue, perime=False)
                sauver(s)
            return etat(s)

    @app.delete("/api/audits/{id_}")
    def supprimer(id_: str):
        """Supprime l'audit de ce poste (fichier déposé, relecture et rapport)."""
        sessions.pop(id_, None)
        historique.supprimer(id_)
        return {"ok": True}

    @app.get("/api/comparaison")
    def comparer(a: str, b: str, langue: str = ""):
        """Deux audits côte à côte (deux versions d'un même produit, par exemple) : progrès mesurés sans IA."""
        lg = _langue(langue)

        def profil(id_):
            s = session(id_, lg)
            f = faits(s.audit, ref)
            par_categorie = {code: 0 for code in ref.categories}
            for p in f.problemes:
                if p.critere:
                    par_categorie[ref.criteres[p.critere]["categorie"]] += 1
            return {**resume(s), "id": id_, "cree": s.cree, "ecrans": f.ecrans, "graves": f.graves,
                    "par_categorie": par_categorie, "maturite": s.rapport.maturite if s.rapport else None}

        return {"a": profil(a), "b": profil(b),
                "categories": [{"code": c, "libelle": ref.libelle_categorie(c, lg)} for c in ref.categories]}

    class DemandeIA(BaseModel):
        remplir: bool = True
        forcer: bool = False
        langue: str = ""

    @app.post("/api/audits/{id_}/ia")
    def analyser_ia(id_: str, d: DemandeIA):
        lg = _langue(d.langue)
        s = session(id_, lg)
        cl = client()
        if cl is None:
            raise HTTPException(400, message("sans_ia", lg))

        def executer(tache):
            with s.verrou:
                s.langue = lg
                analyser(s, cl, tache.progression, d.forcer, d.remplir)
                sauver(s)
                return etat(s)

        return taches.lancer("ia", executer).vue()

    class Decision(BaseModel):
        ligne: int
        champ: str
        action: str  # valider, modifier, refuser
        valeur: str | None = None

    class Decisions(BaseModel):
        decisions: list[Decision]
        langue: str = ""

    @app.post("/api/audits/{id_}/decisions")
    def decisions(id_: str, d: Decisions):
        lg = _langue(d.langue)
        s = session(id_, lg)
        with s.verrou:
            for dec in d.decisions:
                try:
                    decider(s.audit, dec.ligne, dec.champ, dec.action, dec.valeur)
                except (KeyError, ValueError, StopIteration) as e:
                    raise HTTPException(400, str(e)) from e
            recalculer(s, lg)
            sauver(s)
            return etat(s)

    @app.get("/api/audits/{id_}/fichier")
    def fichier_annote(id_: str):
        s = session(id_)
        return Response(s.fichier, media_type=XLSX,
                        headers={"Content-Disposition": f'attachment; filename="{s.nom_sortie}"'})

    # --- Rapport de synthèse ---------------------------------------------------------------------------

    class DemandeRapport(BaseModel):
        forcer: bool = False
        ia: bool = True
        langue: str = ""

    @app.post("/api/audits/{id_}/rapport")
    def generer(id_: str, d: DemandeRapport):
        lg = _langue(d.langue)
        s = session(id_, lg)
        cl = client() if d.ia else None

        def executer(tache):
            with s.verrou:
                s.rapport = rediger(s.audit, ref, cl, lg, forcer=d.forcer, progression=tache.progression)
                s.rapport_perime = False
                sauver(s)
                return ser.rapport(s.rapport, ref)

        return taches.lancer("rapport", executer).vue()

    @app.get("/api/audits/{id_}/rapport")
    def lire_rapport(id_: str):
        s = session(id_)
        if s.rapport is None:
            raise HTTPException(404, message("pas_de_rapport", s.langue))
        return ser.rapport(s.rapport, ref)

    class Modification(BaseModel):
        chemin: str
        valeur: str | int | list[str]

    @app.patch("/api/audits/{id_}/rapport")
    def modifier(id_: str, m: Modification):
        """Le designer corrige ou complète un passage du rapport ; les exports (HTML, PDF, Word) le reprennent."""
        s = session(id_)
        if s.rapport is None:
            raise HTTPException(404, message("pas_de_rapport", s.langue))
        with s.verrou:
            try:
                modifier_rapport(s.rapport, m.chemin, m.valeur)
            except ValueError as e:
                raise HTTPException(400, str(e)) from e
            sauver(s)
            return ser.rapport(s.rapport, ref)

    @app.get("/api/audits/{id_}/rapport.docx")
    def rapport_word(id_: str):
        s = session(id_)
        if s.rapport is None:
            raise HTTPException(404, message("pas_de_rapport", s.langue))
        flux = io.BytesIO()
        ecrire_docx(s.rapport, flux, ref)
        return Response(flux.getvalue(), media_type=DOCX,
                        headers={"Content-Disposition": f'attachment; filename="{s.stem}_rapport.docx"'})

    # --- Tâches ----------------------------------------------------------------------------------------

    @app.get("/api/taches/{id_}")
    def tache(id_: str):
        t = taches.lire(id_)
        if t is None:
            raise HTTPException(404, "Tâche inconnue.")
        return t.vue()

    @app.exception_handler(ErreurSuggestion)
    def erreur_suggestion(_, e):
        return JSONResponse({"detail": str(e)}, status_code=400)

    # --- Interface React compilée -----------------------------------------------------------------------

    if (WEB / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")

        @app.get("/{chemin:path}", include_in_schema=False)
        def interface(chemin: str):
            if chemin.startswith("api/"):
                raise HTTPException(404)
            fichier = (WEB / chemin).resolve()
            if chemin and fichier.is_file() and WEB in fichier.parents:
                return FileResponse(fichier)
            return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-cache"})

    app.state.sessions = sessions
    app.state.taches = taches
    return app
