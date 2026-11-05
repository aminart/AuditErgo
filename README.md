# Audit ergonomique assisté

Aide les UX designers à produire des audits ergonomiques (heuristiques) du même standard : contrôle de forme, proposition du critère, de la recommandation et de la gravité de chaque constat, complétion des cellules vides et correction des saisies, en français ou en anglais.

L'IA est un modèle Mistral servi au format OpenAI (`/v1/chat/completions`) : installé sur le poste (Ollama, LM Studio), auquel cas aucune donnée ne quitte le poste, ou passerelle de l'organisation. La connexion se règle avec `API_BASE`, `API_KEY` et `CA_BUNDLE`. Voir `CONCEPTION.md` § 2.

Le fonctionnement détaillé, écran par écran, est décrit dans [`FONCTIONNEMENT.md`](FONCTIONNEMENT.md).

## Installation

### 1. Le modèle local (une fois)

1. Installer [Ollama](https://ollama.com/download).
2. Installer le modèle : `ollama pull mistral-small` (ou `mistral-nemo` sur un poste moins puissant).
3. **Agrandir la fenêtre de contexte** : définir la variable d'environnement `OLLAMA_CONTEXT_LENGTH=16384`, puis redémarrer Ollama. Sans cela, Ollama tronque le référentiel envoyé au modèle (l'application le détecte et l'indique).

LM Studio convient aussi : renseigner alors `API_BASE=http://localhost:1234/v1` dans `.env` et régler la « Context Length » du modèle à 16384.

### 2. L'application

**Windows** : double-cliquer sur `start.bat`. Prérequis : [Python 3.10+](https://www.python.org/downloads/), installé en cochant « Add python.exe to PATH ». Au premier lancement, `start.bat` crée le fichier `.env` (à vérifier dans le Bloc-notes), installe les dépendances dans un environnement isolé (`.venv`), vérifie que le modèle local répond, puis ouvre l'application sur http://localhost:8501 (accessible depuis ce poste seulement).

**Autres systèmes** :
```bash
pip install -r requirements.txt
cp .env.exemple .env      # à adapter si besoin
python -m serveur        # ouvre http://localhost:8501
```

### 3. Configuration (`.env`)

La connexion au modèle se règle avec **trois paramètres** :

| Variable | Défaut | Rôle |
|---|---|---|
| `API_BASE` | `http://localhost:11434/v1` | Adresse du serveur du modèle : Ollama ou LM Studio sur le poste, ou passerelle compatible OpenAI. |
| `API_KEY` | — | Clé d'API exigée par le serveur ; laisser vide s'il n'en demande pas (Ollama). |
| `CA_BUNDLE` | — | Fichier de certificats (PEM) de l'autorité qui a signé le certificat HTTPS du serveur (inutile en `http://`). Sert aussi à installer les dépendances derrière un proxy d'entreprise. |

S'y ajoutent `AUDIT_ERGO_MODELE` (nom du modèle sur ce serveur, défaut `mistral-small`) et `AUDIT_ERGO_LANGUE` (`fr` ou `en`). La barre latérale de l'application affiche la configuration utilisée et propose un bouton « Tester la connexion ».

Autres réglages (température, délai, cache, désactivation de l'IA…) : voir `.env.exemple`.

## Templates

| Fichier | Langue |
|---|---|
| `template/Audit_ergonomique_FR.xlsx` | Français |
| `template/Ergonomic_audit_EN.xlsx` | Anglais |

Version 2, issue du template d'origine (`referentiel/source/Heuristic_Evaluation_template.xlsx`) : mêmes colonnes de suivi (cas d'usage, tâche, type de recommandation, statut maquette, statut), même échelle de gravité à 4 niveaux (Faible / Moyenne / Élevée / Critique — Low / Medium / High / Critical), défauts corrigés, colonnes du standard commun ajoutées, onglet « Résultats » qui compte les 24 critères. Détail dans `CONCEPTION.md` § 5. Les audits remplis avec le template d'origine restent acceptés.

## Fonctionnalités

### 🎯 Suggérer un critère

Le designer décrit un constat (et s'il le souhaite le critère, la recommandation et la gravité qu'il envisage). L'IA propose le critère principal avec un niveau de confiance et sa justification (règle de départage et question de checklist citées), les critères secondaires et écartés, une recommandation et son type, une gravité, évalue les choix du designer, et signale ce qu'il faudrait préciser.

```bash
python3 -m audit_ergo --suggerer "Après un clic sur Payer, rien ne se passe pendant 5 s" --ecran Paiement
python3 -m audit_ergo --suggerer "..." --critere GUI-01 --langue en
```

### 🔍 Relire, compléter et corriger un audit

Fichier accepté : template v2, template d'origine, ou simple tableau avec une colonne « Constat ».

- **Contrôles de forme**, sans IA : bloquant (champ obligatoire vide, critère inconnu ou hors de sa catégorie, gravité hors échelle), avertissement (constat ou recommandation trop courts, recommandation qui recopie le constat, règle de départage incohérente, doublon…), info (formulations vagues).
- **Complétion et correction par l'IA**, à la demande : les cellules vides sont remplies **en violet**, avec l'explication en commentaire ; les saisies du designer ne sont **jamais écrasées** : l'avis de l'IA est donné à côté, dans les colonnes « IA : … ».
- **Relecture des propositions** dans l'application : chaque cellule remplie par l'IA se **valide**, se **corrige** ou se **refuse** (la cellule redevient vide). Une proposition validée ou corrigée n'est plus en violet dans le fichier exporté.
- **Fichier annoté** : le fichier d'origine (formules et listes conservées), plus deux onglets de synthèse et d'anomalies.

```bash
python3 -m audit_ergo mon_audit.xlsx                          # contrôles de forme -> mon_audit_relu.xlsx
python3 -m audit_ergo mon_audit.xlsx --ia                     # + complétion et correction par l'IA locale
python3 -m audit_ergo mon_audit.xlsx --ia --sans-remplissage  # avis de l'IA seulement
python3 -m audit_ergo mon_audit.xlsx --langue en              # annotations et textes de l'IA en anglais
```

Les réponses de l'IA sont **mémorisées** dans `.cache/suggestions.sqlite` (local, ignoré par Git) : un constat déjà analysé n'est pas recalculé. `--sans-cache` force une nouvelle analyse, `--vider-cache` efface tout (aussi possible depuis l'interface).

### 📄 Rapport de synthèse (HTML et Word)

Depuis la page « Rapport de synthèse », ou en ligne de commande, l'application produit un rapport à remettre à l'équipe produit. Il s'affiche **directement dans l'application**, en HTML (graphiques de gravité et de thématiques, échelle de maturité), s'imprime ou s'enregistre en PDF depuis le navigateur, se télécharge en page HTML autonome, ou en Word :

1. **Synthèse générale** : l'essentiel, niveau de maturité UX, chiffres clés, points forts, faiblesses, problèmes récurrents, impact sur les utilisateurs ;
2. **Problèmes UX principaux**, regroupés par thématique (problèmes observés, pourquoi l'expérience est dégradée, conséquences), tendances récurrentes et cas isolés ;
3. **Recommandations UX et UI** : grands chantiers transverses, hiérarchisés par impact attendu (objectif, importance, bénéfices, problèmes résolus) ;
4. **Prochaines étapes** : quick wins, chantiers à moyen et long terme, démarche d'amélioration continue ;
5. Annexes : méthode, échelles, liste des problèmes.

Le bouton « Modifier le rapport » permet de corriger ou compléter chaque passage rédigé (et le niveau de maturité) directement dans la page : les modifications sont enregistrées et reprises dans les exports PDF, HTML et Word.

Les chiffres (gravités, écrans, récurrence, maturité indicative) sont calculés sans IA ; l'IA rédige les analyses. Sans IA, le rapport contient tous les faits et les passages à rédiger sont surlignés.

```bash
python3 -m audit_ergo mon_audit.xlsx --ia --rapport   # complète l'audit, puis rédige mon_audit_rapport.docx
python3 -m audit_ergo mon_audit_complete.xlsx --rapport   # rapport à partir d'un audit déjà complété
```

Exemples fictifs : `exemples/audit_fictif.xlsx` (erreurs de forme volontaires) et `exemples/audit_a_completer.xlsx` (constats seuls à compléter), régénérables avec `python3 scripts/generer_audit_fictif.py`.

### 🕘 Historique et comparaison

Chaque audit déposé est enregistré sur le poste (`.donnees/audits/`, jamais envoyé ailleurs) avec sa relecture, les avis de l'IA, les décisions du designer et le rapport : il se rouvre après la fermeture de l'application. La page « Historique » liste les audits, permet d'en supprimer, et d'en **comparer deux** (deux versions d'un même produit, par exemple) : problèmes, gravités, écrans et catégories de critères, avec les écarts. `AUDIT_ERGO_HISTORIQUE=0` désactive l'enregistrement ; `AUDIT_ERGO_HISTORIQUE=<dossier>` change son emplacement.

## Lancement par le portail

L'application respecte le contrat commun aux applications de la suite :

| | |
|---|---|
| Port par défaut | **8501** |
| Options | `--port N` (port imposé : échec explicite, code 2, s'il est pris par une autre application), `--no-browser` (ancien nom `--sans-navigateur`, toujours accepté), `--version` |
| État | `GET /health` → `{"status": "ok", "app": "audit-ergo", "name": "Audit ergonomique", "version": "…"}` |

Exemple : `python -m serveur --port 8501 --no-browser`. La version se règle dans `serveur/__init__.py`.

## Interface : développement

L'interface est livrée compilée (`web/dist/`) : les postes n'ont besoin que de Python. Pour la modifier, avec [Node.js](https://nodejs.org) 20 ou plus récent :

```bash
python -m serveur --no-browser       # API sur http://localhost:8501
cd web && npm install && npm run dev  # interface sur http://localhost:5173, rechargée à chaque modification
npm run build                         # recompile web/dist/, à committer avec les sources
```

Couleurs, police et arrondis viennent du design system commun **Night Navy** (paquet `night-navy`, dépôt [aminart/Design-system-](https://github.com/aminart/Design-system-)), partagé avec SpecGen et Analyse documentaire. Il est branché en tête de `web/src/index.css` et figé sur une version dans `web/package.json` : mettre à jour ce numéro pour suivre une nouvelle version. Utiliser les classes du design system (`bg-surface`, `text-ink-muted`, `bg-primary`, `border-line`…) ou les noms de l'app (`fond`, `texte`, `bord`, `marque`…), qui pointent vers les mêmes jetons, jamais une couleur écrite en dur. Seules les couleurs métier (échelle de gravité, graphiques) restent dans l'app. Une couleur manque ? L'ajouter dans le design system, pas ici.

## Tests

```bash
pip install -r requirements-dev.txt
python3 -m pytest -q
```

Les tests utilisent un faux serveur local : ils ne nécessitent ni modèle ni réseau.

## Contenu

| Chemin | Rôle |
|---|---|
| `FONCTIONNEMENT.md` | Fonctionnement de l'application, écran par écran, du point de vue de l'utilisateur |
| `CONCEPTION.md` | Document de conception : confidentialité, modèle local, référentiel, template v2, feuille de route |
| `serveur/` | Serveur de l'application (FastAPI) : API au-dessus du moteur, sert l'interface compilée, sur ce poste uniquement |
| `web/` | Interface (React, TypeScript, Tailwind) ; `web/dist/` est la version compilée, livrée avec l'application |
| `audit_ergo/` | Moteur : lecture, contrôles, IA, complétion, export, rapport Word, cache, textes bilingues |
| `template/` | Templates v2 en français et en anglais (générés par `scripts/build_template.py`) |
| `referentiel/source/` | Fichiers d'origine (CSV et template Excel), jamais modifiés |
| `referentiel/corrections.json`, `regles_departage.json` | Corrections proposées et règles de départage (FR/EN) |
| `referentiel/referentiel.json`, `CHANGEMENTS.md` | Référentiel final et liste des modifications à valider, **générés** par `scripts/build_referentiel.py` |
| `start.bat` | Installation et lancement en un double-clic sous Windows |
| `tests/` | Tests automatiques |
