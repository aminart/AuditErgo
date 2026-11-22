# Historique des versions d'AuditErgo

Format : chaque version liste ses changements par type (Ajouté, Modifié, Corrigé). Les numéros suivent
le [versionnage sémantique](https://semver.org/lang/fr/) : voir README, « Versions ».

## [Non publié]

## [1.4.1] — 2026-11-21

### Modifié

- Design system Night Navy 1.2.1 : les cases à cocher (Historique, Suggestion, Relecture) prennent le style
  commun aux apps de la suite — contour gris foncé, coché en bleu marine, focus visible, clair et sombre. La case
  « remplir » de la relecture par l'IA reste violette, la couleur de l'IA.

## [1.4.0] — 2026-11-19

### Ajouté

- **Nouvelle version du fichier** : un audit corrigé dans Excel se recharge dans le même audit, au lieu d'être
  déposé comme un nouveau document. L'analyse par l'IA se relance seule, et seuls les constats modifiés repartent
  vers le modèle, y compris quand on recharge le fichier complété téléchargé depuis l'application.
- **Prendre l'avis de l'IA** en un clic quand elle propose un autre critère, une autre recommandation ou une autre
  gravité que le designer ; « Revenir à votre saisie » rétablit la valeur d'origine.
- Relecture : filtre « Bloquants », tri par urgence, bandeau d'état et chiffres clés cliquables.
- Temps restant estimé pendant l'analyse par l'IA ; titre de l'onglet et notification quand elle se termine.
- Lien vers le template vierge sur l'écran de dépôt.
- Rapport : sommaire qui reste visible pendant la lecture, avec la partie en cours.
- Tests de l'interface sur l'écran Relecture (décisions affichées sans attente, suivi de l'analyse repris),
  lancés par la CI avec ceux du serveur.

### Modifié

- Les décisions (Valider, Modifier, Refuser) s'affichent tout de suite, sans bloquer les autres boutons.
- La gravité s'affiche partout sous la forme « 3 · Élevée ».
- Le nombre de critères à revoir et de recommandations à améliorer ne compte plus les avis déjà adoptés.

### Corrigé

- Les liens du sommaire du rapport ne renvoient plus vers l'écran Relecture.
- Recharger la page pendant une analyse par l'IA ne bloque plus l'application jusqu'à la fin de l'analyse : l'audit
  s'ouvre tout de suite.
- Changer d'écran pendant l'analyse par l'IA ou la rédaction du rapport ne fait plus perdre la progression : elle
  réapparaît au retour, même après un rechargement. Une seule tâche à la fois par audit : relancer l'analyse rejoint
  celle en cours, et les décisions ou le rapport attendent sa fin.
- Le dépôt d'un audit ne bloque plus le reste de l'application pendant sa lecture.
- Modifier ou refuser une gravité proposée met tout de suite à jour le niveau affiché (« 3 · Élevée »), au lieu
  de montrer l'ancien jusqu'à la réponse du serveur.

### Sécurité

- Les requêtes qui modifient quelque chose (dépôt, réglages, certificat, suppression…) sont refusées si elles
  viennent d'une autre page web que l'application.

## [1.3.0] — 2026-11-17

### Ajouté

- Modèles d'IA de Studio Dock : quand Studio Dock fournit la connexion (Réglages › Modèles d'IA, commune à toutes
  les apps de la suite, y compris un modèle local d'Ollama), AuditErgo l'utilise avec le modèle choisi pour lui.
  L'écran Réglages l'affiche en lecture seule ; les paramètres propres à AuditErgo sont gardés et reprennent la
  main si Studio Dock lui laisse sa configuration propre. Un fichier .env reste prioritaire.
- Choix du modèle parmi ceux de Studio Dock : champ « Modèle d'IA » au lancement de la relecture par l'IA, de la
  suggestion et du rapport de synthèse, valable pour la session ; modèle par défaut dans Réglages.

## [1.2.0] — 2026-11-08

### Ajouté

- Nouvelle icône AuditErgo, commune avec Studio Dock : icône de l'exe, logo de l'en-tête et icône de l'onglet (dossier `icone/`).
- Chaque release contient aussi un zip `AuditErgo-X.Y.Z-windows.zip` (exe, journal, `.env.exemple`), qui passe les
  filtres bloquant le téléchargement d'un `.exe`.
- `scripts/release.sh` : publier une release depuis un PC Windows (tests, exe, tag, release GitHub avec l'exe et le
  zip), sans consommer de minutes GitHub Actions. Voir README, « Release locale ».

### Modifié

- En-tête commun à la suite (design system Night Navy 1.1.0) : la barre latérale devient une barre d'onglets en
  haut ; badge « LLM connecté », langue, thème et réglages (roue crantée) à droite. Le contenu prend toute la largeur.
- Titres de page au format commun (32 px, alignés à gauche).

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
