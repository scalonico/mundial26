"""World Cup history — load + query the complete 1930–2026 match archive.

Powers the archive tab. National names are kept HISTORICALLY accurate in the data (West Germany,
Soviet Union, Yugoslavia, Czechoslovakia, Zaire, Dutch East Indies…); aggregates fold the four
uncontroversial continuations — West Germany → Germany, USA → United States (FIFA-standard),
Czech Republic → Czechia (renamed 2016) and Zaire → DR Congo (renamed 1997) — via fold().
Penalty-shootout knockouts count as DRAWS in the W-D-L table (FIFA convention); titles are tracked
separately. Flags via flagcdn; historical sides map to their nearest modern flag.

TWO SOURCES, joined at load time by matches():
  1930–2022  data/worldcup_matches.csv  — a build artifact of build/history/openfootball_wc.py
  2026       data/wc2026_matches.csv    — the same file the 2026 tabs read

2026 is deliberately NOT baked into worldcup_matches.csv: that builder opens the file with "w" and
rewrites it from scratch, so appended rows would be silently wiped on the next rebuild. Deriving the
48-team edition here instead keeps ONE source of truth per tournament and cannot drift.
"""
from functools import lru_cache
from pathlib import Path

import pandas as pd

_DATA = Path(__file__).resolve().parent / "data"
_CSV = _DATA / "worldcup_matches.csv"
_CSV_2026 = _DATA / "wc2026_matches.csv"
_CSV_2026_TEAMS = _DATA / "wc2026_teams.csv"

# name → ISO 3166-1 alpha-2 (gb-eng/sct/wls/nir for the home nations; historical sides → nearest flag).
ISO2 = {
    "Algeria": "dz", "Angola": "ao", "Argentina": "ar", "Australia": "au", "Austria": "at",
    "Belgium": "be", "Bolivia": "bo", "Bosnia-Herzegovina": "ba", "Brazil": "br", "Bulgaria": "bg",
    "Cameroon": "cm", "Canada": "ca", "Cape Verde": "cv", "Chile": "cl", "China": "cn",
    "Colombia": "co", "Costa Rica": "cr", "Croatia": "hr", "Cuba": "cu", "Curaçao": "cw",
    "Czech Republic": "cz", "Czechia": "cz", "Czechoslovakia": "cz",
    "Côte d'Ivoire": "ci", "DR Congo": "cd", "Denmark": "dk", "Dutch East Indies": "id",
    "East Germany": "de",
    "Ecuador": "ec", "Egypt": "eg", "El Salvador": "sv", "England": "gb-eng", "France": "fr",
    "Germany": "de", "Ghana": "gh", "Greece": "gr", "Haiti": "ht", "Honduras": "hn", "Hungary": "hu",
    "Iceland": "is", "Iran": "ir", "Iraq": "iq", "Ireland": "ie", "Israel": "il", "Italy": "it",
    "Jamaica": "jm", "Japan": "jp", "Jordan": "jo",
    "Kuwait": "kw", "Mexico": "mx", "Morocco": "ma", "Netherlands": "nl",
    "New Zealand": "nz", "Nigeria": "ng", "North Korea": "kp", "Northern Ireland": "gb-nir", "Norway": "no",
    "Panama": "pa", "Paraguay": "py", "Peru": "pe", "Poland": "pl", "Portugal": "pt", "Qatar": "qa",
    "Romania": "ro", "Russia": "ru", "Saudi Arabia": "sa", "Scotland": "gb-sct", "Senegal": "sn",
    "Serbia": "rs", "Serbia and Montenegro": "rs", "Slovakia": "sk", "Slovenia": "si", "South Africa": "za",
    "South Korea": "kr", "Soviet Union": "ru", "Spain": "es", "Sweden": "se", "Switzerland": "ch",
    "Togo": "tg", "Trinidad and Tobago": "tt", "Tunisia": "tn", "Turkey": "tr", "USA": "us",
    "Ukraine": "ua", "United Arab Emirates": "ae", "United States": "us", "Uruguay": "uy",
    "Uzbekistan": "uz", "Wales": "gb-wls",
    "West Germany": "de", "Yugoslavia": "rs", "Zaire": "cd",
}
# Continuations folded for ALL-TIME aggregates (kept historical everywhere else): each pair is ONE
# football association under two names, so their records merge. Czechoslovakia is NOT folded into
# Czechia — that was a state that split, not a rename.
FOLD = {"West Germany": "Germany", "USA": "United States",
        "Czech Republic": "Czechia", "Zaire": "DR Congo"}


