"""Contrôles de forme (niveau 1) : tout ce qui se vérifie par une règle, sans IA."""
from dataclasses import dataclass
from difflib import SequenceMatcher

from .lecture import CONTEXTE_OBLIGATOIRE, LIBELLES, OBLIGATOIRES
from .referentiel import normaliser

BLOQUANT, AVERTISSEMENT, INFO = "bloquant", "avertissement", "info"
NIVEAUX = [BLOQUANT, AVERTISSEMENT, INFO]

TYPES = {"probleme": "Problème", "point fort": "Point fort"}
FREQUENCES = {"rare", "occasionnelle", "systematique"}
IMPACTS = {"faible", "moyen", "fort"}
PRIORITES = {"P1", "P2", "P3"}
LONGUEUR_MIN_CONSTAT = 20
LONGUEUR_MIN_RECO = 20
SEUIL_DOUBLON = 0.9
# Formulations qui signalent souvent un constat ou une recommandation trop vague
TERMES_VAGUES = ["confus", "pas clair", "pas intuitif", "peu intuitif", "à améliorer", "améliorer l'ergonomie",
                 "revoir l'ergonomie", "revoir le design", "pas ergonomique", "mal fait", "bof"]


@dataclass
class Anomalie:
    niveau: str
    code: str
    message: str
    ligne: int | None = None  # ligne Excel ; None = concerne tout le fichier
    constat: str | None = None
    champ: str | None = None


def _gravite(valeur):
    try:
        g = float(valeur)
    except (TypeError, ValueError):
        return None
    return int(g) if g.is_integer() and 0 <= g <= 4 else None


def _vague(texte):
    n = f" {normaliser(texte)} "
    return [t for t in TERMES_VAGUES if f" {normaliser(t)} " in n]


def controler_fichier(audit, ref):
    anomalies = []
    for champ in audit.colonnes_manquantes:
        anomalies.append(Anomalie(BLOQUANT, "COLONNE_MANQUANTE",
                                  f"Colonne obligatoire introuvable : « {LIBELLES[champ]} ».", champ=champ))
    if not audit.constats:
        anomalies.append(Anomalie(BLOQUANT, "AUDIT_VIDE", "Aucun constat trouvé dans le fichier."))
    if audit.colonnes_inconnues:
        anomalies.append(Anomalie(INFO, "COLONNES_INCONNUES",
                                  "Colonnes non reconnues (ignorées) : " + ", ".join(audit.colonnes_inconnues) + "."))
    if not audit.contexte:
        anomalies.append(Anomalie(AVERTISSEMENT, "CONTEXTE_ABSENT",
                                  "Onglet « Contexte » absent : produit, cible et plateforme sont inconnus."))
    else:
        manquants = [c for c in CONTEXTE_OBLIGATOIRE if not audit.contexte.get(c)]
        if manquants:
            anomalies.append(Anomalie(AVERTISSEMENT, "CONTEXTE_INCOMPLET",
                                      "Contexte incomplet : " + ", ".join(manquants) + "."))
        version = audit.contexte.get("version_referentiel")
        if version and str(version) != ref.version:
            anomalies.append(Anomalie(AVERTISSEMENT, "REFERENTIEL_PERIME",
                                      f"Audit réalisé avec le référentiel v{version}, la version actuelle est "
                                      f"v{ref.version} : certains critères ou questions ont pu changer."))
    return anomalies


