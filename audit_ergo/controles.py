"""Contrôles de forme (niveau 1) : tout ce qui se vérifie par une règle, sans IA. Messages en français ou anglais."""
from dataclasses import dataclass
from difflib import SequenceMatcher

from .i18n import GRAVITES, lire_gravite, lire_type, lire_type_reco
from .lecture import CONTEXTE_OBLIGATOIRE, OBLIGATOIRES, libelle_champ
from .referentiel import normaliser

BLOQUANT, AVERTISSEMENT, INFO = "bloquant", "avertissement", "info"
NIVEAUX = [BLOQUANT, AVERTISSEMENT, INFO]

FREQUENCES = {"rare": "rare", "occasionnelle": "occasionnelle", "occasional": "occasionnelle",
              "systematique": "systematique", "systematic": "systematique"}
IMPACTS = {"faible": "faible", "low": "faible", "moyen": "moyen", "medium": "moyen", "fort": "fort", "high": "fort"}
PRIORITES = {"P1", "P2", "P3"}
LONGUEUR_MIN_CONSTAT = 20
LONGUEUR_MIN_RECO = 20
SEUIL_DOUBLON = 0.9
# Formulations qui signalent souvent un constat ou une recommandation trop vague
TERMES_VAGUES = ["confus", "pas clair", "pas intuitif", "peu intuitif", "à améliorer", "améliorer l'ergonomie",
                 "revoir l'ergonomie", "revoir le design", "pas ergonomique", "mal fait", "bof",
                 "confusing", "unclear", "not clear", "not intuitive", "improve the ux", "improve usability",
                 "rework the design", "redesign the page", "bad ux"]

