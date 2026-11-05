# AuditErgo : fonctionnement

Ce document décrit **ce que fait l'application et comment elle fonctionne, du point de vue de l'utilisateur**. L'installation est dans `README.md`, les choix techniques et la confidentialité dans `CONCEPTION.md`.

---

## 1. À quoi sert l'application

Elle aide les UX designers à produire des **audits ergonomiques heuristiques du même standard**, quel que soit l'auteur. Le designer garde la main sur l'audit ; l'application :

- **vérifie la forme** de chaque constat (champs manquants, critère inconnu, gravité hors échelle, formulations vagues…) ;
- **propose**, avec l'IA, le critère, la recommandation et la gravité de chaque constat, en s'appuyant sur un référentiel commun ;
- **complète les cellules vides** et donne son avis sur ce que le designer a saisi, sans jamais l'écraser ;
- **rédige un rapport de synthèse** pour l'équipe produit, consultable et modifiable dans l'application, exportable en PDF, HTML et Word ;
- **conserve l'historique** des audits et permet d'en **comparer deux**.

L'IA est un modèle Mistral installé sur le poste (ou sur une passerelle choisie par l'organisation) : par défaut, **aucune donnée ne quitte le poste**.

### Les principes à retenir

| Principe | Ce que cela veut dire en pratique |
|---|---|
| L'application propose, le designer décide | Toute cellule remplie par l'IA est signalée (en violet) et doit être validée, corrigée ou refusée. |
| Les saisies du designer ne sont jamais modifiées | Quand l'IA n'est pas d'accord, elle le dit à côté, dans des colonnes « IA : … ». |
| Les règles d'abord, l'IA ensuite | Ce qui se vérifie par une règle est fait sans IA, instantanément. L'IA sert au jugement et à la rédaction. |
| Un référentiel unique | 9 catégories, 24 critères (codes `GUI-01` à `VIS-02`) avec leurs checklists, et 9 règles de départage (R1 à R9) entre critères proches. |
| Expliquer | Chaque proposition cite la règle de départage et la question de checklist qui la justifient. |
| Les chiffres sont calculés, pas inventés | Nombres, gravités, écrans, récurrence et maturité indicative sont calculés sans IA. |

---

## 2. Le parcours type

```
 1. Remplir l'audit         2. Le déposer          3. Analyser avec l'IA      4. Valider les propositions
 (template Excel)    ─────▶ (Relire un audit) ───▶ (à la demande)       ───▶ (✓ valider, ✎ corriger, ✗ refuser)
                                 │                                                    │
                                 ▼                                                    ▼
                     Contrôles de forme immédiats                       5. Télécharger l'audit complété (.xlsx)
                                                                         6. Générer le rapport de synthèse
                                                                         7. Le relire, le modifier, l'exporter
                                                                         8. Plus tard : le rouvrir, le comparer
```

1. Le designer remplit le **template Excel** (`template/Audit_ergonomique_FR.xlsx` ou `Ergonomic_audit_EN.xlsx`, téléchargeable aussi depuis l'application). Il peut ne saisir que les constats : le reste peut être proposé par l'IA.
2. Il **dépose le fichier** dans la page « Relire un audit ». Les contrôles de forme s'affichent aussitôt.
3. Il lance **l'analyse par l'IA** (facultatif, mais recommandé avant le rapport).
4. Il **passe en revue les propositions** de l'IA, constat par constat.
5. Il **télécharge l'audit complété** : son fichier d'origine, enrichi.
6. Il **génère le rapport de synthèse**, le relit et le corrige dans la page, puis l'exporte.
7. L'audit reste dans **l'historique** : il peut le rouvrir, ou le comparer à un audit précédent.

---

## 3. Les écrans

L'application s'ouvre dans le navigateur (http://localhost:8501). La barre latérale donne accès à cinq pages, au choix de la langue (FR / EN) et du thème (clair / sombre). Un point vert à côté de « Relire un audit » et « Rapport de synthèse » indique qu'un audit est ouvert et qu'un rapport existe.

### 3.1 Relire un audit

**Déposer un fichier.** On glisse un fichier `.xlsx` dans la zone de dépôt (ou on le choisit). Sont acceptés :

- le **template v2** (recommandé) ;
- le **template d'origine** (`Heuristic_Evaluation_template.xlsx`), y compris ses coquilles de noms ;
- un **simple tableau** qui contient au moins une colonne « Constat ».

Sous la zone de dépôt, les audits récents de l'historique se rouvrent d'un clic.

**Le tableau de bord de l'audit.** Une fois le fichier lu, la page affiche :

- l'état général : « Aucune anomalie bloquante » ou le nombre d'anomalies bloquantes à corriger ;
- les chiffres clés : nombre de constats (problèmes et points forts), constats sans anomalie bloquante, constats sans aucune remarque, champs facultatifs remplis, critères cités ;
- le bouton **Télécharger l'audit annoté** (ou **complété**, après l'IA).

**Les contrôles de forme (sans IA).** Chaque constat est vérifié selon trois niveaux :

| Niveau | Exemples |
|---|---|
| **Bloquant** | Champ obligatoire vide (écran, constat, catégorie, critère, gravité et recommandation pour un problème), critère inconnu ou rangé dans la mauvaise catégorie, gravité hors échelle, type autre que « Problème » ou « Point fort », colonne obligatoire absente |
| **Avertissement** | Constat ou recommandation trop courts, recommandation qui recopie le constat, règle de départage qui ne mène pas au critère choisi, gravité incohérente avec l'impact ou la priorité, gravité donnée à un point fort, doublon sur le même écran, onglet Contexte absent ou incomplet, audit fait avec une ancienne version du référentiel |
| **Info** | Formulations vagues (« pas clair », « améliorer »…), colonnes non reconnues |

**L'analyse par l'IA.** Le panneau « Compléter et corriger avec l'IA » indique ce qui manque (par exemple : des constats n'ont pas encore de critère ou de recommandation) et propose :

