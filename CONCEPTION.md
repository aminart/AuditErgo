# Audit ergonomique assisté : document de conception

> **Objectif** : aider les UX designers à produire des audits ergonomiques **du même standard**, quel que soit l'auteur. L'application relit l'audit (même partiellement rempli), vérifie sa forme, propose le critère, la recommandation et la gravité de chaque constat, corrige ce que le designer a saisi sans jamais l'écraser, et complète les cellules vides.
>
> **Confidentialité** : l'IA est un modèle **Mistral** joint par l'adresse, la clé et le certificat réglés dans l'écran Réglages (ou `API_BASE`, `API_KEY` et `CA_BUNDLE` dans `.env`). Installé sur le poste, aucune donnée ne quitte le poste du designer ; sur une passerelle, les constats ne vont qu'à ce serveur, choisi par l'organisation.

*Version 2 du document. Elle remplace la première version, qui prévoyait une IA en ligne.*

---

## 1. Principes

1. **Assister, pas remplacer** : l'application *propose*, le designer *décide*. Les cellules qu'elle remplit sont signalées (en violet, « à valider ») ; celles du designer ne sont jamais modifiées.
2. **Un référentiel unique et versionné** : toutes les propositions s'appuient sur le même référentiel (24 critères, checklists, 9 règles de départage), pas sur la « culture générale » du modèle. C'est ce qui garantit le standard commun.
3. **Confidentialité par construction** : traitement 100 % local, et des garde-fous dans le code plutôt que des consignes (§ 2).
4. **Règles d'abord, IA ensuite** : tout ce qui se vérifie par une règle (champ vide, critère inconnu, gravité hors échelle…) est fait sans IA, instantanément et sans erreur possible. L'IA sert au jugement.
5. **Expliquer** : chaque proposition cite la règle de départage et la question de checklist qui la justifient. Le designer apprend en corrigeant.
6. **Mesurer** : indicateurs par audit, puis jeu de référence pour mesurer la fiabilité de l'IA (§ 10).

---

## 2. Confidentialité : aucune sortie du poste

### 2.1 Architecture

```
 Poste du designer (rien ne sort de ce cadre)
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │  Navigateur ──▶ Application (FastAPI + React, http://localhost:8501)         │
 │                     │                                                        │
 │                     ├── Lecture / contrôles / export Excel (Python, local)   │
 │                     ├── Cache des réponses (.cache/suggestions.sqlite)       │
 │                     └──▶ Modèle Mistral local (Ollama, http://localhost:11434)│
 │  Fichiers d'audit : lus et écrits sur le disque du poste uniquement          │
 └──────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Garde-fous intégrés à l'application

| Risque | Garde-fou (dans le code) |
|---|---|
| Les constats partent vers un serveur | Les constats ne vont qu'à l'adresse choisie dans l'écran Réglages (ou `API_BASE` dans `.env`), qui indique si elle est sur le poste. Si elle est sur le poste (`localhost`, `127.0.0.1`, `::1`), rien ne sort du poste ; sinon (passerelle de l'organisation), l'interface indique le serveur qui reçoit les constats. Le choix et la validation de ce serveur relèvent de l'organisation. |
| Un proxy d'entreprise intercepte les requêtes | Vers un modèle sur le poste, les appels **ignorent les variables de proxy** : la connexion reste directe (testé). Vers une passerelle, les réglages réseau du poste s'appliquent (proxy, `NO_PROXY`). |
| Un collègue ouvre l'application via le réseau | Le serveur n'écoute que sur `127.0.0.1` (`serveur/__main__.py`). |
| Une page web malveillante joint l'application (« DNS rebinding ») | Le serveur refuse toute requête adressée à un autre nom que `localhost` ou `127.0.0.1` (testé). |
| Statistiques d'usage, ressources externes | Aucune télémétrie ; l'interface est compilée et servie par l'application, sans police, script ni service tiers : elle fonctionne hors ligne. |
| Audits conservés | Les audits déposés (fichier, relecture, avis de l'IA, décisions, rapport) sont enregistrés **sur ce poste uniquement**, dans `.donnees/audits/` (ignoré par Git) ; chacun se supprime depuis la page « Historique ». `AUDIT_ERGO_HISTORIQUE=0` désactive l'enregistrement (dossier temporaire effacé à l'arrêt). |
| Clé d'API qui fuite | La clé, si le serveur en exige une, est chiffrée avec le compte Windows (DPAPI) dans le dossier de l'utilisateur, ou reste dans le fichier `.env`, ignoré par Git ; l'interface n'affiche jamais sa valeur. |
| Données conservées ailleurs | Le cache des réponses est un fichier SQLite local, ignoré par Git ; il peut être vidé depuis l'interface. |

### 2.3 Ce qui demande Internet, une seule fois

- **L'installation** : Python, les dépendances (`pip`), Ollama et le modèle Mistral. `start.bat` utilise `CA_BUNDLE` pour passer le proxy d'entreprise. Si les postes n'ont pas accès à Internet, l'équipe informatique peut préparer un paquet d'installation hors ligne (dépendances téléchargées à l'avance, modèle copié).
- **Ensuite, plus rien** : l'application et le modèle fonctionnent hors ligne.

### 2.4 Points de vigilance (hors de l'application)

- **Mises à jour automatiques** d'Ollama ou de LM Studio : à désactiver ou à faire valider par l'équipe informatique, selon la politique de l'organisation.
- **Stockage des audits** : l'application ne chiffre pas les fichiers ; ils suivent les règles de stockage du poste (disque chiffré, dossiers de projet…).
- **Captures d'écran** : non transmises à l'IA à ce stade.

---

## 3. Le modèle IA local (Mistral)

### 3.1 Serveur local

L'application dialogue avec tout serveur local **compatible OpenAI** (`/v1/chat/completions`) :

| Outil | Adresse par défaut | Remarque |
|---|---|---|
| **Ollama** (recommandé) | `http://localhost:11434/v1` | Valeur par défaut de l'application. Installation du modèle : `ollama pull mistral-small`. |
| LM Studio | `http://localhost:1234/v1` | Interface graphique ; renseigner l'URL dans l'écran Réglages. |

