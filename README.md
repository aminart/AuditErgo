# Audit ergonomique assisté

Application d'aide à la relecture des audits ergonomiques (heuristiques) réalisés par les UX designers.

## Installation

### Windows : double-cliquer sur `start.bat`

Prérequis : [Python 3.10 ou plus récent](https://www.python.org/downloads/), installé en cochant « Add python.exe to PATH ».

`start.bat` s'occupe du reste :
1. au premier lancement, il crée le fichier `.env` et l'ouvre dans le Bloc-notes pour y saisir `API_KEY`, `API_BASE`, `CA_BUNDLE` et `AUDIT_ERGO_MODELE` ;
2. il crée un environnement Python isolé (dossier `.venv`) et y installe les dépendances, en utilisant `CA_BUNDLE` si le proxy de l'entreprise l'exige ; les dépendances ne sont réinstallées que si `requirements.txt` change ;
3. il lance l'application et ouvre le navigateur sur http://localhost:8501. Pour l'arrêter, fermer la fenêtre.

En cas de problème d'installation, supprimer le dossier `.venv` et relancer `start.bat`.

### Autres systèmes, ou installation manuelle

```bash
pip install -r requirements.txt
cp .env.exemple .env      # puis compléter .env (voir ci-dessous)
streamlit run app.py      # ouvre l'interface dans le navigateur
```

Le fichier `.env` (ignoré par Git) contient :

| Variable | Rôle |
|---|---|
| `API_KEY` | Clé d'API. Sans elle, tout fonctionne sauf les suggestions de critères. |
| `API_BASE` | Adresse de la passerelle, par exemple `https://passerelle.exemple.fr/v1` (la forme `…/v1/chat/completions` est aussi acceptée). Vide = API Anthropic directe. |
| `CA_BUNDLE` | Chemin du fichier de certificats (PEM) de l'organisation, si la passerelle ou le proxy utilise une autorité de certification interne. |
| `AUDIT_ERGO_MODELE` | Nom du modèle tel que la passerelle le connaît. |

**Deux formats d'API sont pris en charge** (variable `API_FORMAT`) :
- `openai` : passerelle au format OpenAI (`/v1/chat/completions`). C'est le format par défaut quand `API_BASE` est renseigné. Si la passerelle n'accepte pas `response_format`, l'application réessaie automatiquement sans, et valide elle-même la réponse.
- `anthropic` : API Anthropic (`/v1/messages`), directe ou via une passerelle compatible. Par défaut quand `API_BASE` est vide. Ce format permet en plus la mise en cache du référentiel, le réglage de l'effort de réflexion et la relance automatique en cas de refus.

La clé peut aussi être saisie dans la barre latérale de l'interface (elle n'est alors gardée que le temps de la session). Les noms `ANTHROPIC_API_KEY` et `ANTHROPIC_BASE_URL` sont également acceptés.

## Fonctionnalités

### 🎯 Suggérer un critère (IA)

Le designer décrit un constat (et, s'il le souhaite, sa recommandation et sa gravité) ; l'IA propose une recommandation et une gravité, évalue celles du designer, et propose le critère principal du référentiel avec un niveau de confiance, la justification (règle de départage et question de checklist citées), les critères secondaires, les critères envisagés puis écartés, et ce qu'il faudrait préciser si le constat est trop vague. Si le designer indique le critère qu'il envisage, l'IA le confirme ou le remet en question. Le résultat se copie directement dans le template.

```bash
python3 -m audit_ergo --suggerer "Après un clic sur Payer, rien ne se passe pendant 5 s" --ecran Paiement
python3 -m audit_ergo --suggerer "..." --critere GUI-01    # faire vérifier un choix
```

**Les réponses sont mémorisées** dans `.cache/suggestions.sqlite` (ignoré par Git) : un constat déjà analysé, avec le même écran, le même critère envisagé et le même contexte, est repris sans nouvel appel ni coût (badge « Repris du cache »). Toute modification du référentiel, des consignes ou du modèle invalide automatiquement les anciennes réponses. Les erreurs ne sont jamais mémorisées. Pour forcer une nouvelle analyse : case à cocher dans l'interface ou `--sans-cache` ; pour tout effacer : bouton « Vider le cache de l'IA » ou `--vider-cache`. `AUDIT_ERGO_CACHE` permet de changer l'emplacement du cache (ou de le désactiver avec `0`).

Seuls les codes du référentiel sont acceptés : toute réponse citant un code inconnu est rejetée. Le référentiel complet (~9 000 tokens) est envoyé à chaque appel. Au format `anthropic`, il est **mis en cache** et n'est facturé plein tarif qu'au premier appel de chaque série ; au format `openai`, cela dépend de la passerelle.

### 🔍 Relire, compléter et corriger un audit

Le designer peut déposer un audit **partiellement rempli** : les constats suffisent. Avec l'IA (bouton « Compléter et corriger avec l'IA », ou `--ia`) :

