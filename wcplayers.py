"""Player layer — query the 1930–2026 goal and squad archives (data/wc_goals.csv, wc_squads.csv).

Powers the 👤 Players tab. Both CSVs are built by build/players.py from Wikipedia; see that file for
how the source markup is parsed and why coverage is exact (all 23 editions and all 120 (year, stage)
pairs match the match archive's scorelines).

Identity is the Wikipedia LINK TARGET, not the displayed name — Wikipedia writes `[[Gigi Riva|Riva]]`,
so the display text is often a bare surname that several players share. Keying on the target is what
lets a scorer be joined to his squad entry, which currently succeeds for 96.8% of (edition, scorer)
pairs. Names shown to the reader come from that target too, minus any "(Brazilian footballer)"
disambiguator — see _display(). Using the source's own display text instead would render both
Ronaldos, and both Villalbas, identically. short_name() keeps the bare surname for tight layouts.

APPEARANCES ARE NOT IN THIS DATA. Wikipedia's match boxes carry no lineups, so who actually took the
field is unknowable here. Anything squad-derived is therefore "named in a squad", never "played" —
the youngest-squad record is Jacinto Villalba (Paraguay 1930, 15.7), which is NOT the same statistic
as the youngest player ever to appear. The UI must not blur the two.

OWN GOALS NEVER COUNT TOWARD A SCORING RECORD. build/players.py already re-attributes them to the
scorer's real nation (Wikipedia files them under the team they benefited), so here they only need
excluding from every tally — hence the `_scoring()` helper rather than filtering ad hoc at each site.
"""
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

import wchistory as wch

_DATA = Path(__file__).resolve().parent / "data"
_GOALS = _DATA / "wc_goals.csv"
_SQUADS = _DATA / "wc_squads.csv"

# Squad-page nation spellings → the archive's, so flags resolve and nations read consistently with
# the rest of the site. Only four differ; kept explicit rather than fuzzy-matched.
_ALIAS = {"Bosnia and Herzegovina": "Bosnia-Herzegovina", "China PR": "China",
          "Ivory Coast": "Côte d'Ivoire", "Republic of Ireland": "Ireland"}

POS_NAME = {"GK": "Goalkeeper", "DF": "Defender", "MF": "Midfielder", "FW": "Forward"}


def _bool(s):
    return s.astype(str).str.strip().str.lower().isin(("1", "true", "yes", "y"))


@lru_cache(maxsize=1)
def goals():
    df = pd.read_csv(_GOALS, dtype=str).fillna("")
    df["year"] = df["year"].astype(int)
    df["minute"] = pd.to_numeric(df["minute"], errors="coerce")
    df["minute_extra"] = pd.to_numeric(df["minute_extra"], errors="coerce")
    df["penalty"] = _bool(df["penalty"])
    df["own_goal"] = _bool(df["own_goal"])
    df["nation"] = df["team_code"].map(nations())
    # Sort key that puts 45+2' after 45' but before 46'.
    df["minute_sort"] = df["minute"] + df["minute_extra"].fillna(0) / 100
    return df


@lru_cache(maxsize=1)
def squads():
    df = pd.read_csv(_SQUADS, dtype=str).fillna("")
    df["year"] = df["year"].astype(int)
    df["shirt_no"] = pd.to_numeric(df["shirt_no"], errors="coerce")
    df["caps"] = pd.to_numeric(df["caps"], errors="coerce")
    df["captain"] = _bool(df["captain"])
    df["dob"] = pd.to_datetime(df["dob"], errors="coerce")
    df["nation"] = df["team_name"].map(lambda n: _ALIAS.get(n, n))
    return df


@lru_cache(maxsize=1)
def nations():
    """{team_code: nation name} taken from the squad pages, aliased to the archive's spellings."""
    s = pd.read_csv(_SQUADS, dtype=str).fillna("")
    top = s.groupby("team_code")["team_name"].agg(lambda x: x.value_counts().index[0])
    return {c: _ALIAS.get(n, n) for c, n in top.items()}


