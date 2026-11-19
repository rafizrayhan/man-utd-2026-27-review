"""Step 2: player season totals from FotMob player match stats + shot maps; rotation v league."""
import glob, json, collections
import pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RAW, DATA, OUT = ROOT / "raw" / "fotmob_pl_2026_27", ROOT / "data", ROOT / "out"
DATA.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)

U = "Manchester United"
FIELDS = {"minutes_played": "mins", "goals": "goals", "assists": "assists", "expected_assists": "xa",
          "chances_created": "chances", "touches": "touches", "touches_opp_box": "box_touches",
          "passes_into_final_third": "final_third_passes", "line_breaking_passes": "line_breaking",
          "dispossessed": "dispossessed", "defensive_actions": "def_actions", "matchstats.headers.tackles": "tackles",
          "interceptions": "interceptions", "recoveries": "recoveries", "dribbled_past": "dribbled_past",
          "physical_metrics_distance_covered": "distance", "physical_metrics_number_of_sprints": "sprints"}
FRAC = {"ground_duels_won": "ground_duels", "aerials_won": "aerials", "accurate_passes": "passes"}

rows, shots, rot = [], [], collections.defaultdict(list)
for f in sorted(glob.glob(f"{RAW}/match_*.json")):
    d = json.load(open(f))
    rnd = int(d["general"]["matchRound"])
    for side in ("homeTeam", "awayTeam"):
        T = d["lineup"][side]
        rot[T["name"]].append((rnd, frozenset(p["id"] for p in T["starters"])))
    for p in d["playerStats"].values():
        if p["teamName"] != U or not p["stats"]:
            continue
        r = dict(match=d["general"]["matchId"], round=rnd, player=p["name"], gk=p["isGoalkeeper"])
        for g in p["stats"]:
            for v in g["stats"].values():
                k, st = v.get("key"), v.get("stat") or {}
                if k in FIELDS:
                    r[FIELDS[k]] = st.get("value")
                if k in FRAC:
                    r[FRAC[k] + "_won"], r[FRAC[k] + "_att"] = st.get("value"), st.get("total")
        rows.append(r)
    for s in d["shotmap"]["shots"]:
        if s.get("teamId") is not None and s["playerName"] and s.get("isOwnGoal") is not True:
            shots.append(dict(match=d["general"]["matchId"], round=rnd, team_id=s["teamId"], player=s["playerName"],
                              x=s["x"], y=s["y"], xg=s["expectedGoals"], goal=s["eventType"] == "Goal",
                              pen=s["situation"] == "Penalty", situation=s["situation"]))
P = pd.DataFrame(rows).fillna(0)
P.to_csv(DATA / "mufc_player_matches.csv", index=False)

# United's FotMob team id from any United match
uid = None
for f in glob.glob(f"{RAW}/match_*.json"):
    d = json.load(open(f))
    for t in d["header"]["teams"]:
        if t["name"] == U:
            uid = t["id"]; break
    if uid: break
S = pd.DataFrame(shots)
S = S[(S.team_id == uid) & ~S.pen]
S["outside_box"] = (105 - S.x > 16.5) | ((S.y - 34).abs() > 20.16)
S.to_csv(DATA / "mufc_shots.csv", index=False)

tot = P.groupby("player").sum(numeric_only=True)
sh = S.groupby("player").agg(np_shots=("xg", "size"), np_xg=("xg", "sum"), np_goals=("goal", "sum"), outside=("outside_box", "sum"))
tot = tot.join(sh).fillna(0)
tot["xg_per_shot"] = tot.np_xg / tot.np_shots.where(tot.np_shots > 0)
tot["outside_share"] = tot.outside / tot.np_shots.where(tot.np_shots > 0)
tot["apps"] = P.groupby("player").size()
tot.sort_values("mins", ascending=False).to_csv(DATA / "mufc_players.csv")

pd.set_option("display.width", 220)
print("UNITED NON-PEN SHOTS:", len(S), "| xG/shot", round(S.xg.mean(), 3), "| outside box", f"{S.outside_box.mean():.0%}")
print(tot.sort_values("np_shots", ascending=False)[["mins", "np_shots", "outside", "np_xg", "xg_per_shot", "np_goals", "xa", "chances"]].head(10).round(2).to_string())
print()
print(tot[tot.mins >= 300].sort_values("dribbled_past", ascending=False)[["mins", "dribbled_past", "tackles", "interceptions", "recoveries", "ground_duels_won", "ground_duels_att", "aerials_won", "aerials_att"]].head(10).to_string())

# rotation: XI changes per game, every team
ch = {t: sum(len(b[1] - a[1]) for a, b in zip(sorted(v), sorted(v)[1:])) / (len(v) - 1) for t, v in rot.items()}
ch = pd.Series(ch).sort_values()
print("\nXI changes per game: United", round(ch[U], 2), "| league avg", round(ch.mean(), 2), "| rank (fewest=1)", int(ch.rank(method="min")[U]))
