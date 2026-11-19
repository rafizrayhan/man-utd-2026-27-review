"""Step 4: the 8-page carousel (1080x1350 PNGs + PDF) in a dark red, black and white theme."""
import asyncio, glob, json, collections
import numpy as np
import pandas as pd
from playwright.async_api import async_playwright

from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RAW, DATA, OUT = ROOT / "raw" / "fotmob_pl_2026_27", ROOT / "data", ROOT / "out"
DATA.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)
import sys
sys.path.insert(0, str(ROOT / "src"))
import style as ns_mod
ns_mod.FOOT = "Premier League 2026/27 · first 10 games · data: FotMob (Opta xG models)"
ns = vars(ns_mod)
U = "Manchester United"
CSS, page, GOOD, BAD, SHOOT, KEEP, MUT, sh = (ns[k] for k in ["CSS", "page", "GOOD", "BAD", "SHOOT", "KEEP", "MUT", "sh"])
# United theme: red, black and white on a dark background
RED = "#e03a2f"                      # United red, brightened slightly for a dark background
GOOD, BAD, SHOOT, KEEP = "#ffffff", RED, RED, "#bdbdbd"
INK, SUB, PANEL, LINE = "#ffffff", "#d6d6d6", "#181818", "#555555"
MUT = "#a3a3a3"
CALM = "#b9b4ab"                     # softer off-white for large filled areas
THEME = {"#1d2b33": "#111111", "#26363f": "#1b1b1b", "#364850": "#2e2e2e", "#2e3f48": "#2a1715", "#3a4d55": "#333333",
         "#b3c0c5": "#a3a3a3", "#d0dadd": "#d6d6d6", "#dbe3e6": "#d6d6d6", "#c9d4cf": "#cfcfcf", "#e8eeeb": "#ffffff",
         "#56666e": "#4a4a4a", "#9fb0b8": "#8f8f8f", "#8fa0a8": "#8a8a8a", "#6a7c84": "#555555"}

# ---------------------------------------------------------------- data
X = pd.read_csv(DATA / "xpts_table.csv")
A = pd.read_csv(DATA / "team_averages.csv", index_col=0)
S = pd.read_csv(DATA / "shots_gamestate.csv", dtype={"match": str})
P = pd.read_csv(DATA / "mufc_players.csv", index_col=0)
SP = {"FromCorner", "SetPiece", "FreeKick", "ThrowInSetPiece"}
OPEN = {"RegularPlay", "IndividualPlay", "FastBreak"}

shots_xy = []
matches = {}
for f in sorted(glob.glob(str(RAW / "match_*.json"))):
    d = json.load(open(f))
    ids = {t["id"]: t["name"] for t in d["header"]["teams"]}
    names = list(ids.values())
    if U in names:
        matches[int(d["general"]["matchRound"])] = d
    for s in d["shotmap"]["shots"]:
        if s.get("isOwnGoal"):
            continue
        team = ids[s["teamId"]]
        opp = [n for n in names if n != team][0]
        shots_xy.append(dict(team=team, opp=opp, x=s["x"], y=s["y"], xg=s["expectedGoals"], goal=s["eventType"] == "Goal",
                             sit=s["situation"]))
SX = pd.DataFrame(shots_xy)
SX["outside"] = (105 - SX.x > 16.5) | ((SX.y - 34).abs() > 20.16)
uf = SX[(SX.team == U) & (SX.sit != "Penalty")]
ua = SX[SX.opp == U]

# league ranks used on the pages
out_share = SX[SX.sit != "Penalty"].groupby("team").outside.mean()
out_n = SX[SX.sit != "Penalty"].groupby("team").outside.sum()
xgps = SX[SX.sit != "Penalty"].groupby("team").xg.mean()
op = SX[SX.sit.isin(OPEN)]
op_q = op.groupby("opp").xg.mean(); op_n = op.groupby("opp").size()
sp_for = SX[SX.sit.isin(SP)].groupby("team").xg.sum(); sp_ag = SX[SX.sit.isin(SP)].groupby("opp").xg.sum()
rk = lambda s, team=U, high=True: int(s.rank(ascending=not high, method="min")[team])
ordn = lambda n: f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"

u = X.set_index("team").loc[U]
CHECK = {}                                   # every number printed on a page, for the final check

# ---------------------------------------------------------------- drawing helpers
def tile(label, value, note, c):
    return f"""<div class="panel" style="flex:1;padding:24px 26px 22px;border-top:6px solid {c};border-radius:0 0 20px 20px">
 <div style="font-size:16px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:{c}">{label}</div>
 <div class="num" style="font-size:66px;line-height:1;margin-top:12px">{value}</div>
 <div class="note" style="font-size:18.5px;margin-top:10px">{note}</div></div>"""


