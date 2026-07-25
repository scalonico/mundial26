"""Replay a World Cup — call any past edition's knockout bracket blind, then score it against history.

Powers the 🔁 Replay tab. The 2026 predictor in wc2026.py cannot be reused for this: it hardcodes that
tournament's topology (12 groups, a 32-team knockout, fixed match numbers 73–104, an 8-best-thirds
allocation). Historical editions differ wildly — 1934 was a straight 16-team knockout with no groups at
all, 1950 finished with a round-robin and never played a Final, 1974/78 inserted a second group stage.

So the bracket here is DERIVED FROM THE RESULTS instead of declared. For every match in round r+1 we ask
which round-r matches its two teams won; that pairing is the tree, and it is correct for every era by
construction. The replay starts at the first knockout round and takes the qualifiers as given, because
which group slot feeds which knockout tie is edition-specific and NOT recoverable from match rows.

Scoring mirrors wc2026.score_picks: credit for teams you advanced into a round that really got there,
weighted so later rounds count double, plus a champion bonus. Nothing here reads or writes the actual
results into the UI — only score() does, so a bracket can be filled in without being spoiled.
"""
from functools import lru_cache

import pandas as pd

import wchistory as wch

# The championship tree only. "third-place" is deliberately absent: it is fed by semi-final LOSERS, so
# it hangs off the side of the tree rather than in it, and asking players to call it adds no tension.
KO_ROUNDS = ("round-of-32", "round-of-16", "quarter-final", "semi-final", "final")
ROUND_LABEL = {"round-of-32": "Round of 32", "round-of-16": "Round of 16",
               "quarter-final": "Quarter-finals", "semi-final": "Semi-finals", "final": "Final"}
_SHORT = {"round-of-32": "R32", "round-of-16": "R16", "quarter-final": "QF",
          "semi-final": "SF", "final": "F"}

# Round weights, applied from the SECOND knockout round onward (the first round's picks are scored by
# who they send into the second). Doubling each round makes a correct Final call worth far more than a
# lucky opener, and it scales to any bracket depth.
_BASE_WEIGHT = 1
_CHAMPION_BONUS_FACTOR = 2          # champion bonus = the final round's weight × this


def _winner(r):
    """Winner of a knockout match: goals, else the shootout. None only for a genuinely undecided tie."""
    if r.home_score > r.away_score:
        return r.home
    if r.away_score > r.home_score:
        return r.away
    if pd.notna(r.pens_home) and r.pens_home != r.pens_away:
        return r.home if r.pens_home > r.pens_away else r.away
    return None


def _ties(sub, stage):
    """Collapse a round's match rows into TIES, merging 1934/38-style replays of a drawn game.

    Before shootouts existed a drawn knockout was simply replayed, so 1934's quarter-finals hold 5 rows
    for 4 ties (Italy 1–1 Spain, then Italy 1–0 Spain) and 1938's round of 16 holds 9 rows for 7. Left
    unmerged the player would be asked to call a match that had no winner, and the feeder lookup would
    see one team win twice in a round. Grouping on the unordered PAIR also survives the replay being
    listed with home and away swapped, as 1938's Switzerland–Germany was.
    """
    order, legs = [], {}
    for r in sub.itertuples():
        key = frozenset((r.home, r.away))
        if key not in legs:
            legs[key] = []
            order.append(key)
        legs[key].append(r)
    out = []
    for n, key in enumerate(order, 1):
        rows = legs[key]
        first = rows[0]
        # The decisive leg is the last one that produced a winner; earlier legs were draws.
        win = next((w for w in (_winner(r) for r in reversed(rows)) if w), None)
        out.append({"mid": f"{_SHORT[stage]}-{n}", "stage": stage,
                    "home": first.home, "away": first.away, "winner": win,
                    "feeders": (None, None), "date": first.date,
                    "venue": getattr(first, "venue", ""), "city": getattr(first, "city", ""),
                    "legs": len(rows)})
    return out


