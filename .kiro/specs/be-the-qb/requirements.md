# Requirements Document

## Introduction

Be the QB est un quiz Streamlit pour le hackathon NFL Big Data Bowl Paris (saison 2021, semaines 1–8). L'utilisateur voit une vraie action figée au moment du lancer, sans le ballon, et choisit le receveur à qui il lancerait. Le reveal montre la séparation de chaque receveur, la vraie cible du QB et le résultat ; après 10 actions, l'utilisateur voit son profil comparé aux ~7 200 passes du dataset.

Insight défendu (WR/TE/RB) : au lancer, le QB ne vise le receveur le plus démarqué que dans ~1/3 des cas (hasard ≈ 21 %, ordre de grandeur mesuré sur 2 matchs), et le plus démarqué est souvent une option courte. Message : « le plus démarqué n'est pas toujours la meilleure option », jamais « le QB s'est trompé ». Contrairement à la stat NGS « average separation », qui ne mesure que la cible, on mesure la séparation de toutes les options au lancer, donc le choix réel du QB face à ses alternatives.

Contraintes (steering hackathon.md) : deadline dure 16:00, solution la plus simple, Python 3.9.6, lib exterieurs autorisees, pas de tests unitaires ; textes d'interface, README et titres de graphiques en anglais.

## Glossary