def stat(label, value, note, c=INK, size=46):
    return f"""<div style="flex:1"><div style="font-size:14.5px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:{MUT}">{label}</div>
 <div class="num" style="font-size:{size}px;color:{c};line-height:1.1;margin-top:4px">{value}</div>
 <div style="font-size:16.5px;color:{SUB};margin-top:2px;line-height:1.35">{note}</div></div>"""


def half_pitch(d, X0, PS, style):
    """Vertical half pitch, goal at the top. style(row) -> (fill, fill_opacity, stroke, stroke_opacity)."""
    PW, PH = 68 * PS, (105 - X0) * PS
    L = f'stroke="{LINE}" stroke-width="2" fill="none"'
    m = lambda v: v * PS
    g = [f'<rect x="0" y="0" width="{PW}" height="{PH}" rx="6" fill="{PANEL}" {L}/>',
         f'<rect x="{m(34 - 20.16)}" y="0" width="{m(40.32)}" height="{m(16.5)}" {L}/>',
         f'<rect x="{m(34 - 9.16)}" y="0" width="{m(18.32)}" height="{m(5.5)}" {L}/>',
         f'<line x1="{m(34 - 3.66)}" y1="-6" x2="{m(34 + 3.66)}" y2="-6" stroke="{INK}" stroke-width="5"/>',
         f'<circle cx="{m(34)}" cy="{m(11)}" r="3" fill="{LINE}"/>',
         f'<path d="M {m(34 - 7.3)} {m(16.5)} A {m(9.15)} {m(9.15)} 0 0 0 {m(34 + 7.3)} {m(16.5)}" {L}/>']
    for r in d.sort_values("goal").itertuples():
        cx, cy, rad = m(68 - r.y), m(105 - max(r.x, X0)), 2.5 + 11 * r.xg ** 0.5
        fill, fo, stroke, so = style(r)
        g.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{rad:.1f}" fill="{fill}" fill-opacity="{fo}" stroke="{stroke}" stroke-opacity="{so}" stroke-width="2"/>')
    return f'<svg width="{PW:.0f}" height="{PH + 10:.0f}" viewBox="0 -10 {PW:.0f} {PH + 10:.0f}" style="overflow:visible;display:block">{"".join(g)}</svg>'


def key(items):
    return "".join(f'<span style="display:inline-flex;align-items:center;gap:8px;margin-right:22px"><i style="width:15px;height:15px;border-radius:50%;{css};display:inline-block"></i>{t}</span>' for css, t in items)


pages = []

# ================================================================ 1 cover
long_n = int(out_n[U])
CHECK.update(cover_pts=u.Pts, cover_pos=u.Pos, long_n=long_n, long_rank=rk(out_n))
cover_body = f"""<div style="display:flex;gap:18px">
 {tile("The table", f"{int(u.Pts)} pts", f"{ordn(int(u.Pos))} after 10 games, with 1 win", BAD)}
 {tile("Long shots", long_n, "shots from outside the box, the most in the league", SHOOT)}
 {tile("Leads lost", "6 pts", "thrown away from winning positions", KEEP)}</div>
<div class="panel note" style="padding:26px 30px;margin-top:22px;font-size:22px;line-height:1.5">
 Every shot, lineup and goal from United's first 10 games, set against the rest of the league.
 The numbers say this is a mid-table side that has been unlucky, with <b>three problems Pochettino can fix</b>.
 <div style="margin-top:14px;font-size:19px;color:{MUT}">Swipe →</div></div>"""
p1 = page("Premier League 2026/27 · Man United after 10 games", "Why is Man<br>United's season<br>going wrong?",
          "18th after 10 games with one win. Carrick out, Pochettino in. But was it bad luck, bad football, or both?", cover_body)
pages.append(p1.replace('class="h"', 'class="h" style="font-size:112px"', 1))

# ================================================================ 2 unlucky or bad
Xs = X.sort_values("xPts", ascending=False).reset_index(drop=True)
rows = ""
mx = 28
for i, r in Xs.iterrows():
    is_u = r.team == U
    w = lambda v: v / mx * 300 + 8
    c = RED if is_u else "#8fa0a8"
    rows += f"""<div style="display:flex;align-items:center;height:30px;{'background:#2e3f48;border-radius:6px;' if is_u else ''}">
  <div style="width:142px;font-size:16.5px;{'font-weight:800;color:' + INK if is_u else 'color:' + SUB}">{i + 1}. {sh(r.team)}</div>
  <div style="position:relative;width:320px;height:30px">
   <div style="position:absolute;left:{w(min(r.Pts, r.xPts)):.0f}px;width:{abs(w(r.Pts) - w(r.xPts)):.0f}px;top:14px;height:3px;background:{c};opacity:.55"></div>
   <div style="position:absolute;left:{w(r.xPts) - 8:.0f}px;top:7px;width:16px;height:16px;border-radius:50%;border:3px solid {c};background:#1d2b33"></div>
   <div style="position:absolute;left:{w(r.Pts) - 8:.0f}px;top:7px;width:16px;height:16px;border-radius:50%;background:{c}"></div></div>
  <div class="num" style="width:96px;text-align:right;font-size:16.5px;{'color:' + INK if is_u else 'color:' + MUT}">{int(r.Pts)} v {r.xPts:.1f}</div></div>"""