- **Remplir les cellules vides avec les propositions** (coché par défaut). Décoché, l'IA donne seulement son avis, sans rien remplir.
- **Analyser N constat(s)** : le modèle local traite un constat à la fois, de quelques secondes à une minute chacun. Une barre de progression suit l'avancement.

Pour chaque constat, l'IA propose le critère principal (avec un niveau de confiance et sa justification), les critères secondaires, une recommandation et son type, et une gravité. Si le designer a déjà fait ses choix, elle donne son verdict sur son critère et sur sa recommandation.

Les réponses sont **mémorisées** : un constat déjà analysé n'est pas recalculé (le résultat indique combien de constats ont été repris du cache). « Refaire sans le cache » force une nouvelle analyse.

**Les onglets.**

- **Constats** : une carte par constat, avec ses anomalies, l'avis de l'IA et les cellules proposées. Une recherche (constat, écran…) et des filtres : Tous, À valider, Avec anomalie, Avis IA à revoir.
- **Anomalies** : la liste de toutes les anomalies, par niveau.
- **Couverture** : le nombre de constats par critère (principal et secondaire), et les critères jamais cités. Un critère jamais cité n'est pas une erreur, mais invite à repasser sur sa checklist.
- **Gravité** : la répartition des problèmes par gravité.

**Valider les propositions.** Chaque cellule remplie par l'IA porte la mention « Proposé par l'IA » et trois boutons :

| Action | Effet dans l'application | Effet dans le fichier exporté |
|---|---|---|
| ✓ **Valider** | La cellule passe à « Validé » | Valeur écrite normalement (plus de violet, plus de commentaire) |
| ✎ **Modifier** | Le designer corrige la valeur, qui est validée | Valeur corrigée, écrite normalement |
| ✗ **Refuser** | La cellule redevient vide | Cellule vide |

On peut aussi valider d'un coup toutes les propositions d'un constat, ou de l'audit entier (« Tout valider »). Certaines cellules sont **déduites automatiquement**, sans IA (par exemple la catégorie, qui découle du critère).

**Le fichier téléchargé** est le fichier d'origine, avec ses formules et ses listes déroulantes, plus :

- les cellules remplies par l'IA et non encore validées, **en violet**, avec l'explication en commentaire ;
- les colonnes « IA : … » avec l'avis de l'IA sur les saisies du designer ;
- deux onglets : **Synthèse** et **Anomalies**.

Les valeurs écrites dans les cellules suivent la langue du fichier (pour rester cohérentes avec ses listes) ; les commentaires suivent la langue choisie dans l'application.

### 3.2 Suggérer un critère

Pour un constat isolé, avant même de le saisir dans l'audit. Le designer décrit le constat et l'écran concerné ; il peut indiquer le critère, la recommandation et la gravité qu'il envisage, ainsi que le contexte du produit (produit, cible, plateforme), qui améliore la pertinence.

L'IA répond, en une à deux minutes :

- le **critère principal**, son niveau de confiance, la règle de départage et la question de checklist qui le justifient ;
- les **critères secondaires**, et les critères envisagés puis **écartés** (avec la raison) ;
- ce qu'il faudrait **préciser** si le constat est trop vague pour trancher ;
- une **recommandation** et son type (ou une version améliorée de celle du designer), avec des pistes complémentaires ;
- une **gravité** et sa justification ;
- l'avis sur les choix du designer, s'il en a fait.

