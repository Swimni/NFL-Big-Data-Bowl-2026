"""Be the QB - a quick game: the play is frozen at the throw, who do you pick?

Reads only committed files from data/processed/, falls back to tests/fixture/.
Python 3.9 compatible.
"""
import json
import random
from pathlib import Path

import pandas as pd
import streamlit as st

from src.field import CONTESTED_MIN, OPEN_MIN, draw_play, openness

ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"
FIXTURE = ROOT / "tests" / "fixture"
SESSION_LEN = 3  # short run: the jury plays one session, not a full game
ORDINAL = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}

CSS = """
<style>
.stApp {background: radial-gradient(1200px 600px at 50% -10%, #16233d 0%, #070d18 60%);}
#MainMenu, footer, header {visibility: hidden;}
.block-container {padding-top: 1.6rem; max-width: 1150px;}
h1, h2, h3, p, span, div {color: #eaf0fa;}
.btq-title {font-size: 2.6rem; font-weight: 800; letter-spacing: -1px; margin: 0;
  background: linear-gradient(90deg, #38bdf8, #00e676); -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;}
.btq-ball {-webkit-text-fill-color: initial; background: none;}
.btq-sub {color: #93a4c0; font-size: 1.02rem; margin: .2rem 0 1rem 0;}
.btq-bar {display: flex; gap: .6rem; align-items: center; margin-bottom: .6rem;}
.btq-pill {background: rgba(255,255,255,.07); border: 1px solid rgba(255,255,255,.14);
  border-radius: 999px; padding: .3rem .9rem; font-weight: 700; font-size: .92rem;}
.btq-stars {letter-spacing: .18rem; font-size: 1.15rem;}
div.stButton > button {height: 4.6rem; border-radius: 18px; font-size: 1.05rem;
  font-weight: 800; border: 2px solid rgba(255,255,255,.18); color: #0b1220;
  background: linear-gradient(180deg, #ffffff, #d9e2f2); transition: .12s;
  box-shadow: 0 6px 18px rgba(0,0,0,.35);}
div.stButton > button:hover {transform: translateY(-3px) scale(1.02);
  border-color: #00e676; box-shadow: 0 10px 26px rgba(0,230,118,.35);}
div.stButton > button p, div.stButton > button div, div.stButton > button span
  {color: #0b1220 !important; font-weight: 800;}
.btq-banner {border-radius: 18px; padding: 1rem 1.2rem; font-size: 1.3rem;
  font-weight: 800; margin: .6rem 0 1rem 0; border: 2px solid;}
.btq-good {background: rgba(0,230,118,.14); border-color: #00e676; color: #00e676;}
.btq-miss {background: rgba(56,189,248,.12); border-color: #38bdf8; color: #38bdf8;}
.btq-cards {display: flex; gap: .8rem; flex-wrap: wrap; margin-bottom: .8rem;}
.btq-card {flex: 1 1 200px; background: rgba(255,255,255,.06); border-radius: 18px;
  padding: .9rem 1.1rem; border: 1px solid rgba(255,255,255,.14);}
.btq-card .lab {font-size: .82rem; color: #93a4c0; text-transform: uppercase;
  letter-spacing: .06rem;}
.btq-card .val {font-size: 1.7rem; font-weight: 800; margin: .1rem 0;}
.btq-card .sub {font-size: .9rem; color: #c6d2e6;}
.btq-row {display: flex; align-items: center; gap: .7rem; padding: .35rem 0;
  font-size: 1rem;}
.btq-dot {width: 13px; height: 13px; border-radius: 50%; display: inline-block;}
.btq-track {flex: 1; height: 11px; border-radius: 999px; background: rgba(255,255,255,.09);
  overflow: hidden;}
.btq-fill {height: 100%; border-radius: 999px;}
.btq-note {background: rgba(56,189,248,.10); border-left: 4px solid #38bdf8;
  border-radius: 10px; padding: .8rem 1rem; color: #d7e3f6; font-size: .98rem;}
.btq-score {font-size: 4.2rem; font-weight: 800; line-height: 1;
  background: linear-gradient(90deg, #38bdf8, #00e676); -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;}
</style>
"""


@st.cache_data
def load_data():
    """Real data when build_dataset.py has run, fixture otherwise."""
    src = PROCESSED if (PROCESSED / "quiz_plays.csv").exists() else FIXTURE
    plays = pd.read_csv(src / "quiz_plays.csv")
    players = pd.read_csv(src / "quiz_players.csv")
    stats_file = src / "summary_stats.json"
    stats = json.loads(stats_file.read_text()) if stats_file.exists() else {}
    return plays, players, stats, src.name == "fixture"


