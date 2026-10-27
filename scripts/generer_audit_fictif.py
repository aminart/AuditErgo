"""Génère deux audits FICTIFS à partir du template, pour la démonstration et les tests.

- exemples/audit_fictif.xlsx : audit complet, avec des erreurs de forme volontaires ;
- exemples/audit_a_completer.xlsx : surtout des constats seuls (l'IA complète le reste), plus quelques
  critères et recommandations saisis par le designer, à faire corriger.
Usage : python3 scripts/generer_audit_fictif.py
"""
from datetime import date
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "template" / "Audit_ergonomique_template.xlsx"
OUT = ROOT / "exemples" / "audit_fictif.xlsx"
OUT_A_COMPLETER = ROOT / "exemples" / "audit_a_completer.xlsx"

CONTEXTE = {
    "Produit / interface auditée *": "BoutiqueDemo (site e-commerce FICTIF)",
    "Cible utilisateurs *": "Grand public, 25-60 ans, achats occasionnels",
    "Plateforme *": "Web responsive / mobile",
    "Parcours audités *": "Recherche produit, panier, paiement, compte client",
    "Designer *": "Designer fictif",
    "Date de l'audit *": date(2026, 10, 20),
}

GUI, WKL, CTL, ERR, COD, CPT, VIS = (
    "GUI – Guidage", "WKL – Charge de travail", "CTL – Contrôle explicite", "ERR – Gestion des erreurs",
    "COD – Signifiance des codes et dénominations", "CPT – Compatibilité", "VIS – Design visuel",
)
# (écran, parcours, type, constat, catégorie, critère, secondaires, règle, gravité, fréquence, impact, reco, priorité)
# Le commentaire en fin de ligne indique l'erreur volontaire attendue.
CONSTATS = [
    ("Paiement", "Commander", "Problème",
     "Après un clic sur « Payer », aucun indicateur de chargement pendant environ 5 secondes ; le bouton reste actif.",
     GUI, "GUI-03 – Feedback immédiat (Immediate Feedback)", "ERR-01", "R1", 3, "Systématique", "Fort",
     "Afficher un indicateur de chargement dans le bouton « Payer » et le désactiver jusqu'à la réponse du serveur.",
     "P1"),  # aucune erreur
    ("Formulaire d'inscription", "Créer un compte", "Problème",
     "Le format attendu pour la date de naissance n'est indiqué nulle part ; les saisies « 3/4/90 » sont refusées.",
     GUI, "GUI-01 – Incitation (Prompting)", "ERR-01 ; ERR-02", "R1", 2, "Occasionnelle", "Moyen",
     "Ajouter le format attendu (JJ/MM/AAAA) dans le libellé et un exemple sous le champ.", "P2"),  # aucune
    ("Panier", "Commander", "Problème",
     "Le bouton « Supprimer » retire l'article du panier sans confirmation ni possibilité d'annuler.",
     GUI, "ERR-03 – Correction des erreurs (Error Correction)", "", "", 3, "Occasionnelle", "Fort",
     "Proposer un lien « Annuler » pendant quelques secondes après la suppression d'un article.",
     "P2"),  # critère hors catégorie
    ("Résultats de recherche", "Rechercher", "Problème",
     "La page de résultats affiche 60 produits, 12 filtres et 3 bannières promotionnelles sans hiérarchie claire.",
     WKL, "WKL-05 – Densité informationnelle (Information density)", "WKL-04", "", 2, "Systématique", "Moyen",
     "", "P2"),  # recommandation manquante
    ("Accueil", "", "Problème", "Menu confus.",
     WKL, "WKL-01 – Concision (Concision)", "", "", 1, "", "", "Revoir l'ergonomie du menu.",
     ""),  # constat court + vague, reco courte + vague
    ("Compte client", "Gérer ses commandes", "Problème",
     "L'icône d'engrenage ouvre l'historique des commandes au lieu des paramètres du compte.",
     COD, "COD-01 – Signifiance des codes et dénominations (Significance of Codes)", "CON-01 ; XYZ-99", "R1", 2,
     "Systématique", "Moyen",
     "Remplacer l'engrenage par une icône de liste accompagnée du libellé « Mes commandes ».",
     "P2"),  # règle R1 incohérente avec COD-01 + secondaire inconnu
    ("Paiement", "Commander", "Problème",
     "En cas de carte refusée, le message « Erreur 402 » s'affiche sans explication ni solution proposée.",
     ERR, "ERR-02 – Qualité des messages d'erreur (Quality of Error Messages)", "", "R2", 4, "Occasionnelle",
     "Fort", "Remplacer le code par un message clair : cause du refus, et proposer un autre moyen de paiement.",
     "P3"),  # priorité incohérente avec la gravité
    ("Paiement", "Commander", "Problème",
     "En cas de carte refusée, le message « Erreur 402 » s'affiche sans aucune explication ni solution proposée.",
     ERR, "ERR-02 – Qualité des messages d'erreur (Quality of Error Messages)", "", "", 4, "Occasionnelle",
     "Fort", "Afficher un message compréhensible indiquant la cause du refus et les solutions possibles.",
     "P1"),  # doublon du précédent
    ("Fiche produit", "Rechercher", "Point fort",
     "Les photos produit sont zoomables et la disponibilité en magasin est indiquée clairement.",
     CPT, "CPT-01 – Compatibilité et correspondance avec le monde réel "
          "(Compatibility & match with the real world)", "", "", 2, "", "", "", ""),  # point fort avec gravité
    ("Tunnel de commande", "Commander", "Problème",
     "Aucun bouton « Retour » n'est proposé entre les étapes Livraison et Paiement ; le retour navigateur vide le panier.",
     CTL, "Contrôle utilisateur et liberté", "", "R4", 5, "Systématique", "Fort",
     "Ajouter un bouton « Étape précédente » qui conserve toutes les informations saisies.",
     "P1"),  # critère saisi par son nom (accepté) + gravité hors échelle
    ("Fiche produit", "Rechercher", "Problème",
     "Le prix barré et le prix promotionnel ont la même taille et la même couleur ; on ne sait pas lequel s'applique.",
     VIS, "VIS-01 – Design visuel au service de l'utilisabilité (Visual design for usability)", "GUI-02", "R6", 2,
     "Systématique", "Moyen",
     "Afficher le prix promotionnel en gras et plus grand, et le prix d'origine barré en gris plus petit.",
     "P2"),  # aucune
]


