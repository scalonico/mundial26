"""Regression guards for the DATA GUARANTEES the whole site's credibility rests on.

Every assertion here is a fact that was verified by hand while the data was built, and that a future
edit — a re-ingest, a parser tweak, an alias change — could silently break. They are written to fail
loudly with the actual number, because a wrong count is far worse than a crash: the site would keep
rendering, just lying.

Run:  pytest tests -q          (needs pytest; see requirements-dev.txt)
"""
import collections

import pytest

import wchistory as wch
import wcplayers as wpl

# ── Totals. Bare numbers on purpose: if a re-ingest changes one of these, that is exactly the moment
# a human should look, not something to paper over by making the test derive its own expectation.
EDITIONS = 23
MATCHES = 1068
GOALS = 3028
SQUAD_ROWS = 12213


def test_archive_spans_every_edition():
    ys = wch.years()
    assert len(ys) == EDITIONS
    assert ys[0] == 1930 and ys[-1] == 2026
    assert len(wch.matches()) == MATCHES


def test_goal_count_matches_the_archive_per_edition():
    """The load-bearing coverage check: parsed goals must equal the scorelines, edition by edition."""
    arch = collections.Counter()
    for r in wch.matches().itertuples():
        arch[int(r.year)] += max(r.home_score, 0) + max(r.away_score, 0)
    got = collections.Counter(int(y) for y in wpl.goals()["year"])
    bad = {y: (got.get(y, 0), arch[y]) for y in arch if got.get(y, 0) != arch[y]}
    assert not bad, f"goals != scorelines for {bad} (parsed, archive)"
    assert sum(got.values()) == GOALS


def test_goal_count_matches_the_archive_per_stage():
    """Stricter than per-edition: catches goals filed under the wrong ROUND, which a yearly total hides."""
    arch = collections.Counter()
    for r in wch.matches().itertuples():
        arch[(int(r.year), r.stage)] += max(r.home_score, 0) + max(r.away_score, 0)
    got = collections.Counter((int(r.year), r.stage) for r in wpl.goals().itertuples())
    bad = {k: (got.get(k, 0), arch[k]) for k in set(arch) | set(got) if got.get(k, 0) != arch.get(k, 0)}
    assert not bad, f"{len(bad)} (year, stage) mismatches: {bad}"


@pytest.mark.parametrize("player,goals", [
    ("Miroslav Klose", 16),                 # the all-time record holder
    ("Ronaldo (Brazilian footballer)", 15),
    ("Gerd Müller", 14),
    ("Just Fontaine", 13),
    ("Pelé", 12),
])
def test_canonical_top_scorers(player, goals):
    """External ground truth. These fall out of a correct parse unaided, so they are the best single
    signal that identity, own-goal handling and transclusion are all still right."""
    sc = wpl.goals()
    sc = sc[(~sc["own_goal"]) & (sc["year"] != 2026)]      # career totals predate this repo's 2026
    assert int(sc.groupby("player_key").size().get(player, 0)) == goals


def test_own_goals_are_attributed_to_the_scorers_own_nation():
    """Wikipedia files an own goal under the team it BENEFITED. Getting this backwards would corrupt
    every per-nation tally, and would not crash anything."""
    g = wpl.goals()
    guzman = g[(g["year"] == 1970) & g["player_key"].str.contains("Guzmán", na=False)]
    assert len(guzman) == 1
    row = guzman.iloc[0]
    assert bool(row["own_goal"]) and row["team_code"] == "MEX" and row["opponent_code"] == "ITA"


def test_no_impossible_own_goals():
    g = wpl.goals()
    assert not (g["team_code"] == g["opponent_code"]).any()


def test_own_goals_never_count_toward_a_players_tally():
    g = wpl.goals()
    og = g[g["own_goal"]]
    assert len(og) > 0                                     # there ARE own goals to exclude
    top = wpl.top_scorers_all()
    scored = int(g[~g["own_goal"]].groupby("player_key").size().sum())
    assert int(top["goals"].sum()) == scored


def test_no_duplicate_goals():
    g = wpl.goals()
    key = list(zip(g["year"], g["date"], g["player_key"], g["minute"],
                   g["minute_extra"], g["team_code"]))
    dups = [k for k, n in collections.Counter(key).items() if n > 1]
    assert not dups, f"{len(dups)} duplicate goal rows, e.g. {dups[:3]}"


def test_minutes_are_plausible():
    m = wpl.goals()["minute"].dropna()
    assert m.min() >= 1 and m.max() <= 120


