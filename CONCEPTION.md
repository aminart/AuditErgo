# Audit ergonomique assisté : document de conception

> **Objectif** : l'application relit l'audit rempli par un·e UX designer. Elle vérifie le critère choisi pour chaque constat, propose une correction si besoin, évalue la qualité des recommandations et en ajoute d'autres. Le but est que tous les audits de l'équipe atteignent **le même niveau de qualité et la même rigueur**, quel que soit le ou la designer.

---

## 1. Principes directeurs

1. **Assister, pas remplacer** : l'application *suggère*, le ou la designer *décide*. Chaque suggestion est acceptée, modifiée ou refusée, et le choix est tracé.
2. **Un référentiel unique et versionné** : toutes les vérifications s'appuient sur le même référentiel (vos deux fichiers, nettoyés), pas sur la mémoire du modèle d'IA. C'est ce qui garantit le standard commun.
3. **Contrôles déterministes d'abord, IA ensuite** : tout ce qui se vérifie par une règle (champ vide, critère inexistant, gravité hors échelle) est fait par du code, ce qui est gratuit, instantané et fiable. L'IA intervient seulement pour le jugement (pertinence du critère, qualité de la recommandation).
4. **Expliquer chaque suggestion** : toute proposition cite la définition ou la question de la checklist qui la justifie. Le ou la designer apprend en corrigeant, et l'audit gagne en homogénéité dans le temps.
5. **Mesurable** : un score de qualité par audit permet de comparer et de faire progresser les pratiques.

---

## 2. Analyse des fichiers fournis

### 2.1 `criterias_Evaluation_template.csv`, la grille d'évaluation
Elle compte 9 catégories et 24 critères. Chaque critère a une **définition** et une **checklist de questions** (« Is a title given to each page? »…).

| Catégorie | Critères |
|---|---|
| Guidance | Prompting, Grouping/Distinction, Immediate Feedback, Legibility, Help & Documentation |
| Workload | Concision, Recognition rather than recall, Minimal Actions, Focused attention, Information density |
| Explicit control | Actions explicit, User Control & Freedom |
| Adaptability | Flexibility, Universal Usability & UX (Expertise) |
| Consistency | Consistency & Standard |
| Errors management | Protection against errors, Quality of error messages, Error correction |
| Significance of codes | Significance of codes |
| Compatibility | Compatibility & real world, Fit the intended contexts, Utility & Clear Goals |
| Visual design | Opt for a perfect visual design 1 & 2 |

### 2.2 `Heuristic_Evaluation_template.csv`, les frameworks de référence
Ce fichier contient 125 heuristiques issues de 7 frameworks (Bastien & Scapin, Nielsen, Amélie Boucher, Colombo & Pasch, Shneiderman, Arhippainen, CARMEL). Chacune est rattachée à une **composante qualité** : Learnability, Memorability, Efficiency, Errors, Satisfaction, Utility.

Ces deux fichiers sont convertis en un référentiel JSON par `scripts/build_referentiel.py`, avec pour résultat `referentiel/referentiel.json`.

### 2.3 Anomalies à corriger *avant* de construire l'application
L'application sera aussi fiable que son référentiel. Voici ce que j'ai relevé :

| # | Problème | Impact | Correction proposée |
|---|---|---|---|
| 1 | La checklist de **Minimal Actions** est une copie exacte de celle de **Concision** | L'IA ne peut pas distinguer les deux critères | Réécrire Minimal Actions : nombre de clics/étapes, saisies déductibles, valeurs par défaut |
| 2 | **CARMEL « Recovery_Confirmation dialogs »** reprend le texte de « Font size » | Définition fausse | « Les actions destructrices ou irréversibles demandent une confirmation explicite » |
| 3 | 5 critères **sans checklist** (Focused attention, Fit the intended contexts, Utility & Clear Goals, Visual design 1 & 2) et 1 critère avec seulement 2 questions (Recognition rather than recall) | Ces critères seront mal vérifiés | Compléter avec 4 à 6 questions chacun |
| 4 | Identifiants incohérents : `Significances_of_Codes` / `Significance_of_Codes`, `Errors_Management` / ` Errors_management` (espace en tête), coquilles `Leagibility`, `checjked`, `Correspondance` | Erreurs de correspondance entre le fichier du designer et le référentiel | Un identifiant stable par critère (ex. `GUI-01`) |
| 5 | Questions **en doublon dans plusieurs critères** (« hover effect » dans Prompting *et* Immediate Feedback ; « confirmation avant action irréversible » dans Actions explicit *et* Protection against errors ; « guidance on how to correct » dans Quality of error messages *et* Error correction) | C'est précisément là que les designers divergent | Ajouter des **règles de départage** (§ 5.3) |
| 6 | Bastien & Scapin distingue *Grouping by location* et *by format*, alors que la grille les fusionne | Perte de précision | Garder un critère et ajouter un sous-type facultatif |
| 7 | Colombo & Pasch : « *steep* learning curve to help novice users » | Formulation ambiguë (contresens fréquent) | Remplacer par « courbe d'apprentissage douce » |