- **Build_Script**: src/build_dataset.py [A], data/raw/ → data/processed/.
- **Quiz_Selector**: fonction du Build_Script qui choisit les actions du quiz (seed fixe, liste EXCLUDE).
- **Analysis_Script**: src/analysis.py [A], stats globales → summary_stats.json et assets/*.png.
- **Field_Renderer**: src/field.py [B], draw_play(players, play, reveal=False, pick_nflId=None) → plotly Figure.
- **App**: app.py [B], quiz Streamlit (streamlit==1.50.0).
- **README**: README.md en anglais, lu en premier par le jury.
- **Repo**: dépôt git public (origin Swimni/NFL-Big-Data-Bowl-2026, branche main).
- **Passe**: action de plays.csv avec passResult ∈ {C, I, IN} (S et R exclus).
- **Frame_Lancer**: première frameId dont event vaut 'pass_forward' ou 'autoevent_passforward'.
- **los_x**: x de la ligne de mêlée = absoluteYardlineNumber, ou 120 − absoluteYardlineNumber si playDirection vaut 'left'.
- **first_down_x**: min(los_x + yardsToGo, 110).
- **Option**: joueur de possessionTeam avec pff_role == 'Pass Route'.
- **Défenseur**: joueur de defensiveTeam ; le ballon (team == 'football', sans nflId) n'est ni Option ni Défenseur.
- **QB**: joueur avec pff_role == 'Pass' (1 par action) ; x_QB = x du QB à la Frame_Lancer.
- **Nom_Normalisé**: dernier mot d'un nom (séparateurs : espace et point), suffixes Jr/Sr/II/III/IV/V retirés, en minuscules, sans apostrophe (« C.Lamb » et « CeeDee Lamb » → « lamb »).
- **Cible**: Option visée par le QB (is_target = 1).
- **Cible_Unique**: Passe dont le nom extrait de playDescription correspond au Nom_Normalisé d'exactement 1 Option.
- **Action_Conservée**: Passe avec Frame_Lancer et Cible_Unique ; n_passes = nombre d'Actions_Conservées.
- **Plus_Démarqué**: Option de separation maximale de l'action (is_most_open = 1).
- **Asserts_Pipeline**: taux de Cible_Unique ≥ 90 % des Passes ; x_QB < los_x sur ≥ 95 % des Actions_Conservées ; n_options moyen entre 3 et 6.
- **Contrat_Données**: fichiers de data/processed/ produits par A et lus par B, repris tels quels dans design.md :
  - receivers.csv, 1 ligne par Option et par Action_Conservée : gameId, playId, nflId, displayName, position, jerseyNumber, x, y, separation, depth, is_target, is_most_open, n_options, passResult, coverage
  - quiz_plays.csv, 1 ligne par action du quiz : gameId, playId, offense, defense, quarter, down, yardsToGo, los_x, first_down_x, coverage, passResult, yards, target_nflId, most_open_nflId, description
  - quiz_players.csv, les 22 joueurs à la Frame_Lancer des actions du quiz, sans le ballon : gameId, playId, nflId, displayName, jerseyNumber, position, side ('off'|'def'), is_option, x, y, separation, depth, is_target, is_most_open
  - summary_stats.json : n_passes, most_open_rate, random_baseline, median_sep_target, median_sep_others, by_target_position {WR|TE|RB: n, most_open_rate}, by_coverage {man|zone: n, most_open_rate}, open_but_ignored_by_position {WR|TE|RB}
- **Utilisateur**: personne qui joue au quiz dans l'App.
- **Session**: min(10, nombre d'actions du quiz) actions tirées au hasard ; démarre au premier chargement de l'App et à chaque « Play again ».
- **Phase**: état de l'App dans st.session_state : 'question', 'reveal' ou 'final'.
- **Phrase_Neutre**: phrase factuelle en anglais (poste, numéro, separation, depth) sans jugement sur le choix du QB, ex. « Most open: TE #87 (5.1 yd) but only 2 yd downfield — the QB went for depth. »
- **QB_Instinct**: nombre de choix de l'Utilisateur égaux à la Cible, sur la taille de la Session.
- **Data_Eye**: separation moyenne des choix de l'Utilisateur vs separation moyenne des Cibles sur les mêmes actions.

## Requirements

### Requirement 1: Mesurer chaque option au lancer

**User Story:** En tant qu'analyste (A), je veux la position et la séparation de chaque Option à la Frame_Lancer, afin de comparer la Cible du QB à toutes les alternatives.

#### Acceptance Criteria

1. THE Build_Script SHALL garder uniquement la Frame_Lancer de chaque Passe, en traitant le tracking fichier par fichier.
2. WHEN playDirection vaut 'left', THE Build_Script SHALL remplacer x par 120 − x et y par 160/3 − y pour chaque joueur.
3. THE Build_Script SHALL calculer pour chaque Option separation (distance en yd au Défenseur le plus proche) et depth = x − los_x.
4. THE Build_Script SHALL marquer is_most_open = 1 sur le seul Plus_Démarqué de chaque action.
5. THE Build_Script SHALL marquer is_target = 1 sur l'Option dont le Nom_Normalisé égale le Nom_Normalisé du nom qui suit « to » ou « intended for » dans playDescription.
6. IF une Passe n'a pas de Frame_Lancer ou pas de Cible_Unique, THEN THE Build_Script SHALL exclure cette Passe.
7. IF un des Asserts_Pipeline est faux, THEN THE Build_Script SHALL s'arrêter sur une AssertionError qui affiche la valeur mesurée.

### Requirement 2: Livrer le contrat de données et le quiz

**User Story:** En tant que développeur de l'app (B), je veux des fichiers au format du Contrat_Données et une sélection de quiz automatique, afin de coder l'App sans les données brutes.

#### Acceptance Criteria

1. THE Build_Script SHALL écrire receivers.csv, quiz_plays.csv et quiz_players.csv dans data/processed/, aux colonnes du Contrat_Données.
2. THE Quiz_Selector SHALL choisir 15 à 20 Actions_Conservées ayant au moins 3 Options, avec une seed fixe (même sélection à chaque exécution).
3. THE Quiz_Selector SHALL inclure au moins 1/3 d'actions où la Cible diffère du Plus_Démarqué, et au moins 1 interception (IN).
4. THE Quiz_Selector SHALL inclure au moins une Cible WR, une TE et une RB, et au moins une action en couverture man et une en zone.
5. IF une action figure dans la liste EXCLUDE, THEN THE Quiz_Selector SHALL écarter cette action.
6. THE Repo SHALL versionner quiz_plays.csv, quiz_players.csv et summary_stats.json, et ignorer data/raw/ et data/processed/receivers.csv via .gitignore.

### Requirement 3: Chiffrer l'insight sur toutes les passes

**User Story:** En tant que membre du jury, je veux des chiffres et des graphiques calculés sur toutes les Actions_Conservées, afin de vérifier que le plus démarqué n'est pas toujours la meilleure option.

#### Acceptance Criteria

1. WHEN analysis.py s'exécute, THE Analysis_Script SHALL imprimer les statistiques et écrire data/processed/summary_stats.json avec toutes les clés du Contrat_Données.
2. THE Analysis_Script SHALL calculer most_open_rate comme la part des Actions_Conservées où la Cible est le Plus_Démarqué.
3. THE Analysis_Script SHALL calculer random_baseline comme la moyenne de 1/n_options sur les Actions_Conservées.
4. THE Analysis_Script SHALL calculer n et most_open_rate par poste de la Cible (WR, TE, RB) et par couverture (man, zone).
5. THE Analysis_Script SHALL écrire assets/most_open_vs_random.png : barres most_open_rate global, WR, TE, RB et ligne pointillée à random_baseline.
6. THE Analysis_Script SHALL écrire assets/sep_vs_depth.png : separation en fonction de depth, Cibles et non-Cibles en couleurs distinctes.

### Requirement 4: Voir l'action figée au lancer

**User Story:** En tant qu'Utilisateur, je veux voir l'action figée à la Frame_Lancer sur un terrain à l'échelle, afin de lire le jeu comme un QB.

#### Acceptance Criteria

1. THE Field_Renderer SHALL exposer draw_play(players, play, reveal=False, pick_nflId=None) qui renvoie une plotly Figure.
2. THE Field_Renderer SHALL tracer le terrain 120 × 53,3 yd, une ligne tous les 5 yd, la ligne de mêlée en bleu à los_x et la ligne du 1er down en jaune à first_down_x.
3. THE Field_Renderer SHALL limiter l'axe x à [min x − 5, max x + 5], masquer les axes et fixer un ratio 1:1.
4. THE Field_Renderer SHALL dessiner les joueurs sans le ballon, attaque et défense en deux couleurs, et étiqueter chaque Option « <position> <jerseyNumber> » (ex. « WR 88 »).
5. WHEN draw_play reçoit reveal=False, THE Field_Renderer SHALL omettre cercles de séparation, marqueur de Cible et étiquette « most open ».

### Requirement 5: Choisir un receveur sans indice

**User Story:** En tant qu'Utilisateur, je veux choisir le receveur à qui je lancerais sans indice sur la réponse, afin de tester mon instinct de QB.

#### Acceptance Criteria

1. WHEN une Session démarre, THE App SHALL tirer au hasard l'ordre des actions de la Session et stocker ordre, index, choix et Phase dans st.session_state.
2. WHILE la Phase vaut 'question', THE App SHALL afficher l'en-tête « Play 3/10 · DAL vs NYG · Q2 · 3rd & 7 · Zone » et le terrain avec reveal=False.
3. WHILE la Phase vaut 'question', THE App SHALL afficher un bouton par Option, libellé « WR #88 CeeDee Lamb », triés par y décroissant.
4. WHILE la Phase vaut 'question', THE App SHALL masquer description, résultat, separation et identité de la Cible.
5. WHEN l'Utilisateur clique sur un bouton d'Option, THE App SHALL enregistrer le choix et passer la Phase à 'reveal'.
6. IF data/processed/quiz_plays.csv est absent, THEN THE App SHALL charger tests/fixture/ et afficher le bandeau « fixture data ».

### Requirement 6: Découvrir le choix du QB

**User Story:** En tant qu'Utilisateur, je veux voir la séparation de chaque Option, la Cible du QB et le résultat, afin de comprendre que le plus démarqué n'est pas toujours la meilleure option.

#### Acceptance Criteria

1. WHEN draw_play reçoit reveal=True, THE Field_Renderer SHALL tracer autour de chaque Option un cercle de rayon égal à la separation de l'Option.
2. WHEN draw_play reçoit reveal=True, THE Field_Renderer SHALL marquer la Cible en doré, entourer l'Option pick_nflId et étiqueter le Plus_Démarqué « most open ».
3. WHILE la Phase vaut 'reveal', THE App SHALL afficher le résultat (« Complete · +14 yds », « Incomplete » ou « INTERCEPTED ») et la description.
4. WHILE la Phase vaut 'reveal', THE App SHALL afficher un tableau option / depth / separation des Options de l'action.
5. WHILE la Phase vaut 'reveal', THE App SHALL afficher une Phrase_Neutre comparant la Cible et le Plus_Démarqué.
6. WHEN l'Utilisateur clique sur « Next », THE App SHALL afficher l'action suivante en Phase 'question', ou la Phase 'final' après la dernière action.

### Requirement 7: Voir mon profil après la Session

**User Story:** En tant qu'Utilisateur, je veux un profil après 10 actions, comparé aux QB NFL, afin de situer mon instinct face au dataset.

#### Acceptance Criteria

1. WHILE la Phase vaut 'final', THE App SHALL afficher QB_Instinct, ex. « QB Instinct: 6/10 ».
2. WHILE la Phase vaut 'final', THE App SHALL afficher Data_Eye en yd.
3. WHILE la Phase vaut 'final', THE App SHALL afficher « NFL QBs threw to the most open receiver X% of the time vs Y% by chance, on N passes », avec X = most_open_rate, Y = random_baseline et N = n_passes de summary_stats.json.
4. WHEN l'Utilisateur clique sur « Play again », THE App SHALL démarrer une nouvelle Session en Phase 'question'.

### Requirement 8: Livrer un repo évaluable depuis un clone propre

**User Story:** En tant que membre du jury, je veux un README court et une App qui se lance depuis un clone propre, afin d'évaluer le projet en quelques minutes.

#### Acceptance Criteria

1. THE README SHALL présenter en anglais un titre et 3 à 5 phrases : l'outil, l'insight chiffré repris de summary_stats.json, les usages (broadcaster / fan engagement, scout).
2. THE README SHALL afficher assets/reveal.png, assets/most_open_vs_random.png et assets/sep_vs_depth.png.
3. THE README SHALL donner « How to run » en 1 ligne (pip install -r requirements.txt && streamlit run app.py) et la régénération (python src/build_dataset.py && python src/analysis.py).
4. THE README SHALL lister hypothèses et limites : tracking arrêté 0,5 s après le lancer, Cible parsée dans le texte, separation mesurée au lancer seulement.
5. THE Repo SHALL fournir requirements.txt listant pandas, numpy, plotly, matplotlib et streamlit==1.50.0.
6. WHEN le Repo est cloné dans un dossier temporaire et requirements.txt installé, THE App SHALL démarrer via python3 -m streamlit run app.py sans data/raw/ ni receivers.csv.

## Hypothèses

- Noms réels vérifiés le 21/10/2026 (inventaire express déjà fait) : coverage = plays.pff_passCoverageType en minuscules (man/zone/other), by_coverage ne garde que man et zone ; yards = prePenaltyPlayResult ; position = players.officialPosition ; équipe du tracking = colonne team (pas club) ; jerseyNumber casté en int.
- Données brutes : copie locale dans data/raw/ avec l'arborescence de la source (data/raw/tracking/tracking_<gameId>.csv), jamais commitée.
- matplotlib est ajouté à requirements.txt : analysis.py produit les PNG avec matplotlib (plotly exigerait kaleido, lib interdite). Seul écart à la liste de l'utilisateur.
- assets/reveal.png est une capture manuelle de l'écran reveal (bouton appareil photo de plotly ou capture macOS).
- by_target_position et open_but_ignored_by_position couvrent WR/TE/RB seulement ; FB et QB comptent uniquement dans les stats globales. open_but_ignored_by_position[P] = part des Actions_Conservées où le Plus_Démarqué est de poste P sans être la Cible (dénominateur : actions où le Plus_Démarqué est P). median_sep_target / median_sep_others = médiane de separation des Cibles / des autres Options.
- Zoom x : min et max portent sur les joueurs, los_x et first_down_x, pour garder les deux lignes visibles.
- Boutons triés par y décroissant (ordre visuel), jamais dans un ordre qui trahit la Cible.
- Session = min(10, nombre d'actions du quiz) : la fixture n'en a que 2. tests/fixture/ contient quiz_plays.csv, quiz_players.csv (2 fausses actions au format du Contrat_Données) et un summary_stats.json factice.
- La description (playDescription) s'affiche au reveal seulement.
- Phrase_Neutre : Cible plus profonde que le Plus_Démarqué → « … — the QB went for depth. » ; sinon formulation neutre équivalente ; depth négative → « behind the line » ; Cible = Plus_Démarqué → phrase neutre de confirmation.
- Pas de framework de test ni de property-based testing (hors scope) : la correction repose sur les Asserts_Pipeline et des commandes de vérification (python3, python3 -m streamlit, streamlit.testing.v1.AppTest en one-liner python3 -c), sans fichier de test commité.
- Jalons = tâches checkpoint de tasks.md : 14:30 checkpoint (processed complet + terrain, 3–5 actions vérifiées à l'œil ; plan B à 14:40 : figures reveal statiques + stats, sans quiz), 15:10 freeze, 15:30 clone propre + push, 15:45 soumission.
- Le Repo est déjà public (chaque push est visible immédiatement) ; gh n'est pas installé.
- Hors scope : multi-joueurs, comptes, base de données, paris/cotes, clic sur le graphique, animation, ML, tests unitaires, refactor. Streamlit Cloud seulement si tout est poussé à 15:30.
