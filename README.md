# Be the QB 🏈

![Be the QB](assets/cover.png)

**The most open receiver gets the ball only 33% of the time. Could you do better than an NFL quarterback?**
*Be the QB* drops you into a real 2021 NFL play frozen at the moment of release, with the ball hidden: you pick the WR, TE or RB you'd throw to, then see what Next Gen Stats saw (how open every option was, the QB's real target and the result).
Unlike the NGS separation stat, which only tracks the target, we measure **every receiver at release** across 3 passes, so you see who the QB passed up, and why open isn't always best (21% by pure chance).
Broadcasters get a second-screen game that teaches fans to read a defense; scouts get an *open-but-ignored* rate for every skill position.

`pip install -r requirements.txt && streamlit run app.py` · Limits: tracking ends 0.5 s after release, so no catch or YAC data; the target is parsed from the play text.

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
