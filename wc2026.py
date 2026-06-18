"""2026 FIFA World Cup data layer for the app.

Reads the three extracts produced by db/build/wikipedia_wc2026_ingest.py (groups+teams, the full
104-match schedule, venues). Self-contained — the World Cup is a separate scope from the Argentine
canonical matches.csv. Scores are blank until matches are played; everything here degrades to a
clean pre-tournament preview (standings all zero) and fills in automatically when the ingest is
re-run during the tournament.
"""
import base64
import json
import random
import re
import time
import zlib
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import pandas as pd

_DIR = Path(__file__).resolve().parent / "data"

# Live scores come from the GitHub Action's data-refresh commits. Streamlit Community Cloud does NOT
# re-pull the repo into a WARM (never-rebooted) process, so reading the on-disk CSV would freeze at the
# last reboot — which is exactly why the live site looked stale during the tournament. So `matches()`
# fetches the CSV straight from the repo's raw URL with a short TTL (+ a cache-buster to defeat raw
# GitHub's own ~5-min CDN cache), and falls back to the committed file if the network is unavailable.
_RAW_MATCHES_URL = "https://raw.githubusercontent.com/scalonico/mundial26/main/data/wc2026_matches.csv"
_MATCHES_TTL = 120  # seconds — at most one fetch per 2 min per process
_MATCHES_CACHE: dict = {}

KICKOFF = date(2026, 6, 11)
FINAL_DAY = date(2026, 7, 19)
HOSTS = ["Canada", "Mexico", "United States"]
STAGE_NAMES = {"group": "Group stage", "R32": "Round of 32", "R16": "Round of 16",
               "QF": "Quarter-finals", "SF": "Semi-finals", "3rd": "Third place", "F": "Final"}
STAGE_ORDER = ["group", "R32", "R16", "QF", "SF", "3rd", "F"]
# confederation accent colours (match the app's palette where possible)
CONF_COLOR = {"UEFA": "#6CACE4", "CONMEBOL": "#5BD1A0", "CAF": "#E0563B",
              "AFC": "#B388FF", "CONCACAF": "#F2A65A", "OFC": "#E96BA8"}
# A few names are too long for the tightest tables/cards (4-wide group standings, team cards) — show a
# compact label there (the full name stays in tooltips / wider views like the schedule).
SHORT_NAMES = {"United States": "USA", "Bosnia and Herzegovina": "Bosnia & H."}


def short_name(name: str) -> str:
    return SHORT_NAMES.get(name, name)
# Time-zone options for the schedule. "Local to venue" (None) keeps each match's published kickoff;
# any other converts the absolute UTC instant via zoneinfo. Argentina first (this app's audience).
TIMEZONES = {
    "🏟️ Local to venue": None,
    "🇦🇷 Buenos Aires": "America/Argentina/Buenos_Aires",
    "🇺🇸 New York (ET)": "America/New_York",
    "🇺🇸 Chicago (CT)": "America/Chicago",
    "🇺🇸 Denver (MT)": "America/Denver",
    "🇺🇸 Los Angeles (PT)": "America/Los_Angeles",
    "🇲🇽 Mexico City": "America/Mexico_City",
    "🇧🇷 São Paulo": "America/Sao_Paulo",
    "🇬🇧 London": "Europe/London",
    "🇪🇸 Madrid": "Europe/Madrid",
    "🌍 UTC": "UTC",
}


# --- Visuals (display-only hot-links, NOT part of the released data — same policy as the app's club
#     crests / competition logos). Flags: flagcdn keyed by ISO2 (gb-eng/gb-sct for the home nations).
#     Stadium photos: freely-licensed Wikimedia Commons aerials. The official emblem is a FIFA
#     trademark (non-free); hot-linked for this research viz only — swap if ever deployed commercially.
EMBLEM_URL = ("https://upload.wikimedia.org/wikipedia/en/thumb/1/17/"
              "2026_FIFA_World_Cup_emblem.svg/250px-2026_FIFA_World_Cup_emblem.svg.png")