def new_session(n_plays):
    order = list(range(n_plays))
    random.shuffle(order)
    st.session_state.order = order[:min(SESSION_LEN, n_plays)]
    st.session_state.idx = 0
    st.session_state.picks = {}
    st.session_state.phase = "question"


def options_of(players, play):
    rows = players[(players.gameId == play.gameId) & (players.playId == play.playId)]
    return rows, rows[rows.is_option == 1].sort_values("y", ascending=False)


def hit(players, plays, i, pick):
    _, opts = options_of(players, plays.iloc[i])
    tgt = opts[opts.is_target == 1].iloc[0]
    return pick is not None and int(pick) == int(tgt.nflId)


def depth_words(depth):
    if depth < -0.5:
        return "behind the line"
    if depth < 1:
        return "at the line"
    return "%.0f yd downfield" % depth


def card(label, value, sub, color="#eaf0fa"):
    return ("<div class='btq-card'><div class='lab'>%s</div>"
            "<div class='val' style='color:%s'>%s</div>"
            "<div class='sub'>%s</div></div>" % (label, color, value, sub))


st.set_page_config(page_title="Be the QB", page_icon="\U0001F3C8", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)
plays, players, stats, is_fixture = load_data()

if "order" not in st.session_state:
    new_session(len(plays))

st.markdown("<p class='btq-title'><span class='btq-ball'>\U0001F3C8</span> Be the QB</p>",
            unsafe_allow_html=True)
st.markdown("<p class='btq-sub'>The play is frozen the instant the ball left the "
            "quarterback's hand. Who do you throw to?</p>", unsafe_allow_html=True)
if is_fixture:
    st.warning("fixture data - run python src/build_dataset.py to load the real plays")

# ---------------------------------------------------------------- final screen
if st.session_state.phase == "final":
    order, picks = st.session_state.order, st.session_state.picks
    hits = sum(1 for i in order if hit(players, plays, i, picks.get(i)))
    my_sep, qb_sep = [], []
    for i in order:
        _, opts = options_of(players, plays.iloc[i])
        mine = opts[opts.nflId == picks.get(i)]
        if len(mine):
            my_sep.append(float(mine.iloc[0].separation))
        qb_sep.append(float(opts[opts.is_target == 1].iloc[0].separation))
    avg_mine = sum(my_sep) / len(my_sep) if my_sep else 0.0
    avg_qb = sum(qb_sep) / len(qb_sep) if qb_sep else 0.0

    st.markdown("<div class='btq-score'>%d / %d</div>" % (hits, len(order)),
                unsafe_allow_html=True)
    st.markdown("<p class='btq-sub'>%s same read as the NFL quarterback</p>"
                % ("\u2b50" * max(hits, 1) if hits else "\u2606"),
                unsafe_allow_html=True)
    st.markdown("<div class='btq-cards'>%s%s</div>" % (
        card("Space you threw into", "%.1f yd" % avg_mine,
             "average separation of your picks", "#00e676"),
        card("The real QBs, same plays", "%.1f yd" % avg_qb,
             "they do not always take the biggest gap", "#38bdf8")),
        unsafe_allow_html=True)
    if stats:
        st.markdown("<div class='btq-note'>NFL quarterbacks threw to the most open "
                    "receiver <b>%.0f%%</b> of the time, against <b>%.0f%%</b> if the "
                    "choice were random, over <b>%s</b> passes. Space is only one input: "
                    "depth and the first down line matter too.</div>"
                    % (100 * stats.get("most_open_rate", 0),
                       100 * stats.get("random_baseline", 0),
                       "{:,}".format(int(stats.get("n_passes", 0)))),
                    unsafe_allow_html=True)
    if hits * 2 >= len(order):
        st.balloons()
    st.write("")
    if st.button("Play again", type="primary", width="stretch"):
        new_session(len(plays))
        st.rerun()
    st.stop()

# ------------------------------------------------------- question / reveal
i = st.session_state.order[st.session_state.idx]
play = plays.iloc[i]
rows, opts = options_of(players, play)
reveal = st.session_state.phase == "reveal"
pick = st.session_state.picks.get(i)

done = st.session_state.order[:st.session_state.idx]
stars = "".join("\u2b50" if hit(players, plays, j, st.session_state.picks.get(j)) else "\u2022"
                for j in done)
st.markdown("<div class='btq-bar'><span class='btq-pill'>Play %d / %d</span>"
            "<span class='btq-pill'>%s &nbsp;vs&nbsp; %s</span>"
            "<span class='btq-pill'>%s &amp; %d</span>"
            "<span class='btq-stars'>%s</span></div>"
            % (st.session_state.idx + 1, len(st.session_state.order),
               play.offense, play.defense,
               ORDINAL.get(int(play.down), "%dth" % int(play.down)), int(play.yardsToGo),
               stars), unsafe_allow_html=True)