- **les cellules vides sont remplies** : type, catégorie, critère principal, critères secondaires, règle de départage, gravité et recommandation. Elles apparaissent **en violet**, avec l'explication en commentaire, et sont à valider par le designer ;
- **ce que le designer a déjà saisi n'est jamais écrasé** : l'IA donne son avis à côté, dans les colonnes « IA : critère suggéré / verdict critère / recommandation / avis recommandation / gravité / justification ». Une recommandation vague reçoit une version améliorée qui garde son intention ; un écart de gravité de 2 niveaux ou plus est signalé ;
- un simple tableau avec une colonne « Constat » suffit : les colonnes manquantes sont ajoutées.

```bash
python3 -m audit_ergo mon_audit.xlsx                       # contrôles de forme -> mon_audit_relu.xlsx
python3 -m audit_ergo mon_audit.xlsx --ia                  # + complétion et correction par l'IA
python3 -m audit_ergo mon_audit.xlsx --ia --sans-remplissage   # avis de l'IA seulement, rien n'est rempli
python3 -m audit_ergo mon_audit.xlsx -o relu.xlsx --json
```

`exemples/audit_a_completer.xlsx` (fictif) contient 8 constats, dont 6 sans critère ni recommandation, un critère discutable et une recommandation vague.

L'outil lit le template, mais aussi un fichier libre : il cherche l'onglet et la ligne d'en-tête, reconnaît les colonnes même déplacées ou renommées (« Préconisation » = Recommandation), et accepte un critère saisi par son code, son nom français ou anglais.

Il renvoie le fichier d'origine **annoté** : cellules fautives surlignées et commentées, colonnes « Relecture » ajoutées (et « IA : critère suggéré / verdict / justification » avec `--ia`), et deux onglets « Relecture – Synthèse » (indicateurs, gravités, couverture des 24 critères) et « Relecture – Anomalies ». Les formules et listes déroulantes du designer sont conservées.

Les contrôles de forme (`audit_ergo/controles.py`) sont classés en trois niveaux :
- **Bloquant** : champ obligatoire vide, critère ou catégorie inconnus, critère hors de sa catégorie, gravité hors échelle.
- **Avertissement** : constat ou recommandation trop courts, recommandation qui recopie le constat, priorité ou impact incohérents avec la gravité, règle de départage qui ne mène pas au critère choisi, critère secondaire inconnu, doublon, contexte incomplet, référentiel périmé.
- **Info** : formulations vagues (« confus », « revoir l'ergonomie »…), gravité 0 pour un problème, critère secondaire identique au principal.

`exemples/audit_fictif.xlsx` est un audit **fictif** contenant des erreurs volontaires (régénérable avec `python3 scripts/generer_audit_fictif.py`).

## Tests

```bash
pip install -r requirements-dev.txt
python3 -m pytest -q
```

Les tests de l'IA utilisent de faux clients et une fausse passerelle locale : ils ne nécessitent pas de clé et ne consomment rien.

## Contenu

| Chemin | Rôle |
|---|---|
| `audit_ergo/` | Moteur de relecture : lecture du fichier, contrôles, synthèse, export annoté |
| `app.py`, `interface/` | Interface web (Streamlit) : pages « Suggérer un critère » et « Relire un audit » |
| `audit_ergo/cache.py` | Cache local des réponses de l'IA |
| `audit_ergo/completion.py` | Complétion des cellules vides d'un audit à partir des propositions de l'IA |
| `audit_ergo/suggestion.py` | Suggestion de critères par l'IA (prompt, schéma de réponse, appel API aux formats OpenAI et Anthropic) |
| `start.bat` | Installation et lancement en un double-clic sous Windows |
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