STADIUM_PHOTO = {
    "Estadio Azteca": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/07/Vista_a%C3%A9rea_del_Estadio_Azteca_-_2026_-_02.jpg/500px-Vista_a%C3%A9rea_del_Estadio_Azteca_-_2026_-_02.jpg",
    "Estadio BBVA": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/57/Mexico_Guadalupe_Monterrey_Estadio_BBVA_Bancomer_fifa_world_cup_2026_6.JPG/500px-Mexico_Guadalupe_Monterrey_Estadio_BBVA_Bancomer_fifa_world_cup_2026_6.JPG",
    "Estadio Akron": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/10/Estadio_Akron_02-07-2022_cabecera_sur_lado_derecho_%283%29.jpg/500px-Estadio_Akron_02-07-2022_cabecera_sur_lado_derecho_%283%29.jpg",
    "BC Place": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/ff/BC_Place_2015_Women%27s_FIFA_World_Cup.jpg/500px-BC_Place_2015_Women%27s_FIFA_World_Cup.jpg",
    "BMO Field": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/91/Toronto_BMO_Field_in_2024.jpg/500px-Toronto_BMO_Field_in_2024.jpg",
    "AT&T Stadium": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/11/Arlington_June_2020_4_%28AT%26T_Stadium%29.jpg/500px-Arlington_June_2020_4_%28AT%26T_Stadium%29.jpg",
    "MetLife Stadium": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/04/Metlife_stadium_%28Aerial_view%29.jpg/500px-Metlife_stadium_%28Aerial_view%29.jpg",
    "Mercedes-Benz Stadium": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/10/Mercedes_Benz_Stadium_time_lapse_capture_2017-08-13.jpg/500px-Mercedes_Benz_Stadium_time_lapse_capture_2017-08-13.jpg",
    "Arrowhead Stadium": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/Aerial_view_of_Arrowhead_Stadium_08-31-2013.jpg/500px-Aerial_view_of_Arrowhead_Stadium_08-31-2013.jpg",
    "NRG Stadium": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3e/Nrg_stadium.jpg/500px-Nrg_stadium.jpg",
    "Levi's Stadium": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a6/Levi%27s_Stadium_in_February_2016_prior_to_Super_Bowl_50_%2824398261729%29.jpg/500px-Levi%27s_Stadium_in_February_2016_prior_to_Super_Bowl_50_%2824398261729%29.jpg",
    "SoFi Stadium": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b3/SoFi_Stadium_2023.jpg/500px-SoFi_Stadium_2023.jpg",
    "Lincoln Financial Field": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a1/Lincoln_Financial_Field_%28Aerial_view%29.jpg/500px-Lincoln_Financial_Field_%28Aerial_view%29.jpg",
    "Lumen Field": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/98/2025_FIFA_Club_World_Cup_-_Seattle_Sounders_FC_vs._Atl%C3%A9tico_Madrid_-_05.jpg/500px-2025_FIFA_Club_World_Cup_-_Seattle_Sounders_FC_vs._Atl%C3%A9tico_Madrid_-_05.jpg",
    "Gillette Stadium": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/db/Gillette_Stadium_%28Top_View%29.jpg/500px-Gillette_Stadium_%28Top_View%29.jpg",
    "Hard Rock Stadium": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/ce/Hard_Rock_Stadium_for_Super_Bowl_LIV_%2849606710103%29.jpg/500px-Hard_Rock_Stadium_for_Super_Bowl_LIV_%2849606710103%29.jpg",
}


def flag_url(iso2: str, w: int = 80) -> str:
    """A flag image URL from flagcdn, keyed by ISO 3166-1 alpha-2 (gb-eng/gb-sct for the home nations)."""
    return f"https://flagcdn.com/w{w}/{iso2.lower()}.png" if iso2 else ""


def venue_photo(stadium: str) -> str:
    return STADIUM_PHOTO.get(stadium, "")


@lru_cache(maxsize=1)
def teams() -> pd.DataFrame:
    return pd.read_csv(_DIR / "wc2026_teams.csv", dtype=str).fillna("")


@lru_cache(maxsize=1)
def venues() -> pd.DataFrame:
    return pd.read_csv(_DIR / "wc2026_venues.csv")


@lru_cache(maxsize=1)
def _code_label() -> dict:
    return {r.code: f"{r.flag} {r.name}" for r in teams().itertuples()}


def team_label(code: str) -> str:
    """'🇦🇷 Argentina' for a FIFA code; a knockout placeholder ('Winner Group A') passes through."""
    return _code_label().get(code, code)