Un bloc « À coller dans l'audit » se copie en un clic. La définition et la checklist du critère proposé sont consultables sur place, et les constats précédents de la séance restent listés.

### 3.3 Rapport de synthèse

Le rapport part de l'audit ouvert. Il est conseillé de lancer d'abord l'analyse par l'IA, pour qu'il parte d'un audit complet. Les propositions de l'IA non validées y figurent quand même (un message le signale).

**Générer.** Deux boutons :

- **Générer le rapport** : les chiffres sont calculés, puis l'IA rédige les analyses en deux étapes (regroupement en thématiques, puis synthèse et recommandations) ;
- **Générer sans IA** : les faits sont complets, les thématiques suivent les catégories du référentiel, et les passages à rédiger sont **surlignés**.

Si l'IA échoue en cours de route, le rapport est produit quand même, avec les passages manquants surlignés.

**Contenu du rapport.**

| Partie | Contenu |
|---|---|
| 1. Synthèse générale | L'essentiel en quelques phrases, niveau de maturité UX (sur 5), chiffres clés, problèmes par gravité, points forts, faiblesses, problèmes récurrents, impact sur les utilisateurs |
| 2. Problèmes UX principaux | Problèmes regroupés par thématique, de la plus à la moins pénalisante : problèmes observés, pourquoi l'expérience est dégradée, conséquences, constats représentatifs ; puis tendances récurrentes et cas isolés. Pas de solutions dans cette partie. |
| 3. Recommandations UX et UI | 3 à 6 grands chantiers transverses, hiérarchisés par impact : objectif, importance, bénéfices attendus, problèmes résolus |
| 4. Prochaines étapes | Quick wins (faible effort, valeur immédiate), chantiers à moyen et long terme, démarche d'amélioration continue |
| Annexes | Méthode, échelles de gravité et de maturité, liste complète des problèmes et des points forts |

**Ce qui est calculé, ce qui est rédigé.** Pour que deux rapports restent comparables d'un designer à l'autre :

- **calculé sans IA** : les nombres, les gravités, les écrans touchés, le caractère récurrent d'une thématique (au moins deux problèmes sur au moins deux écrans) ou isolé, l'ordre des thématiques (problèmes pondérés par leur gravité : 1, 2, 4, 8) et le **niveau de maturité indicatif** ;
- **rédigé par l'IA** : les textes. Elle ne peut citer que des constats existants et ne peut s'écarter que d'un niveau de la maturité indicative, en le justifiant.

**Le niveau de maturité indicatif** suit une règle fixe :

| Niveau | Nom | Règle |
|---|---|---|
| 1 | Initiale | Au moins 3 problèmes critiques, ou un problème critique et au moins 40 % de problèmes élevés ou critiques |
| 2 | Fragile | Un problème critique, ou au moins 40 % de problèmes élevés ou critiques |
| 3 | Intermédiaire | Au moins 20 % de problèmes élevés ou critiques |
| 4 | Maîtrisée | Moins de 20 % de problèmes élevés ou critiques |
| 5 | Exemplaire | Aucun problème élevé ni critique |

**Modifier le rapport.** Le bouton « Modifier le rapport » rend chaque passage rédigé modifiable sur place : synthèse, justification de la maturité, impact, listes (points forts, faiblesses, problèmes récurrents, démarche), thématiques, chantiers, quick wins, suites, et le niveau de maturité lui-même. Chaque passage est **enregistré dès qu'on quitte le champ** (un message « Modification enregistrée » s'affiche) et repris dans tous les exports. Les chiffres, eux, ne se modifient pas : ils découlent de l'audit.

Régénérer un rapport modifié remplace les modifications : l'application demande confirmation avant.

**Rapport périmé.** Si l'audit change après la génération (validation ou refus d'une proposition, nouvelle analyse par l'IA), le rapport est conservé mais signalé comme **périmé**, avec l'invitation à le régénérer. Changer la langue de l'interface ne le rend pas périmé.

**Exporter.**

| Bouton | Résultat |
|---|---|
| Imprimer / PDF | Impression du navigateur (toujours en thème clair) ; « Enregistrer au format PDF » pour un PDF |
| Télécharger en HTML | Une page HTML autonome, lisible sans l'application, à archiver ou envoyer |
| Télécharger en Word | Un fichier `.docx` au même contenu, pour retravailler la mise en forme |

### 3.4 Historique

Chaque audit déposé est **enregistré sur le poste**, avec sa relecture, les avis de l'IA, les décisions du designer et le rapport (modifications comprises). Il se rouvre après la fermeture de l'application, et le dernier audit ouvert est rouvert automatiquement au lancement.

La page liste les audits, du plus récemment modifié au plus ancien, avec pour chacun le nombre de problèmes. On peut :

