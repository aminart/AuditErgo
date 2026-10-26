# Modifications proposées du référentiel (version 1.0-proposition)

> Fichier généré par `scripts/build_referentiel.py` : ne pas modifier à la main.
> Pour accepter, modifier ou refuser une proposition, éditer `referentiel/corrections.json` puis relancer le script.

Toutes les propositions ci-dessous sont **à valider** par les designers seniors. Les CSV d'origine (`referentiel/source/`) ne sont pas modifiés.

## Synthèse

- **24 critères** répartis en 9 catégories, chacun avec un code stable (ex. `GUI-01`).
- **37 questions de checklist proposées**, pour les critères qui n'en avaient pas ou pas assez.
- **17 questions déplacées ou retirées** pour supprimer les doublons entre critères.
- **2 définitions et 2 heuristiques corrigées**.

## Codes des critères

| Code | Critère | Nom français | Questions |
|---|---|---|---|
| `GUI-01` | Prompting | Incitation | 8 (8 source, 0 déplacées, 0 proposées) |
| `GUI-02` | Grouping / Distinction between Items | Groupement / distinction entre items | 7 (6 source, 1 déplacées, 0 proposées) |
| `GUI-03` | Immediate Feedback | Feedback immédiat | 6 (6 source, 0 déplacées, 0 proposées) |
| `GUI-04` | Legibility / Readability | Lisibilité | 4 (4 source, 0 déplacées, 0 proposées) |
| `GUI-05` | Help & Documentation | Aide et documentation | 4 (4 source, 0 déplacées, 0 proposées) |
| `WKL-01` | Concision | Concision | 6 (1 source, 0 déplacées, 5 proposées) |
| `WKL-02` | Recognition rather than recall | Reconnaissance plutôt que rappel | 8 (2 source, 1 déplacées, 5 proposées) |
| `WKL-03` | Minimal Actions | Actions minimales | 8 (5 source, 0 déplacées, 3 proposées) |
| `WKL-04` | Focused attention | Attention focalisée | 5 (0 source, 0 déplacées, 5 proposées) |
| `WKL-05` | Information density | Densité informationnelle | 8 (8 source, 0 déplacées, 0 proposées) |
| `CTL-01` | Explicit user actions | Actions explicites | 3 (3 source, 0 déplacées, 0 proposées) |
| `CTL-02` | User Control & Freedom | Contrôle utilisateur et liberté | 5 (5 source, 0 déplacées, 0 proposées) |
| `ADA-01` | Flexibility | Flexibilité | 6 (6 source, 0 déplacées, 0 proposées) |
| `ADA-02` | Universal usability & user expertise | Prise en compte de l'expérience de l'utilisateur | 6 (6 source, 0 déplacées, 0 proposées) |
| `CON-01` | Consistency & standards | Homogénéité et standards | 6 (6 source, 0 déplacées, 0 proposées) |
| `ERR-01` | Protection Against Errors | Protection contre les erreurs | 5 (5 source, 0 déplacées, 0 proposées) |
| `ERR-02` | Quality of Error Messages | Qualité des messages d'erreur | 7 (7 source, 0 déplacées, 0 proposées) |
| `ERR-03` | Error Correction | Correction des erreurs | 6 (6 source, 0 déplacées, 0 proposées) |
| `COD-01` | Significance of Codes | Signifiance des codes et dénominations | 7 (7 source, 0 déplacées, 0 proposées) |
| `CPT-01` | Compatibility & match with the real world | Compatibilité et correspondance avec le monde réel | 8 (8 source, 0 déplacées, 0 proposées) |
| `CPT-02` | Fit the intended contexts | Adaptation aux contextes d'usage | 5 (0 source, 0 déplacées, 5 proposées) |
| `CPT-03` | Utility & Clear Goals | Utilité et objectifs clairs | 5 (0 source, 0 déplacées, 5 proposées) |
| `VIS-01` | Visual design for usability | Design visuel au service de l'utilisabilité | 5 (0 source, 0 déplacées, 5 proposées) |
| `VIS-02` | Aesthetics | Esthétique | 5 (0 source, 1 déplacées, 4 proposées) |

## Questions déplacées ou retirées