def main():
    wb = load_workbook(TEMPLATE)
    ws = wb["Contexte"]
    for row in ws.iter_rows(min_col=1, max_col=2):
        if row[0].value in CONTEXTE:
            row[1].value = CONTEXTE[row[0].value]
    ws = wb["Audit"]
    for i, constat in enumerate(CONSTATS):
        r = 5 + i
        ecran, parcours, *reste = constat
        ws[f"B{r}"], ws[f"C{r}"] = ecran, parcours or None
        for col, valeur in zip("EFGHIJKLMNO", reste):
            ws[f"{col}{r}"] = valeur if valeur != "" else None
    OUT.parent.mkdir(exist_ok=True)
    wb.save(OUT)
    print(f"{len(CONSTATS)} constats fictifs -> {OUT}")
    generer_a_completer()


# (écran, constat, critère du designer ou None, recommandation du designer ou None)
A_COMPLETER = [
    ("Paiement", "Après un clic sur « Payer », aucun indicateur de chargement n'apparaît pendant environ "
                 "5 secondes ; le bouton reste actif et certains utilisateurs cliquent plusieurs fois.", None, None),
    ("Formulaire d'inscription", "Le format attendu pour la date de naissance n'est indiqué nulle part ; "
                                 "la saisie « 3/4/90 » est refusée sans explication.", None, None),
    ("Panier", "Le bouton « Supprimer » retire l'article du panier immédiatement, sans confirmation ni "
               "possibilité d'annuler.", None, None),
    ("Résultats de recherche", "La page affiche 60 produits, 12 filtres et 3 bannières promotionnelles "
                               "sans hiérarchie visuelle claire.", None, None),
    ("Compte client", "L'icône d'engrenage ouvre l'historique des commandes au lieu des paramètres du compte.",
     "GUI-01 – Incitation (Prompting)", None),  # critère discutable, à faire corriger
    ("Paiement", "En cas de carte refusée, le message « Erreur 402 » s'affiche sans explication ni solution.",
     "ERR-02 – Qualité des messages d'erreur (Quality of Error Messages)", "Améliorer le message."),  # reco vague
    ("Tunnel de commande", "Aucun bouton « Retour » entre les étapes Livraison et Paiement ; le retour du "
                           "navigateur vide le panier.", None, None),
    ("Fiche produit", "Le prix barré et le prix promotionnel ont la même taille et la même couleur.", None, None),
]


def generer_a_completer():
    wb = load_workbook(TEMPLATE)
    ws = wb["Contexte"]
    for row in ws.iter_rows(min_col=1, max_col=2):
        if row[0].value in CONTEXTE:
            row[1].value = CONTEXTE[row[0].value]
    ws = wb["Audit"]
    for i, (ecran, constat, critere, reco) in enumerate(A_COMPLETER):
        r = 5 + i
        ws[f"B{r}"], ws[f"F{r}"] = ecran, constat
        if critere:
            ws[f"H{r}"] = critere
        if reco:
            ws[f"N{r}"] = reco
    wb.save(OUT_A_COMPLETER)
    print(f"{len(A_COMPLETER)} constats à compléter -> {OUT_A_COMPLETER}")


if __name__ == "__main__":
    main()
