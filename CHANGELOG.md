# Historique des versions d'AuditErgo

Format : chaque version liste ses changements par type (Ajouté, Modifié, Corrigé). Les numéros suivent
le [versionnage sémantique](https://semver.org/lang/fr/) : voir README, « Versions ».

## [Non publié]

### Ajouté

- Nouvelle icône AuditErgo, commune avec Studio Dock : icône de l'exe, logo de l'en-tête et icône de l'onglet (dossier `icone/`).

## [1.1.0] — 2026-11-05

### Modifié

- Nouveau nom : **AuditErgo** (titre de l'interface, fenêtre, `/health`, propriétés de l'exe).

### Ajouté

- Exécutable Windows `AuditErgo.exe`, sans Python à installer : fabriqué par GitHub à chaque push et joint à
  chaque release. Depuis l'exe, l'historique et le cache sont dans `%APPDATA%\AuditErgo`, le `.env`
  facultatif à côté de l'exe.
- Versionnement : fichier `VERSION` unique, ce journal, `scripts/bump_version.py`.
- Écran Réglages : connexion au modèle comme dans SpecGen (URL, clé chiffrée, certificat `.crt` importé,
  modèle, délai, test avec diagnostic). Le `.env` reste prioritaire champ par champ.

### Modifié

- `start.bat` n'ouvre plus le Bloc-notes au premier lancement : la connexion se règle dans l'application.

## [1.0.0] — version de référence

État de l'application avant le versionnement : relecture et complétion d'audits heuristiques, suggestion
de critère, rapport de synthèse Word, historique et comparaison, interface FR / EN en clair et sombre
(design system Night Navy), contrat du portail (port 8501, `/health`).
