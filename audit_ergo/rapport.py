"""Rapport Word de synthèse d'un audit relu et complété.

Le rapport a quatre parties : synthèse générale, problèmes UX principaux (regroupés par thématique),
recommandations UX/UI (grands chantiers transverses, hiérarchisés) et prochaines étapes (quick wins, chantiers
à moyen et long terme, démarche d'amélioration continue).

Partage des rôles, pour que deux designers obtiennent des rapports comparables :
- les FAITS sont calculés sans IA : nombre de problèmes par gravité, écrans touchés, thématiques récurrentes ou
  isolées, niveau de maturité indicatif (règle fixe, voir `maturite_indicative`) ;
- l'IA RÉDIGE, en deux appels : (1) regroupement des problèmes en thématiques, avec la description, la raison
  et les conséquences de chacune ; (2) synthèse, chantiers, quick wins et suites. Elle ne peut déplacer le
  niveau de maturité que d'un cran par rapport au niveau indicatif, et ne cite que des constats existants.
Sans IA (ou si elle échoue), le rapport contient tous les faits et signale les passages à rédiger.
"""
import io
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime

from .cache import CacheSuggestions
from .i18n import GRAVITES, TYPES_RECO, libelle_gravite, lire_gravite, lire_type, lire_type_reco
from .suggestion import DEFAUT, MAX_TOKENS, MODELE, NOMS_LANGUE, TEMPERATURE, ErreurSuggestion, _appeler

POIDS = {1: 1, 2: 2, 3: 4, 4: 8}  # poids d'un problème selon sa gravité (non renseignée : 1)
IMPACTS = ["fort", "moyen", "modere"]
EFFORTS = ["faible", "moyen", "eleve"]
HORIZONS = ["moyen", "long"]
MAX_TOKENS_RAPPORT = max(MAX_TOKENS, 6000)
BUDGET = 24000  # caractères de données envoyés par appel (le prompt doit tenir dans la fenêtre du modèle local)

MATURITES = {
    1: {"fr": "Initiale", "en": "Initial",
        "def_fr": "Des blocages empêchent de réaliser des tâches clés.",
        "def_en": "Blocking issues prevent key tasks from being completed."},
    2: {"fr": "Fragile", "en": "Fragile",
        "def_fr": "Les tâches aboutissent, mais au prix d'obstacles sérieux et fréquents.",
        "def_en": "Tasks can be completed, but with serious and frequent obstacles."},
    3: {"fr": "Intermédiaire", "en": "Developing",
        "def_fr": "Les bases sont en place ; des problèmes notables subsistent sur plusieurs parcours.",
        "def_en": "The basics are in place; notable issues remain on several journeys."},
    4: {"fr": "Maîtrisée", "en": "Managed",
        "def_fr": "Expérience globalement fluide ; les problèmes restants sont limités.",
        "def_en": "A broadly smooth experience; remaining issues are limited."},
    5: {"fr": "Exemplaire", "en": "Exemplary",
        "def_fr": "Expérience cohérente et efficace ; seuls des ajustements mineurs restent.",
        "def_en": "A consistent and efficient experience; only minor adjustments remain."},
}