st.plotly_chart(draw_play(rows, play, reveal=reveal, pick_nflId=pick),
                config={"displayModeBar": False, "staticPlot": False})

if not reveal:
    st.markdown("<p class='btq-sub'>White circles are your receivers, red are the "
                "defenders. Blue line: where the play started. Yellow line: the first "
                "down they need. <b>Tap a receiver.</b></p>", unsafe_allow_html=True)
    cols = st.columns(len(opts))
    for col, (_, r) in zip(cols, opts.iterrows()):
        col.button("%s #%d\n\n%s" % (r.position, int(r.jerseyNumber), r.displayName),
                   key="pick_%d" % int(r.nflId), width="stretch",
                   on_click=lambda nid=int(r.nflId): (
                       st.session_state.picks.__setitem__(i, nid),
                       st.session_state.__setitem__("phase", "reveal")))
else:
    tgt = opts[opts.is_target == 1].iloc[0]
    mo = opts[opts.is_most_open == 1].iloc[0]
    mine = opts[opts.nflId == pick].iloc[0]
    same = int(mine.nflId) == int(tgt.nflId)
    outcome = {"C": "caught it for %+d yards" % int(play.yards),
               "IN": "it was INTERCEPTED",
               "I": "the pass fell incomplete"}.get(play.passResult, "")

    st.markdown("<div class='btq-banner %s'>%s The QB threw to %s #%d %s - %s</div>"
                % ("btq-good" if same else "btq-miss",
                   "\u2714 Same read!" if same else "\u2192 Different read.",
                   tgt.position, int(tgt.jerseyNumber), tgt.displayName, outcome),
                unsafe_allow_html=True)

    st.markdown("<div class='btq-cards'>%s%s%s</div>" % (
        card("Your pick", "%s #%d" % (mine.position, int(mine.jerseyNumber)),
             "%.1f yd of space - %s" % (float(mine.separation), depth_words(float(mine.depth))),
             openness(float(mine.separation))[0]),
        card("The QB chose", "%s #%d" % (tgt.position, int(tgt.jerseyNumber)),
             "%.1f yd of space - %s" % (float(tgt.separation), depth_words(float(tgt.depth))),
             "#ffd700"),
        card("Most open", "%s #%d" % (mo.position, int(mo.jerseyNumber)),
             "%.1f yd of space - %s" % (float(mo.separation), depth_words(float(mo.depth))),
             "#facc15")), unsafe_allow_html=True)

    max_sep = max(float(opts.separation.max()), OPEN_MIN)
    bars = []
    for _, r in opts.sort_values("separation", ascending=False).iterrows():
        color, tier = openness(float(r.separation))
        tag = " \U0001F3C8" if int(r.nflId) == int(tgt.nflId) else ""
        bars.append("<div class='btq-row'><span class='btq-dot' style='background:%s'></span>"
                    "<span style='width:11rem'>%s #%d%s</span>"
                    "<span class='btq-track'><span class='btq-fill' style='width:%.0f%%;"
                    "background:%s'></span></span>"
                    "<span style='width:7.5rem;text-align:right;color:%s'><b>%.1f yd %s</b></span>"
                    "</div>" % (color, r.position, int(r.jerseyNumber), tag,
                                100.0 * float(r.separation) / max_sep, color, color,
                                float(r.separation), tier))
    st.markdown("".join(bars), unsafe_allow_html=True)
    st.caption("Space = yards to the closest defender when the ball was thrown. "
               "Open from %.1f yd, covered under %.1f yd." % (OPEN_MIN, CONTESTED_MIN))

    if int(tgt.nflId) != int(mo.nflId):
        st.markdown("<div class='btq-note'>The most open man was <b>%s #%d</b> with "
                    "%.1f yd, but only %s. The QB picked <b>%s #%d</b>: less space, "
                    "%s. The biggest gap is not always the best throw.</div>"
                    % (mo.position, int(mo.jerseyNumber), float(mo.separation),
                       depth_words(float(mo.depth)), tgt.position, int(tgt.jerseyNumber),
                       depth_words(float(tgt.depth))), unsafe_allow_html=True)
    else:
        st.markdown("<div class='btq-note'>Here the QB did take the biggest gap: "
                    "<b>%s #%d</b>, %.1f yd of space, %s.</div>"
                    % (tgt.position, int(tgt.jerseyNumber), float(tgt.separation),
                       depth_words(float(tgt.depth))), unsafe_allow_html=True)

    with st.expander("Official play description"):
        st.write(play.description)
    st.write("")
    if st.button("Next play", type="primary", width="stretch"):
        if st.session_state.idx + 1 >= len(st.session_state.order):
            st.session_state.phase = "final"
        else:
            st.session_state.idx += 1
            st.session_state.phase = "question"
        st.rerun()