gap_rank = int((X.Pts - X.xPts).rank(method="min")[X.team == U].iloc[0])
CHECK.update(xpts=round(u.xPts, 1), xpos=u.xPos, xg=round(u.xG, 1), xga=round(u.xGA, 1), gap_rank=gap_rank)
body2 = f"""<div style="display:flex;gap:22px">
 <div class="panel" style="width:604px;flex:none;padding:20px 22px 16px">
  <div style="font-size:15px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:{MUT};margin-bottom:10px">Table by expected points</div>
  {rows}
  <div style="margin-top:12px;font-size:16px;color:{SUB}">{key([(f"background:{RED}", "points"), (f"border:3px solid {RED};background:#1d2b33", "expected points")])}</div></div>
 <div style="flex:1;min-width:0;display:flex;flex-direction:column;gap:16px">
  <div class="panel" style="padding:22px 24px">{stat("Expected points", f"{u.xPts:.1f}", f"{ordn(int(u.xPos))} on chances, not {ordn(int(u.Pos))}", INK, 52)}</div>
  <div class="panel" style="padding:22px 24px">{stat("Chances", f"{u.xG:.1f} v {u.xGA:.1f}", "xG for and against: dead level", INK, 44)}</div>
  <div class="panel" style="padding:22px 24px">{stat("Bad luck", f"−{u.xPts - u.Pts:.1f} pts", f"the {ordn(gap_rank)}-biggest gap in the league. A gap this big happens about 1 time in 11", BAD, 44)}</div></div></div>
<div class="panel note" style="padding:18px 26px;margin-top:18px;font-size:19.5px">
 <b>Verdict: both.</b> About 5 points of bad luck, but even on their chances United are a {ordn(int(u.xPos))}-place side. Luck explains the gap to mid-table, not the gap to the top four.</div>"""
pages.append(page("1 · Unlucky or bad?", "Unlucky,<br>or just bad?",
                  "Expected points rate every game by the chances both teams created, so luck is taken out.", body2))

# ================================================================ 3 long shots
CHECK.update(out_pct=round(out_share[U] * 100), lg_out=round(SX[SX.sit != 'Penalty'].outside.mean() * 100),
             xgps=round(xgps[U], 3), xgps_rank=rk(xgps, high=True))
pitch3 = half_pitch(uf, 68, 7.0, lambda r: (GOOD, 1, "#1d2b33", 1) if r.goal else ((SHOOT, .55, SHOOT, 1) if r.outside else (INK, .1, "#c9d4cf", .8)))
prow = ""
for name in ["Bryan Mbeumo", "Bruno Fernandes", "Matheus Cunha", "Marcus Rashford"]:
    r = P.loc[name]
    good = r.xg_per_shot >= 0.12
    prow += f"""<tr><td style="padding:9px 0;font-weight:700;text-align:left">{name.split()[-1]}</td><td class="num" style="text-align:center">{int(r.np_shots)}</td>
 <td class="num" style="text-align:center;color:{SHOOT}">{int(r.outside)}</td><td class="num" style="text-align:center;color:{GOOD if good else BAD}">{r.xg_per_shot:.2f}</td><td class="num" style="text-align:center">{int(r.np_goals)}</td></tr>"""
    CHECK[f"p_{name}"] = (int(r.np_shots), int(r.outside), round(r.xg_per_shot, 2), int(r.np_goals))
table3 = f"""<table style="width:100%;border-collapse:collapse;font-size:20px;text-align:right;color:#e8eeeb">
 <tr style="font-size:12.5px;letter-spacing:.06em;text-transform:uppercase;color:{MUT}"><td style="text-align:left;vertical-align:bottom;padding:0 0 8px">Player</td><td style="text-align:center;vertical-align:bottom;padding:0 0 8px;width:62px">Shots</td><td style="text-align:center;vertical-align:bottom;padding:0 0 8px;width:72px">Outside</td><td style="text-align:center;vertical-align:bottom;padding:0 0 8px;width:72px">xG/shot</td><td style="text-align:center;vertical-align:bottom;padding:0 0 8px;width:58px">Goals</td></tr>{prow}</table>"""
