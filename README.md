# Be the QB — who was open at the throw?

A real NFL play is frozen at the exact frame the ball left the quarterback's hand. The ball is hidden. You pick the receiver you would throw to, then the app reveals how much space each option really had, who the QB chose, and what happened.

Over **7,234 pass attempts** (2021, weeks 1–8), NFL quarterbacks threw to the **most open** receiver **31%** of the time, against **22%** if the pick were random. The targeted man had **3.3 yd** of separation, the options left behind **2.6 yd**. By position: when a **RB** is the most open man he gets the ball **52%** of the time, a **WR** only **25%** — the biggest gap is usually the shallowest one. So the most open receiver is not always the best throw.

## Play it

```bash
pip install -r requirements.txt && streamlit run app.py
```

3 plays per run, one tap per play. Nothing to download: the app reads the plays committed in `data/processed/`.

Each play is shown from behind the quarterback at the frame of the release: white circles are the receivers, red are the defenders, the blue line is the line of scrimmage and the yellow one the first down. You tap a receiver, and the reveal below appears — green ring = open, orange = tight, red = covered, the dotted line runs to the closest defender and carries the gap in yards, the gold arrow is the throw the QB actually made. After 3 plays you get your score: how often you read the play like the QB, and the average space you threw into versus his.

![Reveal screen](assets/reveal.png)

## The numbers behind it

![How often the QB threw to the most open receiver](assets/most_open_vs_random.png)

![Separation versus depth](assets/sep_vs_depth.png)

Regenerate everything from the raw tracking data (downloads ~850 MB into `data/raw/`, git-ignored):

```bash
python src/build_dataset.py && python src/analysis.py
```

## Method and limits

- Pass attempts only (`passResult` C / I / IN). The throw is the first frame tagged `pass_forward` or `autoevent_passforward`; only that frame is used. Plays going left are mirrored so the offense always attacks `+x`.
- Options = offensive players with PFF `pff_role == 'Pass Route'`. `separation` = distance to the nearest defender of the defensive team. `depth` = yards past the line of scrimmage.
- The targeted receiver is parsed from `playDescription` ("… to C.Lamb") and matched by last name to exactly one route runner; 95.7% of attempts match, the rest are dropped.
- **The tracking stops 0.5 s after the throw**, so the catch, the yards after catch and the tackle cannot be measured here. Everything is measured at the release.
- Separation is a geometric distance at one instant: it ignores closing speed, leverage and coverage responsibility. A wide-open man is not always a possible throw, and this project never claims the QB was wrong.

Data: [NFL Big Data Bowl regional event data](https://github.com/ThompsonJamesBliss/nfl-big-data-bowl-regional-event-data) (Next Gen Stats tracking + PFF scouting).