# Libellés du rapport (français, anglais)
L = {
    "titre": ("Rapport d'audit ergonomique", "Ergonomic audit report"),
    "sous_titre": ("Synthèse et recommandations", "Summary and recommendations"),
    "produit": ("Produit / interface", "Product / interface"), "version": ("Version", "Version"),
    "client": ("Client / équipe", "Client / team"), "cible": ("Utilisateurs cibles", "Target users"),
    "plateforme": ("Plateforme", "Platform"), "parcours": ("Parcours audités", "Audited journeys"),
    "designer": ("Auditeur", "Auditor"), "date": ("Date de l'audit", "Audit date"),
    "referentiel": ("Référentiel", "Referential"),
    "s1": ("Synthèse générale", "Executive summary"),
    "en_bref": ("L'essentiel", "Key takeaways"),
    "maturite": ("Niveau de maturité UX", "UX maturity level"),
    "maturite_niveau": ("Niveau {n} sur 5 : {l}", "Level {n} of 5: {l}"),
    "chiffres": ("Chiffres clés", "Key figures"),
    "nb_constats": ("Constats", "Findings"), "nb_problemes": ("Problèmes", "Issues"),
    "nb_points_forts": ("Points forts", "Strengths"), "nb_ecrans": ("Écrans concernés", "Screens affected"),
    "par_gravite": ("Problèmes par gravité", "Issues by severity"),
    "non_renseignee": ("Non renseignée", "Not set"),
    "forts": ("Principaux points forts", "Main strengths"),
    "faiblesses": ("Principales faiblesses", "Main weaknesses"),
    "recurrents": ("Problèmes récurrents", "Recurring issues"),
    "impact": ("Impact sur les utilisateurs et leurs activités", "Impact on users and their activities"),
    "s2": ("Problèmes UX principaux", "Main UX issues"),
    "s2_intro": ("Les {n} problèmes relevés sont regroupés en {t} thématiques, de la plus pénalisante à la moins "
                 "pénalisante (nombre de problèmes pondéré par leur gravité).",
                 "The {n} issues found are grouped into {t} themes, from the most to the least penalising "
                 "(number of issues weighted by severity)."),
    "theme": ("Thématique", "Theme"), "gravite_max": ("Gravité max.", "Max. severity"),
    "tendance": ("Tendance", "Trend"), "recurrent": ("Récurrent", "Recurring"), "isole": ("Isolé", "Isolated"),
    "meta_theme": ("{n} problème(s) · {e} écran(s) · gravité max. : {g} · {t}",
                   "{n} issue(s) · {e} screen(s) · max. severity: {g} · {t}"),
    "criteres": ("Critères ergonomiques concernés", "Ergonomic criteria involved"),
    "observes": ("Problèmes observés", "Observed issues"),
    "pourquoi": ("Pourquoi l'expérience est dégradée", "Why the experience suffers"),
    "consequences": ("Conséquences", "Consequences"),
    "representatifs": ("Constats représentatifs", "Representative findings"),
    "ref": ("Réf.", "Ref."), "ecran": ("Écran", "Screen"), "constat": ("Constat", "Finding"),
    "gravite": ("Gravité", "Severity"), "critere": ("Critère", "Criterion"),
    "tendances": ("Tendances récurrentes et cas isolés", "Recurring trends and isolated cases"),
    "tendances_rec": ("Tendances récurrentes : thématiques présentes sur plusieurs écrans.",
                      "Recurring trends: themes found on several screens."),
    "tendances_iso": ("Cas isolés : thématiques ponctuelles, limitées à un écran. Les plus graves sont à traiter même "
                      "s'ils sont ponctuels.", "Isolated cases: one-off themes, limited to one screen. The most "
                      "severe ones must be fixed even though they are one-offs."),
    "aucun_rec": ("Aucune thématique récurrente.", "No recurring theme."),
    "aucun_iso": ("Aucun cas isolé.", "No isolated case."),
    "n_problemes": ("{n} problème(s)", "{n} issue(s)"), "n_ecrans": ("{n} écran(s)", "{n} screen(s)"),
    "s3": ("Recommandations UX et UI", "UX and UI recommendations"),
    "s3_intro": ("Plutôt que des corrections écran par écran, les recommandations ci-dessous sont les grands "
                 "chantiers à engager. Elles sont classées par impact attendu.",
                 "Rather than screen-by-screen fixes, the recommendations below are the main initiatives to "
                 "undertake. They are ranked by expected impact."),
    "rang": ("Priorité", "Priority"), "chantier": ("Chantier", "Initiative"), "effort": ("Effort", "Effort"),
    "themes_traites": ("Thématiques traitées", "Themes addressed"),
    "objectif": ("Objectif", "Goal"), "importance": ("Pourquoi c'est important", "Why it matters"),
    "benefices": ("Bénéfices attendus", "Expected benefits"),
    "resout": ("Problèmes résolus", "Issues addressed"),
    "pistes": ("Recommandations issues des constats", "Recommendations from the findings"),
    "s4": ("Prochaines étapes", "Next steps"),
    "qw": ("Quick wins", "Quick wins"),
    "qw_intro": ("Améliorations rapides à mettre en œuvre, avec un faible effort de développement et une valeur "
                 "immédiate pour les utilisateurs.",
                 "Quick improvements with a low development effort and immediate value for users."),
    "qw_candidats": ("Candidats proposés d'après la gravité et le type de recommandation : effort à confirmer avec "
                     "l'équipe de développement.",
                     "Candidates based on severity and recommendation type: effort to be confirmed with the "
                     "development team."),
    "action": ("Action", "Action"), "valeur": ("Valeur immédiate", "Immediate value"),
    "constats_lies": ("Constats", "Findings"),
    "mlt": ("Recommandations à moyen et long terme", "Medium and long-term recommendations"),
    "horizon": ("Horizon", "Horizon"),
    "horizon.moyen": ("Moyen terme (3 à 6 mois)", "Medium term (3 to 6 months)"),
    "horizon.long": ("Long terme (au-delà de 6 mois)", "Long term (beyond 6 months)"),
    "demarche": ("Démarche d'amélioration continue", "Continuous improvement approach"),
    "annexes": ("Annexes", "Appendices"),
    "methode": ("Méthode", "Method"),
    "methode_texte": ("Audit heuristique fondé sur le référentiel de critères ergonomiques (version {v}). Chaque "
                      "constat est rattaché à un critère et évalué sur une échelle de gravité à quatre niveaux.",
                      "Heuristic evaluation based on the ergonomic criteria referential (version {v}). Each finding "
                      "is linked to a criterion and rated on a four-level severity scale."),
    "echelle_gravite": ("Échelle de gravité", "Severity scale"),
    "echelle_maturite": ("Échelle de maturité", "Maturity scale"),
    "regle_maturite": ("Niveau indicatif, calculé sans IA : 1 si au moins 3 problèmes critiques, ou un problème "
                       "critique et 40 % de problèmes élevés ou critiques ; 2 si un problème critique ou 40 % de "
                       "problèmes élevés ou critiques ; 3 à partir de 20 % ; 4 en dessous ; 5 sans problème élevé ni "
                       "critique. L'analyse peut l'ajuster d'un niveau au plus, en le justifiant.",
                       "Indicative level, computed without AI: 1 with at least 3 critical issues, or a critical "
                       "issue and 40% of high or critical issues; 2 with a critical issue or 40% of high or "
                       "critical issues; 3 from 20%; 4 below; 5 with no high or critical issue. The analysis may "
                       "adjust it by one level at most, with a justification."),
    "redaction_ia": ("Rédaction assistée par l'IA ({m}) à partir des constats de l'audit : à relire avant "
                     "diffusion.", "Drafted with AI assistance ({m}) from the audit findings: review before "
                     "sharing."),
    "redaction_sans_ia": ("Rapport généré sans IA : les faits sont complets, les passages surlignés sont à "
                          "rédiger.", "Report generated without AI: facts are complete, highlighted passages "
                          "are to be written."),
    "erreur_ia": ("L'IA n'a pas pu rédiger toutes les parties ({e}) : les passages surlignés sont à rédiger.",
                  "The AI could not write every part ({e}): highlighted passages are to be written."),
    "liste": ("Liste des problèmes", "List of issues"),
    "points_forts_releves": ("Points forts relevés", "Strengths found"),
    "a_rediger": ("[À rédiger]", "[To be written]"),
    "autres": ("Autres constats", "Other findings"),
    "autres_desc": ("Constats que l'analyse n'a rattachés à aucune thématique.",
                    "Findings the analysis did not link to any theme."),
    "non_classes": ("Constats sans critère", "Findings without a criterion"),
    "desc_auto": ("{n} problème(s) relevé(s) sur : {ecrans}.", "{n} issue(s) found on: {ecrans}."),
    "resume_auto": ("L'audit de {p} compte {n} problème(s) et {f} point(s) fort(s), sur {e} écran(s). {g} "
                    "problème(s) sont de gravité élevée ou critique. Les thématiques les plus pénalisantes sont : {t}.",
                    "The audit of {p} found {n} issue(s) and {f} strength(s), on {e} screen(s). {g} issue(s) are "
                    "high or critical. The most penalising themes are: {t}."),
    "le_produit": ("l'interface", "the interface"),
    "faiblesse_auto": ("{t} : {n} problème(s), gravité max. {g}", "{t}: {n} issue(s), max. severity {g}"),
    "recurrent_auto": ("{t} : {e} écrans concernés", "{t}: {e} screens affected"),
    "chantier_auto": ("Traiter : {t}", "Address: {t}"),
    "resout_auto": ("{n} problème(s) de la thématique « {t} » (gravité max. {g}).",
                    "{n} issue(s) of the “{t}” theme (max. severity {g})."),
    "impact.fort": ("Fort", "High"), "impact.moyen": ("Moyen", "Medium"), "impact.modere": ("Modéré", "Moderate"),
    "effort.faible": ("Faible", "Low"), "effort.moyen": ("Moyen", "Medium"), "effort.eleve": ("Élevé", "High"),
    "page": ("Page", "Page"), "impact_court": ("Impact", "Impact"),
}

DEMARCHE_DEFAUT = {
    "fr": ["Corriger les quick wins, puis vérifier sur les écrans concernés que les problèmes ont disparu.",
           "Valider les chantiers prioritaires par des tests utilisateurs sur les parcours critiques.",
           "Intégrer les corrections dans le design system et les guidelines, pour qu'elles s'appliquent aux "
           "nouveaux écrans.",
           "Suivre quelques indicateurs : taux de réussite des tâches, erreurs de saisie, abandons, demandes au "
           "support.",
           "Refaire un audit avec le même référentiel à chaque version majeure, pour mesurer les progrès."],
    "en": ["Fix the quick wins, then check on the screens involved that the issues are gone.",
           "Validate the priority initiatives with user tests on the critical journeys.",
           "Add the fixes to the design system and guidelines, so that they apply to new screens.",
           "Track a few indicators: task success rate, input errors, drop-offs, support requests.",
           "Run a new audit with the same referential at each major release, to measure progress."],
}