body3 = f"""<div style="display:flex;gap:26px;align-items:stretch">
 <div class="panel" style="flex:none;padding:22px 24px 18px">
  <div style="font-size:15px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:{MUT};margin-bottom:14px">All {len(uf)} United shots, no penalties</div>{pitch3}
  <div style="margin-top:14px;font-size:16px;color:{SUB}">{key([(f"background:{SHOOT};opacity:.8", "outside the box"), ("border:2px solid #c9d4cf", "inside"), (f"background:{GOOD}", "goal")])}</div>
  <div style="display:flex;gap:16px;margin-top:22px;border-top:1px solid #364850;padding-top:18px">{stat("Outside the box", f"{int(uf.outside.sum())} shots", f"{int(uf[uf.outside].goal.sum())} goals", SHOOT, 34)}{stat("Inside the box", f"{int((~uf.outside).sum())} shots", f"{int(uf[~uf.outside].goal.sum())} goals", INK, 34)}</div></div>
 <div style="flex:1;min-width:0;display:flex;flex-direction:column;gap:16px">
  <div class="panel" style="padding:20px 22px;display:flex;gap:10px">{stat("From distance", f"{out_share[U]:.0%}", f"of shots; league {SX[SX.sit != 'Penalty'].outside.mean():.0%}. Most in the league", SHOOT, 44)}</div>
  <div class="panel" style="padding:20px 22px;display:flex;gap:10px">{stat("Per shot", f"{xgps[U]:.2f} xG", f"{ordn(rk(xgps))} of 20. Lots of shots, few good ones", BAD, 44)}</div>
  <div class="panel" style="padding:16px 22px 12px">{table3}</div></div></div>
<div class="panel note" style="padding:18px 26px;margin-top:18px;font-size:19.5px">
 Mbeumo gets into good spots. Fernandes and Cunha shoot from distance: <b>29 of their 50 shots</b>. Fernandes is also United's main creator, with 23 chances made, and has scored both of United's penalties. All numbers here leave penalties out.</div>"""
pages.append(page("2 · Attack", "Too many<br>long shots", "United shoot more than anyone in the league. The problem is where from.", body3))

# ================================================================ 4 cut open
uo = ua[ua.sit.isin(OPEN)]
fb = SX[SX.sit == "FastBreak"].groupby("opp").xg.sum()
CHECK.update(op_shots=len(uo), op_rank=rk(op_n, high=False), op_q=round(op_q[U], 3), op_q_rank=rk(op_q),
             bca=A.loc[U, "big_chances_against"], fb_rank=rk(fb))
pitch4 = half_pitch(uo, 68, 7.0, lambda r: (BAD, 1, "#1d2b33", 1) if r.goal else (INK, .1, "#c9d4cf", .8))
body4 = f"""<div style="display:flex;gap:26px;align-items:stretch">
 <div class="panel" style="flex:none;padding:22px 24px 18px">
  <div style="font-size:15px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:{MUT};margin-bottom:14px">Open-play shots against United</div>{pitch4}
  <div style="margin-top:14px;font-size:16px;color:{SUB}">{key([("border:2px solid #c9d4cf", "shot"), (f"background:{BAD}", "goal")])} Bigger = better chance</div>
  <div style="display:flex;gap:16px;margin-top:22px;border-top:1px solid #364850;padding-top:18px">{stat("Goals conceded", int(uo.goal.sum()), "from open play", BAD, 34)}{stat("From inside the box", f"{(~uo.outside).mean():.0%}", f"of shots allowed (league {(~op.outside).mean():.0%})", INK, 34)}</div></div>
 <div style="flex:1;min-width:0;display:flex;flex-direction:column;gap:16px">
  <div class="panel" style="padding:20px 22px">{stat("Shots allowed", len(uo), f"{ordn(rk(op_n, high=False))} fewest in the league. Opponents rarely shoot", GOOD, 46)}</div>
  <div class="panel" style="padding:20px 22px">{stat("Quality allowed", f"{op_q[U]:.2f} xG", f"per shot: the worst in the league (average {op.xg.mean():.2f})", BAD, 46)}</div>
  <div class="panel" style="padding:20px 22px">{stat("Big chances allowed", f"{A.loc[U, 'big_chances_against']:.1f}", f"a game, {ordn(rk(A.big_chances_against))} most", BAD, 46)}</div></div></div>
<div class="panel note" style="padding:18px 26px;margin-top:18px;font-size:19.5px">
 It isn't counter-attacks: United are only {ordn(rk(fb))} for chances conceded on the break. Opponents work through the middle: <b>Tielemans and Mbeumo have each been dribbled past 11 times</b>, the most in the squad.</div>"""
