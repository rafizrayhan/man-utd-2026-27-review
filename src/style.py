"""Shared page style: fonts (bundled in fonts/), CSS and the page() layout used by s4_pages.py."""
import asyncio
import re
import pandas as pd
from playwright.async_api import async_playwright

from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RAW, DATA, OUT = ROOT / "raw" / "fotmob_pl_2026_27", ROOT / "data", ROOT / "out"
DATA.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)
FONTDIR = ROOT / "fonts"
def _ff(fam, f, w): return f"@font-face{{font-family:{fam};src:url('{(FONTDIR / f).as_uri()}') format('woff2');font-weight:{w}}}"
FONTS = "".join([_ff("BS", "big-shoulders-display-latin-800-normal.woff2", 800), _ff("BSX", "big-shoulders-display-latin-ext-800-normal.woff2", 800)]
                + [_ff("FT", f"figtree-latin-{w}-normal.woff2", w) + _ff("FTX", f"figtree-latin-ext-{w}-normal.woff2", w) for w in (400, 500, 600, 700, 800)])
GOOD, BAD, SHOOT, KEEP, MUT = "#2bb886", "#e5534b", "#5aa9e6", "#f2a541", "#b3c0c5"
SHORT = {"Nottingham Forest": "Nott'm Forest", "Manchester City": "Man City", "Manchester United": "Man Utd",
         "Newcastle United": "Newcastle", "Tottenham Hotspur": "Spurs", "AFC Bournemouth": "Bournemouth",
         "Brighton & Hove Albion": "Brighton", "Leeds United": "Leeds", "Ipswich Town": "Ipswich",
         "Coventry City": "Coventry", "Hull City": "Hull", "Crystal Palace": "Palace"}
sh = lambda t: SHORT.get(t, t)
sgn = lambda v: f"{v:+.1f}".replace("-", "−")
col = lambda v: GOOD if v > 0 else BAD
FOOT = "Premier League 2026/27 · first 10 games · data: FotMob (Opta xG models) · own goals left out"

CSS = f"""<style>{FONTS}
*{{box-sizing:border-box;margin:0;padding:0}} body{{background:#111}}
.s{{width:1080px;height:1350px;position:relative;overflow:hidden;background:#1d2b33;color:#e8eeeb;font-family:FT,FTX,sans-serif;
   padding:70px 72px 0;display:flex;flex-direction:column;page-break-after:always}}
.k{{font-weight:700;font-size:21px;letter-spacing:.18em;text-transform:uppercase;color:{GOOD}}}
.h{{font-family:BS,BSX,sans-serif;font-weight:800;text-transform:uppercase;font-size:86px;line-height:.9;margin-top:16px}}
.sub{{font-size:25px;line-height:1.38;color:#d0dadd;margin-top:20px;max-width:900px}}
.body{{flex:1;display:flex;flex-direction:column;justify-content:center;padding:26px 0 18px}}
.foot{{flex:none;height:92px;border-top:1px solid #364850;display:flex;justify-content:space-between;align-items:center;font-size:17px;color:{MUT}}}
.foot b{{color:#e8eeeb;font-weight:700}}
.num{{font-variant-numeric:tabular-nums;font-weight:800}}
.panel{{background:#26363f;border:1px solid #364850;border-radius:20px}}
.note{{font-size:20px;line-height:1.45;color:#dbe3e6}}
</style>"""


def page(kicker, head, sub, body):
    return f"""<section class="s"><div class="k">{kicker}</div><div class="h">{head}</div><div class="sub">{sub}</div>
<div class="body">{body}</div><div class="foot"><span>{FOOT}</span><b>Rafiz Rayhan</b></div></section>"""