def _l(cle, langue, **valeurs):
    fr, en = L[cle]
    texte = en if langue == "en" else fr
    return texte.format(**valeurs) if valeurs else texte


def _txt(valeur):
    return re.sub(r"\s+", " ", str(valeur or "")).strip()


def _court(texte, n):
    texte = _txt(texte)
    return texte if len(texte) <= n else texte[:n - 1].rstrip() + "…"


# --- Faits (sans IA) ----------------------------------------------------------------------------------

@dataclass
class Probleme:
    cle: str  # C1, C2… : identifiant stable transmis à l'IA
    ref: str  # référence affichée (ID du fichier, sinon #ligne)
    ecran: str
    constat: str
    critere: str | None
    gravite: int | None
    recommandation: str
    type_reco: str | None

    @property
    def poids(self):
        return POIDS.get(self.gravite, 1)


@dataclass
class Theme:
    titre: str
    problemes: list
    description: str = ""
    pourquoi: str = ""
    consequences: str = ""

    @property
    def ecrans(self):
        return sorted({p.ecran for p in self.problemes if p.ecran})

    @property
    def gravite_max(self):
        return max((p.gravite for p in self.problemes if p.gravite), default=None)

    @property
    def poids(self):
        return sum(p.poids for p in self.problemes)

    @property
    def recurrent(self):
        return len(self.problemes) >= 2 and len(self.ecrans) >= 2

    @property
    def criteres(self):
        return [code for code, _ in Counter(p.critere for p in self.problemes if p.critere).most_common()]


@dataclass
class Faits:
    contexte: dict
    problemes: list
    points_forts: list  # [(réf, écran, constat)]
    gravites: dict  # niveau -> nombre (None : non renseignée)
    ecrans: list
    version_referentiel: str

    @property
    def graves(self):
        return self.gravites.get(3, 0) + self.gravites.get(4, 0)

    @property
    def maturite_indicative(self):
        return maturite_indicative(self.gravites, len(self.problemes))


def maturite_indicative(gravites, nb_problemes):
    """Niveau de maturité (1 à 5) déduit de la gravité des problèmes : règle fixe, identique pour tous."""
    critiques = gravites.get(4, 0)
    if not nb_problemes:
        return 5
    part = (gravites.get(3, 0) + critiques) / nb_problemes
    if critiques >= 3 or (critiques and part >= 0.4):
        return 1
    if critiques or part >= 0.4:
        return 2
    if part >= 0.2:
        return 3
    return 4 if part > 0 else 5


def faits(audit, ref):
    problemes, forts = [], []
    for c in audit.constats:
        if not _txt(c["constat"]):
            continue
        if lire_type(c["type"]) == "point_fort":
            forts.append((c.ref, _txt(c["ecran"]), _txt(c["constat"])))
            continue
        problemes.append(Probleme(cle=f"C{len(problemes) + 1}", ref=str(c.ref), ecran=_txt(c["ecran"]),
                                  constat=_txt(c["constat"]), critere=ref.trouver_critere(c["critere"]),
                                  gravite=lire_gravite(c["gravite"]), recommandation=_txt(c["recommandation"]),
                                  type_reco=lire_type_reco(c["type_reco"])))
    gravites = Counter(p.gravite for p in problemes)
    return Faits(contexte=dict(audit.contexte), problemes=problemes, points_forts=forts,
                 gravites=dict(gravites), ecrans=sorted({p.ecran for p in problemes if p.ecran}),
                 version_referentiel=ref.version)


# --- Contenu du rapport ---------------------------------------------------------------------------------

@dataclass
class Chantier:
    titre: str
    objectif: str = ""
    importance: str = ""
    benefices: str = ""
    problemes_resolus: str = ""
    themes: list = field(default_factory=list)  # objets Theme
    impact: str = ""  # fort / moyen / modere
    effort: str = ""  # faible / moyen / eleve
    pistes: list = field(default_factory=list)  # recommandations des constats (rapport sans IA)


@dataclass
class QuickWin:
    titre: str
    description: str = ""
    valeur: str = ""
    problemes: list = field(default_factory=list)


@dataclass
class Suite:
    titre: str
    horizon: str  # moyen / long
    description: str = ""


@dataclass
class Rapport:
    faits: Faits
    langue: str
    themes: list
    resume: str = ""
    maturite: int = 3
    maturite_justification: str = ""
    points_forts: list = field(default_factory=list)
    faiblesses: list = field(default_factory=list)
    recurrents: list = field(default_factory=list)
    impact: str = ""
    recommandations: list = field(default_factory=list)
    quick_wins: list = field(default_factory=list)
    quick_wins_candidats: bool = False  # True : choisis sans IA, effort à confirmer
    suites: list = field(default_factory=list)
    demarche: list = field(default_factory=list)
    ia: bool = False
    erreur: str = ""

    @property
    def cas_isoles(self):
        """Thématiques ponctuelles (un seul écran, ou un seul problème), les plus graves d'abord."""
        return sorted((t for t in self.themes if not t.recurrent), key=lambda t: -(t.gravite_max or 0))


def _trier_themes(themes):
    return sorted(themes, key=lambda t: (-t.poids, -(t.gravite_max or 0), t.titre))


def themes_sans_ia(f, ref, langue):
    """Thématiques par catégorie du référentiel (rapport sans IA)."""
    groupes = {}
    for p in f.problemes:
        cle = ref.criteres[p.critere]["categorie"] if p.critere else None
        groupes.setdefault(cle, []).append(p)
    themes = []
    for cat, probs in groupes.items():
        titre = ref.libelle_categorie(cat, langue) if cat else _l("non_classes", langue)
        t = Theme(titre=titre, problemes=probs)
        t.description = _l("desc_auto", langue, n=len(probs), ecrans=", ".join(t.ecrans) or "—")
        themes.append(t)
    return _trier_themes(themes)


def _gravite_txt(g, langue):
    return libelle_gravite(g, langue) if g else _l("non_renseignee", langue)


