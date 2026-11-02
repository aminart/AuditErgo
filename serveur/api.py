"""API de l'application : relecture d'un audit, suggestion d'un critère, rapport de synthèse (HTML et Word).

Les audits déposés restent en mémoire, sur ce poste, le temps de la session : rien n'est écrit ailleurs que dans
un dossier temporaire, supprimé à l'arrêt du serveur.
"""
import io
import os
import tempfile
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from audit_ergo import ErreurLecture, Referentiel, relire
from audit_ergo.cache import CacheSuggestions
from audit_ergo.completion import decider
from audit_ergo.controles import controler
from audit_ergo.export import exporter
from audit_ergo.i18n import LANGUES, langue_defaut
from audit_ergo.rapport import ecrire_docx, rediger
from audit_ergo.suggestion import (MODELE, ErreurSuggestion, adresse_api, client_ou_none, est_locale, ia_configuree,
                                   suggerer)
from audit_ergo.synthese import synthetiser

from . import serialisation as ser
from .taches import Taches

RACINE = Path(__file__).resolve().parent.parent
WEB = RACINE / "web" / "dist"
TEMPLATES = {"fr": RACINE / "template" / "Audit_ergonomique_FR.xlsx", "en": RACINE / "template" / "Ergonomic_audit_EN.xlsx"}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TAILLE_MAX = 30 * 1024 * 1024  # un audit Excel, même avec des captures, reste bien en dessous