pages.append(page("3 · Defence", "Few shots,<br>big chances", "Opponents don't shoot often against United. When they do, it's usually a good chance.", body4))

# ================================================================ 5 set pieces
sf, sa = uf[uf.sit.isin(SP)], ua[ua.sit.isin(SP)]
six_g = int(((sa[sa.goal].x >= 99.5) & ((sa[sa.goal].y - 34).abs() <= 9.16)).sum())
CHECK.update(sp_for=(len(sf), round(sf.xg.sum(), 2), int(sf.goal.sum()), rk(sp_for)), sp_ag=(len(sa), round(sa.xg.sum(), 2), int(sa.goal.sum()), rk(sp_ag)))
sty = lambda c: (lambda r: (c, 1, "#1d2b33", 1) if r.goal else (INK, .1, "#c9d4cf", .8))
block = lambda title, d, c, rank_txt, c2: f"""<div class="panel" style="flex:1;padding:20px 22px 18px">
 <div style="font-size:15px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:{c2};margin-bottom:12px">{title}</div>
 {half_pitch(d, 66, 6.0, sty(c))}
 <div style="display:flex;gap:12px;margin-top:16px">{stat("Shots", len(d), "", INK, 36)}{stat("xG", f"{d.xg.sum():.1f}", "", INK, 36)}{stat("Goals", int(d.goal.sum()), "", c, 36)}</div>
 <div style="font-size:17px;color:{SUB};margin-top:6px">{rank_txt}</div></div>"""
body5 = f"""<div style="display:flex;gap:20px">
 {block("United's set pieces", sf, GOOD, f"{ordn(rk(sp_for))} of 20 for set-piece xG created", MUT)}
 {block("Opponents' set pieces", sa, BAD, f"{ordn(rk(sp_ag))} most set-piece xG conceded", MUT)}</div>
<div class="panel note" style="padding:18px 26px;margin-top:18px;font-size:19.5px">
 Corners, free kicks and long throws. <b>{int(sa.goal.sum())} of the 19 goals United have conceded came from set pieces</b>, {six_g} of them from inside the six-yard box. Their own {len(sf)} set-piece shots have produced {int(sf.goal.sum())}.</div>"""
pages.append(page("4 · Set pieces", "Losing at<br>both ends", "Set pieces should be the easiest goals to win and the easiest to stop. United are doing neither.", body5))

# ================================================================ 6 leads lost: timelines
def timeline(d):
    names = [t["name"] for t in d["header"]["teams"]]
    home = names[0] == U
    ev = d["matchFacts"]["events"]["events"]
    G = sorted([(e["time"] + (e.get("overloadTime") or 0) * (1 if e["time"] == 90 else 0.05) if e["time"] >= 90 else e["time"] + (e.get("overloadTime") or 0) * .05,
                 e["newScore"], e) for e in ev if e["type"] == "Goal"], key=lambda g: g[0])
    end = 96
    W = 640
    xs = lambda t: min(t, end) / end * W
    segs, prev, sc = [], 0, (0, 0)
    marks = []
    for t, ns_, e in G:
        mine, theirs = (sc[0], sc[1]) if home else (sc[1], sc[0])
        segs.append((prev, t, mine - theirs)); prev, sc = t, tuple(ns_)
        mine2, theirs2 = (sc[0], sc[1]) if home else (sc[1], sc[0])
        us = (e["isHome"] == home)
        marks.append((t, us, f"{e['time']}{'+' + str(e['overloadTime']) if e.get('overloadTime') else ''}'", f"{mine2}–{theirs2}"))
    mine, theirs = (sc[0], sc[1]) if home else (sc[1], sc[0])
    segs.append((prev, end, mine - theirs))
    bars = "".join(f'<rect x="{xs(a):.1f}" y="30" width="{max(xs(b) - xs(a), 0):.1f}" height="26" fill="{CALM if df > 0 else ("#56666e" if df == 0 else BAD)}"/>' for a, b, df in segs)
    lab = ""
    for i, (t, us, mt, scr) in enumerate(marks):
        x = xs(t); up = i % 2 == 0
        lab += (f'<line x1="{x:.1f}" y1="24" x2="{x:.1f}" y2="62" stroke="{INK}" stroke-width="2"/>'
                f'<text x="{x:.1f}" y="{16 if up else 82}" text-anchor="middle" font-size="15" font-weight="700" fill="{GOOD if us else BAD}" font-family="FT,FTX,sans-serif">{mt} {scr}</text>')
    opp = names[1] if home else names[0]
    return opp, home, f'<svg width="{W}" height="92" viewBox="0 0 {W} 92" style="overflow:visible;display:block">{bars}{lab}</svg>', mine, theirs


