"""raw -> processed: how open every receiving option was at the moment of the throw.

Run: python3 src/build_dataset.py [--games N]

Steps
  1. download the Big Data Bowl files into data/raw/ (skipped when present)
  2. keep pass attempts (passResult C / I / IN)
  3. keep the single tracking frame of the throw, file by file
  4. normalise so the offense always moves towards +x
  5. options  = offensive players with pff_role 'Pass Route'
     defenders = every player of the defensive team (the football is excluded)
  6. separation = distance to the nearest defender, depth = x - los_x
  7. target    = name parsed out of playDescription, matched to exactly one option
  8. is_most_open = the option with the largest separation

Writes data/processed/receivers.csv, quiz_plays.csv, quiz_players.csv.
Python 3.9 compatible.
"""
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import urlopen

import numpy as np
import pandas as pd

BASE = ("https://raw.githubusercontent.com/ThompsonJamesBliss/"
        "nfl-big-data-bowl-regional-event-data/main/data")
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
META = ("games.csv", "plays.csv", "players.csv", "pffScoutingData.csv")

THROW_EVENTS = ("pass_forward", "autoevent_passforward")
PASS_RESULTS = ("C", "I", "IN")
FIELD_LEN = 120.0
FIELD_WID = 160.0 / 3.0
NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
QUIZ_SIZE = 18
QUIZ_SEED = 7

# Plays removed by hand at the 14:30 checkpoint (bad frame, unreadable picture).
EXCLUDE = []

# "pass short right to C.Lamb", "pass deep left intended for T.Hill"
TARGET_RE = re.compile(
    r"pass (?:incomplete )?(?:short |deep )?(?:left |middle |right )?"
    r"(?:to|intended for) ([A-Z][A-Za-z'\-]*\.\s?[A-Za-z'\-\.]+)")


# --------------------------------------------------------------------- download
def _fetch(rel):
    out = RAW / rel
    if out.exists() and out.stat().st_size > 0:
        return rel, out.stat().st_size, True
    out.parent.mkdir(parents=True, exist_ok=True)
    data = urlopen("%s/%s" % (BASE, rel), timeout=120).read()
    out.write_bytes(data)
    return rel, len(data), False


def ensure_raw(limit=None, workers=10):
    for rel in META:
        name, size, cached = _fetch(rel)
        print("%-22s %7.2f MB %s" % (name, size / 1e6, "cached" if cached else "downloaded"))
    games = pd.read_csv(RAW / "games.csv")
    ids = list(games["gameId"])[:limit] if limit else list(games["gameId"])
    rels = ["tracking/tracking_%d.csv" % g for g in ids]
    total, done = 0.0, 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for rel, size, cached in pool.map(_fetch, rels):
            total += size / 1e6
            done += 1
            if done % 20 == 0 or done == len(rels):
                print("tracking %d/%d  %.0f MB" % (done, len(rels), total), flush=True)
    return ids


def inventory(ids):
    """Confirm the column names this script relies on; never invent a field."""
    print("\n--- inventory ---")
    expected = {
        "plays.csv": ["passResult", "pff_passCoverageType", "prePenaltyPlayResult",
                      "possessionTeam", "defensiveTeam", "absoluteYardlineNumber"],
        "players.csv": ["officialPosition", "displayName"],
        "pffScoutingData.csv": ["pff_role"],
    }
    for name in META:
        cols = list(pd.read_csv(RAW / name, nrows=1).columns)
        print("%-22s %d cols" % (name, len(cols)))
        for col in expected.get(name, []):
            if col not in cols:
                print("   !! MISSING %s in %s" % (col, name))
    tcols = list(pd.read_csv(RAW / ("tracking/tracking_%d.csv" % ids[0]), nrows=1).columns)
    print("%-22s %s" % ("tracking", tcols))
    for col in ("team", "playDirection", "event", "frameId", "jerseyNumber"):
        if col not in tcols:
            print("   !! MISSING %s in tracking" % col)