### 3.2 Choix du modèle

| Modèle (famille Mistral) | Mémoire indicative (quantification 4 bits) | Pour cet usage |
|---|---|---|
| **Mistral Small** (24 B) | environ 15 Go | **Recommandé** : bonne compréhension du français, respect du format de réponse. Idéalement avec une carte graphique. |
| Mistral Nemo (12 B) | environ 8 Go | Compromis possible sur un poste sans carte graphique puissante. |
| Mistral 7B / Ministral | environ 5 Go | Déconseillé : le prompt est long et les règles fines ; risque élevé de critères mal choisis. |

Ces chiffres sont des ordres de grandeur, à vérifier sur les postes réels. Le bouton « Tester la connexion » (barre latérale) et `start.bat` vérifient que le modèle configuré est bien installé.

### 3.3 Réglages importants

- **Fenêtre de contexte : 16 384 tokens au moins.** Le prompt (consignes + référentiel complet + schéma de réponse) fait environ 9 000 à 10 000 tokens. Ollama tronque **sans prévenir** ce qui dépasse sa fenêtre (souvent 4 096 par défaut) : le modèle répondrait alors sans avoir lu le référentiel. Réglage : variable d'environnement `OLLAMA_CONTEXT_LENGTH=16384` puis redémarrage d'Ollama (LM Studio : « Context Length »). **L'application détecte cette troncature** et affiche la marche à suivre.
- **Température basse (0,2)** : un même constat doit donner la même réponse d'un designer à l'autre.
- **Une requête à la fois** : un modèle local traite les constats l'un après l'autre ; en lancer plusieurs ne fait que les ralentir.
- **Délai d'attente long (10 minutes)** : sur un poste sans carte graphique, une réponse peut prendre plus d'une minute.
- **Réponse au format JSON contraint** (`response_format` avec schéma) : les codes de critères, les règles et la gravité sont limités aux valeurs du référentiel. Si le serveur ne gère pas ce format, l'application réessaie sans, puis **revalide entièrement** la réponse (code inconnu = réponse rejetée).
- **Début de prompt identique d'un appel à l'autre** : Ollama réutilise alors ce début déjà calculé, ce qui accélère nettement les constats suivants.
- **Cache local** : un constat déjà analysé (même texte, même écran, mêmes choix, même langue, même référentiel) n'est pas recalculé.

### 3.4 Ce que cela change par rapport à une IA en ligne