- **Ouvrir** un audit (il devient l'audit en cours dans les pages Relecture et Rapport) ;
- **Supprimer** un audit (après confirmation : le fichier déposé, la relecture et le rapport sont effacés du poste) ;
- **Comparer** deux audits, en en sélectionnant deux.

**La comparaison** met côte à côte un audit « Avant » et un audit « Après » (inversables), typiquement deux versions d'un même produit :

- problèmes, problèmes élevés ou critiques, écrans concernés, points forts, maturité indicative, avec l'écart et son sens (en progrès, en recul, stable) ;
- problèmes par gravité et par catégorie de critères ;
- écrans sans problème avant et concernés après, et inversement.

Les chiffres sont calculés sans IA ; ils supposent que les deux audits portent sur un périmètre comparable.

### 3.5 Réglages

- **Modèle IA** : modèle utilisé, serveur, clé d'API (renseignée ou non), certificats, et un message qui indique si le modèle est sur le poste (« aucune donnée n'en sort ») ou sur un serveur distant. Le bouton **Tester la connexion** vérifie que le modèle répond.
- **Cache des réponses** : nombre de réponses de l'IA mémorisées, et un bouton pour **vider le cache**.
- **Template vierge** à télécharger, et version du référentiel.

La connexion elle-même se règle dans le fichier `.env` (voir `README.md`), pas dans l'interface.

---

## 4. Français et anglais

- La **langue de l'interface** se choisit dans la barre latérale ; elle est retenue d'une séance à l'autre.
- Changer de langue relance les contrôles de forme dans la nouvelle langue, sans refaire l'analyse par l'IA.
- Le **rapport** est rédigé dans la langue choisie au moment de sa génération.
- Les **valeurs** écrites dans le fichier Excel suivent la langue du fichier ; les commentaires et annotations suivent la langue de l'interface.
- Le référentiel, les règles de départage et les deux templates existent dans les deux langues.

---

## 5. Où vont les données

| Donnée | Emplacement | Remarque |
|---|---|---|
| Audits déposés, relectures, décisions, rapports | `.donnees/audits/` sur le poste | Supprimables depuis l'Historique. `AUDIT_ERGO_HISTORIQUE=0` désactive l'enregistrement (tout est effacé à l'arrêt). |
| Réponses de l'IA | `.cache/suggestions.sqlite` sur le poste | Vidable depuis les Réglages. |
| Constats envoyés au modèle | Le modèle local (Ollama, LM Studio) ou la passerelle définie par `API_BASE` | Avec un modèle local, rien ne quitte le poste. |
| Préférences (langue, thème, dernier audit ouvert) | Le navigateur | |

L'application n'est accessible que depuis le poste lui-même (adresse `localhost`), et ne charge aucune ressource externe (polices, scripts).

---

## 6. Limites à connaître

- **Le modèle local est lent** : compter de quelques secondes à une minute par constat, et une à deux minutes par étape du rapport. Le cache évite de payer deux fois le même constat.
- **Les propositions de l'IA sont à relire** : elle peut se tromper de critère ou proposer une gravité discutable. Le niveau de confiance et la règle de départage citée aident à juger.
- **Un audit au format d'origine** perd, à la réécriture, sa liste déroulante « Mock up solution status » et deux mises en forme conditionnelles. Le template v2 n'a pas ce problème.
- **La comparaison** ne rapproche pas les constats un à un : elle compare des totaux et des répartitions.
- **Sans IA** (`AUDIT_ERGO_IA=0` ou modèle injoignable), les contrôles de forme, l'historique, la comparaison et le rapport sans IA restent disponibles ; l'analyse des constats et la suggestion de critère ne le sont pas.

---

## 7. Lexique

| Terme | Sens dans l'application |
|---|---|
| Constat | Une ligne de l'audit : un **problème** ou un **point fort** observé sur un écran. |
| Catégorie / critère | Le référentiel compte 9 catégories (Guidage, Charge de travail, Contrôle explicite, Adaptabilité, Homogénéité, Gestion des erreurs, Signifiance des codes, Compatibilité, Design visuel) et 24 critères codés (`GUI-01`…). |
| Règle de départage | Question à se poser pour choisir entre deux critères proches (R1 à R9). |
| Gravité | Faible, Moyenne, Élevée, Critique. Uniquement pour un problème. |
| Proposition | Valeur suggérée par l'IA pour une cellule vide, à valider. |
| Avis de l'IA | Verdict de l'IA sur une valeur saisie par le designer, donné à côté, sans la modifier. |
| Maturité UX | Niveau de 1 (Initiale) à 5 (Exemplaire), calculé par une règle fixe puis ajustable d'un niveau. |
| Rapport périmé | Rapport généré avant une modification de l'audit. |
