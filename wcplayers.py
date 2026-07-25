"""Player layer — query the 1930–2026 goal and squad archives (data/wc_goals.csv, wc_squads.csv).

Powers the 👤 Players tab. Both CSVs are built by build/players.py from Wikipedia; see that file for
how the source markup is parsed and why coverage is exact (all 23 editions and all 120 (year, stage)
pairs match the match archive's scorelines).

Identity is the Wikipedia LINK TARGET, not the displayed name — Wikipedia writes `[[Gigi Riva|Riva]]`,
so the display text is often a bare surname that several players share. Keying on the target is what
lets a scorer be joined to his squad entry, which succeeds for 99.3% of (edition, scorer) pairs once
_KEY_ALIAS reconciles the titles the two page families disagree on (96.8% without it). The six that
remain unmatched are listed under that table, and are left unmatched on purpose: no squad row in
their edition shares a name token, so linking them would rest on outside knowledge rather than on
evidence in the data. Names shown to the reader come from the target too, minus any "(Brazilian footballer)"
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
_AWARDS = _DATA / "wc_awards.csv"
_GOALS = _DATA / "wc_goals.csv"
_SQUADS = _DATA / "wc_squads.csv"

# Squad-page nation spellings → the archive's, so flags resolve and nations read consistently with
# the rest of the site. Only four differ; kept explicit rather than fuzzy-matched.
_ALIAS = {"Bosnia and Herzegovina": "Bosnia-Herzegovina", "China PR": "China",
          "Ivory Coast": "Côte d'Ivoire", "Republic of Ireland": "Ireland"}

POS_NAME = {"GK": "Goalkeeper", "DF": "Defender", "MF": "Midfielder", "FW": "Forward"}

# ── Player identity aliases: goal-page link target → squad-page link target ────────────────────────
# Wikipedia's match reports and squad lists often link the same footballer through different titles,
# which left 52 scorers unjoinable to any squad entry (so no date of birth, no club, no career view).
# Each entry below was checked against the SAME edition and SAME nation before being added; a shared
# surname alone was NOT accepted as proof — "Edino Nazareth Filho" and "Valdo Filho" share only the
# common Brazilian suffix "Filho" and are different players, so that pair is deliberately absent.
#
# The drift falls into five kinds, which is why a generic fuzzy match would be unsafe here:
_KEY_ALIAS = {
    # 1. Punctuation and case in the disambiguator — "(footballer born 1962)" vs "(footballer, born 1962)".
    "Colin Clarke (footballer born 1962)": "Colin Clarke (footballer, born 1962)",
    "Aleksandr Ivanov (footballer born 1928)": "Aleksandr Ivanov (footballer, born 1928)",
    "András Tóth (footballer born 1949)": "András Tóth (footballer, born 1949)",
    # 2. A disambiguator on one side only.
    "Aleksandar Mitrović (footballer)": "Aleksandar Mitrović",
    "David Platt (footballer)": "David Platt",
    "Luis Enrique (footballer)": "Luis Enrique",
    "Winston Reid (footballer)": "Winston Reid",
    "Edmílson (footballer, born 1976)": "Edmílson",
    "Amancio Amaro": "Amancio (footballer)",
    "Theodor Wagner": "Theodor Wagner (footballer)",
    "Carlos Soler": "Carlos Soler (footballer)",
    "Jean Vincent": "Jean Vincent (footballer)",
    "Moderato Wisintainer": "Moderato (footballer)",
    "Miguel Ángel Benítez Pavón": "Miguel Ángel Benítez (footballer)",
    "Márcio Roberto dos Santos": "Márcio Santos (footballer, born 1969)",
    "Luis García Postigo": "Luis García (footballer, born 1969)",
    "José Augusto Torres": "José Torres (footballer, born 1938)",
    # 3. Diacritics, hyphens and Korean/Arabic capitalisation.
    "Óscar Míguez": "Oscar Míguez",
    "Luis Fernández": "Luis Fernandez",
    "Leonel Sanchez": "Leonel Sánchez",
    "Iuliu Barátky": "Iuliu Baratky",
    "Khalid Ismaïl": "Khalid Ismail",
    "Choi Soon-Ho": "Choi Soon-ho",
    "Huh Jung-Moo": "Huh Jung-moo",
    "Kim Jong-Boo": "Kim Jong-boo",
    "Park Chang-Sun": "Park Chang-sun",
    "Sami Al Jaber": "Sami Al-Jaber",
    "Yasser Al Qahtani": "Yasser Al-Qahtani",
    "Mitch Duke": "Mitchell Duke",
    "Andreas Herzog": "Andi Herzog",
    # 4. Transliteration from Cyrillic / Armenian, where the squad page uses the Ukrainian or
    #    Armenian rendering and the match report the Russian one (same player, same squad).
    "Oleg Blokhin": "Oleh Blokhin",
    "Igor Belanov": "Ihor Belanov",
    "Aleksandre Chivadze": "Aleksandr Chivadze",
    "Khoren Oganesian": "Khoren Hovhannisyan",
    "Friedrich Scherfke": "Fryderyk Scherfke",
    "Miklós Kovács (footballer)": "Nicolae Kovács",
    "Ion Andoni Goikoetxea": "Jon Andoni Goikoetxea",
    # 5. Nickname or birth name — the two pages disagree on which the player is filed under.
    "Pep Guardiola": "Josep Guardiola",
    "Txiki Begiristain": "Aitor Begiristain",
    "Brehme": "Andreas Brehme",
    "Ghiggia": "Alcides Ghiggia",
    "Maneca": "Manuel Marinho Alves",
    "Gavril Balint": "Gabi Balint",
    "Ademir de Menezes": "Ademir Marques de Menezes",
    "Alfredo dos Santos": "Alfredo Ramos dos Santos",
    "Reinaldo (footballer, born 1957)": "José Reinaldo de Lima",
    # From the AWARDS pages: Harald "Toni" Schumacher is filed under his nickname there and his given
    # name in West Germany's 1982/86 squads.
    "Toni Schumacher": "Harald Schumacher",
}
# Deliberately NOT aliased — no squad row in that edition shares any name token, so linking them
# would rest on outside knowledge rather than on evidence in the data. They stay unmatched and are
# reported as such: Dani (footballer, born 1951) 1978, Edino Nazareth Filho 1986, Jenílson Ângelo de
# Souza 2002, Júlio Botelho 1954, Thomaz Soares da Silva 1950, Vitaliy Khmelnytskyi 1970.


def _bool(s):
    return s.astype(str).str.strip().str.lower().isin(("1", "true", "yes", "y"))


@lru_cache(maxsize=1)
def goals():
    df = pd.read_csv(_GOALS, dtype=str).fillna("")
    # Canonicalise identity at load, so every downstream tally, join and profile agrees. Applied here
    # rather than at each join site because a player whose goals are split across two link targets
    # would otherwise be double-counted as two people in the all-time table.
    df["player_key"] = df["player_key"].replace(_KEY_ALIAS)
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


def nation_scorers(nation, limit=15):
    """A nation's top World Cup scorers, folding its historical sides — asking for Germany includes
    goals scored as West Germany, matching how wchistory.all_time_table() aggregates nations."""
    g = _scoring().copy()
    g["folded"] = g["nation"].map(wch.fold)
    sub = g[g["folded"] == nation]
    if sub.empty:
        return pd.DataFrame(columns=["player", "goals", "editions", "first", "last"])
    rows = sub.groupby("player_key").agg(
        goals=("player_key", "size"), editions=("year", "nunique"),
        first=("year", "min"), last=("year", "max")).reset_index()
    rows["player"] = rows["player_key"].map(_display())
    return rows.sort_values(["goals", "first"], ascending=[False, True]).head(limit).reset_index(drop=True)


def nation_squad_players(nation, limit=None):
    """Players named in that nation's squads most often (a proxy for a long career, NOT appearances —
    the source has no line-ups, so this counts squads named in, not matches played)."""
    s = squads().copy()
    s["folded"] = s["nation"].map(wch.fold)
    sub = s[s["folded"] == nation]
    if sub.empty:
        return pd.DataFrame(columns=["player", "squads", "first", "last"])
    rows = sub.groupby("player_key").agg(
        squads=("year", "nunique"), first=("year", "min"), last=("year", "max")).reset_index()
    rows["player"] = rows["player_key"].map(_display())
    rows = rows.sort_values(["squads", "first"], ascending=[False, True]).reset_index(drop=True)
    return rows if limit is None else rows.head(limit)


# ── Awards ────────────────────────────────────────────────────────────────────────────────────────
# The OFFICIAL per-edition awards, scraped by build/awards.py from each edition's Awards section. Kept
# separate from the "who scored most" roll computed off wc_goals.csv, because they are different facts:
# the Golden Boot only became an award in 1982 (earlier top scorers were recognised retroactively), and
# in some years its tie-breaks used assists and minutes that this repo has no data for.
AWARD_ORDER = ["Golden Ball", "Golden Boot", "Golden Glove", "Best Young Player",
               "Best player", "Fair Play Trophy", "Most Entertaining Team"]
AWARD_ICON = {"Golden Ball": "🏅", "Golden Boot": "👟", "Golden Glove": "🧤",
              "Best Young Player": "🐣", "Best player": "🗳️", "Fair Play Trophy": "🤝",
              "Most Entertaining Team": "🎉"}
# 1978 has no official Golden Ball (it began in 1982); its article records the journalists' vote that
# FIFA recognises instead. Shown, but labelled so it can't be mistaken for the official award.
AWARD_NOTE = {"Best player": "unofficial — journalists' vote, 1978 had no Golden Ball"}

# A couple of editions pass a non-FIFA abbreviation to the flag template ({{fbicon|HOL}} in 2010), so
# it never resolves through the squad-derived code map. "Soviet Union" needs no entry: it arrives as a
# full nation name already, which is what we want to display.
_AWARD_NATION = {"HOL": "Netherlands", "SPA": "Spain", "GER": "Germany"}


@lru_cache(maxsize=1)
def awards():
    df = pd.read_csv(_AWARDS, dtype=str).fillna("")
    df["player_key"] = df["player_key"].replace(_KEY_ALIAS)     # same canonicalisation as goals()
    df["year"] = df["year"].astype(int)
    df["rank"] = pd.to_numeric(df["rank"], errors="coerce").fillna(1).astype(int)
    df["is_team"] = _bool(df["is_team"])
    df["nation_name"] = df["nation"].map(
        lambda c: _AWARD_NATION.get(c) or nations().get(c, c))
    return df


def award_years():
    """Editions that have any award recorded — the pre-1982 tournaments mostly have none."""
    return sorted(int(y) for y in awards()["year"].unique())


def edition_awards(year, winners_only=True):
    """One edition's awards in canonical order; winners_only drops the ranked runners-up."""
    a = awards()
    a = a[a["year"] == int(year)]
    if winners_only:
        a = a[a["rank"] == 1]
    a = a.copy()
    a["ord"] = a["award"].map(lambda x: AWARD_ORDER.index(x) if x in AWARD_ORDER else 99)
    return a.sort_values(["ord", "rank"])


def player_awards(key):
    """Every award a player won or placed in → [{year, award, rank}], best first."""
    a = awards()
    mine = a[(a["player_key"] == key) & (~a["is_team"])].sort_values(["rank", "year"])
    return [{"year": int(r.year), "award": r.award, "rank": int(r.rank)} for r in mine.itertuples()]


def award_leaders(award, limit=10):
    """Who has won a given award most often (rank 1 only)."""
    a = awards()
    w = a[(a["award"] == award) & (a["rank"] == 1) & (~a["is_team"])]
    if w.empty:
        return pd.DataFrame(columns=["player", "wins", "years"])
    rows = w.groupby("player_key").agg(wins=("year", "nunique"),
                                       years=("year", lambda x: sorted(int(v) for v in x))).reset_index()
    rows["player"] = rows["player_key"].map(_display())
    return rows.sort_values("wins", ascending=False).head(limit).reset_index(drop=True)