> **Statut :** les corrections 1 à 5 et 7 sont proposées dans `referentiel/corrections.json` (les CSV d'origine restent intacts). Elles sont listées pour validation dans `referentiel/CHANGEMENTS.md`. La correction 6 est traitée par une note sur le critère `GUI-02`.

---

## 3. Le fichier d'entrée : ce que remplit le ou la designer

Le fichier d'audit rempli ne figure pas dans les fichiers fournis. Pour qu'il puisse être relu automatiquement, je propose **un template Excel verrouillé**, avec une ligne par constat :

| Colonne | Type | Obligatoire | Contrôle |
|---|---|---|---|
| `ID` | texte (auto) | oui | unique |
| `Écran / Page` | texte | oui | non vide |
| `Parcours / Tâche` | texte | recommandé | – |
| `Capture` | lien ou nom d'image | recommandé | le fichier existe |
| `Type` | liste : Problème / Point fort | oui | valeur de la liste |
| `Constat` (description) | texte long | oui | 20 caractères minimum, factuel |
| `Catégorie` | liste déroulante (9) | oui | existe dans le référentiel |
| `Critère principal` | liste dépendante (24) | oui | appartient à la catégorie |
| `Critères secondaires` | multi | non | – |
| `Gravité` | 0–4 (échelle de Nielsen) | oui | dans l'échelle |
| `Fréquence` / `Impact` | faible / moyen / fort | recommandé | – |
| `Recommandation` | texte long | oui si Problème | non vide |
| `Priorité` | P1 / P2 / P3 | recommandé | cohérente avec la gravité |

Avec des listes déroulantes dépendantes dans Excel (validation de données), la moitié des erreurs disparaît avant même l'analyse.

> **Statut :** ce template existe : `template/Audit_ergonomique_template.xlsx`, généré par `scripts/build_template.py`. Il ajoute deux colonnes au tableau ci-dessus : `Règle de départage` (R1 à R9, facultative) et `Contrôle`, une formule qui signale directement dans Excel les champs manquants, un critère hors catégorie, une recommandation absente, une priorité incohérente avec la gravité ou un constat trop court.

**Échelle de gravité commune** (indispensable pour le standard) :
- **0** : pas un problème d'utilisabilité
- **1** : cosmétique, à corriger si le temps le permet
- **2** : mineur, gêne ponctuelle, faible priorité
- **3** : majeur, l'utilisateur est ralenti ou commet des erreurs, priorité haute
- **4** : bloquant, la tâche ne peut pas être accomplie, à corriger avant mise en production

---

## 4. Fonctionnalités

### 4.1 Niveau 1 : contrôles de forme (règles, sans IA)
- Colonnes manquantes ou renommées (avec une correspondance tolérante des noms)
- Champs obligatoires vides
- Critère inexistant, mal orthographié, ou incohérent avec sa catégorie
- Gravité hors échelle, et priorité incohérente avec la gravité (ex. gravité 4 et P3)
- Doublons (même écran et constat quasi identique)
- Recommandation vide, trop courte ou identique au constat

### 4.2 Niveau 2 : vérification du critère (IA)
Pour chaque constat :
- **Le critère choisi est-il le bon ?** Réponse *Confirmé / À revoir / Incorrect*, avec un indice de confiance.
- Si le critère est à revoir : **critère suggéré** et justification, en citant la définition et la question de checklist concernées.
- **Critères secondaires** pertinents (un même problème touche souvent 2 critères).
- **Gravité suggérée** si l'écart avec celle du designer est d'au moins 2 niveaux.
- **Qualité du constat** : est-il factuel, observable et localisé (« le bouton X de l'écran Y »), ou vague (« la page est confuse ») ?

### 4.3 Niveau 3 : qualité de la recommandation (IA)
Chaque recommandation est notée selon une grille fixe :

| Dimension | Question |
|---|---|
| Spécifique | Nomme-t-elle l'élément concerné ? |
| Actionnable | Une équipe peut-elle l'implémenter sans réinterpréter ? |
| Cohérente | Traite-t-elle la *cause* du constat, et relève-t-elle du critère choisi ? |
| Vérifiable | Peut-on vérifier qu'elle est appliquée ? |
| Référencée | S'appuie-t-elle sur une norme ou un pattern (WCAG, Material, etc.) si pertinent ? |

L'IA propose alors une **reformulation améliorée** (sans perdre l'intention du designer) et des **recommandations complémentaires**, clairement marquées comme « ajoutées par l'assistant ».

### 4.4 Niveau 4 : analyse globale de l'audit
- **Couverture** : carte des 24 critères et des questions de checklist couvertes ou non. Exemple : « aucun constat sur Error management, alors que l'interface contient 3 formulaires ; à vérifier ».
- **Distribution** des gravités et des composantes qualité (Learnability, Efficiency…), pour repérer un audit trop centré sur le visuel.
- **Points de vigilance** : questions de la checklist que l'IA suggère de vérifier, au vu des captures ou de la description de l'interface.
- **Synthèse** : top 5 des problèmes à corriger en priorité.

### 4.5 (Option) Analyse des captures d'écran
Si les captures sont jointes, le modèle (multimodal) peut confirmer que le constat est visible, détecter des problèmes non relevés (contraste, alignement, densité, absence de feedback) et vérifier la cohérence entre écrans.

---

## 5. Architecture

### 5.1 Vue d'ensemble

```
 ┌──────────────┐   ┌────────────────┐   ┌─────────────────┐   ┌────────────────┐
 │ Import .xlsx │──▶│ Normalisation  │──▶│ Contrôles règles│──▶│ Analyse IA     │
 │ (+ captures) │   │ (mapping cols, │   │ (niveau 1)      │   │ par constat    │
 └──────────────┘   │  ID critères)  │   └─────────────────┘   │ (niveaux 2 & 3)│
                    └────────────────┘                         └───────┬────────┘
                            ▲                                          │
                    ┌───────┴────────┐                         ┌───────▼────────┐
                    │ Référentiel    │────────────────────────▶│ Analyse globale│
                    │ JSON versionné │                         │ (niveau 4)     │
                    └────────────────┘                         └───────┬────────┘
                                                                       │
 ┌──────────────────┐   ┌──────────────────────────┐          ┌────────▼───────┐
 │ Export .xlsx     │◀──│ Revue par le designer    │◀─────────│ Suggestions    │
 │ enrichi + rapport│   │ accepter/modifier/refuser│          │ structurées    │
 └──────────────────┘   └──────────────────────────┘          └────────────────┘
```

### 5.2 Moteur IA
- **Modèle** : Claude via l'API Anthropic (`claude-opus-5-5` par défaut), avec **sorties structurées** (`output_config.format` et un schéma JSON) pour obtenir des résultats exploitables par le code.
- **Le référentiel complet tient dans le prompt** (environ 15 000 tokens) : pas besoin de RAG ni de base vectorielle. Il est placé en tête du prompt avec du **prompt caching**, si bien qu'on ne le paie qu'une fois par audit.
- **Un appel par lot de constats** (ex. 10 à 20), puis un appel de synthèse globale. Pour de gros audits non urgents, l'API Batch divise le coût par deux.
- **Garde-fous** : le prompt système impose de ne jamais inventer de critère hors référentiel, de citer la question de checklist, et de répondre « confiance faible » plutôt que de trancher arbitrairement.

**Schéma de sortie par constat (exemple)** :
```json
{
  "finding_id": "F-012",
  "criterion_check": {
    "verdict": "a_revoir",
    "designer_criterion": "GUI-01",
    "suggested_criterion": "GUI-03",
    "secondary_criteria": ["WKL-05"],
    "confidence": 0.82,
    "justification": "Le constat décrit l'absence de réaction APRÈS le clic (règle de départage R1).",
    "checklist_reference": "Is information displayed during the loading of an action, file, or page?"
  },
  "severity_check": { "designer": 1, "suggested": 3, "reason": "Bloque la soumission du formulaire" },
  "finding_quality": { "factual": true, "located": false, "comment": "Préciser l'écran et le composant" },
  "recommendation_quality": {
    "scores": { "specific": 1, "actionable": 2, "coherent": 3, "verifiable": 1, "referenced": 0 },
    "improved_recommendation": "Afficher un indicateur de chargement sur le bouton « Valider » dès le clic, et le désactiver jusqu'à la réponse serveur.",
    "additional_recommendations": [
      "Afficher un message de confirmation explicite après l'enregistrement."
    ]
  }
}
```

### 5.3 Règles de départage : le cœur du « même standard »
Ce sont les cas où deux designers choisissent des critères différents pour le même problème. Ces règles sont intégrées au référentiel et au prompt. La version complète (9 règles, avec une question à se poser et un exemple par cas) se trouve dans `referentiel/regles_departage.json` et dans l'onglet « Règles de départage » du template. En voici l'essentiel :

| Règle | Si le problème concerne… | Critère |
|---|---|---|
| R1 | ce qui guide **avant** l'action | Prompting |
| | la réponse du système **après** l'action | Immediate Feedback |
| R2 | **empêcher** l'erreur | Protection against errors |
| | le **texte** du message d'erreur | Quality of error messages |
| | le **moyen de réparer** l'erreur | Error correction |
| R3 | un élément **isolé** trop long ou trop chargé | Concision |
| | l'écran **dans son ensemble** trop chargé | Information density |
| | le **nombre d'étapes** ou de clics | Minimal actions |
| R4 | le système agit **sans demande** de l'utilisateur | Actions explicit |
| | l'utilisateur **ne peut pas interrompre ou annuler** | User control & freedom |
| R5 | une incohérence **interne** au produit | Consistency |
| | un écart avec les **conventions externes** ou le monde réel | Compatibility |
| | un libellé ou une icône **qui ne dit pas ce qu'il fait** | Significance of codes |
| R6 | la **lecture** du texte (taille, contraste, interligne) | Legibility |
| | l'**organisation** visuelle (regroupement, séparation) | Grouping / Distinction |
| | l'**esthétique** et l'émotion | Visual design |
| R7 | la **personnalisation** par l'utilisateur | Flexibility |
| | l'adaptation au **niveau d'expertise** | Universal usability |

Ces règles sont à valider et compléter avec vos designers seniors : c'est le livrable métier le plus important du projet.

---

## 6. Score de qualité de l'audit

Chaque audit reçoit un score sur 100, affiché de façon pédagogique et non punitive :

| Composante | Poids | Mesure |
|---|---|---|
| Complétude | 15 % | Champs obligatoires remplis |
| Justesse des critères | 30 % | Part des critères confirmés par l'IA (après revue humaine) |
| Qualité des constats | 15 % | Constats factuels et localisés |
| Qualité des recommandations | 25 % | Moyenne de la grille du § 4.3 |
| Couverture | 15 % | Part des critères pertinents examinés |

Ce score permet de suivre la progression d'un·e designer, de repérer les critères mal compris par l'équipe (et de cibler les formations), et de comparer deux audits du même produit.

---

## 7. Parcours utilisateur (écrans)

1. **Accueil** : déposer le fichier `.xlsx` et éventuellement un dossier de captures. Indiquer le contexte : type de produit, cible, plateforme.
2. **Contrôle de forme** : liste des erreurs bloquantes et non bloquantes, avec correction possible directement dans l'outil.
3. **Revue constat par constat** : vue en 2 colonnes, « Designer » et « Suggestion ». Boutons ✅ Accepter / ✏️ Modifier / ❌ Refuser, avec un champ de commentaire en cas de refus. Filtres par verdict, critère et gravité.
4. **Vue globale** : carte de couverture des 24 critères, distribution des gravités, score, points de vigilance.
5. **Export** :
   - le **fichier Excel d'origine enrichi** de colonnes : `Critère suggéré`, `Verdict`, `Reco améliorée`, `Recos complémentaires`, `Statut revue` ;
   - un **rapport d'audit** (PDF/HTML) prêt à livrer au client ;
   - un **journal des décisions** (traçabilité).

Les refus des designers sont précieux : ils servent à améliorer le prompt et les règles de départage (§ 9).

---

## 8. Stack technique recommandée

| Brique | Choix | Pourquoi |
|---|---|---|
| Lecture/écriture Excel | Python + `openpyxl` (ou `pandas`) | Robuste, conserve la mise en forme d'origine à l'export |
| Backend | Python **FastAPI** | Même langage que le traitement Excel et le SDK `anthropic` |
| IA | API Claude (SDK Python `anthropic`), sorties structurées, prompt caching | Fiabilité du JSON, coût maîtrisé |
| Front | **MVP** : Streamlit (quelques jours). **V2** : React/Next.js | Valider la valeur vite, puis industrialiser |
| Stockage | SQLite, puis PostgreSQL | Audits, décisions, scores, versions du référentiel |
| Référentiel | `referentiel.json` versionné dans Git | Chaque audit enregistre la version utilisée |

**Coût indicatif** : un audit de 50 constats représente environ 5 à 8 appels, soit quelques dizaines de centimes à environ 1 € selon la taille. C'est à mesurer sur vos vrais audits.

**Confidentialité** : les audits clients peuvent être sensibles. Il faut vérifier les conditions de traitement des données (rétention API, hébergement), anonymiser le nom du client si besoin, et ne jamais envoyer d'informations personnelles d'utilisateurs finaux.

---

## 9. Garantir la fiabilité : jeu de référence (« golden set »)

Avant de déployer l'outil, il faut prouver qu'il améliore vraiment les audits :
1. Rassembler **3 à 5 audits passés** (environ 100 à 150 constats).
2. Faire annoter par **2 designers seniors** le critère correct et la gravité de chaque constat. Mesurer leur accord (kappa de Cohen) : il donne le plafond atteignable.
3. Lancer l'outil et mesurer :
   - le **taux d'accord** de l'outil avec les seniors (objectif : au moins égal à l'accord entre seniors) ;
   - le **taux de faux positifs**, c'est-à-dire de suggestions inutiles (une source de fatigue si trop élevé).
4. Ajuster les règles de départage et le prompt, puis re-mesurer. Recommencer à chaque modification du référentiel.

---

## 10. Feuille de route

| Phase | Contenu | Durée indicative |
|---|---|---|
| **0. Référentiel** | Corriger les anomalies (§ 2.3), compléter les checklists, écrire les règles de départage, figer le template Excel | 1 à 2 semaines (travail métier) |
| **1. MVP** | Import Excel, contrôles niveau 1, vérification des critères (niveau 2), export Excel enrichi. Interface Streamlit | 2 à 3 semaines |
| **2. Qualité** | Niveaux 3 et 4, score, rapport PDF, golden set et mesures | 3 à 4 semaines |
| **3. Industrialisation** | Front React, comptes utilisateurs, historique, tableau de bord équipe, analyse des captures | selon besoin |

---

## 11. Questions à trancher

1. **Le fichier du designer** : avez-vous un exemple d'audit rempli ? Sa structure réelle conditionne le module d'import.
2. **Langue** : le référentiel est en anglais. Les audits et recommandations sont-ils rédigés en français, en anglais, ou les deux ?
3. **Échelle de gravité** : utilisez-vous déjà celle de Nielsen (0–4) ou une échelle interne ?
4. **Frameworks** : les designers doivent-ils citer le framework source (Nielsen, Bastien & Scapin…) ou seulement la grille des 9 catégories ?
5. **Captures d'écran** : sont-elles systématiquement jointes ? (Cela détermine si l'analyse visuelle doit être prévue dès le MVP.)
6. **Utilisateurs** : outil individuel pour le ou la designer, ou outil de relecture pour un·e lead (avec un tableau de bord d'équipe) ?
7. **Hébergement** : outil interne (SSO, cloud de l'entreprise) ou application web simple ?
