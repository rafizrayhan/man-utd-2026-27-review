"""Step 1: per-team, per-match stats from the FotMob match files -> data/team_match_stats.csv and data/team_averages.csv,
plus Man United's league ranks."""
import glob, json, re
import pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RAW, DATA, OUT = ROOT / "raw" / "fotmob_pl_2026_27", ROOT / "data", ROOT / "out"
DATA.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)

KEYS = {"BallPossesion": "possession", "expected_goals": "xg", "expected_goals_open_play": "xg_open",
        "expected_goals_set_play": "xg_set", "expected_goals_on_target": "xgot", "total_shots": "shots",
        "ShotsOnTarget": "sot", "touches_opp_box": "box_touches", "big_chance": "big_chances", "corners": "corners",
        "passes": "passes", "accurate_passes": "acc_passes", "own_half_passes": "own_half_passes",
        "opposition_half_passes": "opp_half_passes", "long_balls_accurate": "long_balls", "accurate_crosses": "crosses",
        "matchstats.headers.tackles": "tackles", "interceptions": "interceptions", "clearances": "clearances",
        "fouls": "fouls", "aerials_won": "aerials", "physical_metrics_distance_covered": "distance",
        "physical_metrics_sprinting": "sprint_dist", "physical_metrics_number_of_sprints": "sprints", "Offsides": "offsides"}


def parse(v):
    """'601 (93%)' -> (601, None); '30 (81%)' needs attempts: return made and pct."""
    if v is None:
        return None, None
    m = re.match(r"\s*([\d.]+)\s*(?:\((\d+)%\))?", str(v))
    return float(m.group(1)), (float(m.group(2)) if m.group(2) else None)


rows = []
for f in sorted(glob.glob(f"{RAW}/match_*.json")):
    d = json.load(open(f))
    teams = [t["name"] for t in d["header"]["teams"]]
    score = [t["score"] for t in d["header"]["teams"]]
    rec = [dict(team=t, opp=teams[1 - i], home=i == 0, gf=score[i], ga=score[1 - i], match=d["general"]["matchId"],
                round=int(d["general"]["matchRound"])) for i, t in enumerate(teams)]
    for grp in d["stats"]["Periods"]["All"]["stats"]:
        for s in grp["stats"]:
            k = KEYS.get(s.get("key"))
            if not k or s["stats"][0] is None:
                continue
            for i in (0, 1):
                val, pct = parse(s["stats"][i])
                rec[i][k] = val
                if pct is not None and k in ("long_balls", "crosses"):
                    rec[i][k + "_att"] = round(val / pct * 100) if pct else 0
    rows += rec
M = pd.DataFrame(rows)
# opponent columns, for "against" numbers and a PPDA-style pressing proxy
O = M.set_index(["match", "team"])
M["opp_passes"] = [O.loc[(r.match, r.opp), "passes"] for r in M.itertuples()]
M["opp_own_half_passes"] = [O.loc[(r.match, r.opp), "own_half_passes"] for r in M.itertuples()]
for c in ["xg", "xgot", "shots", "sot", "box_touches", "big_chances", "xg_set", "xg_open", "corners"]:
    M[c + "_against"] = [O.loc[(r.match, r.opp), c] for r in M.itertuples()]
M.to_csv(DATA / "team_match_stats.csv", index=False)

A = M.groupby("team").mean(numeric_only=True)
A["pts"] = M.assign(p=(M.gf > M.ga) * 3 + (M.gf == M.ga)).groupby("team").p.sum()
A["long_ball_share"] = M.groupby("team").long_balls_att.sum() / M.groupby("team").passes.sum()
A["opp_half_share"] = M.groupby("team").opp_half_passes.sum() / (M.groupby("team").opp_half_passes.sum() + M.groupby("team").own_half_passes.sum())
A["ppda_proxy"] = M.groupby("team").opp_own_half_passes.sum() / (M.groupby("team").tackles.sum() + M.groupby("team").interceptions.sum() + M.groupby("team").fouls.sum())
A.to_csv(DATA / "team_averages.csv")

show = [("pts", "Points", False), ("possession", "Possession %", False), ("passes", "Passes", False),
        ("opp_half_share", "Share of passes in opp half", False), ("long_ball_share", "Long balls / passes", False),
        ("crosses_att", "Crosses attempted", False), ("box_touches", "Touches in opp box", False),
        ("shots", "Shots", False), ("xg", "xG", False), ("xg_open", "xG open play", False), ("xg_set", "xG set play", False),
        ("big_chances", "Big chances", False), ("xg_against", "xG against", True), ("shots_against", "Shots against", True),
        ("big_chances_against", "Big chances against", True), ("xg_set_against", "Set-play xG against", True),
        ("ppda_proxy", "Opp own-half passes per def action (lower = more pressing)", True),
        ("distance", "Distance (m)", False), ("sprints", "Sprints", False), ("aerials", "Aerials won", False)]
b = "Manchester United"
print(f"{'metric':52s} {'Man Utd':>9s} {'league':>9s} {'rank':>5s}")
for c, lab, low in show:
    r = A[c].rank(ascending=low, method="min")[b]
    print(f"{lab:52s} {A.loc[b, c]:9.2f} {A[c].mean():9.2f} {int(r):5d}")
print("\nmatches:", (M.team == b).sum())
print(M[M.team == b][["round", "opp", "home", "gf", "ga", "xg", "xg_against", "possession"]].to_string(index=False))