def controler_constat(c, ref):
    out = []

    def ajouter(niveau, code, message, champ=None):
        out.append(Anomalie(niveau, code, message, ligne=c.ligne, constat=c.ref, champ=champ))

    type_ = TYPES.get(normaliser(c["type"] or ""))
    est_probleme = type_ != "Point fort"

    for champ in OBLIGATOIRES:
        if champ == "recommandation" and not est_probleme:
            continue
        if c[champ] in (None, ""):
            ajouter(BLOQUANT, "CHAMP_VIDE", f"« {LIBELLES[champ]} » n'est pas renseigné.", champ)

    if c["type"] and not type_:
        ajouter(BLOQUANT, "TYPE_INVALIDE", f"Type « {c['type']} » inconnu (attendu : Problème ou Point fort).", "type")

    constat = str(c["constat"] or "")
    if constat and len(constat) < LONGUEUR_MIN_CONSTAT:
        ajouter(AVERTISSEMENT, "CONSTAT_COURT", "Constat trop court pour être compris sans l'auteur.", "constat")
    if constat and (termes := _vague(constat)):
        ajouter(INFO, "CONSTAT_VAGUE", f"Formulation vague (« {termes[0]} ») : décrire ce qui est observé, "
                                       "où, et l'effet sur l'utilisateur.", "constat")

    # Catégorie et critère
    cat = ref.trouver_categorie(c["categorie"])
    crit = ref.trouver_critere(c["critere"])
    if c["categorie"] and not cat:
        ajouter(BLOQUANT, "CATEGORIE_INCONNUE", f"Catégorie « {c['categorie']} » absente du référentiel.", "categorie")
    if c["critere"] and not crit:
        ajouter(BLOQUANT, "CRITERE_INCONNU", f"Critère « {c['critere']} » absent du référentiel.", "critere")
    if cat and crit and ref.criteres[crit]["categorie"] != cat:
        bonne = ref.categories[ref.criteres[crit]["categorie"]]
        ajouter(BLOQUANT, "CRITERE_HORS_CATEGORIE",
                f"Le critère {crit} appartient à la catégorie {bonne['code']} – {bonne['label_fr']}, "
                f"pas à {cat}.", "critere")

    connus, inconnus = ref.codes_mentionnes(c["secondaires"])
    if inconnus:
        ajouter(AVERTISSEMENT, "SECONDAIRE_INCONNU",
                "Critère(s) secondaire(s) inconnu(s) : " + ", ".join(inconnus) + ".", "secondaires")
    if c["secondaires"] and not connus and not inconnus:
        ajouter(AVERTISSEMENT, "SECONDAIRE_ILLISIBLE",
                "Critères secondaires à saisir sous forme de codes (ex. ERR-01 ; WKL-05).", "secondaires")
    if crit and crit in connus:
        ajouter(INFO, "SECONDAIRE_EGAL_PRINCIPAL", f"{crit} est à la fois critère principal et secondaire.",
                "secondaires")

    regle = str(c["regle"] or "").strip().upper()
    if regle:
        if regle not in ref.regles:
            ajouter(AVERTISSEMENT, "REGLE_INCONNUE", f"Règle de départage « {regle} » inconnue.", "regle")
        elif crit and crit not in {cas["critere"] for cas in ref.regles[regle]["cas"]}:
            issues = ", ".join(cas["critere"] for cas in ref.regles[regle]["cas"])
            ajouter(AVERTISSEMENT, "REGLE_INCOHERENTE",
                    f"La règle {regle} départage {issues} : elle ne mène pas au critère {crit}.", "regle")

    # Gravité, fréquence, impact, priorité
    g = _gravite(c["gravite"])
    if c["gravite"] not in (None, "") and g is None:
        ajouter(BLOQUANT, "GRAVITE_INVALIDE", f"Gravité « {c['gravite']} » hors échelle (0 à 4).", "gravite")
    if not est_probleme and g:
        ajouter(AVERTISSEMENT, "POINT_FORT_GRAVE", "Un point fort ne devrait pas avoir de gravité supérieure à 0.",
                "gravite")
    if est_probleme and g == 0:
        ajouter(INFO, "PROBLEME_GRAVITE_0", "Gravité 0 (« pas un problème ») pour un constat de type Problème.",
                "gravite")

    freq, impact = normaliser(c["frequence"] or ""), normaliser(c["impact"] or "")
    if freq and freq not in FREQUENCES:
        ajouter(AVERTISSEMENT, "FREQUENCE_INVALIDE", f"Fréquence « {c['frequence']} » inconnue.", "frequence")
    if impact and impact not in IMPACTS:
        ajouter(AVERTISSEMENT, "IMPACT_INVALIDE", f"Impact « {c['impact']} » inconnu.", "impact")
    if est_probleme and g is not None and impact in IMPACTS:
        if g >= 4 and impact == "faible":
            ajouter(AVERTISSEMENT, "GRAVITE_IMPACT", "Gravité 4 (bloquant) avec un impact « Faible ».", "gravite")
        if g <= 1 and impact == "fort" and freq == "systematique":
            ajouter(AVERTISSEMENT, "GRAVITE_IMPACT",
                    "Gravité ≤ 1 alors que l'impact est fort et le problème systématique.", "gravite")

    prio = str(c["priorite"] or "").strip().upper()
    if prio and prio not in PRIORITES:
        ajouter(AVERTISSEMENT, "PRIORITE_INVALIDE", f"Priorité « {c['priorite']} » inconnue.", "priorite")
    if est_probleme and g is not None and prio in PRIORITES:
        if (g >= 3 and prio == "P3") or (g <= 1 and prio == "P1"):
            ajouter(AVERTISSEMENT, "PRIORITE_GRAVITE", f"Priorité {prio} incohérente avec la gravité {g}.", "priorite")

    # Recommandation
    reco = str(c["recommandation"] or "")
    if est_probleme and reco:
        if len(reco) < LONGUEUR_MIN_RECO:
            ajouter(AVERTISSEMENT, "RECO_COURTE", "Recommandation trop courte pour être actionnable.",
                    "recommandation")
        if constat and SequenceMatcher(None, normaliser(reco), normaliser(constat)).ratio() > SEUIL_DOUBLON:
            ajouter(AVERTISSEMENT, "RECO_COPIE_CONSTAT", "La recommandation reprend le constat au lieu de "
                                                         "proposer une solution.", "recommandation")
        if termes := _vague(reco):
            ajouter(INFO, "RECO_VAGUE", f"Recommandation vague (« {termes[0]} ») : nommer l'élément à modifier "
                                        "et le changement attendu.", "recommandation")
    return out


def controler_doublons(constats):
    out = []
    textes = [(c, normaliser(c["ecran"] or ""), normaliser(c["constat"] or "")) for c in constats]
    for i, (a, ecran_a, txt_a) in enumerate(textes):
        for b, ecran_b, txt_b in textes[i + 1:]:
            if txt_a and txt_b and ecran_a == ecran_b and SequenceMatcher(None, txt_a, txt_b).ratio() > SEUIL_DOUBLON:
                out.append(Anomalie(AVERTISSEMENT, "DOUBLON",
                                    f"Constat quasi identique à {a.ref} (ligne {a.ligne}) sur le même écran.",
                                    ligne=b.ligne, constat=b.ref, champ="constat"))
    return out


def controler(audit, ref):
    anomalies = controler_fichier(audit, ref)
    for c in audit.constats:
        anomalies += controler_constat(c, ref)
    anomalies += controler_doublons(audit.constats)
    return sorted(anomalies, key=lambda a: (a.ligne or 0, NIVEAUX.index(a.niveau)))