def flag_url(name, w=40):
    code = ISO2.get(name) or ISO2.get(FOLD.get(name, ""), "")
    return f"https://flagcdn.com/w{w}/{code}.png" if code else ""


def fold(name):
    return FOLD.get(name, name)


COLS = ["year", "host", "stage", "group", "date", "home", "away", "home_score", "away_score",
        "extra_time", "pens_home", "pens_away", "venue", "city", "source"]

_HOST_2026 = "Canada, Mexico & United States"          # co-host precedent: 2002 = "South Korea & Japan"
_STAGE_2026 = {"group": "group", "R32": "round-of-32", "R16": "round-of-16", "QF": "quarter-final",
               "SF": "semi-final", "3rd": "third-place", "F": "final"}
# 2026 squad-list spellings → the archive's, so all-time aggregates merge without a FOLD entry.
# These are the same name written differently; genuine RENAMES (Czechia, DR Congo) go via FOLD.
_NAME_2026 = {"Bosnia and Herzegovina": "Bosnia-Herzegovina", "Ivory Coast": "Côte d'Ivoire"}


def _matches_2026():
    """The 48-team edition, mapped from the 2026 CSVs into the archive's schema."""
    m = pd.read_csv(_CSV_2026, dtype={"group": str})
    t = pd.read_csv(_CSV_2026_TEAMS)
    nm = {c: _NAME_2026.get(n, n) for c, n in zip(t["code"], t["name"])}
    return pd.DataFrame({
        "year": 2026, "host": _HOST_2026,
        "stage": m["stage"].map(_STAGE_2026),
        "group": m["group"], "date": m["date"],
        "home": m["team1"].map(nm), "away": m["team2"].map(nm),
        "home_score": m["score1"], "away_score": m["score2"],
        "extra_time": m["et"], "pens_home": m["pens1"], "pens_away": m["pens2"],
        "venue": m["stadium"], "city": m["city"], "source": "wikipedia",
    })[COLS]


@lru_cache(maxsize=1)
def matches():
    """Every World Cup match, 1930–2026 (the 2026 rows derived from the live-tab CSVs)."""
    arch = pd.read_csv(_CSV, dtype={"group": str})
    df = pd.concat([arch, _matches_2026()], ignore_index=True)
    df = df.fillna({"home_score": -1, "away_score": -1})       # unplayed → -1, as before
    df["home_score"] = df["home_score"].astype(int)
    df["away_score"] = df["away_score"].astype(int)
    df["pens_home"] = pd.to_numeric(df["pens_home"], errors="coerce")
    df["pens_away"] = pd.to_numeric(df["pens_away"], errors="coerce")
    df["group"] = df["group"].astype("object").where(df["group"].notna(), None)
    return df


def years():
    return [int(y) for y in sorted(matches()["year"].unique())]   # plain ints (numpy scalars trip widgets)


def edition_matches(year):
    return matches()[matches()["year"] == year].copy()


_PTS_3_FROM = 1994                                   # 3 points for a win since USA 1994 (2 before)


def _standings(gm, year):
    """Group standings from a slice of matches — era-correct points, sorted Pts → GD → GF."""
    win = 3 if year >= _PTS_3_FROM else 2
    agg = {}
    for r in gm.itertuples():
        for tm, gf, ga in ((r.home, r.home_score, r.away_score), (r.away, r.away_score, r.home_score)):
            a = agg.setdefault(tm, dict(P=0, W=0, D=0, L=0, GF=0, GA=0, Pts=0))
            a["P"] += 1
            a["GF"] += gf
            a["GA"] += ga
            if gf > ga:
                a["W"] += 1
                a["Pts"] += win
            elif gf < ga:
                a["L"] += 1
            else:
                a["D"] += 1
                a["Pts"] += 1
    rows = [{"team": t, **v, "GD": v["GF"] - v["GA"]} for t, v in agg.items()]
    return pd.DataFrame(rows).sort_values(["Pts", "GD", "GF"], ascending=False).reset_index(drop=True)