tl = ""
for rnd in (2, 3, 6, 7):
    opp, home, svg, gf, ga = timeline(matches[rnd])
    res = "Won" if gf > ga else "Drew" if gf == ga else "Lost"
    tl += f"""<div style="display:flex;align-items:center;gap:22px;padding:12px 0;border-bottom:1px solid #364850">
 <div style="width:190px"><div style="font-size:22px;font-weight:800">{sh(opp)} <span style="color:{MUT};font-weight:400;font-size:17px">({'H' if home else 'A'})</span></div>
  <div style="font-size:17px;color:{GOOD if res == 'Won' else KEEP};font-weight:700">{res} {gf}–{ga}{'' if res == 'Won' else ' · −2 pts'}</div></div>{svg}</div>"""
lead = S[(S.team == U) & (S.state == "leading")].groupby("match").xg.agg(["size", "sum"])
lead_a = S[(S.opp == U) & (S.state == "trailing")].groupby("match").xg.agg(["size", "sum"])
drawn = [matches[r]["general"]["matchId"] for r in (3, 6, 7)]
lf, la = lead.reindex(drawn).fillna(0), lead_a.reindex(drawn).fillna(0)
CHECK.update(lead_for=(int(lf["size"].sum()), round(lf["sum"].sum(), 2)), lead_against=(int(la["size"].sum()), round(la["sum"].sum(), 2)))
body6 = f"""<div class="panel" style="padding:10px 26px 14px">{tl}
 <div style="margin-top:12px;font-size:16px;color:{SUB}">{key([(f"background:{CALM};border-radius:2px", "United ahead"), ("background:#56666e;border-radius:2px", "level"), (f"background:{BAD};border-radius:2px", "behind")])}</div></div>
<div style="display:flex;gap:16px;margin-top:16px">
 <div class="panel" style="flex:1;padding:20px 24px">{stat("United, while ahead", f"{int(lf['size'].sum())} shots", f"{lf['sum'].sum():.2f} xG in the three draws", INK, 42)}</div>
 <div class="panel" style="flex:1;padding:20px 24px">{stat("Opponents, while behind", f"{int(la['size'].sum())} shots", f"{la['sum'].sum():.2f} xG in the same spells", BAD, 42)}</div>
 <div class="panel" style="flex:1;padding:20px 24px">{stat("If they'd held on", "14 pts", "9th, level on points with Brentford", GOOD, 42)}</div></div>"""
pages.append(page("5 · Game management", "Can't hold<br>a lead", "United have led in four games and won one. Two equalisers came in stoppage time.", body6))

# ================================================================ 7 momentum
def momentum(d, rnd):
    names = [t["name"] for t in d["header"]["teams"]]
    home = names[0] == U
    data = d["matchFacts"]["momentum"]["main"]["data"]
    W, H = 900, 96
    xs = lambda m: (m - 0.5) / 91 * W
    ys = lambda v: H / 2 - v / 100 * (H / 2 - 6)
    vals = [(p["minute"], p["value"] if home else -p["value"]) for p in data]
    bw = W / 91 * 0.86
    bars = "".join(f'<rect x="{xs(m) - bw / 2:.1f}" y="{min(ys(v), H / 2):.1f}" width="{bw:.1f}" height="{abs(ys(v) - H / 2):.1f}" fill="{RED if v > 0 else "#9fb0b8"}" opacity=".9"/>' for m, v in vals)
    ev = [e for e in d["matchFacts"]["events"]["events"] if e["type"] == "Goal"]
    shade, marks, sc, prev_lead_start, late = "", "", (0, 0), None, []
    gm = lambda e: 90.5 if e["time"] >= 90 and e.get("overloadTime") else (45.5 if e["time"] == 45 and e.get("overloadTime") else e["time"])
    ev = sorted(ev, key=lambda e: (e["time"], e.get("overloadTime") or 0))
    for gi, e in enumerate(ev):
        sc = tuple(e["newScore"]); mine, theirs = (sc[0], sc[1]) if home else (sc[1], sc[0])
        t = gm(e)
        if mine > theirs and prev_lead_start is None:
            prev_lead_start = t
        if mine <= theirs and prev_lead_start is not None:
            shade += f'<rect x="{xs(prev_lead_start):.1f}" y="0" width="{xs(t) - xs(prev_lead_start):.1f}" height="{H}" fill="{GOOD}" opacity=".13"/>'
            prev_lead_start = None
        us = e["isHome"] == home
        lbl = f'{e["time"]}{"+" + str(e["overloadTime"]) if e.get("overloadTime") else ""}\' {mine}–{theirs}'
        marks += f'<line x1="{xs(t):.1f}" y1="-4" x2="{xs(t):.1f}" y2="{H + 4}" stroke="{GOOD if us else "#9a9a9a"}" stroke-width="2" stroke-dasharray="{"0" if us else "5 4"}"/>'
        if t < 80:
            marks += f'<text x="{xs(t) + 6:.1f}" y="14" font-size="15" font-weight="700" fill="{GOOD if us else "#9a9a9a"}" font-family="FT,FTX,sans-serif">{lbl}</text>'
        else:
            late.append((lbl, GOOD if us else "#9a9a9a"))
    if prev_lead_start is not None:
        shade += f'<rect x="{xs(prev_lead_start):.1f}" y="0" width="{W - xs(prev_lead_start):.1f}" height="{H}" fill="{GOOD}" opacity=".13"/>'
    if late:
        sp = "".join(f'<tspan fill="{c}">{l}</tspan>' + ('<tspan fill="#6a7c84">  ·  </tspan>' if i < len(late) - 1 else '') for i, (l, c) in enumerate(late))
        marks += f'<text x="{W - 8}" y="-12" text-anchor="end" font-size="15" font-weight="700" font-family="FT,FTX,sans-serif">{sp}</text>'
    axis = f'<line x1="0" y1="{H / 2}" x2="{W}" y2="{H / 2}" stroke="{LINE}" stroke-width="1.5"/>'
    ticks = "".join(f'<text x="{xs(m):.1f}" y="{H + 20}" text-anchor="middle" font-size="13" fill="{MUT}" font-family="FT,FTX,sans-serif">{m}\'</text>' for m in (15, 30, 45, 60, 75, 90))
    opp = names[1] if home else names[0]
    return opp, home, f'<svg width="{W}" height="{H + 24}" viewBox="0 0 {W} {H + 24}" style="overflow:visible;display:block">{shade}{axis}{bars}{marks}{ticks}</svg>'