Un modèle local de 12 à 24 milliards de paramètres est moins performant qu'un grand modèle en ligne : la **fiabilité des propositions doit être mesurée** sur de vrais constats avant un usage généralisé (§ 10). Les contrôles de forme, eux, ne dépendent pas de l'IA.

---

## 4. Le référentiel

- **Sources** : les deux CSV d'origine (grille des 9 catégories / 24 critères avec checklists ; 125 heuristiques de 7 frameworks), jamais modifiés.
- **Codes stables** : `GUI-01` à `VIS-02`, conservés dans le template v2 et ses listes déroulantes.
- **Corrections proposées** (`referentiel/corrections.json`, détail dans `referentiel/CHANGEMENTS.md`, **à valider par les designers seniors**) : checklists de *Concision* et *Actions minimales* distinguées (elles étaient identiques), 37 questions ajoutées aux critères qui n'en avaient pas, 17 doublons déplacés, définitions erronées corrigées (CARMEL « Confirmation dialogs », « steep learning curve »).
- **9 règles de départage** (R1 à R9), en français et en anglais : la question à se poser pour choisir entre deux critères proches (ex. R1 : le problème est-il *avant* l'action — Incitation — ou *après* — Feedback ?).
- **Compatibilité** : les noms de critères du template d'origine sont reconnus tels quels, coquilles comprises (« Leagibility/Readability »).

---

## 5. Le template Excel v2

### 5.1 Analyse du template d'origine (`Heuristic_Evaluation_template.xlsx`)

Ce qui est **repris** : la logique de grille (cas d'usage, tâche, critère, sous-critère, description, capture, emplacement, gravité, type de recommandation, recommandation, statut de maquette, statut), l'**échelle de gravité à 4 niveaux** (Low, Medium, High, Critical) avec ses définitions, l'onglet de résultats, l'onglet des frameworks.

Défauts **corrigés** :

| Défaut constaté dans le template d'origine | Correction dans la v2 |
|---|---|
| L'onglet « Results » ne compte que 22 sous-critères sur 24 (les deux critères « Visual design » sont absents) | Les 24 critères sont comptés, par gravité, avec les points forts à part et un total par catégorie |
| « Results » mélange des plages différentes (`F7:F1048576` d'un côté, `$F$7:$F$472` de l'autre) | Une seule plage cohérente |
| Les sous-critères des listes contiennent un retour à la ligne final (« Prompting⏎ ») : les comptages dépendent de ce caractère invisible | Listes propres, préfixées par le code (« GUI-01 – … ») ; comptage par code |
| La liste déroulante des sous-critères ne va que jusqu'à la ligne 38, et la ligne 12 pointe vers une catégorie fixe (`$E$12`) | Listes sur 300 lignes, toutes dépendantes de la catégorie de leur ligne |
| Une liste de gravité est posée sur la cellule d'en-tête (`J6`) | Supprimé |
| Coquilles et noms incohérents (« Leagibility », « Significances_of_Codes », « Mock up solution status␣ ») | Noms corrigés ; les anciens restent reconnus à la lecture |
| Pas d'identifiant de constat, pas de type (problème / point fort), pas de justification du critère | Colonnes ID (automatique), Type, Critères secondaires, Règle de départage, Justification du critère |
| Rien ne signale une ligne incomplète | Colonne « Contrôle » (formule) : champ manquant, sous-critère hors de sa catégorie, gravité ou recommandation manquante, constat trop court |
| Zone d'impression (`Print_Area`) invalide | Mise en page paysage, ajustée à la largeur, en-tête répété |

À la lecture, les audits déjà remplis avec le template d'origine restent **acceptés tels quels** (colonnes, noms de critères, cellules fusionnées d'un même cas d'usage). Seule limite : en réécrivant un fichier au format d'origine, la liste déroulante « Mock up solution status » et deux mises en forme conditionnelles (format Excel non géré par la bibliothèque) sont perdues ; le template v2 n'a pas ce problème.

### 5.2 Structure de la v2

Deux fichiers générés par `scripts/build_template.py` : `template/Audit_ergonomique_FR.xlsx` et `template/Ergonomic_audit_EN.xlsx`.

| Onglet | Contenu |
|---|---|
| Mode d'emploi / How to use | Étapes, code couleur, bonnes pratiques de rédaction |
| Contexte / Context | Produit, cible, plateforme, parcours, designer, date de l'audit, langue, versions |
| Audit | Une ligne par constat (colonnes ci-dessous), 300 lignes prêtes, une ligne d'exemple |
| Résultats / Results | Comptage automatique par critère × gravité, points forts, total par catégorie |
| Critères / Criteria | Définition et checklist de chaque critère (questions proposées signalées) |
| Règles de départage / Tie-break rules | R1 à R9 avec exemples |
| Gravité / Severity | Les 4 niveaux et leurs définitions |

Colonnes de l'onglet Audit : ID · Parcours / cas d'usage · Tâche · **Écran / emplacement** · Capture · Type · **Constat** · **Catégorie** · **Critère principal** · Critères secondaires · Règle de départage · Justification du critère · **Gravité** (si problème) · Type de recommandation · **Recommandation** (si problème) · Statut maquette · Statut · Contrôle. En gras : obligatoire. La date par ligne du template d'origine est remplacée par la date de l'audit, dans l'onglet Contexte (une date par ligne reste lue si elle existe).

---

## 6. Fonctionnalités

### 6.1 Suggérer un critère
Le designer décrit un constat (et, s'il le souhaite, le critère, la recommandation et la gravité qu'il envisage). Le modèle local renvoie : critère principal et niveau de confiance, justification (règle de départage et question de checklist citées), critères secondaires, critères écartés et pourquoi, recommandation et type de recommandation, avis sur la recommandation du designer avec une version améliorée, gravité et sa justification, et ce qu'il faudrait préciser si le constat est trop vague. Le résultat se copie dans le template.

### 6.2 Relire, compléter et corriger un audit
Le designer dépose son fichier (template v2, template d'origine ou simple tableau avec une colonne « Constat ») :

1. **Contrôles de forme** (sans IA), en trois niveaux : bloquant, avertissement, info.
2. **Complétion et correction par l'IA** (à la demande) : les cellules vides sont remplies (en violet, avec l'explication en commentaire) ; les saisies du designer ne sont jamais modifiées, l'avis de l'IA est donné dans des colonnes « IA : … » à côté.
3. **Fichier annoté** : le fichier d'origine, avec ses formules et listes déroulantes, plus les colonnes de relecture et deux onglets « Synthèse » et « Anomalies ».

Les valeurs écrites dans les cellules suivent la **langue du fichier** (pour rester cohérentes avec ses listes) ; les commentaires et annotations suivent la langue choisie dans l'application.

### 6.3 Rapport de synthèse (HTML et Word)
À partir de l'audit relu (et de préférence complété par l'IA), l'application produit un rapport destiné à l'équipe produit et à ses décideurs. Il s'affiche dans l'application en HTML (avec graphiques), s'imprime en PDF, s'exporte en page HTML autonome ou en Word ; le contenu est le même :

| Partie | Contenu |
|---|---|
| 1. Synthèse générale | L'essentiel en quelques phrases, niveau de maturité UX (échelle à 5 niveaux), chiffres clés, problèmes par gravité, principaux points forts, principales faiblesses, problèmes récurrents, impact sur les utilisateurs et leurs activités |
| 2. Problèmes UX principaux | Problèmes regroupés par grandes thématiques, de la plus pénalisante à la moins pénalisante : problèmes observés, pourquoi l'expérience est dégradée, conséquences, constats représentatifs ; puis tendances récurrentes et cas isolés. Aucune solution dans cette partie. |
| 3. Recommandations UX et UI | 3 à 6 grands chantiers transverses (pas de corrections écran par écran), hiérarchisés par impact attendu : objectif, importance, bénéfices attendus, problèmes résolus, thématiques traitées, effort |
| 4. Prochaines étapes | Quick wins (faible effort, valeur immédiate, constats concernés), chantiers à moyen et long terme, démarche d'amélioration continue |
| Annexes | Méthode, échelles de gravité et de maturité, liste complète des problèmes, points forts |

**Partage des rôles, pour des rapports comparables d'un designer à l'autre :**
- Les **faits** sont calculés sans IA : nombres, gravités, écrans touchés, thématique récurrente (au moins deux problèmes sur au moins deux écrans) ou isolée, ordre des thématiques (problèmes pondérés par leur gravité : 1, 2, 4, 8), et **niveau de maturité indicatif** par une règle fixe (voir l'annexe du rapport).
- L'IA **rédige**, en deux appels : (1) regroupement des problèmes en thématiques, avec leur description, la raison et les conséquences ; (2) synthèse, chantiers, quick wins et suites. Elle ne cite que des constats existants (les clés inconnues sont écartées, un constat non classé va dans « Autres constats ») et ne peut s'écarter que d'un niveau de la maturité indicative.
- Le prompt ne contient pas tout le référentiel mais seulement les constats, en version courte si l'audit est long : il tient dans la fenêtre de contexte d'un modèle local, même pour 200 constats.
- **Sans IA**, ou si elle échoue, le rapport est produit quand même : les faits sont complets, les thématiques suivent les catégories du référentiel, les quick wins sont des candidats (effort à confirmer), et les passages à rédiger sont surlignés en jaune.
- Les réponses sont mémorisées dans le cache, comme les suggestions.

---

## 7. Français / anglais

| Élément | Français | Anglais |
|---|---|---|
| Interface (sélecteur dans la barre latérale) | ✓ | ✓ |
| Template Excel | ✓ | ✓ |
| Messages des contrôles, annotations, onglets de synthèse | ✓ | ✓ |
| Textes rédigés par l'IA (justifications, recommandations) | ✓ | ✓ |
| Règles de départage | ✓ | ✓ |
| Définitions et checklists des critères | — | ✓ (langue du référentiel d'origine) |

**À faire** : traduire les définitions et les 143 questions de checklist en français, puis les faire valider.

La langue par défaut se règle dans `.env` (`AUDIT_ERGO_LANGUE=fr` ou `en`).

---

## 8. Architecture logicielle

| Module | Rôle |
|---|---|
| `audit_ergo/lecture.py` | Lecture tolérante : onglet et ligne d'en-tête trouvés automatiquement, colonnes reconnues en français, en anglais et au format d'origine, cellules fusionnées, langue du fichier |
| `audit_ergo/controles.py` | Contrôles de forme, messages bilingues |
| `audit_ergo/suggestion.py` | Dialogue avec le modèle local : garde-fous réseau, prompt, schéma, validation, gestion des erreurs |
| `audit_ergo/completion.py` | Remplissage des cellules vides, jamais des cellules saisies |
| `audit_ergo/export.py` | Fichier annoté, onglets de synthèse |
| `audit_ergo/rapport.py` | Rapport Word de synthèse : faits calculés, rédaction par l'IA, mise en page (python-docx) |
| `audit_ergo/cache.py` | Cache local des réponses |
| `audit_ergo/i18n.py` | Textes bilingues, échelle de gravité, listes communes |
| `serveur/api.py` | API de l'application (FastAPI) : dépôt et relecture d'un audit, analyse par l'IA en tâche de fond avec progression, décisions du designer sur les propositions, suggestion, rapport (JSON pour l'affichage HTML, Word) |
| `serveur/historique.py` | Historique des audits sur le poste : enregistrement après chaque étape, réouverture après un redémarrage, suppression |
| `serveur/serialisation.py` | Conversion des objets du moteur en JSON, libellés dans la langue choisie |
| `web/` | Interface React + TypeScript + Tailwind : pages « Relire un audit », « Suggérer un critère », « Rapport de synthèse », « Réglages » ; thème clair et sombre ; compilée dans `web/dist/` |
| `scripts/` | Génération du référentiel, des templates et des exemples ; vérification du modèle local |
| `start.bat` | Installation et lancement en un double-clic sous Windows |

---

## 9. Configuration

La connexion au modèle se règle dans l'écran Réglages (paramètres enregistrés dans `%APPDATA%\AuditErgo`, clé chiffrée, certificat `.crt` importé ; voir README § 3). Le fichier `.env` est prioritaire, champ par champ :

| Variable | Défaut | Rôle |
|---|---|---|
| `API_BASE` | `http://localhost:11434/v1` | Adresse du serveur du modèle (sur le poste ou passerelle de l'organisation) |
| `API_KEY` | — | Clé d'API exigée par le serveur, s'il en demande une |
| `CA_BUNDLE` | — | Certificats (PEM) de l'autorité qui a signé le certificat HTTPS du serveur ; sert aussi à installer les dépendances derrière un proxy. Les autorités internes sans extension « key usage », refusées par défaut depuis Python 3.13, sont acceptées (la chaîne et le nom du serveur restent vérifiés). |

Autres réglages :

| Variable | Défaut | Rôle |
|---|---|---|
| `AUDIT_ERGO_MODELE` | `mistral-small` | Nom du modèle sur le serveur |
| `AUDIT_ERGO_LANGUE` | `fr` | Langue par défaut |
| `AUDIT_ERGO_TEMPERATURE`, `AUDIT_ERGO_MAX_TOKENS`, `AUDIT_ERGO_DELAI`, `AUDIT_ERGO_PARALLELE` | 0,2 · 4000 · 600 s · 1 | Réglages du modèle |
| `AUDIT_ERGO_IA` | `1` | `0` désactive l'IA (contrôles de forme seuls) |

---

## 10. Qualité et fiabilité

- **Tests automatiques** : 138 tests, dont de véritables appels vers un faux serveur local : en HTTP (vérifie que le proxy du poste est contourné) et en HTTPS avec `API_BASE`, `API_KEY` et `CA_BUNDLE` (certificat signé par une autorité interne, clé exigée), la lecture du template d'origine, la complétion, le rapport Word (avec et sans IA, repli en cas d'erreur, gros audit), le cache et les deux langues. Ils ne nécessitent ni modèle ni réseau.
- **À faire avant un usage généralisé : un jeu de référence.**
  1. Réunir 3 à 5 audits passés (100 à 150 constats).
  2. Faire classer chaque constat par deux designers seniors ; mesurer leur accord (il donne le plafond atteignable).
  3. Mesurer l'accord du modèle local avec eux, et le taux de propositions inutiles.
  4. Ajuster les règles de départage, le prompt ou le modèle, puis mesurer à nouveau.
- **Boucle d'amélioration** (prévue) : boutons 👍 / 👎 sur chaque proposition, pour constituer ce jeu de référence au fil des audits.

---

## 11. Feuille de route

| Étape | Statut |
|---|---|
| Référentiel structuré, codes stables, règles de départage FR/EN | ✓ fait — **corrections à valider** par les seniors |
| Template v2 (FR/EN), corrigé et compatible avec l'origine | ✓ fait — à tester dans Excel |
| Contrôles de forme, fichier annoté, synthèse | ✓ fait |
| IA locale : suggestion, complétion, correction, justification | ✓ fait — **à tester avec le vrai modèle Mistral** |
| Confidentialité : 100 % local, garde-fous | ✓ fait |
| Interface bilingue, lancement Windows en un clic | ✓ fait — `start.bat` à tester sur un poste Windows |
| Premier essai sur un poste avec Ollama et Mistral, réglage du contexte | à faire |
| Avis des designers (👍 / 👎) et jeu de référence | à faire |
| Traduction française des définitions et checklists | à faire |
| Rapport Word de synthèse (FR/EN) | ✓ fait — **à relire sur un vrai audit avec le modèle Mistral** |
| Interface React + Tailwind, rapport HTML dans l'application, validation des propositions de l'IA | ✓ fait — `start.bat` à tester sur un poste Windows |
| Rapport modifiable dans l'application (repris dans les exports), historique des audits et comparaison de deux audits | ✓ fait |
| Score de qualité d'un audit | à faire |
| Paquet d'installation hors ligne pour l'équipe informatique | à faire si les postes n'ont pas Internet |

---

## 12. Questions ouvertes

1. **Postes** : mémoire et carte graphique disponibles ? Cela décide du modèle (Mistral Small ou Nemo).
2. **Installation** : l'équipe informatique autorise-t-elle Ollama (ou LM Studio) ? Faut-il un paquet hors ligne ?
3. **Validation du référentiel** : qui valide `CHANGEMENTS.md` et les règles de départage ?
4. **Colonne « Statut »** : faut-il une liste de valeurs (ex. ouvert, en cours, corrigé, rejeté) ?
5. **Serveur interne** : l'organisation préfère-t-elle, à terme, un modèle partagé sur un serveur interne (plus puissant) plutôt qu'un modèle par poste ? L'application le permet : il suffit de renseigner `API_BASE`, `API_KEY` et `CA_BUNDLE`.