def edition_group_tables(year):
    """[(stage, group, standings_df, matches_df)] for every group-type stage, in order."""
    df = edition_matches(year)
    out = []
    for stage in ("group", "group-2", "final-round"):
        sub = df[df["stage"] == stage]
        if sub.empty:
            continue
        sub = sub.assign(group=sub["group"].fillna(""))
        for g in sorted(sub["group"].unique(), key=lambda s: (len(str(s)), str(s))):
            gm = sub[sub["group"] == g]
            out.append((stage, str(g), _standings(gm, year), gm.sort_values("date")))
    return out


_KO_ORDER = ("round-of-32", "round-of-16", "quarter-final", "semi-final", "third-place", "final")


def edition_knockouts(year):
    """[(stage, matches_df)] for the knockout rounds present, in bracket order."""
    df = edition_matches(year)
    return [(s, df[df["stage"] == s].sort_values("date")) for s in _KO_ORDER if (df["stage"] == s).any()]


# how far each stage is into the tournament (higher = later); groups feed everything above them.
_SRANK = {"group": 0, "group-2": 1, "final-round": 1, "round-of-32": 2, "round-of-16": 3,
          "quarter-final": 4, "semi-final": 5, "third-place": 6, "final": 6}


def advanced_from(year, stage):
    """Teams that PROGRESSED past a group `stage` — i.e. show up in any later-ranked stage.
    Data-driven, so it's correct for every era: 1 per group (1930/1950, only winners advanced),
    2 per group (most), or 2 + best-thirds (1986/1994, where some groups send 3)."""
    df = edition_matches(year)
    r = _SRANK.get(stage, -1)
    out = set()
    for x in df.itertuples():
        if _SRANK.get(x.stage, -1) > r:
            out.add(x.home)
            out.add(x.away)
    return out


def edition_overview(year):
    """Headline facts for one edition (champion/host/match & goal totals)."""
    em = edition_matches(year)
    c = next((c for c in champions() if c["year"] == int(year)), None)
    return {"year": int(year), "host": em["host"].iloc[0] if len(em) else "",
            "matches": len(em),
            "goals": int(em.home_score.clip(lower=0).sum() + em.away_score.clip(lower=0).sum()),
            "champion": c["champion"] if c else None, "runner_up": c["runner_up"] if c else None,
            "score": c["score"] if c else ""}


def _match_winner(r):
    """Winner of a match (knockout-decisive): goals, else the shootout. None for a true draw."""
    if r.home_score > r.away_score:
        return r.home
    if r.away_score > r.home_score:
        return r.away
    if pd.notna(r.pens_home) and r.pens_home != r.pens_away:
        return r.home if r.pens_home > r.pens_away else r.away
    return None


# 1950 had no single Final (final round-robin); the decisive match was Uruguay 2–1 Brazil.
_CHAMP_1950 = ("Uruguay", "Brazil")


@lru_cache(maxsize=1)
def champions():
    """[{year, host, champion, runner_up, final}] for every edition (1950 from its decider)."""
    out = []
    df = matches()
    for y in years():
        host = df[df["year"] == y]["host"].iloc[0]
        fin = df[(df["year"] == y) & (df["stage"] == "final")]
        if y == 1950:
            champ, runner = _CHAMP_1950
            row = df[(df["year"] == 1950) & (df["home"].isin(_CHAMP_1950)) & (df["away"].isin(_CHAMP_1950))]
            final = row.iloc[0] if len(row) else None
        elif len(fin):
            final = fin.iloc[0]
            w = _match_winner(final)
            champ = w
            runner = final.away if w == final.home else final.home
        else:
            champ = runner = final = None
        score = ""
        if final is not None:                                # champion-first score
            if champ == final.home:
                hs, as_, ph, pa = final.home_score, final.away_score, final.pens_home, final.pens_away
            else:
                hs, as_, ph, pa = final.away_score, final.home_score, final.pens_away, final.pens_home
            score = f"{hs}–{as_}"
            if pd.notna(ph):
                score += f" ({int(ph)}–{int(pa)} pen)"
        out.append({"year": int(y), "host": host, "champion": champ, "runner_up": runner,
                    "final_home": None if final is None else final.home,
                    "final_away": None if final is None else final.away, "score": score})
    return out


