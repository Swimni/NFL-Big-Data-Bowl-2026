"""Broadcast-style pseudo-3D renderer for one play frozen at the throw.

The field is drawn in one-point perspective from a camera placed behind the
quarterback, so the picture reads like a TV angle: near players are bigger and
lower, the field converges towards the horizon. Players stand on a shadow, so
the eye instantly separates the two teams and the space around them.

Pure plotly (no streamlit import) so a figure can be written to HTML from the
command line. Python 3.9 compatible: typing.Optional, no PEP 604 unions.
"""
import math
from typing import Optional

import numpy as np
import plotly.graph_objects as go

FIELD_LEN = 120.0
FIELD_WID = 160.0 / 3.0  # 53.33 yd

# Virtual camera: behind the deepest offensive player, above the field.
CAM_BACK = 18.0
CAM_HEIGHT = 30.0
PLAYER_HEIGHT = 2.0       # yards, used for the "standing" offset
MARKER_REF = 23.0         # marker size reference, scaled by distance
ASPECT = 2.3              # width / height of the final frame

# Palette: night game, neon accents.
SKY = "#070d18"
GRASS = "#0f7a3d"
GRASS_ALT = "#0c6a35"
ENDZONE = "#0a4f29"
CHALK = "rgba(255,255,255,0.55)"
CHALK_SOFT = "rgba(255,255,255,0.22)"
LOS_COLOR = "#38bdf8"
FIRST_DOWN_COLOR = "#facc15"
DEF_COLOR = "#ff3b5c"
DEF_EDGE = "#7f0f24"
BLOCKER_COLOR = "#8fa0ba"
QB_COLOR = "#1d4ed8"
OPTION_COLOR = "#ffffff"
TARGET_COLOR = "#ffd700"
PICK_COLOR = "#22d3ee"
SHADOW = "rgba(0,0,0,0.28)"
SHADOW_R = 0.7            # yards, radius of the shadow under a player

# Separation tiers (yards to the nearest defender at the throw).
OPEN_MIN = 3.0
CONTESTED_MIN = 1.5
C_OPEN = "#00e676"
C_CONTESTED = "#ffb300"
C_COVERED = "#ff1744"


def openness(sep):
    # type: (float) -> tuple
    """Colour and plain-language label for a separation value."""
    if sep >= OPEN_MIN:
        return C_OPEN, "OPEN"
    if sep >= CONTESTED_MIN:
        return C_CONTESTED, "TIGHT"
    return C_COVERED, "COVERED"


def _camera(players, play):
    """Build the projection for this play."""
    los_x = float(play["los_x"])
    first_down_x = float(play["first_down_x"])
    x_min = min(float(min(players["x"])), los_x)
    x_max = max(float(max(players["x"])), first_down_x)
    cam_x = x_min - CAM_BACK
    cam_y = FIELD_WID / 2.0

    def dist(x):
        return max(float(x) - cam_x, 2.0)

    def proj(x, y):
        """Ground point (yards) -> screen point (tangent angles)."""
        d = dist(x)
        return ((float(y) - cam_y) / d, -CAM_HEIGHT / d)

    def rise(x):
        """Screen height of a standing player at this distance."""
        return PLAYER_HEIGHT / dist(x)

    def scale(x):
        return MARKER_REF / dist(x)

    return proj, rise, scale, dict(los_x=los_x, first_down_x=first_down_x,
                                   x_min=x_min, x_max=x_max, cam_x=cam_x)


def _path(points, close=True):
    d = "M %.5f,%.5f" % points[0]
    for pt in points[1:]:
        d += " L %.5f,%.5f" % pt
    return d + " Z" if close else d