MESSAGES = {
    "ok": ("Modèle disponible.", "Model available."),
    "cle": ("Clé refusée par le serveur : vérifiez API_KEY dans .env.", "Key refused by the server: check API_KEY in .env."),
    "absent": ("Le serveur répond, mais le modèle « {m} » n'y est pas installé. Modèles disponibles : {liste}. "
               "Corrigez AUDIT_ERGO_MODELE dans .env, ou installez-le (« ollama pull {m} »).",
               "The server answers, but model “{m}” is not installed. Available models: {liste}. Fix "
               "AUDIT_ERGO_MODELE in .env, or install it (“ollama pull {m}”)."),
    "injoignable": ("Le modèle ne répond pas à {a}. Vérifiez API_BASE, API_KEY et CA_BUNDLE dans .env, ou lancez "
                    "Ollama (ou LM Studio) s'il est sur ce poste.",
                    "The model does not answer at {a}. Check API_BASE, API_KEY and CA_BUNDLE in .env, or start "
                    "Ollama (or LM Studio) if it runs on this computer."),
    "desactivee": ("IA désactivée (AUDIT_ERGO_IA=0) : seuls les contrôles de forme sont disponibles.",
                   "AI disabled (AUDIT_ERGO_IA=0): only form checks are available."),
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
    dossier: tempfile.TemporaryDirectory
    langue: str
    audit: object = None
    anomalies: list = field(default_factory=list)
    synthese: object = None
    ia: dict | None = None
    fichier: bytes = b""
    nom_sortie: str = ""
    rapport: object = None
    verrou: threading.RLock = field(default_factory=threading.RLock)

    @property
    def entree(self):
        return Path(self.dossier.name) / self.nom

    @property
    def stem(self):
        return Path(self.nom).stem


def creer_app(ref=None):
    ref = ref or Referentiel.charger()
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
        if s is None:
            raise HTTPException(404, message("introuvable", lg))
        return s

    def recalculer(s, lg=None):
        """Contrôles, synthèse et fichier annoté à partir de l'audit en mémoire (sans IA)."""
        s.langue = _langue(lg or s.langue)
        s.anomalies = controler(s.audit, ref, s.langue)
        s.synthese = synthetiser(s.audit, s.anomalies, ref)
        sortie = Path(s.dossier.name) / f"{s.stem}_relu.xlsx"
        exporter(s.audit, s.anomalies, s.synthese, ref, sortie, s.ia, s.langue)
        s.fichier = sortie.read_bytes()
        s.nom_sortie = f"{s.stem}_complete.xlsx" if s.audit.completions else f"{s.stem}_relu.xlsx"
        s.rapport = None  # le rapport correspond à un état de l'audit : il est à refaire

    def analyser(s, cl=None, progression=None, forcer=False, remplir=True):
        audit, anomalies, synthese, sortie, ia = relire(s.entree, Path(s.dossier.name) / f"{s.stem}_relu.xlsx", ref,
                                                        cl, progression, forcer, remplir, s.langue)
        s.audit, s.anomalies, s.synthese, s.ia = audit, anomalies, synthese, ia
        s.fichier = Path(sortie).read_bytes()
        s.nom_sortie = f"{s.stem}_complete.xlsx" if audit.completions else f"{s.stem}_relu.xlsx"
        s.rapport = None

    # --- Configuration ---------------------------------------------------------------------------------

    @app.get("/api/config")
    def config(langue: str = ""):
        lg = _langue(langue)
        cache = CacheSuggestions.defaut()
        adresse = adresse_api()
        cle, ca = os.environ.get("API_KEY", "").strip(), os.environ.get("CA_BUNDLE", "").strip()
        return {
            "langue_defaut": langue_defaut(), "langues": LANGUES,
            "referentiel": ser.referentiel(ref, lg),
            "ia": {"active": ia_configuree(), "modele": MODELE, "adresse": adresse, "cle": bool(cle),
                   "ca_bundle": Path(ca).name if ca else "", "locale": est_locale(adresse),
                   "hote": urlparse(adresse).hostname or ""},
            "cache": None if cache is None else cache.taille(),
        }

    @app.post("/api/connexion")
    def tester_connexion(langue: str = ""):
        lg = _langue(langue)
        if not ia_configuree():
            return {"statut": "desactivee", "message": message("desactivee", lg)}
        try:
            cl = client_ou_none()
        except ErreurSuggestion as e:
            return {"statut": "configuration", "message": str(e)}
        import openai

        try:
            modeles = [m.id for m in cl.models.list()]
        except openai.NotFoundError:  # passerelle sans /v1/models : elle répond, mais ne liste pas ses modèles
            return {"statut": "ok", "message": message("ok", lg)}
        except openai.AuthenticationError:
            return {"statut": "cle", "message": message("cle", lg)}
        except Exception as e:  # noqa: BLE001 : serveur injoignable, certificat refusé…
            return {"statut": "injoignable", "message": message("injoignable", lg, a=adresse_api()),
                    "detail": f"{type(e).__name__} : {e}"}
        # Ollama nomme les modèles « nom:étiquette » ; « mistral-small » désigne « mistral-small:latest »
        if any(m == MODELE or m.split(":")[0] == MODELE for m in modeles):
            return {"statut": "ok", "message": message("ok", lg)}
        return {"statut": "absent", "message": message("absent", lg, m=MODELE, liste=", ".join(modeles) or "—")}

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
        s = Session(id=uuid.uuid4().hex, nom=nom, dossier=tempfile.TemporaryDirectory(prefix="audit_ergo_"), langue=lg)
        s.entree.write_bytes(contenu)
        try:
            analyser(s)
        except ErreurLecture as e:
            s.dossier.cleanup()
            raise HTTPException(400, message("illisible", lg, e=e)) from e
        except Exception as e:  # noqa: BLE001 : fichier corrompu, protégé par mot de passe…
            s.dossier.cleanup()
            raise HTTPException(400, message("corrompu", lg, e=type(e).__name__)) from e
        sessions[s.id] = s
        return ser.etat_audit(s, ref)

    @app.get("/api/audits/{id_}")
    def lire(id_: str, langue: str = ""):
        s = session(id_, _langue(langue))
        with s.verrou:
            if langue and _langue(langue) != s.langue:  # messages et annotations dans la nouvelle langue
                recalculer(s, langue)
            return ser.etat_audit(s, ref)

    @app.delete("/api/audits/{id_}")
    def fermer(id_: str):
        s = sessions.pop(id_, None)
        if s:
            s.dossier.cleanup()
        return {"ok": True}

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
                return ser.etat_audit(s, ref)

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
            return ser.etat_audit(s, ref)

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
                return ser.rapport(s.rapport, ref)

        return taches.lancer("rapport", executer).vue()

    @app.get("/api/audits/{id_}/rapport")
    def lire_rapport(id_: str):
        s = session(id_)
        if s.rapport is None:
            raise HTTPException(404, message("pas_de_rapport", s.langue))
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