MESSAGES = {
    "COLONNE_MANQUANTE": ("Colonne obligatoire introuvable : « {nom} ».", "Required column not found: “{nom}”."),
    "AUDIT_VIDE": ("Aucun constat trouvé dans le fichier.", "No finding found in the file."),
    "COLONNES_INCONNUES": ("Colonnes non reconnues (ignorées) : {liste}.", "Unrecognised columns (ignored): {liste}."),
    "CONTEXTE_ABSENT": ("Onglet « Contexte » absent : produit, cible et plateforme sont inconnus.",
                        "No “Context” sheet: product, target users and platform are unknown."),
    "CONTEXTE_INCOMPLET": ("Contexte incomplet : {liste}.", "Incomplete context: {liste}."),
    "REFERENTIEL_PERIME": ("Audit réalisé avec le référentiel v{version}, la version actuelle est v{actuelle} : "
                           "certains critères ou questions ont pu changer.",
                           "Audit made with referential v{version}, the current version is v{actuelle}: some "
                           "criteria or questions may have changed."),
    "CHAMP_VIDE": ("« {nom} » n'est pas renseigné.", "“{nom}” is empty."),
    "TYPE_INVALIDE": ("Type « {valeur} » inconnu (attendu : Problème ou Point fort).",
                      "Unknown type “{valeur}” (expected: Issue or Strength)."),
    "CONSTAT_COURT": ("Constat trop court pour être compris sans l'auteur.",
                      "Finding too short to be understood without its author."),
    "CONSTAT_VAGUE": ("Formulation vague (« {terme} ») : décrire ce qui est observé, où, et l'effet sur l'utilisateur.",
                      "Vague wording (“{terme}”): describe what is observed, where, and the effect on the user."),
    "CATEGORIE_INCONNUE": ("Catégorie « {valeur} » absente du référentiel.", "Criteria “{valeur}” not in the referential."),
    "CRITERE_INCONNU": ("Critère « {valeur} » absent du référentiel.", "Sub-criterion “{valeur}” not in the referential."),
    "CRITERE_HORS_CATEGORIE": ("Le critère {crit} appartient à la catégorie {bonne}, pas à {cat}.",
                               "Sub-criterion {crit} belongs to {bonne}, not to {cat}."),
    "SECONDAIRE_INCONNU": ("Critère(s) secondaire(s) inconnu(s) : {liste}.", "Unknown secondary criteria: {liste}."),
    "SECONDAIRE_ILLISIBLE": ("Critères secondaires à saisir sous forme de codes (ex. ERR-01 ; WKL-05).",
                             "Enter secondary criteria as codes (e.g. ERR-01 ; WKL-05)."),
    "SECONDAIRE_EGAL_PRINCIPAL": ("{crit} est à la fois critère principal et secondaire.",
                                  "{crit} is both the main and a secondary criterion."),
    "REGLE_INCONNUE": ("Règle de départage « {regle} » inconnue.", "Unknown tie-break rule “{regle}”."),
    "REGLE_INCOHERENTE": ("La règle {regle} départage {issues} : elle ne mène pas au critère {crit}.",
                          "Rule {regle} decides between {issues}: it does not lead to {crit}."),
    "GRAVITE_INVALIDE": ("Gravité « {valeur} » hors échelle ({echelle}).", "Severity “{valeur}” not on the scale ({echelle})."),
    "POINT_FORT_GRAVE": ("Une gravité n'a pas de sens pour un point fort.", "A severity makes no sense for a strength."),
    "FREQUENCE_INVALIDE": ("Fréquence « {valeur} » inconnue.", "Unknown frequency “{valeur}”."),
    "IMPACT_INVALIDE": ("Impact « {valeur} » inconnu.", "Unknown impact “{valeur}”."),
    "GRAVITE_IMPACT_HAUTE": ("Gravité critique avec un impact « Faible ».", "Critical severity with a “Low” impact."),
    "GRAVITE_IMPACT_BASSE": ("Gravité faible alors que l'impact est fort et le problème systématique.",
                             "Low severity although the impact is high and the problem systematic."),
    "PRIORITE_INVALIDE": ("Priorité « {valeur} » inconnue.", "Unknown priority “{valeur}”."),
    "PRIORITE_GRAVITE": ("Priorité {prio} incohérente avec la gravité « {gravite} ».",
                         "Priority {prio} inconsistent with severity “{gravite}”."),
    "TYPE_RECO_INVALIDE": ("Type de recommandation « {valeur} » inconnu.", "Unknown type of recommendation “{valeur}”."),
    "RECO_COURTE": ("Recommandation trop courte pour être actionnable.", "Recommendation too short to be actionable."),
    "RECO_COPIE_CONSTAT": ("La recommandation reprend le constat au lieu de proposer une solution.",
                           "The recommendation repeats the finding instead of proposing a solution."),
    "RECO_VAGUE": ("Recommandation vague (« {terme} ») : nommer l'élément à modifier et le changement attendu.",
                   "Vague recommendation (“{terme}”): name the element to change and the expected change."),
    "DOUBLON": ("Constat quasi identique à {autre} (ligne {ligne}) sur le même écran.",
                "Finding almost identical to {autre} (row {ligne}) on the same screen."),
}


@dataclass
class Anomalie:
    niveau: str
    code: str
    message: str
    ligne: int | None = None  # ligne Excel ; None = concerne tout le fichier
    constat: str | None = None
    champ: str | None = None


def message(code, langue="fr", **valeurs):
    fr, en = MESSAGES[code]
    return (en if langue == "en" else fr).format(**valeurs)


def _vague(texte):
    n = f" {normaliser(texte)} "
    return [t for t in TERMES_VAGUES if f" {normaliser(t)} " in n]


def _echelle(langue):
    return ", ".join(f"{g} {v[langue]}" for g, v in GRAVITES.items())