def _ground_ellipse(proj, cx, cy, r, n=26):
    """A circle painted on the grass becomes an ellipse once projected."""
    pts = [proj(cx + r * math.cos(2 * math.pi * k / n),
                cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]
    return _path(pts)


def _band(proj, x0, x1, fill, opacity=1.0, line_width=0, line_color=None):
    pts = [proj(x0, 0.0), proj(x1, 0.0), proj(x1, FIELD_WID), proj(x0, FIELD_WID)]
    return dict(type="path", path=_path(pts), fillcolor=fill, opacity=opacity,
                line=dict(width=line_width,
                          color=line_color or "rgba(0,0,0,0)"),
                layer="below")


def _cross_line(proj, x, color, width, dash=None):
    a, b = proj(x, 0.0), proj(x, FIELD_WID)
    return dict(type="line", x0=a[0], y0=a[1], x1=b[0], y1=b[1],
                line=dict(color=color, width=width, dash=dash))


def _field_shapes(proj, geo):
    x_near = geo["cam_x"] + 9.0
    x_far = min(FIELD_LEN, geo["x_max"] + 30.0)
    shapes = [_band(proj, x_near, x_far, GRASS)]
    # Alternating 10-yard bands give an instant sense of distance.
    x = math.floor(x_near / 10.0) * 10.0
    while x < x_far:
        if int(x / 10) % 2 == 0:
            shapes.append(_band(proj, max(x, x_near), min(x + 10.0, x_far), GRASS_ALT))
        x += 10.0
    for a, b in ((0.0, 10.0), (110.0, FIELD_LEN)):
        if b > x_near and a < x_far:
            shapes.append(_band(proj, max(a, x_near), min(b, x_far), ENDZONE))
    # Yard lines every 5 yards, goal lines brighter.
    yl = math.ceil(x_near / 5.0) * 5.0
    while yl <= min(110.0, x_far):
        if yl >= 10.0:
            bright = yl in (10.0, 110.0)
            shapes.append(_cross_line(proj, yl, CHALK if bright else CHALK_SOFT,
                                      2.5 if bright else 1.2))
        yl += 5.0
    # Sidelines converge towards the horizon: this is what sells the 3D.
    for side_y in (0.0, FIELD_WID):
        a, b = proj(x_near, side_y), proj(x_far, side_y)
        shapes.append(dict(type="line", x0=a[0], y0=a[1], x1=b[0], y1=b[1],
                           line=dict(color=CHALK, width=2)))
    shapes.append(_cross_line(proj, geo["los_x"], LOS_COLOR, 4))
    shapes.append(_cross_line(proj, geo["first_down_x"], FIRST_DOWN_COLOR, 4, dash="6px,5px"))
    return shapes


def _yard_numbers(proj, geo):
    """Painted yard numbers, so the viewer reads the position on the field."""
    ann = []
    x_near = geo["cam_x"] + 9.0
    x_far = min(FIELD_LEN, geo["x_max"] + 30.0)
    for x in range(20, 101, 10):
        if not (x_near + 3 <= x <= x_far - 1):
            continue
        number = int(x - 10) if x <= 60 else int(110 - x)
        dist = max(x - geo["cam_x"], 2.0)
        size = max(9, min(17, int(260.0 / dist)))
        for side_y in (7.0, FIELD_WID - 7.0):
            pt = proj(x, side_y)
            ann.append(dict(x=pt[0], y=pt[1], text="<b>%d</b>" % number,
                            showarrow=False, yanchor="middle",
                            font=dict(color="rgba(255,255,255,0.40)", size=size)))
    return ann


def _chip(x, y, text, color, bg="rgba(5,10,20,0.72)", size=11, yanchor="bottom",
          border=False):
    return dict(x=x, y=y, text="<b>%s</b>" % text, showarrow=False, yanchor=yanchor,
                font=dict(color=color, size=size), bgcolor=bg, borderpad=3,
                bordercolor=color, borderwidth=1 if border else 0)


def _nearest_defender(opt, defense):
    d = np.hypot(defense["x"].values - float(opt["x"]),
                 defense["y"].values - float(opt["y"]))
    k = int(np.argmin(d))
    return defense.iloc[k], float(d[k])


def _player_layer(fig, proj, rise, scale, df, color, edge, name, label_mode=None,
                  symbol="circle", text_color="#0b1220", halo=None):
    """Shadow + standing marker for a group of players."""
    if not len(df):
        return [], []
    gx, gy, mx, my, sizes, labels = [], [], [], [], [], []
    for _, r in df.iterrows():
        g = proj(r["x"], r["y"])
        gx.append(g[0])
        gy.append(g[1])
        mx.append(g[0])
        my.append(g[1] + rise(r["x"]))
        sizes.append(max(12.0, min(34.0, 24.0 * scale(r["x"]))))
        labels.append(str(int(r["jerseyNumber"])))
    # Stick from the grass to the marker: the player looks planted on the field.
    shapes = [dict(type="line", x0=gx[i], y0=gy[i], x1=mx[i], y1=my[i],
                   line=dict(color="rgba(0,0,0,0.45)", width=2))
              for i in range(len(gx))]
    if halo:
        fig.add_trace(go.Scatter(x=mx, y=my, mode="markers", showlegend=False,
                                 marker=dict(size=[s * 1.8 for s in sizes],
                                             color=halo, line=dict(width=0)),
                                 hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=mx, y=my, mode="markers+text", name=name,
        marker=dict(size=sizes, color=color, symbol=symbol,
                    line=dict(color=edge, width=2)),
        text=labels if label_mode != "qb" else ["QB"] * len(mx),
        textposition="middle center",
        textfont=dict(color=text_color, size=10),
        hovertext=["%s - %s #%s" % (r["displayName"], r["position"], int(r["jerseyNumber"]))
                   for _, r in df.iterrows()],
        hoverinfo="text"))
    return shapes, list(zip(mx, my))


def draw_play(players, play, reveal=False, pick_nflId=None):
    # type: (object, object, bool, Optional[int]) -> go.Figure
    """Draw one play at the throw frame.

    players: quiz_players rows for this play (22 players, football excluded).
    play:    the matching quiz_plays row.
    reveal:  False hides separation, the QB target and the "most open" badge,
             so the question screen gives nothing away.
    pick_nflId: the option the user picked, ringed in cyan on reveal.
    """
    proj, rise, scale, geo = _camera(players, play)

    options = players[players["is_option"] == 1]
    defense = players[players["side"] == "def"]
    off_rest = players[(players["side"] == "off") & (players["is_option"] != 1)]
    qb = off_rest[off_rest["position"] == "QB"]
    blockers = off_rest[off_rest["position"] != "QB"]

    shapes = _field_shapes(proj, geo)
    ann = _yard_numbers(proj, geo)
    fig = go.Figure()

    # Shadows under every player, drawn before the markers.
    for _, r in players.iterrows():
        shapes.append(dict(type="path",
                           path=_ground_ellipse(proj, float(r["x"]), float(r["y"]),
                                                SHADOW_R, 14),
                           fillcolor=SHADOW, line=dict(width=0), layer="below"))

    # --------------------------------------------------------- reveal: space
    if reveal:
        for _, r in options.iterrows():
            sep = float(r["separation"])
            color, tier = openness(sep)
            shapes.append(dict(type="path",
                               path=_ground_ellipse(proj, float(r["x"]), float(r["y"]), sep),
                               fillcolor=color, opacity=0.20,
                               line=dict(color=color, width=2, dash="3px,4px"),
                               layer="below"))
            if len(defense):
                dfd, dist = _nearest_defender(r, defense)
                a = proj(float(r["x"]), float(r["y"]))
                b = proj(float(dfd["x"]), float(dfd["y"]))
                shapes.append(dict(type="line", x0=a[0], y0=a[1], x1=b[0], y1=b[1],
                                   line=dict(color=color, width=2, dash="2px,3px")))
                mid = proj((float(r["x"]) + float(dfd["x"])) / 2.0,
                           (float(r["y"]) + float(dfd["y"])) / 2.0)
                ann.append(_chip(mid[0], mid[1], "%.1f yd" % dist, color, size=12,
                                 yanchor="middle"))

    # ------------------------------------------------------------- players
    sticks, _ = _player_layer(fig, proj, rise, scale, defense, DEF_COLOR, DEF_EDGE,
                              "Defense", text_color="#ffffff",
                              halo="rgba(255,59,92,0.16)")
    shapes += sticks
    sticks, _ = _player_layer(fig, proj, rise, scale, blockers, BLOCKER_COLOR,
                              "#5b6b84", "Blockers", text_color="#15202f")
    shapes += sticks
    if len(qb):
        sticks, _ = _player_layer(fig, proj, rise, scale, qb, QB_COLOR, "#ffffff",
                                  "QB", label_mode="qb", symbol="square",
                                  text_color="#ffffff")
        shapes += sticks

    # Receivers stay white so they are never confused with a red defender;
    # on reveal the openness colour goes on the outline, not on the fill.
    opt_edges = [openness(float(s))[0] for s in options["separation"]] if reveal \
        else ["#0b1220"] * len(options)
    opt_halo = "rgba(255,255,255,0.18)" if not reveal else "rgba(255,255,255,0.10)"
    ox, oy, osz = [], [], []
    for _, r in options.iterrows():
        g = proj(r["x"], r["y"])
        ox.append(g[0])
        oy.append(g[1] + rise(r["x"]))
        osz.append(max(16.0, min(40.0, 30.0 * scale(r["x"]))))
        shapes.append(dict(type="line", x0=g[0], y0=g[1], x1=g[0], y1=g[1] + rise(r["x"]),
                           line=dict(color="rgba(0,0,0,0.45)", width=2)))
    fig.add_trace(go.Scatter(x=ox, y=oy, mode="markers", showlegend=False,
                             marker=dict(size=[s * 1.9 for s in osz], color=opt_halo,
                                         line=dict(width=0)), hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=ox, y=oy, mode="markers+text", name="Receivers",
        marker=dict(size=osz, color=OPTION_COLOR,
                    line=dict(color=opt_edges, width=3.5)),
        text=[str(int(j)) for j in options["jerseyNumber"]],
        textposition="middle center", textfont=dict(color="#0b1220", size=12),
        hovertext=["%s - %s #%s" % (r["displayName"], r["position"], int(r["jerseyNumber"]))
                   for _, r in options.iterrows()],
        hoverinfo="text"))

    # Labels and badges above each receiver.
    for k, (_, r) in enumerate(options.iterrows()):
        top = oy[k] + 0.015
        if reveal:
            color, tier = openness(float(r["separation"]))
            # The gap itself is written on the link line, so keep this chip short.
            ann.append(_chip(ox[k], top, "%s %d &nbsp;%s"
                             % (r["position"], int(r["jerseyNumber"]), tier), color))
        else:
            ann.append(_chip(ox[k], top, "%s %d" % (r["position"], int(r["jerseyNumber"])),
                             "#ffffff", size=12))

    # ------------------------------------------------- reveal: who got the ball
    if reveal:
        tgt = options[options["is_target"] == 1]
        mo = options[options["is_most_open"] == 1]
        if len(tgt) and len(qb):
            t = tgt.iloc[0]
            a = proj(float(qb.iloc[0]["x"]), float(qb.iloc[0]["y"]))
            b = proj(float(t["x"]), float(t["y"]))
            ann.append(dict(x=b[0], y=b[1] + rise(float(t["x"])) * 0.6,
                            ax=a[0], ay=a[1] + rise(float(qb.iloc[0]["x"])),
                            xref="x", yref="y", axref="x", ayref="y",
                            showarrow=True, arrowhead=3, arrowsize=1.3, arrowwidth=3,
                            arrowcolor=TARGET_COLOR, text=""))
            k = list(options["nflId"]).index(int(t["nflId"]))
            # Drop lower when the user picked this same man, to clear "YOUR PICK".
            same = pick_nflId is not None and int(pick_nflId) == int(t["nflId"])
            ann.append(_chip(ox[k], oy[k] - (0.058 if same else 0.030),
                             "BALL THROWN HERE", "#0b1220",
                             bg=TARGET_COLOR, size=11, yanchor="top"))
            fig.add_trace(go.Scatter(
                x=[ox[k]], y=[oy[k]], mode="markers", name="QB target",
                marker=dict(size=osz[k] * 2.1, color="rgba(0,0,0,0)", symbol="circle",
                            line=dict(color=TARGET_COLOR, width=3)),
                hoverinfo="skip"))
        if len(mo):
            k = list(options["nflId"]).index(int(mo.iloc[0]["nflId"]))
            ann.append(_chip(ox[k], oy[k] + 0.062, "MOST OPEN", "#0b1220",
                             bg=FIRST_DOWN_COLOR, size=11))
        if pick_nflId is not None and pick_nflId in list(options["nflId"]):
            k = list(options["nflId"]).index(int(pick_nflId))
            fig.add_trace(go.Scatter(
                x=[ox[k]], y=[oy[k]], mode="markers", name="Your pick",
                marker=dict(size=osz[k] * 2.7, color="rgba(0,0,0,0)",
                            line=dict(color=PICK_COLOR, width=3)),
                hoverinfo="skip"))
            ann.append(_chip(ox[k], oy[k] - 0.030, "YOUR PICK", PICK_COLOR,
                             size=11, yanchor="top", border=True))

    # Line labels, placed on the left edge of each line.
    for x_line, color, label in ((geo["los_x"], LOS_COLOR, "LINE OF SCRIMMAGE"),
                                 (geo["first_down_x"], FIRST_DOWN_COLOR, "1ST DOWN")):
        pt = proj(x_line, 0.0)
        ann.append(_chip(pt[0], pt[1], label, color, size=10, yanchor="middle"))

    # ------------------------------------------------------------- framing
    xs = list(ox) + [p for p in (proj(r["x"], r["y"])[0] for _, r in players.iterrows())]
    ys = list(oy) + [proj(r["x"], r["y"])[1] for _, r in players.iterrows()]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    span_x, span_y = x1 - x0, y1 - y0
    x0 -= 0.07 * span_x
    x1 += 0.07 * span_x
    y0 -= 0.12 * span_y
    y1 += 0.26 * span_y
    # Keep a predictable widescreen frame without distorting the perspective.
    w, h = x1 - x0, y1 - y0
    if w / h < ASPECT:
        extra = (ASPECT * h - w) / 2.0
        x0 -= extra
        x1 += extra
    else:
        # Give the spare height to the far side: empty foreground grass looks dead.
        extra = w / ASPECT - h
        y0 -= 0.25 * extra
        y1 += 0.75 * extra

    ordinal = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}.get(
        int(play["down"]), "%dth" % int(play["down"]))
    ann.append(dict(xref="paper", yref="paper", x=0.012, y=0.975, xanchor="left",
                    yanchor="top", showarrow=False,
                    text="<b>%s</b> vs <b>%s</b>   Q%d   %s & %d   %s coverage"
                         % (play["offense"], play["defense"], int(play["quarter"]),
                            ordinal, int(play["yardsToGo"]),
                            str(play["coverage"]).capitalize()),
                    font=dict(color="rgba(255,255,255,0.92)", size=13),
                    bgcolor="rgba(5,10,20,0.55)", borderpad=6))

    fig.update_layout(
        shapes=shapes, annotations=ann,
        xaxis=dict(range=[x0, x1], visible=False, constrain="domain", fixedrange=True),
        yaxis=dict(range=[y0, y1], visible=False, scaleanchor="x", scaleratio=1,
                   fixedrange=True),
        plot_bgcolor=SKY, paper_bgcolor=SKY,
        margin=dict(l=0, r=0, t=0, b=0), height=520,
        showlegend=False,
        hoverlabel=dict(bgcolor="rgba(5,10,20,0.9)", font=dict(color="#ffffff")))
    return fig