def flag(code_or_nation, w=40):
    """Flag for a team CODE or a nation name (codes are what the goal rows carry)."""
    return wch.flag_url(nations().get(code_or_nation, code_or_nation), w)


def _scoring():
    """Goals that count toward a player's record — i.e. everything except own goals."""
    g = goals()
    return g[~g["own_goal"]]


_PAREN = re.compile(r"\s*\([^)]*\)\s*$")


@lru_cache(maxsize=1)
def _display():
    """{player_key: name to show} — the wikilink TARGET with any disambiguator stripped.

    Deliberately NOT `player_display`: Wikipedia's display text is usually a bare surname, which
    collides badly in a stats table — Cristiano Ronaldo and Brazil's Ronaldo both render as
    "Ronaldo", as do the two Villalbas. The target is the full name, so stripping "(Brazilian
    footballer)" from it gives "Ronaldo" for one and "Cristiano Ronaldo" for the other.
    """
    keys = set(goals()["player_key"]) | set(squads()["player_key"])
    return {k: _PAREN.sub("", k) or k for k in keys}


def short_name(key):
    """The bare surname Wikipedia displays — for tight contexts where the full name won't fit."""
    return _short().get(key, _display().get(key, key))


@lru_cache(maxsize=1)
def _short():
    g = goals()
    d = dict(zip(g["player_key"], g["player_display"]))
    s = squads()
    for k, v in zip(s["player_key"], s["player_display"]):
        d.setdefault(k, v)
    return d


@lru_cache(maxsize=1)
def top_scorers_all():
    """All-time scoring table: goals, editions scored in, nations represented, pens."""
    g = _scoring()
    rows = g.groupby("player_key").agg(
        goals=("player_key", "size"),
        editions=("year", "nunique"),
        penalties=("penalty", "sum"),
        first=("year", "min"),
        last=("year", "max"),
    ).reset_index()
    nat = g.groupby("player_key")["nation"].agg(lambda x: x.value_counts().index[0])
    rows["nation"] = rows["player_key"].map(nat)
    disp = _display()
    rows["player"] = rows["player_key"].map(disp)
    return rows.sort_values(["goals", "editions"], ascending=[False, True]).reset_index(drop=True)


def top_scorers(limit=25, year=None):
    """Top scorers all-time, or within one edition."""
    if year is None:
        return top_scorers_all().head(limit)
    g = _scoring()
    g = g[g["year"] == int(year)]
    if g.empty:
        return pd.DataFrame(columns=["player", "nation", "goals", "penalties"])
    rows = g.groupby("player_key").agg(goals=("player_key", "size"),
                                       penalties=("penalty", "sum")).reset_index()
    nat = g.groupby("player_key")["nation"].first()
    rows["nation"] = rows["player_key"].map(nat)
    rows["player"] = rows["player_key"].map(_display())
    return rows.sort_values("goals", ascending=False).head(limit).reset_index(drop=True)


@lru_cache(maxsize=1)
def golden_boots():
    """[{year, players: [(display, nation, goals)]}] — the edition's top scorer(s), ties included.

    NOT the official Golden Boot award (which used assists and minutes as tie-breaks in some years);
    this is simply who scored most, computed from the data. Labelled as such in the UI.
    """
    out = []
    g = _scoring()
    disp = _display()
    for y in sorted(g["year"].unique()):
        sub = g[g["year"] == y]
        cnt = sub.groupby("player_key").size()
        best = cnt.max()
        tied = sorted(cnt[cnt == best].index)
        nat = sub.groupby("player_key")["nation"].first()
        out.append({"year": int(y), "goals": int(best),
                    "players": [(disp.get(k, k), nat.get(k, ""), int(best)) for k in tied]})
    return out


def player_keys():
    """Every player we know, scorers and squad members alike → [(display, key)] sorted by name."""
    disp = _display()
    keys = set(goals()["player_key"]) | set(squads()["player_key"])
    return sorted(((disp.get(k, k), k) for k in keys), key=lambda t: t[0].lower())