def controler_fichier(audit, ref, langue="fr"):
    def anomalie(niveau, code, champ=None, **valeurs):
        return Anomalie(niveau, code, message(code, langue, **valeurs), champ=champ)

    anomalies = [anomalie(BLOQUANT, "COLONNE_MANQUANTE", champ, nom=libelle_champ(champ, langue))
                 for champ in audit.colonnes_manquantes]
    if not audit.constats:
        anomalies.append(anomalie(BLOQUANT, "AUDIT_VIDE"))
    if audit.colonnes_inconnues:
        anomalies.append(anomalie(INFO, "COLONNES_INCONNUES", liste=", ".join(audit.colonnes_inconnues)))
    if not audit.contexte:
        anomalies.append(anomalie(AVERTISSEMENT, "CONTEXTE_ABSENT"))
    else:
        manquants = [c for c in CONTEXTE_OBLIGATOIRE if not audit.contexte.get(c)]
        if manquants:
            anomalies.append(anomalie(AVERTISSEMENT, "CONTEXTE_INCOMPLET", liste=", ".join(manquants)))
        version = audit.contexte.get("version_referentiel")
        if version and str(version) != ref.version:
            anomalies.append(anomalie(AVERTISSEMENT, "REFERENTIEL_PERIME", version=version, actuelle=ref.version))
    return anomalies