@lru_cache(maxsize=1)
def all_time_table():
    """Per nation (folded): titles · finals · editions · P · W · D · L · GF · GA · GD."""
    df = matches()
    champ_count, final_count = {}, {}
    for c in champions():
        if c["champion"]:
            champ_count[fold(c["champion"])] = champ_count.get(fold(c["champion"]), 0) + 1
        for side in (c["runner_up"], c["champion"]):
            if side:
                final_count[fold(side)] = final_count.get(fold(side), 0) + 1
    agg = {}
    seen_year = {}
    for r in df.itertuples():
        for team, gf, ga in ((r.home, r.home_score, r.away_score), (r.away, r.away_score, r.home_score)):
            n = fold(team)
            a = agg.setdefault(n, dict(P=0, W=0, D=0, L=0, GF=0, GA=0))
            a["P"] += 1
            a["GF"] += gf
            a["GA"] += ga
            if gf > ga:
                a["W"] += 1
            elif gf < ga:
                a["L"] += 1
            else:
                a["D"] += 1                                  # shootout KOs count as draws (FIFA convention)
            seen_year.setdefault(n, set()).add(int(r.year))
    rows = []
    for n, a in agg.items():
        rows.append({"nation": n, "titles": champ_count.get(n, 0), "finals": final_count.get(n, 0),
                     "editions": len(seen_year[n]), **a, "GD": a["GF"] - a["GA"]})
    t = pd.DataFrame(rows).sort_values(["titles", "finals", "W", "GD"], ascending=False).reset_index(drop=True)
    return t


def head_to_head(a, b):
    """All World Cup meetings between two nations (folded names; includes their historical sides)."""
    df = matches()
    fa = {k for k, v in {**{n: n for n in ISO2}, **FOLD}.items() if fold(k) == a}
    fb = {k for k, v in {**{n: n for n in ISO2}, **FOLD}.items() if fold(k) == b}
    m = df[(df["home"].isin(fa) & df["away"].isin(fb)) | (df["home"].isin(fb) & df["away"].isin(fa))]
    return m.sort_values("year")


def nations():
    """Sorted list of folded nation names (for pickers)."""
    return sorted(all_time_table()["nation"])


@lru_cache(maxsize=1)
def records():
    df = matches()
    df = df.assign(total=df.home_score + df.away_score, gd=(df.home_score - df.away_score).abs())
    big = df.sort_values("gd", ascending=False).iloc[0]
    high = df.sort_values("total", ascending=False).iloc[0]
    fin = df[df["stage"] == "final"].assign(t=lambda d: d.home_score + d.away_score).sort_values("t", ascending=False).iloc[0]
    at = all_time_table()
    return {
        "editions": len(years()), "matches": len(df), "nations": at["nation"].nunique(),
        "goals": int(df.home_score.clip(lower=0).sum() + df.away_score.clip(lower=0).sum()),
        "most_titles": at.iloc[0]["nation"], "most_titles_n": int(at.iloc[0]["titles"]),
        "most_apps": at.sort_values("editions", ascending=False).iloc[0]["nation"],
        "most_apps_n": int(at.sort_values("editions", ascending=False).iloc[0]["editions"]),
        "biggest": (big.home, int(big.home_score), int(big.away_score), big.away, int(big.year)),
        "highest": (high.home, int(high.home_score), int(high.away_score), high.away, int(high.year)),
        "highest_final": (fin.home, int(fin.home_score), int(fin.away_score), fin.away, int(fin.year)),
    }