def search(term, limit=40):
    """Player search over BOTH display name and key (the key holds the full name, the display often
    only a surname — so 'Riva' and 'Gigi Riva' must both find him)."""
    t = (term or "").strip().lower()
    if not t:
        return []
    hits = [(d, k) for d, k in player_keys() if t in d.lower() or t in k.lower()]
    # Prefer names that START with the term — "kane" should surface Harry Kane above "Kanembwa".
    hits.sort(key=lambda x: (not x[0].lower().startswith(t), x[0].lower()))
    return hits[:limit]


def profile(key):
    """Everything known about one player: goals by edition, squad spells, dob, age at first goal."""
    g = goals()
    mine = g[g["player_key"] == key].sort_values(["year", "date", "minute_sort"])
    s = squads()
    apps = s[s["player_key"] == key].sort_values("year")
    scored = mine[~mine["own_goal"]]
    dob = apps["dob"].dropna()
    dob = dob.iloc[0] if len(dob) else pd.NaT
    per_ed = (scored.groupby("year").size().rename("goals").reset_index()
              if not scored.empty else pd.DataFrame(columns=["year", "goals"]))
    nat = ""
    if not apps.empty:
        nat = apps["nation"].value_counts().index[0]
    elif not mine.empty:
        nat = mine["nation"].value_counts().index[0]
    age_first = None
    if pd.notna(dob) and not scored.empty:
        d = pd.to_datetime(scored["date"].iloc[0], errors="coerce")
        if pd.notna(d):
            age_first = (d - dob).days / 365.25
    return {
        "key": key, "player": _display().get(key, key), "nation": nat, "dob": dob,
        "goals": int(len(scored)), "own_goals": int(mine["own_goal"].sum()),
        "penalties": int(scored["penalty"].sum()),
        "editions_scored": sorted(int(y) for y in scored["year"].unique()),
        "editions_squad": sorted(int(y) for y in apps["year"].unique()),
        "per_edition": per_ed, "goal_rows": scored, "squad_rows": apps,
        "captain_years": sorted(int(y) for y in apps[apps["captain"]]["year"].unique()),
        "clubs": list(dict.fromkeys(apps["club"].tolist())),
        "positions": list(dict.fromkeys(apps["pos"].tolist())),
        "age_at_first_goal": age_first,
    }


@lru_cache(maxsize=1)
def minute_bands():
    """Goals per 15-minute band, for the distribution chart. Stoppage-time goals are folded into the
    band their base minute belongs to (a 90+8' goal is a 76–90 goal, not a 91–105 one)."""
    g = _scoring()
    m = g["minute"].dropna()
    edges = [(1, 15), (16, 30), (31, 45), (46, 60), (61, 75), (76, 90), (91, 105), (106, 120)]
    out = []
    for lo, hi in edges:
        out.append({"band": f"{lo}–{hi}", "goals": int(((m >= lo) & (m <= hi)).sum())})
    return pd.DataFrame(out)


@lru_cache(maxsize=1)
def hauls():
    """Best single-match hauls → [{player, nation, goals, year, stage, opponent}].

    A player cannot appear in two matches on one day, so (year, date, player) identifies the match
    without needing to join back to the match archive.
    """
    g = _scoring()
    grp = g.groupby(["year", "date", "player_key"])
    rows = []
    for (y, d, k), sub in grp:
        if len(sub) >= 4:
            rows.append({"player": _display().get(k, k), "nation": sub["nation"].iloc[0],
                         "goals": len(sub), "year": int(y), "stage": sub["stage"].iloc[0],
                         "opponent": nations().get(sub["opponent_code"].iloc[0],
                                                  sub["opponent_code"].iloc[0])})
    return pd.DataFrame(rows).sort_values(["goals", "year"], ascending=[False, True]).reset_index(drop=True)