def completer_sans_ia(r, ref):
    """Parties rédigées à défaut d'IA : uniquement des faits ; le reste est signalé « à rédiger »."""
    lg, f = r.langue, r.faits
    principaux = r.themes[:3]
    if not r.resume:
        r.resume = _l("resume_auto", lg, p=f.contexte.get("produit") or _l("le_produit", lg), n=len(f.problemes),
                      f=len(f.points_forts), e=len(f.ecrans), g=f.graves,
                      t=", ".join(t.titre for t in principaux) or "—")
    if not r.maturite_justification:
        r.maturite = f.maturite_indicative
    r.points_forts = r.points_forts or [_court(c, 200) for _, _, c in f.points_forts[:6]]
    r.faiblesses = r.faiblesses or [_l("faiblesse_auto", lg, t=t.titre, n=len(t.problemes),
                                       g=_gravite_txt(t.gravite_max, lg)) for t in principaux]
    r.recurrents = r.recurrents or [_l("recurrent_auto", lg, t=t.titre, e=len(t.ecrans))
                                    for t in r.themes if t.recurrent]
    if not r.recommandations:
        for t in r.themes[:5]:
            g = t.gravite_max or 1
            pistes = [p.recommandation for p in sorted(t.problemes, key=lambda p: -p.poids) if p.recommandation]
            r.recommandations.append(Chantier(
                titre=_l("chantier_auto", lg, t=t.titre), themes=[t],
                problemes_resolus=_l("resout_auto", lg, n=len(t.problemes), t=t.titre, g=_gravite_txt(t.gravite_max, lg)),
                impact="fort" if g >= 3 else "moyen" if g == 2 else "modere",
                pistes=list(dict.fromkeys(pistes))[:3]))
    if not r.quick_wins:
        candidats = [p for p in sorted(f.problemes, key=lambda p: -p.poids)
                     if p.recommandation and p.type_reco in (None, "design") and (p.gravite or 0) >= 2]
        r.quick_wins = [QuickWin(titre=_court(p.recommandation, 160), problemes=[p]) for p in candidats[:6]]
        r.quick_wins_candidats = bool(r.quick_wins)
    r.demarche = r.demarche or DEMARCHE_DEFAUT[lg if lg in DEMARCHE_DEFAUT else "fr"]
    return r


# --- IA -------------------------------------------------------------------------------------------------

def _consigne_langue(langue):
    return (f"Rédige tous les textes en {NOMS_LANGUE.get(langue, 'français')}, dans un style professionnel, "
            "clair et factuel, adapté à un rapport remis à une équipe produit. Les clés et valeurs imposées par "
            "le schéma restent telles quelles.")


def _requete(nom, consignes, schema, donnees, langue):
    consigne_json = ("Réponds uniquement avec un objet JSON valide, sans texte autour ni bloc de code, conforme à "
                     "ce schéma JSON :\n" + json.dumps(schema, ensure_ascii=False))
    return {
        "model": MODELE, "max_tokens": MAX_TOKENS_RAPPORT, "temperature": TEMPERATURE,
        "messages": [{"role": "system", "content": f"{consignes}\n\n{consigne_json}"},
                     {"role": "user", "content": f"{donnees}\n\n{_consigne_langue(langue)}"}],
        "response_format": {"type": "json_schema", "json_schema": {"name": nom, "strict": True, "schema": schema}},
    }


def _objet(proprietes):
    return {"type": "object", "properties": proprietes, "required": list(proprietes), "additionalProperties": False}


TEXTE, TEXTES = {"type": "string"}, {"type": "array", "items": {"type": "string"}}

SCHEMA_THEMES = _objet({"themes": {"type": "array", "items": _objet({
    "titre": TEXTE, "constats": TEXTES, "description": TEXTE, "pourquoi": TEXTE, "consequences": TEXTE})}})

CONSIGNES_THEMES = """Tu es un expert UX senior. On te donne les problèmes relevés lors d'un audit ergonomique \
heuristique, chacun identifié par une clé (C1, C2…). Regroupe-les en grandes thématiques UX (par exemple : \
retour d'information et état du système, navigation et repérage, formulaires et saisie, lisibilité et \
hiérarchie visuelle, gestion des erreurs, cohérence, accessibilité…), selon ce que les constats révèlent.

Règles :
1. Entre {min_t} et {max_t} thématiques. Chaque problème appartient à exactement une thématique : cite sa clé \
dans « constats ». N'invente aucune clé.
2. « titre » : court (8 mots au plus), compréhensible par une équipe produit.
3. « description » : les problèmes observés, en 2 à 4 phrases factuelles qui citent les écrans concernés et \
signalent si le problème se répète ou s'il est ponctuel.
4. « pourquoi » : pourquoi ces problèmes dégradent l'expérience, en 2 ou 3 phrases, en t'appuyant sur les \
critères ergonomiques concernés.
5. « consequences » : les conséquences pour les utilisateurs et leurs activités (erreurs, abandons, temps \
perdu, charge mentale, perte de confiance, sollicitations du support…), en 2 ou 3 phrases.
6. Reste centré sur les constats : ne propose AUCUNE solution ni recommandation."""

SCHEMA_SYNTHESE = _objet({
    "synthese": _objet({"resume": TEXTE, "maturite": _objet({"niveau": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
                                                             "justification": TEXTE}),
                        "points_forts": TEXTES, "faiblesses": TEXTES, "problemes_recurrents": TEXTES, "impact": TEXTE}),
    "recommandations": {"type": "array", "items": _objet({
        "titre": TEXTE, "objectif": TEXTE, "importance": TEXTE, "benefices": TEXTE, "problemes_resolus": TEXTE,
        "themes": TEXTES, "impact": {"type": "string", "enum": IMPACTS}, "effort": {"type": "string", "enum": EFFORTS}})},
    "quick_wins": {"type": "array", "items": _objet({"titre": TEXTE, "description": TEXTE, "valeur": TEXTE,
                                                     "constats": TEXTES})},
    "moyen_long_terme": {"type": "array", "items": _objet({"titre": TEXTE, "horizon": {"type": "string",
                                                                                       "enum": HORIZONS},
                                                           "description": TEXTE})},
    "demarche_amelioration_continue": TEXTES,
})

CONSIGNES_SYNTHESE = """Tu es un expert UX senior. Tu rédiges la synthèse d'un rapport d'audit ergonomique \
destiné à une équipe produit et à ses décideurs. On te donne le contexte, les chiffres clés, les thématiques de \
problèmes (T1, T2…), les points forts et les recommandations rédigées pour chaque constat (C1, C2…).

1. « synthese » : doit permettre de comprendre rapidement les conclusions de l'audit.
   - « resume » : 4 à 6 phrases sur les principaux enseignements.
   - « maturite » : niveau de maturité UX de 1 à 5 selon l'échelle fournie. Pars du niveau indicatif ; tu ne \
peux t'en écarter que d'un niveau, en le justifiant. « justification » : 2 ou 3 phrases.
   - « points_forts » : 2 à 5 points forts, tirés des points forts relevés (sinon de ce qui fonctionne).
   - « faiblesses » : 3 à 5 principales faiblesses.
   - « problemes_recurrents » : 2 à 5 problèmes qui se répètent d'un écran à l'autre.
   - « impact » : 3 à 5 phrases sur l'impact général sur les utilisateurs et leurs activités.
2. « recommandations » : 3 à 6 GRANDS CHANTIERS UX/UI transverses, pas des corrections écran par écran. Pour \
chacun : « objectif », « importance » (pourquoi c'est important), « benefices » (bénéfices attendus pour les \
utilisateurs et pour l'organisation), « problemes_resolus » (types de problèmes qu'il résout), « themes » (clés \
T… des thématiques traitées), « impact » attendu (fort, moyen, modere) et « effort » (faible, moyen, eleve). \
Chaque texte : 1 à 3 phrases.
3. « quick_wins » : 3 à 8 améliorations rapides à mettre en œuvre, à faible effort de développement et à valeur \
immédiate, appuyées sur les recommandations des constats (cite leurs clés C… dans « constats »). « valeur » : \
le bénéfice immédiat, en une phrase.
4. « moyen_long_terme » : 2 à 5 chantiers, horizon « moyen » (3 à 6 mois) ou « long » (au-delà).
5. « demarche_amelioration_continue » : 3 à 6 étapes d'une démarche d'amélioration continue (vérification des \
corrections, tests utilisateurs, design system, indicateurs de suivi, audits réguliers…), adaptées au contexte.

N'invente ni constat, ni chiffre, ni clé. Ne cite que des clés T… et C… fournies."""


