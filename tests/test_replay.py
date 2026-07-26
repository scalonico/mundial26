"""Guards for the Replay bracket, which is DERIVED from results rather than declared.

That derivation is clever and therefore fragile: it infers each round's pairings by asking which
earlier tie each team won. Three eras break the naive version of that, and each is pinned below.
"""
import pytest

import wcreplay as R

REPLAYABLE = 20                 # 1950, 1974 and 1978 have no bracket to call


def test_replayable_editions():
    ys = [y for y, _n, _l in R.replayable()]
    assert len(ys) == REPLAYABLE
    for excluded in (1950, 1974, 1978):
        assert excluded not in ys, f"{excluded} has no multi-round knockout"


@pytest.mark.parametrize("year,stage,ties", [
    (1934, "quarter-final", 4),   # 5 match rows: Italy 1-1 Spain was REPLAYED
    (1938, "round-of-16", 7),     # 9 rows for 7 ties, and only 7 because Sweden had a bye
    (1938, "quarter-final", 4),   # Brazil 1-1 Czechoslovakia replayed
    (2026, "round-of-32", 16),
    (1930, "semi-final", 2),
])
def test_replays_are_merged_into_single_ties(year, stage, ties):
    rd = next(r for r in R.bracket(year) if r["stage"] == stage)
    assert len(rd["matches"]) == ties


def test_1938_bye_leaves_a_none_feeder():
    """Sweden reached the quarter-finals without playing, so that side has no feeding tie."""
    qf = next(r for r in R.bracket(1938) if r["stage"] == "quarter-final")
    swe = next(m for m in qf["matches"] if "Sweden" in (m["home"], m["away"]))
    assert None in swe["feeders"]


@pytest.mark.parametrize("year", [y for y, _n, _l in R.replayable()])
def test_feeder_integrity(year):
    """Every non-first-round team must trace to a tie it actually won, or to a bye."""
    rds = R.bracket(year)
    for i in range(1, len(rds)):
        prev = {m["mid"]: m for m in rds[i - 1]["matches"]}
        for m in rds[i]["matches"]:
            for feeder, team in zip(m["feeders"], (m["home"], m["away"])):
                if feeder is not None:
                    assert prev[feeder]["winner"] == team, f"{year} {m['mid']} feeder mismatch"


@pytest.mark.parametrize("year", [y for y, _n, _l in R.replayable()])
def test_a_perfect_bracket_scores_100_percent(year):
    perfect = {m["mid"]: m["winner"] for rd in R.bracket(year) for m in rd["matches"] if m["winner"]}
    sc = R.score(year, perfect)
    assert sc["pct"] == 100 and sc["champion_correct"]
    assert R.picked_count(year, perfect) == R.total_matches(year)


def test_a_wrong_bracket_still_earns_partial_credit():
    """Scoring is by REACH, so an early mistake must not zero out later correct calls."""
    wrong = {m["mid"]: m["away"] for rd in R.bracket(1986) for m in rd["matches"]}
    sc = R.score(1986, wrong)
    assert 0 < sc["total"] < sc["possible"]


def test_changing_an_early_pick_drops_the_stale_ones_downstream():
    b = R.bracket(1986)
    picks = {m["mid"]: m["winner"] for rd in b for m in rd["matches"] if m["winner"]}
    assert R.champion(1986, picks) == "Argentina"
    first = b[0]["matches"][0]
    picks[first["mid"]] = first["away"] if picks[first["mid"]] == first["home"] else first["home"]
    assert R.picked_count(1986, picks) < R.total_matches(1986)
    assert R.champion(1986, picks) is None


@pytest.mark.parametrize("year", [y for y, _n, _l in R.replayable()])
def test_share_codes_round_trip(year):
    full = {m["mid"]: m["winner"] for rd in R.bracket(year) for m in rd["matches"] if m["winner"]}
    for picks in (full, dict(list(full.items())[:3]), {}):
        code = R.encode(year, picks)
        back = R.decode(code)
        assert back is not None and back[0] == year
        assert R.encode(year, back[1]) == code, "encode(decode(x)) must be stable"
    assert R.decode(R.encode(year, full))[1] == full


@pytest.mark.parametrize("bad", ["", "nonsense", "RP1.1899.0.0", "RP1.2026", None])
def test_malformed_codes_return_none_rather_than_raising(bad):
    assert R.decode(bad) is None