# ── Squads ────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("year,teams", [
    (1930, 13), (1934, 16), (1938, 15),                    # 1938 really was 15 — Austria withdrew
    (1950, 13), (1954, 16), (1978, 16),
    (1982, 24), (1994, 24), (1998, 32), (2022, 32), (2026, 48),
])
def test_squad_team_counts(year, teams):
    """1934/1938 head each nation at level 2 (no group stage); 2006/2014 use an older row template.
    Both broke silently once, so the per-edition team count is pinned."""
    assert len(wpl.squad_nations(year)) == teams


def test_every_edition_has_squads():
    assert len(wpl.squad_years()) == EDITIONS
    assert len(wpl.squads()) == SQUAD_ROWS


def test_scorers_join_to_squads():
    """Identity is the wikilink target, reconciled by _KEY_ALIAS. Below ~99% means the alias table has
    fallen behind a page move and player profiles are quietly losing data."""
    sc = wpl.goals()
    sc = sc[~sc["own_goal"]]
    squad_keys = {(int(r.year), r.player_key) for r in wpl.squads().itertuples()}
    pairs = {(int(r.year), r.player_key) for r in sc.itertuples()}
    rate = sum(1 for p in pairs if p in squad_keys) / len(pairs)
    assert rate >= 0.99, f"join rate fell to {rate:.3f}"


# ── Nation folding ────────────────────────────────────────────────────────────────────────────────
def test_west_germany_folds_into_germany():
    s = wch.nation_summary("Germany")
    assert s["editions"] == 21 and s["titles"] == 4
    assert "West Germany" in s["names"]


def test_czechoslovakia_is_not_folded_into_czechia():
    """A state that split, not a rename — merging them would invent a 3-title nation."""
    at = wch.all_time_table()
    assert "Czechoslovakia" in set(at["nation"])
    assert wch.fold("Czechoslovakia") == "Czechoslovakia"
    assert wch.fold("Czech Republic") == "Czechia"
    cz = wch.nation_summary("Czechia")
    assert cz["editions"] == 2                             # 2006 as Czech Republic + 2026 as Czechia


def test_zaire_folds_into_dr_congo():
    s = wch.nation_summary("DR Congo")
    assert s["editions"] == 2 and "Zaire" in s["names"]


def test_shootouts_count_as_draws():
    """FIFA convention, used throughout the all-time table."""
    at = wch.all_time_table()
    row = at[at["nation"] == "Brazil"].iloc[0]
    assert row["P"] == row["W"] + row["D"] + row["L"]


# ── Match metadata, awards, shootouts ─────────────────────────────────────────────────────────────
def test_attendance_and_referee_cover_every_match():
    m = wpl.matchmeta()
    assert len(m) == MATCHES
    assert m["attendance"].notna().all()
    assert (m["referee"] != "").all()


def test_biggest_crowd_is_the_1950_decider():
    top = wpl.crowds(1).iloc[0]
    assert int(top["attendance"]) == 173850 and int(top["year"]) == 1950


@pytest.mark.parametrize("year,award,winner", [
    (2022, "Golden Ball", "Lionel Messi"),
    (2022, "Golden Boot", "Kylian Mbappé"),
    (2018, "Golden Ball", "Luka Modrić"),
    (2006, "Golden Ball", "Zinedine Zidane"),
    (2006, "Golden Glove", "Gianluigi Buffon"),
    (1982, "Golden Ball", "Paolo Rossi"),
])
def test_award_winners(year, award, winner):
    a = wpl.awards()
    got = a[(a["year"] == year) & (a["award"] == award) & (a["rank"] == 1) & (~a["is_team"])]
    assert winner in set(got["player_key"])


def test_team_awards_have_no_player():
    a = wpl.awards()
    assert (a[a["is_team"]]["player_key"] == "").all()
    assert (a[~a["is_team"]]["player_key"] != "").all()


@pytest.mark.parametrize("nation,won,lost", [
    ("Argentina", 6, 1),          # the best shootout record in the tournament's history
    ("Germany", 4, 1),
    ("England", 1, 3),
    ("Netherlands", 1, 4),
])
def test_shootout_records(nation, won, lost):
    r = wpl.nation_shootouts(nation)
    assert (r["won"], r["lost"]) == (won, lost)


def test_shootout_taker_coverage_is_reported_not_assumed():
    """Takers exist for MOST shootouts, not all. The gap must stay visible so the UI can caveat it."""
    c = wpl.shootout_coverage()
    assert c["total"] == 39
    assert c["with_takers"] < c["total"], "if this is now equal, drop the UI's coverage caveat"
    assert 0.5 < c["rate"] < 0.9                           # conversion is ~71%