def _contexte_txt(f):
    noms = {"produit": "Produit", "cible": "Utilisateurs cibles", "plateforme": "Plateforme",
            "contexte_usage": "Contexte d'usage", "parcours": "Parcours audités"}
    lignes = [f"{nom} : {_txt(f.contexte[k])}" for k, nom in noms.items() if _txt(f.contexte.get(k))]
    return "Contexte de l'audit :\n" + ("\n".join(lignes) if lignes else "non renseigné")


def _ligne_probleme(p, n):
    return f"{p.cle} | {p.ecran or '?'} | {p.critere or '?'} | {p.gravite or '?'} | {_court(p.constat, n)}"


def _legende(f, ref):
    """Libellé des critères cités et échelle de gravité, une seule fois (les lignes ne portent que les codes)."""
    codes = sorted({p.critere for p in f.problemes if p.critere})
    return ("Critères cités : " + " ; ".join(ref.libelle_critere(c) for c in codes) + "\nGravité : "
            + ", ".join(f"{g} = {v['fr']}" for g, v in GRAVITES.items()) + " (? = non renseignée)")


def _dans_budget(fabriquer, longueurs=(260, 180, 120, 80, 50, 30)):
    """Le plus long texte de données qui tient dans le budget, en raccourcissant les constats si besoin."""
    for n in longueurs:
        texte = fabriquer(n)
        if len(texte) <= BUDGET:
            return texte
    return texte


def requete_themes(f, ref, langue):
    n = len(f.problemes)
    consignes = CONSIGNES_THEMES.replace("{min_t}", str(min(3, n))).replace("{max_t}", str(min(7, n)))

    def donnees(longueur):
        return (_contexte_txt(f) + "\n\n" + _legende(f, ref)
                + f"\n\nProblèmes ({n}) : clé | écran | critère | gravité | constat\n"
                + "\n".join(_ligne_probleme(p, longueur) for p in f.problemes))
    return _requete("themes_audit", consignes, SCHEMA_THEMES, _dans_budget(donnees), langue)


def interpreter_themes(f, data, langue):
    par_cle = {p.cle: p for p in f.problemes}
    vus, themes = set(), []
    for item in data.get("themes") or []:
        if not isinstance(item, dict):
            continue
        probs = []
        for cle in item.get("constats") or []:
            cle = _txt(cle).upper()
            if cle in par_cle and cle not in vus:
                vus.add(cle)
                probs.append(par_cle[cle])
        if probs and _txt(item.get("titre")):
            themes.append(Theme(titre=_txt(item["titre"]), problemes=probs, description=_txt(item.get("description")),
                                pourquoi=_txt(item.get("pourquoi")), consequences=_txt(item.get("consequences"))))
    if not themes:
        raise ErreurSuggestion("L'IA n'a proposé aucune thématique exploitable : réessayez.")
    restants = [p for p in f.problemes if p.cle not in vus]
    if restants:
        themes.append(Theme(titre=_l("autres", langue), problemes=restants, description=_l("autres_desc", langue)))
    return _trier_themes(themes)


def requete_synthese(f, themes, ref, langue):
    echelle = "\n".join(f"{n} = {m['fr']} : {m['def_fr']}" for n, m in MATURITES.items())
    chiffres = (f"Chiffres clés : {len(f.problemes)} problème(s), {len(f.points_forts)} point(s) fort(s), "
                f"{len(f.ecrans)} écran(s) concerné(s). Gravité : "
                + ", ".join(f"{GRAVITES[g]['fr']} = {f.gravites.get(g, 0)}" for g in GRAVITES)
                + (f", non renseignée = {f.gravites[None]}" if f.gravites.get(None) else ""))

    def donnees(longueur):
        parties = [_contexte_txt(f), chiffres,
                   f"Échelle de maturité :\n{echelle}\nNiveau indicatif (calculé d'après les gravités) : "
                   f"{f.maturite_indicative}", "Thématiques de problèmes :"]
        for i, t in enumerate(themes, 1):
            parties.append(
                f"T{i} – {t.titre} : {len(t.problemes)} problème(s), {len(t.ecrans)} écran(s), gravité max. "
                f"{t.gravite_max or 'non renseignée'}, {'récurrent' if t.recurrent else 'isolé'}. Critères : "
                f"{', '.join(ref.libelle_critere(c) for c in t.criteres[:4]) or '—'}. {_court(t.description, longueur * 2)}")
            for p in sorted(t.problemes, key=lambda p: -p.poids)[:6]:
                if p.recommandation:
                    type_reco = f", {TYPES_RECO[p.type_reco]['fr']}" if p.type_reco else ""
                    parties.append(f"  {p.cle} [gravité {p.gravite or '?'}{type_reco}] {p.ecran} : "
                                   f"{_court(p.recommandation, longueur)}")
        parties.append("Points forts relevés : " + ("\n" + "\n".join(
            f"- {e} : {_court(c, longueur)}" for _, e, c in f.points_forts[:12]) if f.points_forts else "aucun"))
        return "\n".join(parties)
    return _requete("synthese_audit", CONSIGNES_SYNTHESE, SCHEMA_SYNTHESE, _dans_budget(donnees), langue)


def _liste(valeur, n=8):
    return [_txt(v) for v in (valeur or []) if _txt(v)][:n] if isinstance(valeur, list) else []


def _cles(valeurs, connues):
    """Clés citées par l'IA (T1, C3…) qui existent, sans doublon, dans l'ordre."""
    return list(dict.fromkeys(k for k in (_txt(v).upper() for v in valeurs or []) if k in connues))