# ------------------------------------------------------------------ name parsing
def norm_last(name):
    """'C.Lamb', 'CeeDee Lamb Jr.' -> 'lamb'"""
    parts = [p for p in re.split(r"[\s\.]+", str(name)) if p]
    parts = [p for p in parts if p.lower() not in NAME_SUFFIXES]
    return re.sub(r"[^a-z]", "", parts[-1].lower()) if parts else ""


# ---------------------------------------------------------------------- pipeline
def throw_frames(game_id, play_ids):
    """The single tracking frame of the throw for the given plays of one game."""
    path = RAW / ("tracking/tracking_%d.csv" % game_id)
    if not path.exists():
        return None
    tr = pd.read_csv(path, usecols=["gameId", "playId", "nflId", "frameId", "jerseyNumber",
                                    "team", "playDirection", "x", "y", "event"])
    tr = tr[tr.playId.isin(play_ids)]
    if tr.empty:
        return None
    ev = tr[tr.event.isin(THROW_EVENTS)].groupby("playId", as_index=False).frameId.min()
    ev = ev.rename(columns={"frameId": "throwFrame"})
    tr = tr.merge(ev, on="playId")
    tr = tr[tr.frameId == tr.throwFrame]
    # The football has no nflId: drop it, we only measure players.
    return tr[tr.nflId.notna()].drop(columns=["event", "throwFrame"])


