"""
Download every finished 2026/27 Premier League match from FotMob: shots with xG, team stats,
lineups (formation, starting XI, bench, substitutions) and player match stats.

It opens FotMob in a real browser (Playwright), the same as you visiting each match page,
and saves the data each page loads. Nothing is sent anywhere else.

    python src/s0_download.py            run in the background
    python src/s0_download.py --show     open a visible browser window (use this if the first run finds nothing)

Output: raw/fotmob_pl_2026_27/, one JSON file per finished match. Run it again after each
matchday: matches already saved are skipped. Files saved by the older version of this script
(without lineups) are downloaded again once, so every match gets the new data.

Personal, non-commercial use only. Data: FotMob (xG by Opta). Please don't republish the raw files.
"""
import asyncio, json, random, sys
from pathlib import Path
from playwright.async_api import async_playwright

LEAGUE_ID = 47                                    # Premier League on FotMob
SEASON = "2026/2027"
FIXTURES_URL = f"https://www.fotmob.com/leagues/{LEAGUE_ID}/fixtures/premier-league"
OUT = Path("raw/fotmob_pl_2026_27"); OUT.mkdir(parents=True, exist_ok=True)
SHOW = "--show" in sys.argv


def walk(o):
    """Yield every dict inside a JSON value."""
    if isinstance(o, dict):
        yield o
        for v in o.values(): yield from walk(v)
    elif isinstance(o, list):
        for v in o: yield from walk(v)


def finished_matches(blobs):
    """Find finished matches (id, home, away, status.finished) anywhere in the page data."""
    found = {}
    for b in blobs:
        for d in walk(b):
            st = d.get("status")
            if "id" in d and isinstance(d.get("home"), dict) and isinstance(d.get("away"), dict) and isinstance(st, dict):
                if st.get("finished") and not st.get("cancelled") and not st.get("awarded"):
                    found[str(d["id"])] = {"id": str(d["id"]), "home": d["home"].get("name"), "away": d["away"].get("name"),
                                          "utcTime": st.get("utcTime") or d.get("utcTime"), "pageUrl": d.get("pageUrl")}
    return found


def trim(details):
    """Keep what the projects need: shots, team stats, lineups, player stats and match events."""
    content = details.get("content") or {}
    return {"general": details.get("general"), "header": details.get("header"),
            "shotmap": content.get("shotmap"), "stats": content.get("stats"),
            "lineup": content.get("lineup"), "playerStats": content.get("playerStats"),
            "matchFacts": content.get("matchFacts")}


def complete(path):
    """True if a saved match file already has the lineup and player stats."""
    try:
        d = json.load(open(path))
        return bool(d.get("lineup")) and bool(d.get("playerStats"))
    except Exception:
        return False


async def next_data(page):
    try:
        txt = await page.locator("script#__NEXT_DATA__").first.text_content(timeout=5000)
        return json.loads(txt) if txt else None
    except Exception:
        return None


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not SHOW)
        ctx = await browser.new_context(locale="en-GB", viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()

        # 1. fixture list --------------------------------------------------------------
        blobs = []
        async def grab(resp):
            if "json" in (resp.headers.get("content-type") or ""):
                try: blobs.append(await resp.json())
                except Exception: pass
        page.on("response", grab)
        print("Opening the Premier League fixtures page...")
        await page.goto(FIXTURES_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)
        nd = await next_data(page)
        if nd: blobs.append(nd)
        page.remove_listener("response", grab)
        matches = finished_matches(blobs)
        if not matches:
            print("\nNo finished matches found on the fixtures page.")
            print("Try again with:  python src/s0_download.py --show")
            (OUT / "_debug_fixtures.json").write_text(json.dumps(blobs)[:5_000_000])
            await browser.close(); return
        json.dump(sorted(matches.values(), key=lambda m: m["utcTime"] or ""), open(OUT / "_matches.json", "w"), indent=1)
        todo = [m for m in matches.values() if not complete(OUT / f"match_{m['id']}.json")]
        print(f"Found {len(matches)} finished matches; {len(matches) - len(todo)} already saved, {len(todo)} to download.\n")

        # 2. each match ------------------------------------------------------------------
        ok, failed = 0, []
        for k, m in enumerate(sorted(todo, key=lambda m: m["utcTime"] or ""), 1):
            got = {}
            async def catch(resp):
                if "matchDetails" in resp.url and resp.status == 200:
                    try: got["d"] = await resp.json()
                    except Exception: pass
            page.on("response", catch)
            url = f"https://www.fotmob.com/match/{m['id']}"
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                for _ in range(20):                       # wait up to 10 s for the match data
                    if "d" in got: break
                    await page.wait_for_timeout(500)
                d = got.get("d")
                if not d:                                 # fall back to the data built into the page
                    nd = await next_data(page)
                    pp = (nd or {}).get("props", {}).get("pageProps", {})
                    if pp.get("content"): d = pp
                if d and (d.get("content") or {}).get("shotmap"):
                    json.dump(trim(d), open(OUT / f"match_{m['id']}.json", "w"))
                    n = len(((d["content"]["shotmap"]) or {}).get("shots") or [])
                    ps = len((d["content"].get("playerStats") or {}))
                    lu = "lineup ok" if d["content"].get("lineup") else "NO lineup"
                    ok += 1; print(f"[{k}/{len(todo)}] {m['home']} v {m['away']}: {n} shots, {ps} players, {lu}")
                else:
                    failed.append(m); print(f"[{k}/{len(todo)}] {m['home']} v {m['away']}: no shot data found")
            except Exception as e:
                failed.append(m); print(f"[{k}/{len(todo)}] {m['home']} v {m['away']}: error {type(e).__name__}")
            page.remove_listener("response", catch)
            await page.wait_for_timeout(random.randint(1500, 3000))   # be gentle with the site

        await browser.close()

    saved = sorted(OUT.glob("match_*.json"))
    full = sum(complete(p) for p in saved)
    print(f"\nDone. Saved {len(saved)} of {len(matches)} matches in {OUT} ({full} with lineups and player stats).")
    if failed:
        print(f"{len(failed)} could not be read this time; run the script again to retry them"
              + ("" if SHOW else ", or use --show") + ".")

asyncio.run(main())