| Critère | Question | Vers | Raison |
|---|---|---|---|
| `GUI-03` | Do clickable elements exhibit a "hover" effect upon mouseover (e.g., color change)? | `GUI-01` | Doublon avec GUI-01 (« change appearance when hovered »). L'état de survol signale qu'un élément est cliquable AVANT l'action : règle R1. |
| `GUI-04` | Are clickable elements visually prominent? | `GUI-01` | Identifier ce qui est cliquable relève de l'incitation (GUI-01 : « action elements easily identifiable »), pas de la lisibilité du texte : règle R6. |
| `GUI-04` | Is the use of colors harmonious? | `VIS-02` | Harmonie des couleurs = esthétique : règle R6. |
| `GUI-04` | Do colors and shapes serve as visual cues for different page elements (e.g., sections, menus, text, headings)? | `GUI-02` | Distinction par le format : règle R6. |
| `WKL-01` | Is memorization minimized? | `WKL-02` | Relève de la reconnaissance plutôt que du rappel. |
| `WKL-01` | Are the mandatory steps for the user brief? | `WKL-03` | Nombre d'étapes = actions minimales : règle R3. |
| `WKL-01` | Is the number of steps in a procedure minimized? | `WKL-03` | Nombre d'étapes = actions minimales : règle R3. |
| `WKL-01` | Are shortcuts provided? | `WKL-03` | Raccourcis = réduction du nombre d'actions : règle R3. |
| `WKL-01` | Does the system anticipate user needs by highlighting the most frequent or relevant choices? | `WKL-03` | Réduit le nombre d'actions : règle R3. |
| `WKL-01` | On long pages, is there an anchor to return to the top of the page? | `WKL-03` | Réduit le nombre d'actions : règle R3. |
| `WKL-01` | Is the page width adapted to different devices? | `CPT-01` | Adaptation aux supports = compatibilité (déjà couverte par CPT-01). |
| `WKL-03` | Is memorization minimized? | `WKL-02` | Relève de la reconnaissance plutôt que du rappel. |
| `WKL-03` | Is the amount of information to enter reduced to a minimum? | `WKL-01` | Quantité d'information d'un champ = concision : règle R3. |
| `WKL-03` | Is the page width adapted to different devices? | `CPT-01` | Adaptation aux supports = compatibilité. |
| `CTL-01` | Do actions with significant and/or irreversible consequences require explicit confirmation from the user? | `ERR-01` | Doublon avec ERR-01 (« confirmation before triggering an irreversible action ») : la confirmation sert à prévenir une erreur, règle R2. |
| `ERR-01` | Does the system provide a help section (e.g., assistance, chat, tooltips)? | `GUI-05` | L'aide consultable relève d'Aide et documentation : règle R8. |
| `ERR-03` | Do error messages provide guidance on how to correct the error? | `ERR-02` | Doublon avec ERR-02 : le contenu du message relève de la qualité des messages, règle R2. |

## Questions proposées


**`WKL-01`**

- [ ] Are labels, titles and texts short while remaining explicit?
- [ ] Are units of measure part of the field label rather than entered by the user?
- [ ] Are codes and abbreviations short and consistent?
- [ ] Do fields offer relevant default values when the value can be anticipated?
- [ ] Is the size of input fields consistent with the expected length of the data?

**`WKL-02`**

- [ ] Are options, actions and commands visible rather than hidden or to be remembered?
- [ ] Is information entered in a previous step recalled when needed (e.g., summary before validation)?
- [ ] Do form fields keep a visible label once filled in (no placeholder-only labels)?
- [ ] Are history, recent items or suggestions (e.g., autocomplete) offered?
- [ ] Is the user's location always visible (breadcrumb, active menu item, step indicator)?

**`WKL-03`**

- [ ] Can key tasks be completed with a minimum number of clicks or screens?
- [ ] Does the system avoid asking for data it already knows or can deduce (e.g., city from postcode)?
- [ ] Are bulk actions available for repetitive operations on several items?

**`WKL-04`**

- [ ] Is the main task of each screen immediately identifiable?
- [ ] Is there a clear visual hierarchy with one primary call-to-action per screen?
- [ ] Are elements unrelated to the task (ads, pop-ups, autoplaying media, promotions) absent from task flows or easy to dismiss?
- [ ] Are notifications and alerts proportionate to their importance and non-intrusive?
- [ ] Can the user complete a flow without being interrupted (e.g., surveys, cross-selling)?

