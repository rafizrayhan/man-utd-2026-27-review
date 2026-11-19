"""Step 3: game state for every team, from the match events (own goals included).

Clock: first half runs 0 .. 45+added1, second half continues to 90+added1+added2.
Each shot is placed on that clock and tagged with the score at that moment (for the shooting team).
Minutes in each state come from the same clock, so xG per 90 in each state is comparable across teams.
"""
import glob, json
import pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RAW, DATA, OUT = ROOT / "raw" / "fotmob_pl_2026_27", ROOT / "data", ROOT / "out"
DATA.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)

U = "Manchester United"


def clock(time, over, first_half, a1):
    over = over or 0
    return time + over if first_half else a1 + time + over


shots, spans, goals_u = [], [], []
for f in sorted(glob.glob(f"{RAW}/match_*.json")):
    d = json.load(open(f))
    home, away = [t["name"] for t in d["header"]["teams"]]
    ids = {t["id"]: t["name"] for t in d["header"]["teams"]}
    ev = d["matchFacts"]["events"]["events"]
    added = {e["time"]: e.get("minutesAddedInput") or 0 for e in ev if e["type"] == "AddedTime"}
    a1, a2 = added.get(45, 0), added.get(90, 0)
    end = 90 + a1 + a2
    # goals in order, with the score after each
    G = []
    for e in ev:
        if e["type"] != "Goal":
            continue
        first = e["time"] <= 45 and not (e["time"] == 45 and False)
        t = clock(e["time"], e.get("overloadTime"), e["time"] <= 45, a1)
        last = max(t, end) if t > end else t
        G.append((t, e["newScore"][0], e["newScore"][1], e["isHome"], e.get("ownGoal"), (e.get("player") or {}).get("name"), e["time"], e.get("overloadTime")))
    G.sort()
    end = max(end, (G[-1][0] + 1) if G else end)
    # state spans for each team
    bounds = [0] + [g[0] for g in G] + [end]
    scores = [(0, 0)] + [(g[1], g[2]) for g in G]
    for i in range(len(bounds) - 1):
        h, a = scores[i]
        for team, diff in ((home, h - a), (away, a - h)):
            spans.append(dict(match=d["general"]["matchId"], team=team, state="leading" if diff > 0 else "level" if diff == 0 else "trailing",
                              mins=bounds[i + 1] - bounds[i]))
    for s in d["shotmap"]["shots"]:
        if s.get("isOwnGoal"):
            continue
        t = clock(s["min"], s.get("minAdded"), s.get("period") == "FirstHalf", a1)
        # score just before this shot (a goal shot is taken at the goal's time: use strictly earlier goals)
        prior = [g for g in G if g[0] < t or (g[0] == t and s["eventType"] != "Goal" and False)]
        h, a = (prior[-1][1], prior[-1][2]) if prior else (0, 0)
        team = ids[s["teamId"]]
        diff = (h - a) if team == home else (a - h)
        shots.append(dict(match=d["general"]["matchId"], team=team, opp=away if team == home else home, t=round(t, 1),
                          state="leading" if diff > 0 else "level" if diff == 0 else "trailing", xg=s["expectedGoals"],
                          goal=s["eventType"] == "Goal", situation=s["situation"]))
    if U in (home, away):
        for g in G:
            goals_u.append(dict(match=d["general"]["matchId"], round=int(d["general"]["matchRound"]), home=home, away=away,
                                t=round(g[0], 1), minute=f"{g[6]}" + (f"+{g[7]}" if g[7] else "") + "'", score=f"{g[1]}-{g[2]}",
                                scorer=g[5], own_goal=bool(g[4]), for_united=(g[3] == (home == U)) != bool(g[4]) if False else None,
                                united_home=home == U))

S, SP = pd.DataFrame(shots), pd.DataFrame(spans)
S.to_csv(DATA / "shots_gamestate.csv", index=False)
mins = SP.groupby(["team", "state"]).mins.sum().unstack(fill_value=0)
xgf = S.groupby(["team", "state"]).xg.sum().unstack(fill_value=0)
opp_state = S.assign(st=S.state.map({"leading": "trailing", "trailing": "leading", "level": "level"}))
xga = opp_state.groupby(["opp", "st"]).xg.sum().unstack(fill_value=0)
xga.index.name = "team"
out = pd.concat({"mins": mins, "xgf": xgf, "xga": xga}, axis=1).fillna(0)
for st in ("leading", "level", "trailing"):
    out[("xgf90", st)] = out[("xgf", st)] / out[("mins", st)] * 90
    out[("xga90", st)] = out[("xga", st)] / out[("mins", st)] * 90
out.to_csv(DATA / "gamestate_by_team.csv")

u = out.loc[U]
print("UNITED")
for st in ("leading", "level", "trailing"):
    print(f"  {st:9s} {u[('mins', st)]:6.0f} min | xG for {u[('xgf', st)]:5.2f} ({u[('xgf90', st)]:.2f}/90) | against {u[('xga', st)]:5.2f} ({u[('xga90', st)]:.2f}/90)")
lead = out[out[("mins", "leading")] >= 90].copy()
lead["diff90"] = lead[("xgf90", "leading")] - lead[("xga90", "leading")]
print("\nxG difference per 90 while leading (teams with 90+ min leading):")
r = lead["diff90"].sort_values()
print(r.round(2).to_string())
print("United rank (worst=1):", int(r.rank(method="min")[U]), "of", len(r))
print("league while leading: xGF90 %.2f, xGA90 %.2f" % (out[("xgf", "leading")].sum() / out[("mins", "leading")].sum() * 90,
                                                      out[("xga", "leading")].sum() / out[("mins", "leading")].sum() * 90))

GU = pd.DataFrame(goals_u).sort_values(["round", "t"])
GU.to_csv(DATA / "united_goals.csv", index=False)
print("\nUnited match goals from events:")
for rnd, g in GU.groupby("round"):
    r0 = g.iloc[0]
    print(rnd, r0.home, "v", r0.away, " | ", " ; ".join(f"{x.minute} {x.score} {x.scorer}{' (OG)' if x.own_goal else ''}" for x in g.itertuples()))