mom = ""
notes = {3: "Everton on top in 22 of the 37 minutes United led before the 83rd-minute equaliser.",
         7: "Leeds on top in 13 of the 17 minutes United led, until the 51st-minute equaliser.",
         6: "The exception: United stayed on top, then conceded to Spurs' only shot while behind."}
for rnd in (3, 7, 6):
    opp, home, svg = momentum(matches[rnd], rnd)
    mom += f"""<div class="panel" style="padding:14px 24px 12px;margin-bottom:12px">
 <div style="font-size:22px;font-weight:800;margin-bottom:16px">{'United v ' + sh(opp) if home else sh(opp) + ' v United'}</div>{svg}
 <div style="font-size:16.5px;color:{SUB};font-style:italic;margin-top:6px">{notes[rnd]}</div></div>"""
body7 = mom + f"""<div class="panel note" style="padding:14px 24px;font-size:17px">
 {key([(f"background:{RED};border-radius:2px", "United on top"), ("background:#9fb0b8;border-radius:2px", "opponent on top"), ("background:rgba(255,255,255,.16);border:1px solid #777;border-radius:2px", "United leading (shaded)")])}
 <br>Momentum: FotMob's minute-by-minute measure of which team is threatening more. Over the season, without penalties, United's xG while leading is close to even (2.4 for, 2.6 against, Ipswich 5–2 included); the clearest problem is games like these.<br><b>It wasn't the substitutions:</b> all four changes made while ahead were like-for-like, including two forwards on at Everton at 1–0.</div>"""
pages.append(page("5 · Game management", "After they<br>score", "Two of the three leads United threw away followed the same pattern: once they went ahead, the other team took over.", body7))

# ================================================================ 8 same team, what needs fixing
slots = collections.defaultdict(collections.Counter)
coach, forms = set(), collections.Counter()
for d in matches.values():
    for side in ("homeTeam", "awayTeam"):
        T = d["lineup"][side]
        if T["name"] != U:
            continue
        coach.add(T["coach"]["name"]); forms[T["formation"]] += 1
        for p in T["starters"]:
            v = p["verticalLayout"]
            slots[(round(v["y"], 2), round(v["x"], 2))][p.get("lastName") or p["name"]] += 1
PWd, PHd = 470, 560
lineup = f'<rect x="0" y="0" width="{PWd}" height="{PHd}" rx="10" fill="{PANEL}" stroke="{LINE}" stroke-width="2"/>' \
         f'<line x1="0" y1="{PHd / 2}" x2="{PWd}" y2="{PHd / 2}" stroke="{LINE}" stroke-width="2"/><circle cx="{PWd / 2}" cy="{PHd / 2}" r="55" fill="none" stroke="{LINE}" stroke-width="2"/>' \
         f'<rect x="{PWd / 2 - 110}" y="0" width="220" height="40" fill="none" stroke="{LINE}" stroke-width="2"/>'