@lru_cache(maxsize=32)
def bracket(year):
    """The knockout tree for one edition, derived from actual results.

    Returns [{stage, label, matches: [tie, …]}, …] first round first, where each tie is
    {mid, stage, home, away, winner, feeders: (mid|None, mid|None), date, venue, city, legs}.
    A feeder is None when that side entered from the group stage (the tree's leaves) — or on a bye, as
    Sweden's 1938 quarter-final was after Austria withdrew, leaving that round of 16 with only 7 ties.
    """
    df = wch.edition_matches(year)
    rounds = []
    for stage in KO_ROUNDS:
        sub = df[df["stage"] == stage]
        if sub.empty:
            continue
        # Deterministic ordering so tie ids are stable across runs (date alone ties on same-day games).
        sub = sub.sort_values(["date", "home", "away"], kind="stable")
        rounds.append({"stage": stage, "label": ROUND_LABEL[stage], "matches": _ties(sub, stage)})

    # Link each round to the one before it: a team in round r+1 got there by winning a round-r tie.
    for i in range(1, len(rounds)):
        won = {m["winner"]: m["mid"] for m in rounds[i - 1]["matches"] if m["winner"]}
        for m in rounds[i]["matches"]:
            m["feeders"] = (won.get(m["home"]), won.get(m["away"]))

    if rounds:
        rounds = _order_as_bracket(rounds)
    return rounds


def _order_as_bracket(rounds):
    """Re-order each round top-to-bottom so a feeder sits beside the tie it flows into.

    Without this the columns are in date order and the lines would cross visually. An in-order walk of
    the tree from the Final down puts each match directly between the two that feed it.
    """
    by_mid = {m["mid"]: m for rd in rounds for m in rd["matches"]}
    seq = {rd["stage"]: [] for rd in rounds}

    def walk(mid):
        m = by_mid.get(mid)
        if not m:
            return
        f1, f2 = m["feeders"]
        walk(f1)
        seq[m["stage"]].append(m)
        walk(f2)

    for m in rounds[-1]["matches"]:                    # usually one Final; loop keeps it general
        walk(m["mid"])
    # Anything the walk missed (a bye, or a round that doesn't feed forward) keeps its date order.
    for rd in rounds:
        seen = {m["mid"] for m in seq[rd["stage"]]}
        rd["matches"] = seq[rd["stage"]] + [m for m in rd["matches"] if m["mid"] not in seen]
    return rounds


def replayable():
    """Editions with a knockout tree at least two rounds deep → [(year, n_matches, first_round_label)].

    Excludes 1950 (a final round-robin, no knockout at all) and 1974/1978, whose "knockout" was the
    Final alone after a second group stage — there is no bracket there to call.
    """
    out = []
    for y in wch.years():
        rds = bracket(y)
        if len(rds) >= 2:
            out.append((y, sum(len(r["matches"]) for r in rds), rds[0]["label"]))
    return out


def resolve(year, picks):
    """Apply a player's picks forward. Returns rounds where every match carries the teams THE PLAYER
    produced — 'pick' (their winner) and 'p_home'/'p_away' (None until both feeders are decided).

    The first round always shows the real qualifiers; later rounds show whoever the player advanced,
    so the bracket fills in as they click, exactly like the 2026 Challenge.
    """
    rds = [dict(rd, matches=[dict(m) for m in rd["matches"]]) for rd in bracket(year)]
    decided = {}                                        # mid → the team the player advanced from it
    for i, rd in enumerate(rds):
        for m in rd["matches"]:
            if i == 0:
                m["p_home"], m["p_away"] = m["home"], m["away"]
            else:
                f1, f2 = m["feeders"]
                # A None feeder means that side entered here directly (group qualifier or 1938 bye):
                # take the real team, since the player was never asked to produce it.
                m["p_home"] = decided.get(f1) if f1 else m["home"]
                m["p_away"] = decided.get(f2) if f2 else m["away"]
            pick = picks.get(m["mid"])
            # Drop a stale pick if re-picking upstream changed who is in this tie.
            m["pick"] = pick if pick in (m["p_home"], m["p_away"]) else None
            if m["pick"]:
                decided[m["mid"]] = m["pick"]
    return rds


def total_matches(year):
    return sum(len(r["matches"]) for r in bracket(year))


def picked_count(year, picks):
    """How many of the player's picks are live (a stale pick from a changed upstream tie doesn't count)."""
    return sum(1 for rd in resolve(year, picks) for m in rd["matches"] if m["pick"])


def champion(year, picks):
    rds = resolve(year, picks)
    return rds[-1]["matches"][0]["pick"] if rds else None


def actual_champion(year):
    c = next((c for c in wch.champions() if c["year"] == int(year)), None)
    return c["champion"] if c else None


def _weights(rds):
    """Weight per round, scored from the 2nd round on: 1, 2, 4, … so the Final dwarfs the opener."""
    return {rd["stage"]: _BASE_WEIGHT * 2 ** (i - 1) for i, rd in enumerate(rds) if i >= 1}