def interpreter_synthese(r, data):
    f = r.faits
    s = data.get("synthese") or {}
    r.resume = _txt(s.get("resume"))
    m = s.get("maturite") or {}
    try:
        niveau = int(m.get("niveau"))
    except (TypeError, ValueError):
        niveau = f.maturite_indicative
    indic = f.maturite_indicative  # l'IA ne peut s'écarter que d'un niveau du niveau indicatif
    r.maturite = min(5, max(1, indic - 1, min(indic + 1, niveau)))
    r.maturite_justification = _txt(m.get("justification"))
    r.points_forts, r.faiblesses = _liste(s.get("points_forts")), _liste(s.get("faiblesses"))
    r.recurrents, r.impact = _liste(s.get("problemes_recurrents")), _txt(s.get("impact"))

    par_t = {f"T{i}": t for i, t in enumerate(r.themes, 1)}
    for item in data.get("recommandations") or []:
        if isinstance(item, dict) and _txt(item.get("titre")):
            themes = [par_t[k] for k in _cles(item.get("themes"), par_t)]
            r.recommandations.append(Chantier(
                titre=_txt(item["titre"]), objectif=_txt(item.get("objectif")), importance=_txt(item.get("importance")),
                benefices=_txt(item.get("benefices")), problemes_resolus=_txt(item.get("problemes_resolus")),
                themes=themes, impact=item.get("impact") if item.get("impact") in IMPACTS else "moyen",
                effort=item.get("effort") if item.get("effort") in EFFORTS else ""))
    # Hiérarchie : impact attendu, puis poids des problèmes traités, puis effort le plus faible
    r.recommandations.sort(key=lambda c: (IMPACTS.index(c.impact), -sum(t.poids for t in c.themes),
                                          EFFORTS.index(c.effort) if c.effort else 1))

    par_c = {p.cle: p for p in f.problemes}
    for item in data.get("quick_wins") or []:
        if isinstance(item, dict) and _txt(item.get("titre")):
            probs = [par_c[k] for k in _cles(item.get("constats"), par_c)]
            r.quick_wins.append(QuickWin(titre=_txt(item["titre"]), description=_txt(item.get("description")),
                                         valeur=_txt(item.get("valeur")), problemes=probs))
    for item in data.get("moyen_long_terme") or []:
        if isinstance(item, dict) and _txt(item.get("titre")):
            r.suites.append(Suite(titre=_txt(item["titre"]), description=_txt(item.get("description")),
                                  horizon=item.get("horizon") if item.get("horizon") in HORIZONS else "moyen"))
    r.suites.sort(key=lambda s: HORIZONS.index(s.horizon))
    r.demarche = _liste(data.get("demarche_amelioration_continue"))
    return r


def _interroger(client, requete, interpreter, cache, forcer, nom):
    """Appel au modèle, avec le cache local ; `interpreter(data)` valide la réponse avant qu'elle soit mémorisée."""
    cle = cache.cle(nom, requete) if cache else None
    if cache and not forcer and (memorise := cache.lire(cle)):
        try:
            return interpreter(memorise["data"])
        except (ErreurSuggestion, KeyError, TypeError, AttributeError):
            pass
    data, usage = _appeler(client, requete)
    resultat = interpreter(data)
    if cache:
        cache.ecrire(cle, {"data": data, "usage": usage})
    return resultat


def rediger(audit, ref, client=None, langue=None, cache=DEFAUT, forcer=False, progression=None):
    """Prépare le contenu du rapport. Sans `client`, ou si l'IA échoue, les parties rédigées sont remplacées
    par des faits et signalées « à rédiger » (`Rapport.erreur` indique alors la cause)."""
    langue = langue or audit.langue
    f = faits(audit, ref)
    r = Rapport(faits=f, langue=langue, themes=[])
    cache = CacheSuggestions.defaut() if cache is DEFAUT else cache
    if client is not None and f.problemes:
        try:
            if progression:
                progression(0, 2)
            r.themes = _interroger(client, requete_themes(f, ref, langue),
                                   lambda d: interpreter_themes(f, d, langue), cache, forcer, "rapport-themes")
            if progression:
                progression(1, 2)
            themes = r.themes
            r = _interroger(client, requete_synthese(f, themes, ref, langue),
                            lambda d: interpreter_synthese(Rapport(faits=f, langue=langue, themes=themes), d),
                            cache, forcer, "rapport-synthese")
            r.ia = True
            if progression:
                progression(2, 2)
        except ErreurSuggestion as e:
            r.erreur = str(e)
    if not r.themes:
        r.themes = themes_sans_ia(f, ref, langue)
    return completer_sans_ia(r, ref)


# --- Document Word --------------------------------------------------------------------------------------

BLEU, GRIS = "1F3864", "595959"
COULEURS_GRAVITE = {1: "E2EFDA", 2: "FFF2CC", 3: "FCE4D6", 4: "F4B183", None: "EDEDED"}
COULEURS_IMPACT = {"fort": "F4B183", "moyen": "FFF2CC", "modere": "E2EFDA"}


def _ombrer(cellule, couleur):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    tc_pr = cellule._tc.get_or_add_tcPr()
    for ancien in tc_pr.findall(qn("w:shd")):
        tc_pr.remove(ancien)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), couleur)
    tc_pr.append(shd)