**`CPT-02`**

- [ ] Have the contexts of use been identified (place, device, mobility, environment, time constraints)?
- [ ] Is the interface usable in real conditions of use (e.g., outdoors with glare, one-handed on mobile, noisy environment)?
- [ ] Are formats adapted to the cultural and linguistic context (dates, currencies, addresses, reading direction)?
- [ ] Does the interface support interrupted use (resuming later, offline mode if relevant)?
- [ ] Is the interface suited to shared or public contexts (privacy of displayed data)?

**`CPT-03`**

- [ ] Is the purpose of the product or service understandable within a few seconds on the entry page?
- [ ] Do affordances (buttons, visuals, wording) make the possible uses explicit?
- [ ] Can users achieve their main goals end to end?
- [ ] Do the features match the needs identified for the target users?
- [ ] Do additional features exceed expectations without cluttering the core experience?

**`VIS-01`**

- [ ] Does the visual hierarchy (size, weight, color, position) reflect the importance of information?
- [ ] Is a grid and alignment system applied consistently?
- [ ] Is white space used to structure content?
- [ ] Is color never the only means of conveying information?
- [ ] Are interactive elements visually distinguishable from static content?

**`VIS-02`**

- [ ] Is the overall look pleasant and professional for the target audience?
- [ ] Is the visual style consistent with the brand and the values it conveys?
- [ ] Are images, illustrations and icons of good quality and in a consistent style?
- [ ] Do animations and micro-interactions bring pleasure without hindering the task?

## Définitions et heuristiques corrigées

**GUI-01**

- Avant : Encourage the user to perform specific actions by providing indices. For example, guide data entries indicating the correct format and acceptable values: Date (dd / mm / yy) _ _ / _ _ / _ _. See this example of incitement ... missed! But as another example, successful.

Can also see this example where the incentive is so bad that we must tell the user where to click!
- Après : Encourage the user to perform specific actions by providing cues. For example, guide data entry by indicating the correct format and acceptable values: Date (dd / mm / yy) _ _ / _ _ / _ _.

**VIS**

- Avant : (vide)
- Après : Visual design serves two purposes: improving usability by making the interface more understandable, consistent and guiding, and making the interface aesthetically pleasing. Visual choices (e.g., colours) also affect the user experience through the values they convey (Arhippainen).

**Kaniasty's CARMEL Guidelines / Recovery_Confirmation dialogs** : Le texte d'origine était une copie de « Accessibility_Font size ».

- Avant : The design meets minimum font size legibility guidelines.
- Après : Confirmation dialogs prevent unintended destructive or irreversible actions.

**Colombo & Pasch's** : « Steep » est ambigu (souvent compris comme « difficile ») : l'intention est un apprentissage rapide et progressif.

- Avant : Challenges/Skills Balance_The system should have a steep learning curve to help novice users.
- Après : Challenges/Skills Balance_The system should have a gentle learning curve to help novice users.

## Noms corrigés

| Code | Avant | Après |
|---|---|---|
| `GUI-04` | Leagibility/Readability | Legibility / Readability |
| `CTL-01` | Actions Explicit | Explicit user actions |
| `ADA-02` | Universal Usability & User Experience (Expertise) | Universal usability & user expertise |
| `CON-01` | Consistency & Standard | Consistency & standards |
| `CPT-01` | Compatibility & Correspondance between the system and the real world | Compatibility & match with the real world |
| `CPT-02` | Design the Product or Service to Fit the Intended Contexts | Fit the intended contexts |
| `VIS-01` | Opt for a perfect visual design 1 | Visual design for usability |
| `VIS-02` | Opt for a perfect visual design 2 | Aesthetics |

## Notes

- `GUI-01` : Définition : retrait des renvois à des exemples visuels absents du fichier (« See this example… »).
- `GUI-02` : Bastien & Scapin distinguent « par la localisation » et « par le format » : indiquer le sous-type dans le constat si utile.
- `WKL-01` : La checklist d'origine était identique à celle de Minimal Actions. Concision porte sur UN élément (un libellé, un champ) : règle R3.
- `WKL-03` : Checklist réécrite : elle était identique à celle de Concision. Actions minimales porte sur le NOMBRE d'étapes, de clics ou de saisies : règle R3.
