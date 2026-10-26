# Audit ergonomique assisté

Application d'aide à la relecture des audits ergonomiques (heuristiques) réalisés par les UX designers.

## Contenu

| Chemin | Rôle |
|---|---|
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