def score(year, picks):
    """Score a filled bracket against history.

    Credit is by REACH, like wc2026.score_picks: for each round after the first, every team the player
    advanced into it that really did play in it. That way a bracket which diverges early still earns for
    the teams it got right later, and every pick is accounted for (the Final's pick is the champion).
    """
    real = bracket(year)
    mine = resolve(year, picks)
    w = _weights(real)
    breakdown, total, possible = [], 0, 0
    for i in range(1, len(real)):
        stage = real[i]["stage"]
        actual_in = {t for m in real[i]["matches"] for t in (m["home"], m["away"])}
        mine_in = {t for m in mine[i]["matches"] for t in (m["p_home"], m["p_away"]) if t}
        hit = mine_in & actual_in
        pts = len(hit) * w[stage]
        breakdown.append({"stage": stage, "label": real[i]["label"], "hit": len(hit),
                          "of": len(actual_in), "weight": w[stage], "points": pts})
        total += pts
        possible += len(actual_in) * w[stage]

    fin_w = w.get(real[-1]["stage"], _BASE_WEIGHT) if len(real) > 1 else _BASE_WEIGHT
    champ_pts_max = fin_w * _CHAMPION_BONUS_FACTOR
    mine_champ, real_champ = champion(year, picks), actual_champion(year)
    champ_ok = bool(real_champ) and mine_champ == real_champ
    total += champ_pts_max if champ_ok else 0
    possible += champ_pts_max
    return {"total": total, "possible": possible, "breakdown": breakdown,
            "champion": mine_champ, "actual_champion": real_champ, "champion_correct": champ_ok,
            "champion_points": champ_pts_max if champ_ok else 0,
            "champion_max": champ_pts_max,
            "pct": round(100 * total / possible) if possible else 0}


def flag(team, w=40):
    return wch.flag_url(team, w)


# ── Share codes ───────────────────────────────────────────────────────────────────────────────────
# A code carries ONE BIT PER TIE in canonical bracket order saying which SIDE was picked, plus a mask
# of which ties are decided so a half-finished bracket survives the round trip. Encoding the side
# rather than the team makes codes short (2026's 31 ties fit in two base-36 words) and self-validating:
# a code can only ever produce teams that really are in that edition's bracket, so a corrupted or
# hand-edited one degrades into a different bracket instead of inventing fixtures.
_CODE_PREFIX = "RP1"
_B36 = "0123456789abcdefghijklmnopqrstuvwxyz"


def _b36(n):
    if not n:
        return "0"
    out = ""
    while n:
        n, r = divmod(n, 36)
        out = _B36[r] + out
    return out


def _walk(year, mask=None, val=None, picks=None):
    """Single forward pass over the tree, used by BOTH encode and decode.

    It has to be a forward pass either way: which teams are in a later tie depends on the earlier
    picks, so the bits cannot be read or written independently of the ones before them.
    """
    rds = bracket(year)
    decided, out_picks, i = {}, {}, 0
    m_out = v_out = 0
    for ri, rd in enumerate(rds):
        for m in rd["matches"]:
            if ri == 0:
                ph, pa = m["home"], m["away"]
            else:
                f1, f2 = m["feeders"]
                ph = decided.get(f1) if f1 else m["home"]
                pa = decided.get(f2) if f2 else m["away"]
            if mask is None:                                    # ENCODE from `picks`
                p = (picks or {}).get(m["mid"])
                if p and p in (ph, pa):
                    m_out |= 1 << i
                    if p == pa:
                        v_out |= 1 << i
                    decided[m["mid"]] = p
            elif mask >> i & 1:                                 # DECODE into picks
                side = pa if (val >> i & 1) else ph
                if side:
                    out_picks[m["mid"]] = decided[m["mid"]] = side
            i += 1
    return (m_out, v_out) if mask is None else out_picks


def encode(year, picks):
    m, v = _walk(year, picks=picks)
    return f"{_CODE_PREFIX}.{year}.{_b36(m)}.{_b36(v)}"


def decode(code):
    """Inverse of encode → (year, picks); None if malformed or for an edition we can't replay."""
    try:
        parts = (code or "").strip().split(".")
        if len(parts) != 4 or parts[0].upper() != _CODE_PREFIX:
            return None
        year, mask, val = int(parts[1]), int(parts[2], 36), int(parts[3], 36)
    except (ValueError, AttributeError):
        return None
    if year not in [y for y, _n, _l in replayable()]:
        return None
    return year, _walk(year, mask=mask, val=val)