def build(limit=None):
    OUT.mkdir(parents=True, exist_ok=True)
    ids = ensure_raw(limit=limit)
    inventory(ids)

    plays = pd.read_csv(RAW / "plays.csv", usecols=[
        "gameId", "playId", "playDescription", "quarter", "down", "yardsToGo",
        "possessionTeam", "defensiveTeam", "passResult", "prePenaltyPlayResult",
        "absoluteYardlineNumber", "pff_passCoverageType"])
    players = pd.read_csv(RAW / "players.csv", usecols=["nflId", "displayName",
                                                        "officialPosition"])
    pff = pd.read_csv(RAW / "pffScoutingData.csv",
                      usecols=["gameId", "playId", "nflId", "pff_role"])

    passes = plays[plays.passResult.isin(PASS_RESULTS) & plays.gameId.isin(ids)].copy()
    passes["coverage"] = passes.pff_passCoverageType.str.lower()
    print("\npass attempts: %d in %d games" % (len(passes), passes.gameId.nunique()))

    routes = pff[pff.pff_role == "Pass Route"].merge(players, on="nflId")
    routes["last"] = routes.displayName.map(norm_last)
    qbs = pff[pff.pff_role == "Pass"][["gameId", "playId", "nflId"]]

    # ---- targeted receiver, parsed from the play description
    passes["target_name"] = passes.playDescription.str.extract(TARGET_RE)[0]
    named = passes.dropna(subset=["target_name"]).copy()
    named["last"] = named.target_name.map(norm_last)
    match = named[["gameId", "playId", "last"]].merge(
        routes[["gameId", "playId", "nflId", "last"]], on=["gameId", "playId", "last"])
    counts = match.groupby(["gameId", "playId"]).nflId.nunique()
    unique = counts[counts == 1].index
    target = (match.set_index(["gameId", "playId"]).loc[unique, ["nflId"]]
              .reset_index().drop_duplicates(["gameId", "playId"])
              .rename(columns={"nflId": "target_nflId"}))
    rate = len(target) / float(len(passes))
    print("target name parsed: %.1f%% | matched to one option: %.1f%%"
          % (100.0 * len(named) / len(passes), 100 * rate))

    keep = passes.merge(target, on=["gameId", "playId"])

    # ---- tracking: one frame per play, game by game
    frames = []
    for n, game_id in enumerate(sorted(keep.gameId.unique()), start=1):
        sub = keep[keep.gameId == game_id]
        fr = throw_frames(game_id, set(sub.playId))
        if fr is not None:
            frames.append(fr)
        if n % 20 == 0 or n == keep.gameId.nunique():
            print("tracking read %d/%d" % (n, keep.gameId.nunique()), flush=True)
    track = pd.concat(frames, ignore_index=True)
    track["nflId"] = track.nflId.astype("int64")

    track = track.merge(keep[["gameId", "playId", "possessionTeam", "defensiveTeam",
                              "absoluteYardlineNumber", "yardsToGo", "passResult",
                              "coverage"]],
                        on=["gameId", "playId"])

    # ---- normalise: the offense always attacks towards +x
    left = track.playDirection == "left"
    track.loc[left, "x"] = FIELD_LEN - track.loc[left, "x"]
    track.loc[left, "y"] = FIELD_WID - track.loc[left, "y"]
    track["los_x"] = np.where(left, FIELD_LEN - track.absoluteYardlineNumber,
                              track.absoluteYardlineNumber)
    track["first_down_x"] = np.minimum(track.los_x + track.yardsToGo, 110.0)
    track["side"] = np.where(track.team == track.possessionTeam, "off", "def")

    route_ids = set(zip(routes.gameId, routes.playId, routes.nflId))
    track["is_option"] = [1 if k in route_ids else 0
                          for k in zip(track.gameId, track.playId, track.nflId)]
    track = track.merge(players.rename(columns={"officialPosition": "position"}),
                        on="nflId", how="left")
    track = track.merge(target, on=["gameId", "playId"])
    track["is_target"] = (track.nflId == track.target_nflId).astype(int)

    # ---- separation: distance to the nearest defender at the throw
    track["separation"] = np.nan
    track["depth"] = track.x - track.los_x
    sep_values = {}
    for (g, p), grp in track.groupby(["gameId", "playId"], sort=False):
        d = grp[grp.side == "def"]
        o = grp[grp.is_option == 1]
        if d.empty or o.empty:
            continue
        dx = o.x.values[:, None] - d.x.values[None, :]
        dy = o.y.values[:, None] - d.y.values[None, :]
        nearest = np.hypot(dx, dy).min(axis=1)
        for idx, val in zip(o.index, nearest):
            sep_values[idx] = val
    track.loc[list(sep_values), "separation"] = list(sep_values.values())

    opts = track[track.is_option == 1].copy()
    opts["n_options"] = opts.groupby(["gameId", "playId"]).nflId.transform("size")
    best = opts.loc[opts.groupby(["gameId", "playId"]).separation.idxmax()]
    most_open = best[["gameId", "playId", "nflId"]].rename(
        columns={"nflId": "most_open_nflId"})
    opts = opts.merge(most_open, on=["gameId", "playId"])
    opts["is_most_open"] = (opts.nflId == opts.most_open_nflId).astype(int)
    track = track.merge(most_open, on=["gameId", "playId"], how="left")
    track["is_most_open"] = (track.nflId == track.most_open_nflId).astype(int)

    # ---- sanity checks on the whole dataset
    n_plays = opts.groupby(["gameId", "playId"]).ngroups
    qb_frame = track.merge(qbs.rename(columns={"nflId": "qbId"}), on=["gameId", "playId"])
    qb_frame = qb_frame[qb_frame.nflId == qb_frame.qbId]
    behind = float((qb_frame.x < qb_frame.los_x).mean())
    mean_opts = float(opts.groupby(["gameId", "playId"]).size().mean())
    print("\nplays kept: %d | QB behind the line: %.1f%% | options/play: %.2f"
          % (n_plays, 100 * behind, mean_opts))
    assert rate >= 0.90, "unique target rate too low: %.3f" % rate
    assert behind >= 0.95, "QB behind the line only %.3f of plays" % behind
    assert 3.0 <= mean_opts <= 6.0, "mean options per play out of range: %.2f" % mean_opts

    receivers = opts[["gameId", "playId", "nflId", "displayName", "position",
                      "jerseyNumber", "x", "y", "separation", "depth", "is_target",
                      "is_most_open", "n_options", "passResult", "coverage"]].copy()
    receivers.to_csv(OUT / "receivers.csv", index=False)
    print("receivers.csv: %d rows" % len(receivers))

    # ---- quiz selection
    geo = track.groupby(["gameId", "playId"], as_index=False)[["los_x", "first_down_x"]].first()
    quiz = select_quiz(receivers, keep, geo)
    quiz.to_csv(OUT / "quiz_plays.csv", index=False)
    qp = track.merge(quiz[["gameId", "playId"]], on=["gameId", "playId"])
    qp = qp[["gameId", "playId", "nflId", "displayName", "jerseyNumber", "position",
             "side", "is_option", "x", "y", "separation", "depth", "is_target",
             "is_most_open"]]
    qp.to_csv(OUT / "quiz_players.csv", index=False)
    print("quiz: %d plays, %d player rows (%.1f per play)"
          % (len(quiz), len(qp), len(qp) / float(len(quiz))))
    return receivers, quiz


