# Audit ergonomique assisté

Application d'aide à la relecture des audits ergonomiques (heuristiques) réalisés par les UX designers.

## Utilisation (version 1 : contrôles de forme)

```bash
pip install -r requirements.txt

# Interface web : déposer l'audit, voir les anomalies, télécharger le fichier annoté
streamlit run app.py

# Ligne de commande : produit <audit>_relu.xlsx (code retour 1 s'il reste des anomalies bloquantes)
python3 -m audit_ergo exemples/audit_fictif.xlsx
python3 -m audit_ergo mon_audit.xlsx -o relu.xlsx --json
```

L'outil lit le template, mais aussi un fichier libre : il cherche l'onglet et la ligne d'en-tête, reconnaît les colonnes même déplacées ou renommées (« Préconisation » = Recommandation), et accepte un critère saisi par son code, son nom français ou anglais.

Il renvoie le fichier d'origine **annoté** : cellules fautives surlignées et commentées, deux colonnes « Relecture » ajoutées, et deux onglets « Relecture – Synthèse » (indicateurs, gravités, couverture des 24 critères) et « Relecture – Anomalies ». Les formules et listes déroulantes du designer sont conservées.

Les contrôles (`audit_ergo/controles.py`) sont classés en trois niveaux :
- **Bloquant** : champ obligatoire vide, critère ou catégorie inconnus, critère hors de sa catégorie, gravité hors échelle.
- **Avertissement** : constat ou recommandation trop courts, recommandation qui recopie le constat, priorité ou impact incohérents avec la gravité, règle de départage qui ne mène pas au critère choisi, critère secondaire inconnu, doublon, contexte incomplet, référentiel périmé.
- **Info** : formulations vagues (« confus », « revoir l'ergonomie »…), gravité 0 pour un problème, critère secondaire identique au principal.

`exemples/audit_fictif.xlsx` est un audit **fictif** contenant des erreurs volontaires (régénérable avec `python3 scripts/generer_audit_fictif.py`).

## Tests

```bash
python3 -m pytest -q
```

## Contenu

| Chemin | Rôle |
|---|---|
| `audit_ergo/` | Moteur de relecture : lecture du fichier, contrôles, synthèse, export annoté |
| `app.py` | Interface web (Streamlit) |
| `tests/` | Tests automatiques |
| `CONCEPTION.md` | Document de conception : fonctionnalités, architecture, règles de départage, score, feuille de route |
| `template/Audit_ergonomique_template.xlsx` | **Template à remplir par les designers** (listes déroulantes, contrôles automatiques, aide intégrée) |
| `referentiel/source/` | CSV d'origine (grille des critères et frameworks heuristiques), jamais modifiés |
| `referentiel/corrections.json` | Corrections proposées : codes des critères, noms français, checklists complétées, doublons retirés |
| `referentiel/regles_departage.json` | Règles pour choisir entre deux critères proches (R1 à R9) |
| `referentiel/referentiel.json` | Référentiel final, **généré**, utilisé par le template et par la future application |
| `referentiel/CHANGEMENTS.md` | Liste lisible des modifications proposées, **générée**, à faire valider |

## Modifier le référentiel

1. Éditer `referentiel/corrections.json` ou `referentiel/regles_departage.json`.
2. Régénérer :
   ```bash
   python3 scripts/build_referentiel.py   # référentiel.json + CHANGEMENTS.md
   python3 scripts/build_template.py      # template Excel (nécessite openpyxl)
   ```

`build_referentiel.py` refuse de générer le référentiel si une question d'origine disparaît sans justification, si une question déplacée n'existe pas dans son critère d'origine, ou si une règle de départage cite un critère inconnu.