# ── Nation history ────────────────────────────────────────────────────────────────────────────────
# Labels for how far a nation got, keyed by the deepest stage it appears in that edition. The two
# group-type stages read as eliminations because reaching them is not itself an achievement.
_FINISH = {"final": "Runners-up", "third-place": "Fourth place", "semi-final": "Semi-finals",
           "quarter-final": "Quarter-finals", "round-of-16": "Round of 16",
           "round-of-32": "Round of 32", "final-round": "Final round",
           "group-2": "Second group stage", "group": "Group stage"}

# Ranking for "best finish", lower is better. Not derived from _SRANK because the podium places are
# decided by RESULTS rather than by which round a team last appeared in — a beaten finalist and a
# third-place winner both stop at the same stage index.
_FINISH_RANK = {"Champions": 0, "Runners-up": 1, "Third place": 2, "Fourth place": 3,
                "Semi-finals": 4, "Quarter-finals": 5, "Round of 16": 6, "Round of 32": 7,
                "Final round": 3, "Second group stage": 8, "Group stage": 9}


def _sides(nation):
    """Every historical name that folds into `nation` — so asking for Germany covers West Germany."""
    return {n for n in ISO2 if fold(n) == nation} | {nation}


def nation_history(nation):
    """One row per edition the nation played: matches, W-D-L, goals, and how far it got.

    Shootout knockouts count as draws in W-D-L (the FIFA convention used everywhere else in this
    module); the finish label still reflects who actually advanced.
    """
    names = _sides(nation)
    df = matches()
    ch = {c["year"]: c for c in champions()}
    out = []
    for y in years():
        em = df[(df["year"] == y) & (df["home"].isin(names) | df["away"].isin(names))]
        if em.empty:
            continue
        w = d = l = gf = ga = 0
        deepest, best = "group", -1
        for r in em.itertuples():
            mine, theirs = ((r.home_score, r.away_score) if r.home in names
                            else (r.away_score, r.home_score))
            gf += max(mine, 0)
            ga += max(theirs, 0)
            if mine > theirs:
                w += 1
            elif mine < theirs:
                l += 1
            else:
                d += 1
            if _SRANK.get(r.stage, -1) > best:
                best, deepest = _SRANK.get(r.stage, -1), r.stage
        c = ch.get(y, {})
        if c.get("champion") and fold(c["champion"]) == nation:
            finish = "Champions"
        elif c.get("runner_up") and fold(c["runner_up"]) == nation:
            finish = "Runners-up"
        else:
            finish = _FINISH.get(deepest, deepest)
            if deepest == "third-place":                 # decided by the result, not the round
                tp = em[em["stage"] == "third-place"].iloc[0]
                won = _match_winner(tp)
                finish = "Third place" if (won and won in names) else "Fourth place"
        out.append({"year": int(y), "played": len(em), "W": w, "D": d, "L": l,
                    "GF": gf, "GA": ga, "finish": finish, "host": em["host"].iloc[0]})
    return out


def nation_summary(nation):
    """Headline career: editions, titles, finals, best finish and all-time W-D-L."""
    h = nation_history(nation)
    at = all_time_table()
    row = at[at["nation"] == nation]
    best = min((x["finish"] for x in h), key=lambda f: _FINISH_RANK.get(f, 99)) if h else "—"
    return {
        "nation": nation, "editions": len(h),
        "titles": int(row["titles"].iloc[0]) if len(row) else 0,
        "finals": int(row["finals"].iloc[0]) if len(row) else 0,
        "best": best,
        "best_years": [x["year"] for x in h if x["finish"] == best],
        "P": sum(x["played"] for x in h), "W": sum(x["W"] for x in h),
        "D": sum(x["D"] for x in h), "L": sum(x["L"] for x in h),
        "GF": sum(x["GF"] for x in h), "GA": sum(x["GA"] for x in h),
        "first": h[0]["year"] if h else None, "last": h[-1]["year"] if h else None,
        "names": sorted(n for n in _sides(nation) if n != nation),
    }


def nation_matches(nation, year=None):
    """Every match a nation played, newest first — optionally limited to one edition."""
    names = _sides(nation)
    df = matches()
    m = df[df["home"].isin(names) | df["away"].isin(names)]
    if year is not None:
        m = m[m["year"] == int(year)]
    return m.sort_values(["year", "date"], ascending=[False, True])