def select_quiz(receivers, keep, geo, n=QUIZ_SIZE, seed=QUIZ_SEED):
    """Deterministic pick: mixed positions, both coverages, at least one INT."""
    tgt = receivers[receivers.is_target == 1]
    pl = tgt[["gameId", "playId", "position", "separation", "n_options",
              "passResult", "coverage"]].rename(columns={"position": "target_position"})
    mo = receivers[receivers.is_most_open == 1][["gameId", "playId", "nflId"]]
    pl = pl.merge(mo.rename(columns={"nflId": "most_open_nflId"}), on=["gameId", "playId"])
    pl = pl.merge(tgt[["gameId", "playId", "nflId"]].rename(
        columns={"nflId": "target_nflId"}), on=["gameId", "playId"])
    pl["diff"] = pl.target_nflId != pl.most_open_nflId
    pl = pl[(pl.n_options >= 3) & pl.target_position.isin(["WR", "TE", "RB"])]
    pl = pl[~pl.set_index(["gameId", "playId"]).index.isin(EXCLUDE)]
    pl = pl.sample(frac=1.0, random_state=seed)

    need_pos = {"WR": 2, "TE": 2, "RB": 2}
    need_cov = {"man": 1, "zone": 1}
    need_in, need_diff = 1, max(1, n // 3)
    chosen = []

    def take(row):
        chosen.append(row)
        if need_pos.get(row.target_position, 0) > 0:
            need_pos[row.target_position] -= 1
        if need_cov.get(row.coverage, 0) > 0:
            need_cov[row.coverage] -= 1

    for _, r in pl.iterrows():
        if len(chosen) >= n:
            break
        wanted = ((r.passResult == "IN" and need_in > 0)
                  or need_pos.get(r.target_position, 0) > 0
                  or need_cov.get(r.coverage, 0) > 0
                  or (need_diff > 0 and r["diff"]))
        if wanted:
            if r.passResult == "IN":
                need_in = max(0, need_in - 1)
            if r["diff"]:
                need_diff = max(0, need_diff - 1)
            take(r)
    for _, r in pl.iterrows():  # fill up, skipping what is already in
        if len(chosen) >= n:
            break
        if any(c.gameId == r.gameId and c.playId == r.playId for c in chosen):
            continue
        take(r)

    # keep already carries target_nflId: only most_open_nflId comes from the selection.
    sel = pd.DataFrame(chosen)[["gameId", "playId", "most_open_nflId"]]
    out = sel.merge(keep, on=["gameId", "playId"]).merge(geo, on=["gameId", "playId"])
    out = out.rename(columns={"possessionTeam": "offense", "defensiveTeam": "defense",
                              "prePenaltyPlayResult": "yards",
                              "playDescription": "description"})
    return out[["gameId", "playId", "offense", "defense", "quarter", "down", "yardsToGo",
                "los_x", "first_down_x", "coverage", "passResult", "yards",
                "target_nflId", "most_open_nflId", "description"]]


if __name__ == "__main__":
    n = None
    if "--games" in sys.argv:
        n = int(sys.argv[sys.argv.index("--games") + 1])
    build(limit=n)