def _utc_kickoff(date_val, time_local: str):
    """Absolute UTC instant of a kickoff from its local date + 'H:MM a.m./p.m. UTC±N' string."""
    if pd.isna(date_val) or not time_local:
        return pd.NaT
    m = re.search(r"(\d{1,2}):(\d{2})\s*([ap])\.?\s*m\.?\s*UTC([^\d]*)(\d{1,2})", time_local, re.I)
    if not m:
        return pd.NaT
    h, mn, ap = int(m.group(1)), int(m.group(2)), m.group(3).lower()
    if ap == "p" and h != 12:
        h += 12
    elif ap == "a" and h == 12:
        h = 0
    sign = -1 if ("−" in m.group(4) or "-" in m.group(4)) else 1
    d = pd.Timestamp(date_val)
    return pd.Timestamp(datetime(d.year, d.month, d.day, h, mn,
                        tzinfo=timezone(timedelta(hours=sign * int(m.group(5)))))).tz_convert("UTC")


def localize(kickoff_utc, tzname: str):
    """(date_str 'Thu Jun 11', time_str '4:00 PM') for a UTC kickoff seen from tzname; ('','') if unknown.
    Avoids strftime '%-I'/'%-d' (not portable on Windows) by formatting the hour/day by hand."""
    if pd.isna(kickoff_utc) or not tzname:
        return "", ""
    t = kickoff_utc.tz_convert(tzname)
    h = t.hour % 12 or 12
    return t.strftime("%a %b ") + str(t.day), f"{h}:{t.minute:02d} {'AM' if t.hour < 12 else 'PM'}"


def _read_matches_csv() -> pd.DataFrame:
    """Prefer the live raw-URL copy (always current); fall back to the committed file offline."""
    try:
        url = f"{_RAW_MATCHES_URL}?nocache={int(time.time())}"
        return pd.read_csv(url, dtype=str).fillna("")
    except Exception:
        return pd.read_csv(_DIR / "wc2026_matches.csv", dtype=str).fillna("")