def _champ(paragraphe, instruction):
    """Champ Word (ex. numéro de page), calculé à l'ouverture du document."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    run = paragraphe.add_run()
    for type_, texte in (("begin", None), (None, instruction), ("separate", None), (None, "1"), ("end", None)):
        if type_:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), type_)
        elif texte == instruction:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = f" {instruction} "
        else:
            el = OxmlElement("w:t")
            el.text = texte
        run._r.append(el)


def _repeter_entete(ligne):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    ligne._tr.get_or_add_trPr().append(el)


class _Document:
    """Petites aides de mise en page autour de python-docx."""

    def __init__(self, langue):
        from docx import Document
        from docx.enum.text import WD_COLOR_INDEX
        from docx.shared import Cm, Pt, RGBColor

        self.Pt, self.Cm, self.RGB, self.SURLIGNE = Pt, Cm, RGBColor, WD_COLOR_INDEX.YELLOW
        self.langue = langue
        self.doc = Document()
        section = self.doc.sections[0]
        section.page_height, section.page_width = Cm(29.7), Cm(21.0)
        section.left_margin = section.right_margin = Cm(2.2)
        section.top_margin, section.bottom_margin = Cm(2.0), Cm(2.0)
        styles = self.doc.styles
        styles["Normal"].font.name = "Calibri"
        styles["Normal"].font.size = Pt(10.5)
        styles["Normal"].paragraph_format.space_after = Pt(6)
        for nom, taille in (("Title", 26), ("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 11)):
            styles[nom].font.name = "Calibri"
            styles[nom].font.size = Pt(taille)
            styles[nom].font.color.rgb = RGBColor.from_string(BLEU)
        styles["Heading 1"].paragraph_format.space_before = Pt(18)
        styles["Heading 2"].paragraph_format.space_before = Pt(12)

    def l(self, cle, **valeurs):
        return _l(cle, self.langue, **valeurs)

    def titre(self, texte, niveau):
        return self.doc.add_heading(texte, niveau)

    def paragraphe(self, texte="", gras=None, italique=False, couleur=None, taille=None, style=None):
        p = self.doc.add_paragraph(style=style)
        if gras:
            p.add_run(gras).bold = True
        if texte:
            run = p.add_run(texte)
            run.italic = italique
            if couleur:
                run.font.color.rgb = self.RGB.from_string(couleur)
            if taille:
                run.font.size = self.Pt(taille)
        return p

    def texte_ou_a_rediger(self, texte, etiquette=None):
        """Paragraphe (avec étiquette en gras) ; un texte vide devient « [À rédiger] » surligné."""
        p = self.doc.add_paragraph()
        if etiquette:
            p.add_run(f"{etiquette} : ").bold = True
        if texte:
            p.add_run(texte)
        else:
            run = p.add_run(self.l("a_rediger"))
            run.italic = True
            run.font.highlight_color = self.SURLIGNE
        return p

    def puces(self, elements):
        if not elements:
            self.texte_ou_a_rediger("")
        for e in elements:
            self.doc.add_paragraph(e, style="List Bullet")

    def tableau(self, entetes, lignes, largeurs=None, couleurs=None, taille=9):
        """Tableau avec en-tête bleu répété sur chaque page ; `couleurs` : {(ligne, colonne): couleur}."""
        t = self.doc.add_table(rows=1, cols=len(entetes))
        t.style = "Table Grid"
        for i, texte in enumerate(entetes):
            cellule = t.rows[0].cells[i]
            cellule.text = ""
            run = cellule.paragraphs[0].add_run(texte)
            run.bold, run.font.size = True, self.Pt(taille)
            run.font.color.rgb = self.RGB.from_string("FFFFFF")
            _ombrer(cellule, BLEU)
        _repeter_entete(t.rows[0])
        for i, ligne in enumerate(lignes):
            cellules = t.add_row().cells
            for j, valeur in enumerate(ligne):
                cellules[j].text = ""
                run = cellules[j].paragraphs[0].add_run(str(valeur if valeur is not None else ""))
                run.font.size = self.Pt(taille)
                if couleurs and (i, j) in couleurs:
                    _ombrer(cellules[j], couleurs[(i, j)])
        if largeurs:
            t.autofit = False
            for j, largeur in enumerate(largeurs):
                t.columns[j].width = self.Cm(largeur)
            for ligne in t.rows:
                for j, largeur in enumerate(largeurs):
                    ligne.cells[j].width = self.Cm(largeur)
        self.doc.add_paragraph()
        return t


def _date(valeur):
    if isinstance(valeur, (datetime, date)):
        return valeur.strftime("%d/%m/%Y")
    return _txt(valeur)


def ecrire_docx(r, sortie, ref=None):
    """Écrit le rapport Word dans `sortie` (chemin ou flux binaire)."""
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    d, f, lg = _Document(r.langue), r.faits, r.langue
    ctx = f.contexte
    g = lambda n: _gravite_txt(n, lg)  # noqa: E731

    # Page de titre
    d.doc.add_paragraph().paragraph_format.space_before = d.Pt(120)
    d.doc.add_paragraph(d.l("titre"), style="Title")
    d.paragraphe(_txt(ctx.get("produit")) or d.l("sous_titre"), taille=16, couleur=GRIS)
    d.doc.add_paragraph()
    champs = [("produit", "produit"), ("version", "version_produit"), ("client", "client"), ("cible", "cible"),
              ("plateforme", "plateforme"), ("parcours", "parcours"), ("designer", "designer"), ("date", "date")]
    infos = [(d.l(libelle), _date(ctx.get(cle))) for libelle, cle in champs if _date(ctx.get(cle))]
    infos.append((d.l("referentiel"), f"v{f.version_referentiel}"))
    for nom, valeur in infos:
        d.paragraphe(valeur, gras=f"{nom} : ")
    d.doc.add_paragraph()
    note = d.l("redaction_ia", m=MODELE) if r.ia else d.l("redaction_sans_ia")
    d.paragraphe(note, italique=True, couleur=GRIS, taille=9)
    if r.erreur:
        d.paragraphe(d.l("erreur_ia", e=r.erreur), italique=True, couleur="C00000", taille=9)
    d.doc.add_page_break()

    # Pied de page : produit et numéro de page
    pied = d.doc.sections[0].footer.paragraphs[0]
    pied.alignment = WD_ALIGN_PARAGRAPH.CENTER
    produit = _txt(ctx.get("produit"))
    pied.add_run(f"{d.l('titre')}{' – ' + produit if produit else ''}   ·   {d.l('page')} ").font.size = d.Pt(8)
    _champ(pied, "PAGE")

    # 1. Synthèse générale
    d.titre(f"1. {d.l('s1')}", 1)
    d.titre(d.l("en_bref"), 2)
    d.texte_ou_a_rediger(r.resume)

    d.titre(d.l("maturite"), 2)
    echelle = d.tableau([f"{n}. {m[lg]}" for n, m in MATURITES.items()],
                        [[m[f"def_{lg}"] for m in MATURITES.values()]], taille=8,
                        couleurs={(0, r.maturite - 1): "BDD7EE"})
    _ombrer(echelle.rows[0].cells[r.maturite - 1], "C00000")
    d.paragraphe(d.l("maturite_niveau", n=r.maturite, l=MATURITES[r.maturite][lg]), taille=12).runs[0].bold = True
    d.texte_ou_a_rediger(r.maturite_justification)

    d.titre(d.l("chiffres"), 2)
    d.tableau([d.l("nb_constats"), d.l("nb_problemes"), d.l("nb_points_forts"), d.l("nb_ecrans")],
              [[len(f.problemes) + len(f.points_forts), len(f.problemes), len(f.points_forts), len(f.ecrans)]],
              taille=11)
    niveaux = list(GRAVITES) + ([None] if f.gravites.get(None) else [])
    d.paragraphe(gras=d.l("par_gravite"))
    d.tableau([g(n) for n in niveaux], [[f.gravites.get(n, 0) for n in niveaux]], taille=11,
              couleurs={(0, j): COULEURS_GRAVITE[n] for j, n in enumerate(niveaux)})

    for cle, elements in (("forts", r.points_forts), ("faiblesses", r.faiblesses), ("recurrents", r.recurrents)):
        d.titre(d.l(cle), 2)
        d.puces(elements)
    d.titre(d.l("impact"), 2)
    d.texte_ou_a_rediger(r.impact)

    # 2. Problèmes UX principaux
    d.doc.add_page_break()
    d.titre(f"2. {d.l('s2')}", 1)
    d.paragraphe(d.l("s2_intro", n=len(f.problemes), t=len(r.themes)))
    if r.themes:
        d.tableau([d.l("theme"), d.l("nb_problemes"), d.l("nb_ecrans"), d.l("gravite_max"), d.l("tendance")],
                  [[t.titre, len(t.problemes), len(t.ecrans), g(t.gravite_max),
                    d.l("recurrent") if t.recurrent else d.l("isole")] for t in r.themes],
                  largeurs=[7.5, 2.2, 2.2, 2.6, 2.3],
                  couleurs={(i, 3): COULEURS_GRAVITE[t.gravite_max] for i, t in enumerate(r.themes)})
    for i, t in enumerate(r.themes, 1):
        d.titre(f"2.{i} {t.titre}", 2)
        d.paragraphe(d.l("meta_theme", n=len(t.problemes), e=len(t.ecrans), g=g(t.gravite_max),
                         t=d.l("recurrent") if t.recurrent else d.l("isole")), italique=True, couleur=GRIS)
        if t.criteres and ref is not None:
            d.paragraphe(", ".join(ref.libelle_critere(c, lg) for c in t.criteres[:5]), gras=f"{d.l('criteres')} : ",
                         taille=9.5)
        d.texte_ou_a_rediger(t.description, d.l("observes"))
        d.texte_ou_a_rediger(t.pourquoi, d.l("pourquoi"))
        d.texte_ou_a_rediger(t.consequences, d.l("consequences"))
        exemples = sorted(t.problemes, key=lambda p: -p.poids)[:4]
        d.paragraphe(gras=d.l("representatifs"))
        d.tableau([d.l("ref"), d.l("ecran"), d.l("constat"), d.l("gravite")],
                  [[p.ref, p.ecran, _court(p.constat, 300), g(p.gravite)] for p in exemples],
                  largeurs=[1.6, 3.2, 9.6, 2.4],
                  couleurs={(k, 3): COULEURS_GRAVITE[p.gravite] for k, p in enumerate(exemples)})

    d.titre(f"2.{len(r.themes) + 1} {d.l('tendances')}", 2)
    d.paragraphe(d.l("tendances_rec"), italique=True)
    d.puces([f"{t.titre} — {d.l('n_problemes', n=len(t.problemes))}, {d.l('n_ecrans', n=len(t.ecrans))} "
             f"({', '.join(t.ecrans[:6])}{'…' if len(t.ecrans) > 6 else ''})"
             for t in r.themes if t.recurrent] or [d.l("aucun_rec")])
    d.paragraphe(d.l("tendances_iso"), italique=True)
    d.puces([f"{t.titre} — " + " ; ".join(f"{p.ref} ({p.ecran or '—'}, {g(p.gravite)}) : {_court(p.constat, 160)}"
                                          for p in t.problemes[:3]) for t in r.cas_isoles] or [d.l("aucun_iso")])

    # 3. Recommandations UX et UI
    d.doc.add_page_break()
    d.titre(f"3. {d.l('s3')}", 1)
    d.paragraphe(d.l("s3_intro"))
    if r.recommandations:
        d.tableau([d.l("rang"), d.l("chantier"), d.l("impact_court"), d.l("effort"), d.l("themes_traites")],
                  [[i, c.titre, _l(f"impact.{c.impact}", lg) if c.impact else "—",
                    _l(f"effort.{c.effort}", lg) if c.effort else "—", ", ".join(t.titre for t in c.themes)]
                   for i, c in enumerate(r.recommandations, 1)],
                  largeurs=[1.6, 6.2, 1.8, 1.8, 5.4],
                  couleurs={(i, 2): COULEURS_IMPACT.get(c.impact, "FFFFFF") for i, c in enumerate(r.recommandations)})
    for i, c in enumerate(r.recommandations, 1):
        d.titre(f"3.{i} {c.titre}", 2)
        d.paragraphe(f"{d.l('impact_court')} : {_l(f'impact.{c.impact}', lg) if c.impact else '—'}"
                     f"   ·   {d.l('effort')} : {_l(f'effort.{c.effort}', lg) if c.effort else '—'}",
                     italique=True, couleur=GRIS)
        d.texte_ou_a_rediger(c.objectif, d.l("objectif"))
        d.texte_ou_a_rediger(c.importance, d.l("importance"))
        d.texte_ou_a_rediger(c.benefices, d.l("benefices"))
        d.texte_ou_a_rediger(c.problemes_resolus, d.l("resout"))
        if c.themes:
            nb = sum(len(t.problemes) for t in c.themes)
            d.paragraphe(f"{', '.join(t.titre for t in c.themes)} ({d.l('n_problemes', n=nb)})",
                         gras=f"{d.l('themes_traites')} : ", taille=9.5)
        if c.pistes:
            d.paragraphe(gras=d.l("pistes"))
            d.puces(c.pistes)

    # 4. Prochaines étapes
    d.doc.add_page_break()
    d.titre(f"4. {d.l('s4')}", 1)
    d.titre(f"4.1 {d.l('qw')}", 2)
    d.paragraphe(d.l("qw_intro"))
    if r.quick_wins_candidats:
        d.paragraphe(d.l("qw_candidats"), italique=True, couleur=GRIS)
    if r.quick_wins:
        d.tableau([d.l("action"), d.l("valeur"), d.l("constats_lies")],
                  [[c.titre + (f"\n{c.description}" if c.description else ""), c.valeur or d.l("a_rediger"),
                    ", ".join(f"{p.ref} ({p.ecran})" if p.ecran else p.ref for p in c.problemes)]
                   for c in r.quick_wins], largeurs=[8.6, 5.0, 3.2])
    else:
        d.texte_ou_a_rediger("")
    d.titre(f"4.2 {d.l('mlt')}", 2)
    if r.suites:
        d.tableau([d.l("horizon"), d.l("chantier"), d.l("objectif")],
                  [[_l(f"horizon.{s.horizon}", lg), s.titre, s.description] for s in r.suites],
                  largeurs=[3.4, 5.0, 8.4])
    else:
        d.texte_ou_a_rediger("")
    d.titre(f"4.3 {d.l('demarche')}", 2)
    for i, etape in enumerate(r.demarche, 1):
        d.paragraphe(etape, gras=f"{i}. ")

    # Annexes
    d.doc.add_page_break()
    d.titre(d.l("annexes"), 1)
    d.titre(f"A. {d.l('methode')}", 2)
    d.paragraphe(d.l("methode_texte", v=f.version_referentiel))
    d.paragraphe(gras=d.l("echelle_gravite"))
    d.tableau([d.l("gravite"), ""], [[f"{n}. {v[lg]}", v[f"def_{lg}"]] for n, v in GRAVITES.items()],
              largeurs=[3.0, 13.8], couleurs={(i, 0): COULEURS_GRAVITE[n] for i, n in enumerate(GRAVITES)})
    d.paragraphe(gras=d.l("echelle_maturite"))
    d.tableau([d.l("maturite"), ""], [[f"{n}. {m[lg]}", m[f"def_{lg}"]] for n, m in MATURITES.items()],
              largeurs=[3.0, 13.8])
    d.paragraphe(d.l("regle_maturite"), italique=True, couleur=GRIS, taille=9)

    d.titre(f"B. {d.l('liste')}", 2)
    tries = sorted(f.problemes, key=lambda p: (-(p.gravite or 0), p.ecran, p.cle))
    d.tableau([d.l("ref"), d.l("ecran"), d.l("critere"), d.l("constat"), d.l("gravite")],
              [[p.ref, p.ecran, p.critere or "—", p.constat, g(p.gravite)] for p in tries],
              largeurs=[1.4, 2.8, 1.8, 8.6, 2.2], taille=8,
              couleurs={(i, 4): COULEURS_GRAVITE[p.gravite] for i, p in enumerate(tries)})
    if f.points_forts:
        d.titre(f"C. {d.l('points_forts_releves')}", 2)
        d.tableau([d.l("ref"), d.l("ecran"), d.l("constat")], [list(x) for x in f.points_forts],
                  largeurs=[1.6, 3.4, 11.8], taille=8)

    d.doc.save(sortie)
    return sortie


def generer_rapport(audit, ref, sortie=None, client=None, langue=None, forcer=False, progression=None):
    """Rédige le rapport et l'écrit en Word. Renvoie (rapport, sortie) ; sans `sortie`, des octets."""
    r = rediger(audit, ref, client, langue, forcer=forcer, progression=progression)
    if sortie is None:
        flux = io.BytesIO()
        ecrire_docx(r, flux, ref)
        return r, flux.getvalue()
    ecrire_docx(r, sortie, ref)
    return r, sortie
