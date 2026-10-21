---
inclusion: always
---
# Hackathon NFL Big Data Bowl Paris — règles pour toute la session
- Voici le lien avec toutes les donnees : 
https://github.com/ThompsonJamesBliss/nfl-big-data-bowl-regional-event-data/tree/main

## Priorités
- Deadline dure 16:00. Un outil qui marche et se voit vaut mieux que du code parfait. Toujours la solution la plus simple.
- Pas de questions bloquantes : fais l'hypothèse raisonnable, note-la en commentaire, continue.
- Ne modifie que les fichiers de la tâche en cours. Pas de refactor, pas de tests unitaires
- Après chaque tâche : lance la commande de vérification et montre la sortie.

## Environnement
- Python 3.9.6 : pas de `match`, pas de `int | None` dans les annotations (utiliser typing.Optional).
- Libs : pandas, numpy, plotly, matplotlib, streamlit==1.50.0 (`python3 -m pip install streamlit==1.50.0`).
- Chemins relatifs à la racine du repo (pathlib). data/raw/ n'est jamais commité.
- Développer sur 1 seul fichier de tracking, puis lancer sur tout. read_csv avec usecols (le tracking fait 865 Mo).
- UI, README et titres de graphiques en anglais (jury international).

## Pièges des données (vérifiés sur les vraies données)
- pff_role vaut 'Pass Route' et 'Coverage' (avec majuscules, contrairement au README des données).
- Lancer = première frame avec event 'pass_forward' OU 'autoevent_passforward' (les deux coexistent).
- Utiliser frameId (10 Hz), jamais `time` (précise à la seconde seulement).
- absoluteYardlineNumber = x brut de la ligne de mêlée.
- Le tracking s'arrête 5 frames (0,5 s) après le lancer : réception, YAC et plaquage ne sont PAS mesurables.
- Pas de colonne « receveur ciblé » : le nom est dans playDescription (« ... to C.Lamb », « ... intended for C.Lamb »).
- playDirection == 'left' → x = 120 − x, y = 160/3 − y, los_x = 120 − absoluteYardlineNumber. Ensuite l'attaque avance toujours vers +x.
- Le ballon est une ligne du tracking (club 'football', pas de nflId) : à exclure des joueurs.