def matches() -> pd.DataFrame:
    now = time.time()
    if _MATCHES_CACHE and now - _MATCHES_CACHE["t"] < _MATCHES_TTL:
        return _MATCHES_CACHE["df"]
    df = _read_matches_csv()
    df["match_no"] = pd.to_numeric(df["match_no"])
    for c in ("score1", "score2"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["kickoff_utc"] = [_utc_kickoff(dv, tl) for dv, tl in zip(df["date"], df["time_local"])]
    lab = _code_label()
    df["team1_label"] = df["team1"].map(lambda c: lab.get(c, c))
    df["team2_label"] = df["team2"].map(lambda c: lab.get(c, c))
    df["stage_name"] = df["stage"].map(STAGE_NAMES)
    df["played"] = df["score1"].notna() & df["score2"].notna()
    _MATCHES_CACHE["t"], _MATCHES_CACHE["df"] = now, df
    return df


def days_to_kickoff(today: date | None = None) -> int:
    return (KICKOFF - (today or date.today())).days


def days_to_final(today: date | None = None) -> int:
    return (FINAL_DAY - (today or date.today())).days


def short_slot(s: str) -> str:
    """Compact a knockout placeholder for bracket display: 'Runner-up Group B' -> '2B',
    'Winner Group A' -> '1A', '3rd Group A/B/C/D/F' -> '3rd A/B/C/D/F', 'Winner Match 73' -> 'W73'."""
    s = str(s)
    m = __import__("re").match(r"Winner Group ([A-L])$", s)
    if m:
        return "1" + m.group(1)
    m = __import__("re").match(r"Runner-up Group ([A-L])$", s)
    if m:
        return "2" + m.group(1)
    s = s.replace("3rd Group ", "3rd ")
    s = __import__("re").sub(r"Winner Match (\d+)", r"W\1", s)
    s = __import__("re").sub(r"Loser Match (\d+)", r"L\1", s)
    return s


def group_standings(letter: str) -> pd.DataFrame:
    """P-W-D-L-GF-GA-GD-Pts for a group from played scores (all zero before the tournament).
    Sorted by the FIFA tiebreak chain we can compute from data: points, goal difference, goals for."""
    g = teams()[teams().group == letter]
    rec = {r.code: dict(code=r.code, flag=r.flag, flag_url=flag_url(r.iso2), team=r.name, pos=r.pos,
                        P=0, W=0, D=0, L=0, GF=0, GA=0, Pts=0) for r in g.itertuples()}
    gm = matches()
    gm = gm[(gm.stage == "group") & (gm.group == letter) & gm.played]
    for r in gm.itertuples():
        if r.team1 not in rec or r.team2 not in rec:
            continue
        a, b, s1, s2 = rec[r.team1], rec[r.team2], int(r.score1), int(r.score2)
        a["P"] += 1; b["P"] += 1; a["GF"] += s1; a["GA"] += s2; b["GF"] += s2; b["GA"] += s1
        if s1 > s2:
            a["W"] += 1; b["L"] += 1; a["Pts"] += 3
        elif s2 > s1:
            b["W"] += 1; a["L"] += 1; b["Pts"] += 3
        else:
            a["D"] += 1; b["D"] += 1; a["Pts"] += 1; b["Pts"] += 1
    df = pd.DataFrame(rec.values())
    df["GD"] = df["GF"] - df["GA"]
    # Pre-tournament (all zero) this falls through to `pos` = the FIFA seed/pot order (1 = top seed), so a
    # group reads naturally (host/top seed first) instead of alphabetically; once results come in, points/
    # GD/GF dominate and seed is just the final deterministic tiebreak.
    return df.sort_values(["Pts", "GD", "GF", "pos"],
                          ascending=[False, False, False, True]).reset_index(drop=True)


def confederation_counts() -> pd.Series:
    return teams()["confederation"].value_counts()


@lru_cache(maxsize=1)
def _code_short() -> dict:
    return {r.code: f"{r.flag} {r.code}" for r in teams().itertuples()}


@lru_cache(maxsize=1)
def _code_flag() -> dict:
    return {r.code: flag_url(r.iso2) for r in teams().itertuples()}


def code_flag(code: str) -> str:
    """Flag image URL for a FIFA code ('' for a knockout placeholder)."""
    return _code_flag().get(code, "")


def box_slot(x: str) -> str:
    """Compact box label: '🇦🇷 ARG' once a team is known, else the short placeholder ('2B', 'W73')."""
    return _code_short().get(x, short_slot(x))


def _feeder(slot: str):
    import re
    m = re.search(r"Match (\d+)", str(slot))
    return int(m.group(1)) if m else None


def bracket_layout(resolved=None):
    """Geometry for a two-sided knockout bracket. Returns (nodes, edges, third):
      nodes[match_no] = {x, y, stage, t1, t2, prov1, prov2, date, city}; edges = [(parent, child), …].
    The Final sits at x=4; the left half fans out to x=0 (R32) and the right half to x=8, both
    spanning y=0..7. Each internal node sits at the mean y of its two feeders, so the connectors
    never cross. `third` is the separate third-place match row (not part of the tree).

    If `resolved` (a resolve_bracket result, e.g. from projected_bracket()) is supplied, every slot
    the official data still carries as a placeholder ("Winner Group A", "3rd Group …", "Winner Match
    73") is filled with the PROJECTED team and flagged provisional (prov1/prov2=True). Slots the data
    already names with a real team (once Wikipedia resolves them) stay actual (prov=False)."""
    real = set(_seed_maps()[1])

    def disp(raw, mno, which):
        """(display_slot, is_provisional) for one side of a knockout match."""
        if str(raw) in real:                       # official data already names a real team
            return raw, False
        if resolved:
            code = resolved.get(mno, {}).get(which)
            if code:                               # fill the placeholder with the projection
                return code, True
        return raw, False                          # unresolved placeholder ("1A", "W73")

    ko = matches()[lambda d: d["stage"] != "group"]
    byno = {int(r.match_no): r for r in ko.itertuples()}
    feed = {}
    for r in ko.itertuples():
        f1, f2 = _feeder(r.team1), _feeder(r.team2)
        if f1 and f2:
            feed[int(r.match_no)] = (f1, f2)
    final = int(ko[ko["stage"] == "F"]["match_no"].iloc[0])
    nodes, edges, cnt = {}, [], [0.0]

    def node_for(n, x, y):
        r = byno[n]
        t1, p1 = disp(r.team1, n, "t1")
        t2, p2 = disp(r.team2, n, "t2")
        return dict(x=x, y=y, stage=r.stage, t1=t1, t2=t2, prov1=p1, prov2=p2,
                    date=r.date, city=r.city, stadium=r.stadium, s1=r.score1, s2=r.score2)

    def place(n, side, depth):
        x = (4 - depth) if side == "L" else (4 + depth)
        if n in feed:
            c1, c2 = feed[n]
            edges.append((n, c1)); edges.append((n, c2))
            place(c1, side, depth + 1); place(c2, side, depth + 1)
            y = (nodes[c1]["y"] + nodes[c2]["y"]) / 2
        else:
            y = cnt[0]; cnt[0] += 1
        nodes[n] = node_for(n, x, y)

    c1, c2 = feed[final]
    cnt[0] = 0.0; place(c1, "L", 1)
    cnt[0] = 0.0; place(c2, "R", 1)
    edges.append((final, c1)); edges.append((final, c2))
    nodes[final] = node_for(final, 4, 3.5)
    third = byno.get(103)
    return nodes, edges, third


# ──────────────────────────────────────────────────────────────────────────── Bracket predictor
# Pure logic for the interactive "Play your bracket" game: from a predicted group finishing order it
# fills the 32-team knockout and plays it out, defaulting every undecided tie to the stronger side so
# the board is always complete. The user's explicit winner picks override the defaults.
GROUP_LETTERS = list("ABCDEFGHIJKL")


@lru_cache(maxsize=1)
def _seed_maps():
    """(order, meta): order[letter] = [codes in seeded pot order]; meta[code] = group/pos/name/flag/iso2.
    `pos` (1 = top seed) is the only strength signal in the data, so it doubles as the default favourite."""
    t = teams()
    order, meta = {}, {}
    for letter in GROUP_LETTERS:
        g = t[t.group == letter].copy()
        g["pos_i"] = pd.to_numeric(g["pos"], errors="coerce").fillna(9).astype(int)
        g = g.sort_values("pos_i")
        order[letter] = list(g["code"])
        for r in g.itertuples():
            meta[r.code] = dict(group=letter, pos=int(r.pos_i), name=r.name, flag=r.flag, iso2=r.iso2)
    return order, meta


def seed_order() -> dict:
    """Fresh, mutable copy of the default per-group finishing order (seeded pot position)."""
    return {k: list(v) for k, v in _seed_maps()[0].items()}


def seed_pos(code: str) -> int:
    """Seeded pot position 1–4 within the group; 9 for an unknown/placeholder slot."""
    return _seed_maps()[1].get(code, {}).get("pos", 9)


def team_group(code: str) -> str:
    return _seed_maps()[1].get(code, {}).get("group", "")


def team_name(code: str) -> str:
    return _seed_maps()[1].get(code, {}).get("name", code)


def strength(code: str, order: dict):
    """Lower is stronger: (finish position in its group, seed pot position). A group winner beats a
    runner-up beats a third-placer; ties broken by the seeded pot. Drives the default-favourite winner."""
    m = _seed_maps()[1].get(code)
    if not m:
        return (9, 9)
    letter = m["group"]
    fin = order[letter].index(code) if code in order.get(letter, []) else 3
    return (fin, m["pos"])


@lru_cache(maxsize=1)
def _third_slots() -> dict:
    """{match_no: frozenset(eligible group letters)} for the eight R32 third-placed slots (from data)."""
    out = {}
    for r in matches().itertuples():
        for slot in (r.team1, r.team2):
            m = re.match(r"3rd Group ([A-L/]+)$", str(slot))
            if m:
                out[int(r.match_no)] = frozenset(m.group(1).split("/"))
    return out


def third_allocation(order: dict, rank=None) -> dict:
    """Assign third-placed teams to the eight eligible R32 slots → {match_no: code}.
    The eight 'best' thirds advance; each is matched to a slot that lists its group as eligible. The 2026
    bracket is built so a valid assignment exists for any 8-of-12 set of advancing groups, so we solve it
    exactly with bipartite matching (a transparent stand-in for FIFA's lookup table). `rank(code)` orders
    which thirds advance (lower = better); it defaults to the pot seed, but the live bracket passes a
    current-standings ranker so the best thirds reflect today's results, not the draw."""
    thirds = [(L, order[L][2]) for L in GROUP_LETTERS if len(order.get(L, [])) > 2]
    rank = rank or (lambda code: seed_pos(code))
    ranked = sorted(thirds, key=lambda lc: (rank(lc[1]), lc[0]))
    by_letter = {L: code for L, code in ranked[:8]}      # the eight advancing thirds
    slots = _third_slots()
    slot_of = {}                                         # slot match_no -> assigned group letter

    def augment(letter, seen):
        for mno in sorted(m for m in slots if letter in slots[m]):
            if mno in seen:
                continue
            seen.add(mno)
            if mno not in slot_of or augment(slot_of[mno], seen):
                slot_of[mno] = letter
                return True
        return False

    for L in sorted(by_letter, key=lambda L: (seed_pos(by_letter[L]), L)):  # strongest thirds first
        augment(L, set())
    alloc = {mno: by_letter[L] for mno, L in slot_of.items()}
    # Defensive fallback (should not trigger for a full 48-team field): park any unmatched third anywhere.
    leftover = [by_letter[L] for L in by_letter if L not in slot_of.values()]
    for mno in sorted(slots):
        if mno not in alloc and leftover:
            alloc[mno] = leftover.pop()
    return alloc


def order_from_quals(quals: dict) -> dict:
    """Build a full per-group finishing order from just the user's 1st/2nd picks.
    quals[letter] = [winner_code, runner_up_code] (0–2 entries); remaining teams fill in by seed.
    Lets the game ask for only two picks per group while third_allocation still has a 3rd-placer to use."""
    base = _seed_maps()[0]
    order = {}
    for letter in GROUP_LETTERS:
        q = [c for c in quals.get(letter, []) if c in base[letter]][:2]
        order[letter] = q + [c for c in base[letter] if c not in q]
    return order


def order_from_standings() -> dict:
    """Current per-group finishing order from the LIVE standings table (1st→4th as things stand today).
    Feeds the Round-of-32 fill: as the groups stand right now, this is who finishes where, which is all
    resolve_bracket needs to place the 1st/2nd/3rd slots. A group that has not kicked off falls back to
    the seeded order (group_standings sorts on the pot seed `pos` when teams are level)."""
    return {L: list(group_standings(L)["code"]) for L in GROUP_LETTERS}


def groups_played() -> int:
    """How many of the 72 group matches have been played — drives whether the R32 fill is meaningful."""
    g = matches()
    return int(((g.stage == "group") & g.played).sum())


def _standings_record() -> dict:
    """code -> (Pts, GD, GF) from the current live standings, for ranking teams ACROSS groups."""
    out = {}
    for L in GROUP_LETTERS:
        for r in group_standings(L).itertuples():
            out[r.code] = (r.Pts, r.GD, r.GF)
    return out


def standings_third_rank():
    """Ranker (lower = better) for the eight best third-placed teams, by the live record
    (points, then goal difference, then goals for; seed breaks an exact tie) — NOT by pot seed."""
    rec = _standings_record()

    def rank(code):
        p, gd, gf = rec.get(code, (0, 0, 0))
        return (-p, -gd, -gf, seed_pos(code))
    return rank


def standings_bracket() -> dict:
    """Fill ONLY the Round of 32 from the current standings — no predicted knockout results.
    1X/2X = the current group winner / runner-up; the eight '3rd Group …' slots = the best current
    third-placed teams (by points, goal difference, goals for). Because fill_defaults=False, every
    undecided tie has winner=None, so the Round of 16 and beyond stay as their fixtures (date + venue)
    with no team filled in until real results put a team through."""
    return resolve_bracket(order_from_standings(), {}, fill_defaults=False,
                           third_rank=standings_third_rank())


def resolve_bracket(order: dict, wins: dict, fill_defaults: bool = True, chooser=None,
                    third_rank=None) -> dict:
    """Play the whole knockout from a group finishing `order` and explicit `wins` (match_no → code).
    Returns {match_no: dict(stage, t1, t2, winner, loser, date, city, slot1, slot2)} for matches 73–104.
    With fill_defaults=True every undecided tie defaults to the stronger side (always-complete bracket);
    with False, undecided ties have winner=None so downstream slots stay empty until picked (a bracket
    that fills in as you choose). `chooser(t1, t2)` overrides how an undecided tie is filled (e.g. weaker
    side, coin flip) — defaults to the stronger seed. An explicit pick that no longer matches its matchup
    is ignored, not blocking."""
    alloc = third_allocation(order, rank=third_rank)
    ko = matches()[lambda d: d["stage"] != "group"].sort_values("match_no")
    res: dict = {}

    def slot(s, mno):
        s = str(s)
        m = re.match(r"Winner Group ([A-L])$", s)
        if m:
            g = order.get(m.group(1), [])
            return g[0] if g else None
        m = re.match(r"Runner-up Group ([A-L])$", s)
        if m:
            g = order.get(m.group(1), [])
            return g[1] if len(g) > 1 else None
        if s.startswith("3rd Group"):
            return alloc.get(mno)
        m = re.match(r"Winner Match (\d+)$", s)
        if m:
            return res.get(int(m.group(1)), {}).get("winner")
        m = re.match(r"Loser Match (\d+)$", s)
        if m:
            r = res.get(int(m.group(1)))
            if not r or not r.get("winner"):
                return None
            return r["t1"] if r["winner"] == r["t2"] else r["t2"]
        return None

    for r in ko.itertuples():
        mno = int(r.match_no)
        t1, t2 = slot(r.team1, mno), slot(r.team2, mno)
        w = wins.get(mno)
        if w not in (t1, t2):                            # stale/invalid pick → drop it
            w = None
        if w is None and fill_defaults and t1 and t2:    # fill an undecided tie (default = stronger seed)
            w = chooser(t1, t2) if chooser else (t1 if strength(t1, order) <= strength(t2, order) else t2)
        loser = (t2 if w == t1 else t1) if (w and t1 and t2) else None
        res[mno] = dict(stage=r.stage, t1=t1, t2=t2, winner=w, loser=loser,
                        date=r.date, city=r.city, slot1=r.team1, slot2=r.team2)
    return res


def champion(order: dict, wins: dict) -> str | None:
    """Predicted champion = winner of the Final (match 104)."""
    return resolve_bracket(order, wins).get(104, {}).get("winner")


def autofill_wins(order: dict, base_wins: dict, strategy: str = "fav") -> dict:
    """Fill every UNDECIDED knockout tie by a strategy, keeping the user's explicit picks → wins dict.
    'fav' = stronger seed advances · 'underdog' = weaker seed advances (upsets) · 'random' = coin flip.
    Resolved round by round so the strategy propagates (an R16 winner feeds the QF, etc.)."""
    rng = random.Random()

    def chooser(t1, t2):
        if strategy == "underdog":
            return t1 if strength(t1, order) >= strength(t2, order) else t2
        if strategy == "random":
            return rng.choice([t1, t2])
        return t1 if strength(t1, order) <= strength(t2, order) else t2      # 'fav'

    full = resolve_bracket(order, base_wins, fill_defaults=True, chooser=chooser)
    return {m: full[m]["winner"] for m in full if full[m]["winner"]}


# ── Shareable bracket codes ───────────────────────────────────────────────────────────────────
# A whole prediction (group 1st/2nd picks + knockout winners) round-trips through one short string,
# so a bracket can be copied to a friend or carried in a `?b=` URL — no backend needed.
def encode_picks(quals: dict, wins: dict) -> str:
    payload = {"q": {k: list(v) for k, v in quals.items() if v},
               "w": {str(k): v for k, v in wins.items() if v}}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return "WC1." + base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii").rstrip("=")


def decode_picks(code: str):
    """Inverse of encode_picks → (quals, wins); None if the code is malformed."""
    try:
        s = (code or "").strip()
        s = s[4:] if s.startswith("WC1.") else s
        s += "=" * (-len(s) % 4)
        raw = zlib.decompress(base64.urlsafe_b64decode(s.encode("ascii")))
        payload = json.loads(raw.decode("utf-8"))
        return ({k: list(v) for k, v in payload.get("q", {}).items()},
                {int(k): v for k, v in payload.get("w", {}).items()})
    except Exception:
        return None


# ── Scoring a bracket against actual results ──────────────────────────────────────────────────
# Points are awarded for teams correctly predicted to REACH each round (robust to bracket-path
# differences) plus correct group qualifiers and the right champion. All zero until games are played;
# fills in live as the ingest re-runs during the tournament.
SCORE_WEIGHTS = {"group": 1, "R16": 1, "QF": 2, "SF": 4, "F": 8, "champion": 16}


def _reach_from_rows(rows, codes):
    """{stage: set(real team codes appearing in that stage's matches)} — i.e. teams that reach it."""
    reach = {st: set() for st in ("R16", "QF", "SF", "F")}
    for r in rows:
        if r["stage"] in reach:
            for t in (r["t1"], r["t2"]):
                if t in codes:
                    reach[r["stage"]].add(t)
    return reach


def predicted_reach(order: dict, wins: dict) -> dict:
    """What a bracket predicts: teams reaching each round, the champion, and group top-2."""
    codes = set(_seed_maps()[1])
    res = resolve_bracket(order, wins, fill_defaults=True)
    reach = _reach_from_rows(res.values(), codes)
    reach["champion"] = res.get(104, {}).get("winner")
    reach["groups"] = {L: order.get(L, [])[:2] for L in GROUP_LETTERS}
    return reach


def actual_reach() -> dict:
    """The same shape, derived from played results (empty pre-tournament)."""
    codes = set(_seed_maps()[1])
    df = matches()
    rows = [dict(stage=r.stage, t1=r.team1, t2=r.team2) for r in df.itertuples()]
    reach = _reach_from_rows(rows, codes)
    fin = df[df.match_no == 104]
    champ = None
    if not fin.empty:
        r = fin.iloc[0]
        if pd.notna(r.score1) and pd.notna(r.score2) and r.team1 in codes and r.team2 in codes:
            champ = r.team1 if r.score1 > r.score2 else (r.team2 if r.score2 > r.score1 else None)
    reach["champion"] = champ
    groups = {}
    for L in GROUP_LETTERS:
        tbl = group_standings(L)
        if tbl["P"].sum() > 0:                     # only score a group once it has played
            groups[L] = list(tbl["code"].head(2))
    reach["groups"] = groups
    return reach


def score_picks(order: dict, wins: dict) -> dict:
    """Score a bracket vs actual results → {total, breakdown, champion, champion_correct, has_results}."""
    pred, act = predicted_reach(order, wins), actual_reach()
    w, bd, total = SCORE_WEIGHTS, {}, 0
    gpts = 0
    for L, top2 in act["groups"].items():
        gpts += len(set(pred["groups"].get(L, [])) & set(top2 or [])) * w["group"]
    bd["group"] = gpts
    total += gpts
    for st in ("R16", "QF", "SF", "F"):
        bd[st] = len(pred[st] & act[st]) * w[st]
        total += bd[st]
    champ_ok = bool(act["champion"]) and pred["champion"] == act["champion"]
    bd["champion"] = w["champion"] if champ_ok else 0
    total += bd["champion"]
    has_results = bool(act["groups"]) or any(act[st] for st in ("R16", "QF", "SF", "F"))
    return {"total": total, "breakdown": bd, "champion": pred["champion"],
            "champion_correct": champ_ok, "has_results": has_results}


@lru_cache(maxsize=1)
def match_feeders() -> dict:
    """{match_no: (feeder1, feeder2)} for every knockout match fed by two earlier matches (R16 → Final).
    R32 matches feed from group slots (not matches) so they're absent — i.e. they're the tree's leaves.
    The third-place match (Loser-fed) is excluded; this is the championship tree only (89–100, 101–102, 104)."""
    out = {}
    for r in matches().itertuples():
        m1 = re.match(r"Winner Match (\d+)$", str(r.team1))
        m2 = re.match(r"Winner Match (\d+)$", str(r.team2))
        if m1 and m2:
            out[int(r.match_no)] = (int(m1.group(1)), int(m2.group(1)))
    return out


def bracket_round_order() -> dict:
    """Vertical (top-to-bottom) ordering of matches within each knockout round for a single-direction
    bracket, via an in-order walk of the championship tree → {stage: [match_no, …]}. Feeders sit directly
    above/below the match they flow into, so a left-to-right column layout reads as a real bracket."""
    feeders = match_feeders()
    by_depth: dict = {}

    def walk(n, depth):
        if n in feeders:
            a, b = feeders[n]
            walk(a, depth + 1)
            by_depth.setdefault(depth, []).append(n)
            walk(b, depth + 1)
        else:
            by_depth.setdefault(depth, []).append(n)

    walk(104, 0)                                              # 0=Final, 1=SF, 2=QF, 3=R16, 4=R32
    return {"R32": by_depth.get(4, []), "R16": by_depth.get(3, []), "QF": by_depth.get(2, []),
            "SF": by_depth.get(1, []), "F": by_depth.get(0, [])}