for (yy, xx), c in slots.items():
    cx = (1 - xx) * PWd * 0.86 + PWd * 0.07
    cy = PHd - (yy * 1.05) * PHd - 0.01 * PHd
    top = c.most_common(2)
    shared = len(top) > 1 and top[1][1] == top[0][1]
    nm = f"{top[0][0]} / {top[1][0]}" if shared else top[0][0]
    sub = f"{top[0][1]} starts each" if shared else f"{top[0][1]} of 10"
    lineup += (f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="13" fill="{KEEP if shared else RED}" stroke="#1d2b33" stroke-width="3"/>'
               f'<text x="{cx:.0f}" y="{cy + 33:.0f}" text-anchor="middle" font-size="15.5" font-weight="800" fill="{INK}" font-family="FT,FTX,sans-serif">{nm}</text>'
               f'<text x="{cx:.0f}" y="{cy + 51:.0f}" text-anchor="middle" font-size="13" fill="{MUT}" font-family="FT,FTX,sans-serif">{sub}</text>')
lineup_svg = f'<svg width="{PWd}" height="{PHd}" viewBox="0 0 {PWd} {PHd}" style="overflow:visible;display:block">{lineup}</svg>'
CHECK.update(coach=coach, forms=dict(forms))
fixes = [(SHOOT, "Better shots, not more", f"{long_n} from outside the box. Work it into the area, where Mbeumo already thrives."),
         (BAD, "Protect the middle and the six-yard box", "The worst chance quality allowed, and 6 set-piece goals conceded."),
         (KEEP, "Keep playing with a lead", "6 points lost from winning positions, 2 of them in stoppage time.")]
fx = "".join(f"""<div class="panel" style="padding:18px 22px;margin-bottom:12px;border-left:6px solid {c};border-radius:0 20px 20px 0">
 <div style="font-size:15px;font-weight:700;letter-spacing:.12em;color:{c}">FIX {i + 1}</div>
 <div style="font-size:23px;font-weight:800;margin-top:4px">{t}</div><div style="font-size:17.5px;color:{SUB};margin-top:4px;line-height:1.4">{d}</div></div>""" for i, (c, t, d) in enumerate(fixes))
body8 = f"""<div style="display:flex;gap:24px">
 <div class="panel" style="padding:18px 20px">
  <div style="font-size:15px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:{MUT};margin-bottom:12px">Carrick's most-used XI · {list(forms)[0]} in all 10 games</div>{lineup_svg}
  <div style="font-size:15.5px;color:{SUB};margin-top:12px">{key([(f"background:{RED}", "most starts"), (f"background:{KEEP}", "shared equally")])}</div></div>
 <div style="flex:1">{fx}
  <div class="panel" style="padding:18px 22px;margin-top:4px"><div style="font-size:22px;font-weight:800;line-height:1.3">Which fix should Pochettino start with?</div>
   <div style="font-size:15.5px;color:{MUT};margin-top:8px">Ten games is a small sample: tendencies, not verdicts.</div></div></div></div>"""
pages.append(page("6 · The verdict", "Pochettino's<br>to-do list", "Carrick used the same shape in all 10 games, so the problems are in how United played, not constant change. These are the fixes Pochettino inherits when he starts on 18 November.", body8))

# ---------------------------------------------------------------- render
N = len(pages)
pages = [p.replace("<b>Rafiz Rayhan</b>", f"<b>Rafiz Rayhan · {i + 1} / {N}</b>") for i, p in enumerate(pages)]
html = f"<html><head><meta charset='utf-8'>{CSS}<style>@page{{size:1080px 1350px;margin:0}} .k{{color:{RED}}} .s{{border-top:10px solid {RED}}}</style></head><body>{''.join(pages)}</body></html>"
for old, new in THEME.items():
    html = html.replace(old, new)
open(OUT / "carousel.html", "w", encoding="utf-8").write(html)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 1080, "height": 1350})
        await pg.goto((OUT / "carousel.html").as_uri()); await pg.evaluate("document.fonts.ready"); await pg.wait_for_timeout(400)
        print("fits:", await pg.evaluate("[...document.querySelectorAll('section.s')].map(s=>{const b=s.querySelector('.body');return b.scrollHeight<=b.clientHeight+1})"))
        for i, el in enumerate(await pg.query_selector_all("section.s")):
            await el.screenshot(path=str(OUT / f"page_{i + 1}.png"))
        await pg.pdf(path=str(OUT / "Man_United_Why_Is_It_Going_Wrong.pdf"), width="1080px", height="1350px", print_background=True)
        await b.close()
asyncio.run(main())
for k, v in CHECK.items():
    print(k, v)