@lru_cache(maxsize=1)
def records():
    """Headline player records, all computed rather than hardcoded."""
    g = goals()
    sc = _scoring()
    top = top_scorers_all()
    s = squads()

    # Youngest / oldest scorer — needs the goal date joined to a date of birth, so it only covers
    # scorers we could match to a squad entry with a parseable dob.
    dobs = s.dropna(subset=["dob"]).drop_duplicates("player_key").set_index("player_key")["dob"]
    j = sc[sc["player_key"].isin(dobs.index)].copy()
    j["dob"] = j["player_key"].map(dobs)
    j["gdate"] = pd.to_datetime(j["date"], errors="coerce")
    j = j.dropna(subset=["gdate"])
    j["age"] = (j["gdate"] - j["dob"]).dt.days / 365.25
    j = j[(j["age"] > 14) & (j["age"] < 50)]            # guard against a bad dob skewing a record
    young = j.loc[j["age"].idxmin()] if not j.empty else None
    old = j.loc[j["age"].idxmax()] if not j.empty else None

    most_eds = top.sort_values(["editions", "goals"], ascending=[False, False]).iloc[0]
    h = hauls()
    disp = _display()

    # Squad-side records.
    sd = s.dropna(subset=["dob"]).copy()
    sd["tour"] = pd.to_datetime(sd["year"].astype(str) + "-06-15", errors="coerce")
    sd["age"] = (sd["tour"] - sd["dob"]).dt.days / 365.25
    sd = sd[(sd["age"] > 13) & (sd["age"] < 55)]
    sq_young = sd.loc[sd["age"].idxmin()] if not sd.empty else None
    sq_old = sd.loc[sd["age"].idxmax()] if not sd.empty else None
    apps = s.groupby("player_key")["year"].nunique().sort_values(ascending=False)
    most_apps_key = apps.index[0]

    return {
        "goals": int(len(g)), "scoring_goals": int(len(sc)),
        "own_goals": int(g["own_goal"].sum()), "penalties": int(sc["penalty"].sum()),
        "scorers": int(sc["player_key"].nunique()),
        "squad_players": int(s["player_key"].nunique()),
        "top": (top.iloc[0]["player"], top.iloc[0]["nation"], int(top.iloc[0]["goals"])),
        "most_editions": (most_eds["player"], most_eds["nation"], int(most_eds["editions"])),
        "best_haul": (None if h.empty else
                      (h.iloc[0]["player"], int(h.iloc[0]["goals"]), h.iloc[0]["opponent"],
                       int(h.iloc[0]["year"]))),
        "youngest_scorer": (None if young is None else
                            (disp.get(young["player_key"], young["player_key"]),
                             young["nation"], round(young["age"], 1), int(young["year"]))),
        "oldest_scorer": (None if old is None else
                          (disp.get(old["player_key"], old["player_key"]),
                           old["nation"], round(old["age"], 1), int(old["year"]))),
        # NB these two are YOUNGEST/OLDEST NAMED IN A SQUAD, not youngest/oldest to PLAY —
        # lineups and appearances are absent from the source, so who actually took the
        # field is unknowable here. The UI must label them accordingly.
        "youngest_squad": (None if sq_young is None else
                           (sq_young["player_display"], sq_young["nation"],
                            round(sq_young["age"], 1), int(sq_young["year"]))),
        "oldest_squad": (None if sq_old is None else
                         (sq_old["player_display"], sq_old["nation"],
                          round(sq_old["age"], 1), int(sq_old["year"]))),
        "most_squads": (_display().get(most_apps_key, most_apps_key), int(apps.iloc[0])),
        "first_minute_goals": int((goals()["minute"] == 1).sum()),
    }


def edition_squad(year, nation):
    """One nation's squad for one edition, in shirt order — the roster view."""
    s = squads()
    sub = s[(s["year"] == int(year)) & (s["nation"] == nation)]
    return sub.sort_values(["shirt_no", "player_display"])


def squad_nations(year):
    return sorted(squads()[squads()["year"] == int(year)]["nation"].unique())


def years():
    return sorted(int(y) for y in goals()["year"].unique())