def controler_constat(c, ref, langue="fr"):
    out = []

    def ajouter(niveau, code, champ=None, **valeurs):
        out.append(Anomalie(niveau, code, message(code, langue, **valeurs), ligne=c.ligne, constat=c.ref,
                            champ=champ))

    type_ = lire_type(c["type"])
    est_probleme = type_ != "point_fort"  # sans type (template d'origine), un constat est un problème

    for champ in OBLIGATOIRES:
        if champ in ("recommandation", "gravite") and not est_probleme:
            continue
        if c[champ] in (None, ""):
            ajouter(BLOQUANT, "CHAMP_VIDE", champ, nom=libelle_champ(champ, langue))

    if c["type"] and not type_:
        ajouter(BLOQUANT, "TYPE_INVALIDE", "type", valeur=c["type"])

    constat = str(c["constat"] or "")
    if constat and len(constat) < LONGUEUR_MIN_CONSTAT:
        ajouter(AVERTISSEMENT, "CONSTAT_COURT", "constat")
    if constat and (termes := _vague(constat)):
        ajouter(INFO, "CONSTAT_VAGUE", "constat", terme=termes[0])

    # Catégorie et critère
    cat = ref.trouver_categorie(c["categorie"])
    crit = ref.trouver_critere(c["critere"])
    if c["categorie"] and not cat:
        ajouter(BLOQUANT, "CATEGORIE_INCONNUE", "categorie", valeur=c["categorie"])
    if c["critere"] and not crit:
        ajouter(BLOQUANT, "CRITERE_INCONNU", "critere", valeur=c["critere"])
    if cat and crit and ref.criteres[crit]["categorie"] != cat:
        bonne = ref.libelle_categorie(ref.criteres[crit]["categorie"], langue)
        ajouter(BLOQUANT, "CRITERE_HORS_CATEGORIE", "critere", crit=crit, bonne=bonne, cat=cat)

    connus, inconnus = ref.codes_mentionnes(c["secondaires"])
    if inconnus:
        ajouter(AVERTISSEMENT, "SECONDAIRE_INCONNU", "secondaires", liste=", ".join(inconnus))
    if c["secondaires"] and not connus and not inconnus:
        ajouter(AVERTISSEMENT, "SECONDAIRE_ILLISIBLE", "secondaires")
    if crit and crit in connus:
        ajouter(INFO, "SECONDAIRE_EGAL_PRINCIPAL", "secondaires", crit=crit)

    regle = str(c["regle"] or "").strip().upper()
    if regle:
        if regle not in ref.regles:
            ajouter(AVERTISSEMENT, "REGLE_INCONNUE", "regle", regle=regle)
        elif crit and crit not in {cas["critere"] for cas in ref.regles[regle]["cas"]}:
            issues = ", ".join(cas["critere"] for cas in ref.regles[regle]["cas"])
            ajouter(AVERTISSEMENT, "REGLE_INCOHERENTE", "regle", regle=regle, issues=issues, crit=crit)

    # Gravité (échelle à 4 niveaux du template d'origine), fréquence, impact, priorité
    g = lire_gravite(c["gravite"])
    if c["gravite"] not in (None, "") and g is None:
        ajouter(BLOQUANT, "GRAVITE_INVALIDE", "gravite", valeur=c["gravite"], echelle=_echelle(langue))
    if not est_probleme and g:
        ajouter(INFO, "POINT_FORT_GRAVE", "gravite")

    freq = FREQUENCES.get(normaliser(c["frequence"] or ""))
    impact = IMPACTS.get(normaliser(c["impact"] or ""))
    if c["frequence"] and not freq:
        ajouter(AVERTISSEMENT, "FREQUENCE_INVALIDE", "frequence", valeur=c["frequence"])
    if c["impact"] and not impact:
        ajouter(AVERTISSEMENT, "IMPACT_INVALIDE", "impact", valeur=c["impact"])
    if est_probleme and g is not None and impact:
        if g == 4 and impact == "faible":
            ajouter(AVERTISSEMENT, "GRAVITE_IMPACT_HAUTE", "gravite")
        if g == 1 and impact == "fort" and freq == "systematique":
            ajouter(AVERTISSEMENT, "GRAVITE_IMPACT_BASSE", "gravite")

    prio = str(c["priorite"] or "").strip().upper()
    if prio and prio not in PRIORITES:
        ajouter(AVERTISSEMENT, "PRIORITE_INVALIDE", "priorite", valeur=c["priorite"])
    if est_probleme and g is not None and prio in PRIORITES:
        if (g >= 3 and prio == "P3") or (g == 1 and prio == "P1"):
            ajouter(AVERTISSEMENT, "PRIORITE_GRAVITE", "priorite", prio=prio, gravite=GRAVITES[g][langue])

    if c["type_reco"] and not lire_type_reco(c["type_reco"]):
        ajouter(AVERTISSEMENT, "TYPE_RECO_INVALIDE", "type_reco", valeur=c["type_reco"])

    # Recommandation
    reco = str(c["recommandation"] or "")
    if est_probleme and reco:
        if len(reco) < LONGUEUR_MIN_RECO:
            ajouter(AVERTISSEMENT, "RECO_COURTE", "recommandation")
        if constat and SequenceMatcher(None, normaliser(reco), normaliser(constat)).ratio() > SEUIL_DOUBLON:
            ajouter(AVERTISSEMENT, "RECO_COPIE_CONSTAT", "recommandation")
        if termes := _vague(reco):
            ajouter(INFO, "RECO_VAGUE", "recommandation", terme=termes[0])
    return out


def controler_doublons(constats, langue="fr"):
    out = []
    textes = [(c, normaliser(c["ecran"] or ""), normaliser(c["constat"] or "")) for c in constats]
    for i, (a, ecran_a, txt_a) in enumerate(textes):
        for b, ecran_b, txt_b in textes[i + 1:]:
            if txt_a and txt_b and ecran_a == ecran_b and SequenceMatcher(None, txt_a, txt_b).ratio() > SEUIL_DOUBLON:
                out.append(Anomalie(AVERTISSEMENT, "DOUBLON", message("DOUBLON", langue, autre=a.ref, ligne=a.ligne),
                                    ligne=b.ligne, constat=b.ref, champ="constat"))
    return out


def controler(audit, ref, langue="fr"):
    anomalies = controler_fichier(audit, ref, langue)
    for c in audit.constats:
        anomalies += controler_constat(c, ref, langue)
    anomalies += controler_doublons(audit.constats, langue)
    return sorted(anomalies, key=lambda a: (a.ligne or 0, NIVEAUX.index(a.niveau)))
