"""Ingest the 2026 FIFA World Cup (groups, teams, full 104-match schedule, venues) from the
per-group + knockout English Wikipedia articles (CC BY-SA 4.0).

The tournament (June 11 – July 19, 2026, hosted by Canada/Mexico/USA, 48 teams, 12 groups) had
its final draw on 2025-12-05; the schedule was fixed earlier. Matches use {{#invoke:football box}}
with FIFA 3-letter codes ({{#invoke:flag|fb-rt|MEX}}); group membership is derived from each
group's six fixtures; knockout fixtures carry placeholder slots ("Winner Group A", "3rd C/E/F/H/I").
As of the retrieval date no match has been played, so scores are empty (the parser reads them when
present, so a re-run during the tournament fills results in).

Writes (read by app/wc2026.py — NOT merged into the Argentina matches.csv, different scope):
  db/data/wc2026_matches.csv   104 fixtures (72 group + 32 knockout)
  db/data/wc2026_teams.csv     48 teams (code, name, group, confederation, iso2, flag)
  db/data/wc2026_venues.csv    16 host venues

Run: .venv/bin/python db/build/wikipedia_wc2026_ingest.py   (uses cache under sources/wikipedia/wc2026)
"""
import csv
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "sources" / "wc2026"
DATA = ROOT / "data"
UA = {"User-Agent": "ArgFootballDB/0.2 (research; scalonico@ucdavis.edu)"}

# --- Curated metadata for exactly the 48 qualified teams (FIFA code -> name, ISO-3166-1 alpha-2,
#     confederation). Names follow the common short form; ISO2 drives the flag emoji. England and
#     Scotland use subdivision flags. Verified against the drawn groups (2025-12-05 final draw). ---
TEAMS = {
    "MEX": ("Mexico", "MX", "CONCACAF"), "RSA": ("South Africa", "ZA", "CAF"),
    "KOR": ("South Korea", "KR", "AFC"), "CZE": ("Czechia", "CZ", "UEFA"),
    "CAN": ("Canada", "CA", "CONCACAF"), "BIH": ("Bosnia and Herzegovina", "BA", "UEFA"),
    "QAT": ("Qatar", "QA", "AFC"), "SUI": ("Switzerland", "CH", "UEFA"),
    "BRA": ("Brazil", "BR", "CONMEBOL"), "MAR": ("Morocco", "MA", "CAF"),
    "HAI": ("Haiti", "HT", "CONCACAF"), "SCO": ("Scotland", "GB-SCT", "UEFA"),
    "USA": ("United States", "US", "CONCACAF"), "PAR": ("Paraguay", "PY", "CONMEBOL"),
    "AUS": ("Australia", "AU", "AFC"), "TUR": ("Turkey", "TR", "UEFA"),
    "GER": ("Germany", "DE", "UEFA"), "CUW": ("Curaçao", "CW", "CONCACAF"),
    "CIV": ("Ivory Coast", "CI", "CAF"), "ECU": ("Ecuador", "EC", "CONMEBOL"),
    "NED": ("Netherlands", "NL", "UEFA"), "JPN": ("Japan", "JP", "AFC"),
    "SWE": ("Sweden", "SE", "UEFA"), "TUN": ("Tunisia", "TN", "CAF"),
    "BEL": ("Belgium", "BE", "UEFA"), "EGY": ("Egypt", "EG", "CAF"),
    "IRN": ("Iran", "IR", "AFC"), "NZL": ("New Zealand", "NZ", "OFC"),
    "ESP": ("Spain", "ES", "UEFA"), "CPV": ("Cape Verde", "CV", "CAF"),
    "KSA": ("Saudi Arabia", "SA", "AFC"), "URU": ("Uruguay", "UY", "CONMEBOL"),
    "FRA": ("France", "FR", "UEFA"), "SEN": ("Senegal", "SN", "CAF"),
    "IRQ": ("Iraq", "IQ", "AFC"), "NOR": ("Norway", "NO", "UEFA"),
    "ARG": ("Argentina", "AR", "CONMEBOL"), "ALG": ("Algeria", "DZ", "CAF"),
    "AUT": ("Austria", "AT", "UEFA"), "JOR": ("Jordan", "JO", "AFC"),
    "POR": ("Portugal", "PT", "UEFA"), "COD": ("DR Congo", "CD", "CAF"),
    "UZB": ("Uzbekistan", "UZ", "AFC"), "COL": ("Colombia", "CO", "CONMEBOL"),
    "ENG": ("England", "GB-ENG", "UEFA"), "CRO": ("Croatia", "HR", "UEFA"),
    "GHA": ("Ghana", "GH", "CAF"), "PAN": ("Panama", "PA", "CONCACAF"),
}

# 16 host venues (stadium, city, country, capacity) — from the main article's Venues table.
VENUES = [
    ("Estadio Azteca", "Mexico City", "Mexico", 83264),
    ("Estadio BBVA", "Monterrey", "Mexico", 53500),
    ("Estadio Akron", "Guadalajara", "Mexico", 48071),
    ("BC Place", "Vancouver", "Canada", 54500),
    ("BMO Field", "Toronto", "Canada", 45736),
    ("AT&T Stadium", "Dallas", "United States", 94000),
    ("MetLife Stadium", "New York/New Jersey", "United States", 82500),
    ("Mercedes-Benz Stadium", "Atlanta", "United States", 75000),
    ("Arrowhead Stadium", "Kansas City", "United States", 76416),
    ("NRG Stadium", "Houston", "United States", 72220),
    ("Levi's Stadium", "San Francisco Bay Area", "United States", 70909),
    ("SoFi Stadium", "Los Angeles", "United States", 70240),
    ("Lincoln Financial Field", "Philadelphia", "United States", 69596),
    ("Lumen Field", "Seattle", "United States", 68740),
    ("Gillette Stadium", "Boston", "United States", 65878),
    ("Hard Rock Stadium", "Miami", "United States", 65326),
]


def flag_emoji(iso2):
    """Regional-indicator flag from an ISO 3166-1 alpha-2 code; England/Scotland use tag sequences."""
    if iso2 == "GB-ENG":
        return "\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F"
    if iso2 == "GB-SCT":
        return "\U0001F3F4\U000E0067\U000E0062\U000E0073\U000E0063\U000E0074\U000E007F"
    return chr(0x1F1E6 + ord(iso2[0]) - 65) + chr(0x1F1E6 + ord(iso2[1]) - 65)


def wikitext(page):
    """Cached wikitext for a Wikipedia page (fetch once, then reuse offline). Set WC2026_REFRESH=1 to
    bypass the cache and re-fetch live from Wikipedia (used by the tournament cron to pull fresh scores)."""
    fn = CACHE / (page.replace("2026 FIFA World Cup ", "").replace(" ", "_") + ".wikitext")
    if fn.exists() and not __import__("os").environ.get("WC2026_REFRESH"):
        return fn.read_text(encoding="utf-8")
    url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "parse", "page": page, "prop": "wikitext", "format": "json", "redirects": 1})
    txt = __import__("json").load(urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=30))["parse"]["wikitext"]["*"]
    CACHE.mkdir(parents=True, exist_ok=True)
    fn.write_text(txt, encoding="utf-8")
    return txt


def _clean(s):
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[\[([^\]]*)\]\]", r"\1", s)
    s = s.replace("&nbsp;", " ")
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"<[^>]+>", "", s)            # strip stray tags (<ref/>, <includeonly>, <noinclude>…)
    return re.sub(r"\s+", " ", s).strip()


FBOX = re.compile(r"\{\{#invoke:football box\|main(.*?)\n\}\}", re.S)


def _field(block, name):
    m = re.search(r"\|%s=([^\n]*(?:\n(?!\s*\|)[^\n]*)*)" % name, block)
    return m.group(1).strip() if m else ""


# During the tournament FIFA uses sponsorship-neutral generic stadium names ("Toronto Stadium" = BMO
# Field); Wikipedia's fixture list mixes these with the common names. Normalise to the common name used
# in VENUES so every match joins its venue (Toronto is the one that actually appears mixed; the rest are
# defensive in case a re-ingest picks up the FIFA naming).
STADIUM_FIX = {
    "Toronto Stadium": "BMO Field", "Vancouver Stadium": "BC Place", "Dallas Stadium": "AT&T Stadium",
    "New York New Jersey Stadium": "MetLife Stadium", "Atlanta Stadium": "Mercedes-Benz Stadium",
    "Kansas City Stadium": "Arrowhead Stadium", "Houston Stadium": "NRG Stadium",
    "San Francisco Bay Area Stadium": "Levi's Stadium", "Los Angeles Stadium": "SoFi Stadium",
    "Philadelphia Stadium": "Lincoln Financial Field", "Seattle Stadium": "Lumen Field",
    "Boston Stadium": "Gillette Stadium", "Miami Stadium": "Hard Rock Stadium",
    "Estadio Ciudad de México": "Estadio Azteca", "Estadio Monterrey": "Estadio BBVA",
    "Estadio Guadalajara": "Estadio Akron",
}


def _venue(block):
    raw = _clean(_field(block, "stadium"))
    parts = [p.strip() for p in raw.split(",", 1)]
    return STADIUM_FIX.get(parts[0], parts[0]), (parts[1] if len(parts) > 1 else "")


def _score(block):
    """(score1, score2) if the match has been played, else ('', '').
    Pre-match the score field is {{score link|<anchor>|Match N}} (no digits). Once played, Wikipedia
    swaps the link LABEL for the actual score, {{score link|<anchor>|2–0}} — so read the score from the
    link label, not the field start (a leading-digits fallback covers a bare numeric score field).
    A first number–dash–number captures the regulation/extra-time score; any '(x–y p)' penalty tail is
    ignored (the schema stores the on-the-pitch score)."""
    sc = _field(block, "score")
    m = re.search(r"\{\{\s*score link\s*\|[^|}]*\|([^}]*)\}\}", sc)
    label = m.group(1) if m else sc
    m = re.search(r"(\d+)\s*[–-]\s*(\d+)", label)
    if m:
        return m.group(1), m.group(2)
    return "", ""


def _match_no(block):
    """The fixture number = the score-link LABEL, e.g. {{score link|<anchor>|Match 89}}. Use the LAST
    'Match N' in the score field: a knockout anchor embeds its source matches ('#Winner Match 73 vs
    Winner Match 75'), so the first 'Match N' is wrong — the real number is the trailing label.
    Returns 0 once the match is PLAYED (the label becomes the score and the number disappears) — main()
    then recovers it from the prior extract by (date, stadium)."""
    nums = re.findall(r"Match (\d+)", _field(block, "score"))
    return int(nums[-1]) if nums else 0


def parse_group(letter):
    wt = wikitext(f"2026 FIFA World Cup Group {letter}")
    rows, teams = [], []
    for blk in FBOX.findall(wt):
        t1 = re.search(r"\|team1=(?:<!--.*?-->)?\{\{#invoke:flag\|fb[^|]*\|([A-Za-z]{3})\}\}", blk)
        t2 = re.search(r"\|team2=(?:<!--.*?-->)?\{\{#invoke:flag\|fb[^|]*\|([A-Za-z]{3})\}\}", blk)
        d = re.search(r"\|date=\{\{Start date\|(\d+)\|(\d+)\|(\d+)\}\}", blk)
        if not (t1 and t2):
            continue
        c1, c2 = t1.group(1).upper(), t2.group(1).upper()
        for c in (c1, c2):
            if c not in teams:
                teams.append(c)
        stadium, city = _venue(blk)
        s1, s2 = _score(blk)
        rows.append({
            "match_no": _match_no(blk), "stage": "group", "group": letter,
            "date": "%s-%02d-%02d" % (int(d.group(1)), int(d.group(2)), int(d.group(3))) if d else "",
            "time_local": _clean(_field(blk, "time")), "team1": c1, "team2": c2,
            "score1": s1, "score2": s2, "stadium": stadium, "city": city})
    return rows, teams


# Wikipedia's exact level-2 knockout headers -> our stage codes (the Final is transcluded separately).
KO_HDR = {"Round of 32": "R32", "Round of 16": "R16", "Quarterfinals": "QF",
          "Semifinals": "SF", "Match for third place": "3rd"}


def _parse_ko_box(blk, stage):
    """One knockout {{football box}} -> a match row (teams may be 'Winner Group A' placeholders)."""
    d = re.search(r"\|date=\{\{Start date\|(\d+)\|(\d+)\|(\d+)\}\}", blk)
    c1 = re.search(r"\|team1=(?:<!--.*?-->)?\{\{#invoke:flag\|fb[^|]*\|([A-Za-z]{3})\}\}", blk)
    c2 = re.search(r"\|team2=(?:<!--.*?-->)?\{\{#invoke:flag\|fb[^|]*\|([A-Za-z]{3})\}\}", blk)
    stadium, city = _venue(blk)
    s1, s2 = _score(blk)
    return {
        "match_no": _match_no(blk), "stage": stage, "group": "",
        "date": "%s-%02d-%02d" % (int(d.group(1)), int(d.group(2)), int(d.group(3))) if d else "",
        "time_local": _clean(_field(blk, "time")),
        "team1": c1.group(1).upper() if c1 else (_clean(_field(blk, "team1")) or "TBD"),
        "team2": c2.group(1).upper() if c2 else (_clean(_field(blk, "team2")) or "TBD"),
        "score1": s1, "score2": s2, "stadium": stadium, "city": city}


def parse_knockout():
    wt = wikitext("2026 FIFA World Cup knockout stage")
    # tag each football box with the most recent KO-stage header above it
    stage_at = [(h.start(), KO_HDR[h.group(1)]) for h in
                re.finditer(r"^==\s*(%s)\s*==\s*$" % "|".join(map(re.escape, KO_HDR)), wt, re.M)]

    def stage_for(pos):
        cur = "R32"
        for s, c in stage_at:
            if s <= pos:
                cur = c
        return cur

    rows = [_parse_ko_box(m.group(1), stage_for(m.start())) for m in FBOX.finditer(wt)]
    # the Final is transcluded from its own article ({{#lst:2026 FIFA World Cup final|Final}})
    fwt = wikitext("2026 FIFA World Cup final")
    fb = FBOX.search(fwt)
    if fb:
        rows.append(_parse_ko_box(fb.group(1), "F"))
    return rows


MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], 1)}

# The knockout BRACKET template ({{#invoke:RoundN|N32 …}}) is where Wikipedia publishes the actual
# resolved matchups — crucially the eight third-placed teams, which the individual {{football box}}
# entries keep as "3rd Group A/B/C/D/F" placeholders right up to kickoff. Each bracket match line reads
#   |<Month> <D> – [[City…|City]]|{{#invoke:flag|fb|T1}}|<s1>|{{#invoke:flag|fb|T2}}|<s2>
# (the dash is an en-dash). We read both real 3-letter codes keyed by (date, city) so the schedule can
# fill those slots from the source of truth instead of a projection.
BRACKET_LINE = re.compile(
    r"\|([A-Z][a-z]+)\s+(\d{1,2})\s*[–-]\s*\[\[(?:[^\]|]*\|)?([^\]|]+)\]\]"
    r"\|\{\{#invoke:flag\|fb\|([A-Z]{3})\}\}\|[^|]*\|\{\{#invoke:flag\|fb\|([A-Z]{3})\}\}")


def parse_bracket_teams():
    """{(date_iso, city): (team1, team2)} for every knockout bracket match whose BOTH sides have
    resolved to a real 3-letter code. The football boxes lag on third-place slots, so this bracket is
    the authoritative source for who actually plays whom once a round's draw is set."""
    wt = wikitext("2026 FIFA World Cup knockout stage")
    out = {}
    for mon, day, city, t1, t2 in BRACKET_LINE.findall(wt):
        if mon in MONTHS:
            out[("2026-%02d-%02d" % (MONTHS[mon], int(day)), city.strip())] = (t1.upper(), t2.upper())
    return out


# A played match loses its 'Match N' label (it becomes the score), so a mid-tournament ingest can't read
# the number off the box. (date, stadium) is a schedule-fixed key — stable even as knockout placeholders
# resolve to real teams — so the number is recovered from the previous extract. The two tournament openers
# are played from Day 1, so a from-scratch ingest never sees their label either; they are structurally
# fixed (Match 1 = the host nation's opener), so seed them as the bootstrap.
OPENERS = {("2026-06-11", "Estadio Azteca"): 1, ("2026-06-11", "Estadio Akron"): 2}


def backfill_match_nos(matches):
    """Fill match_no for played matches whose 'Match N' label is gone, from the prior CSV's (date, stadium)
    map (self-healing once written) with the OPENERS seed as the from-scratch fallback."""
    prior = DATA / "wc2026_matches.csv"
    sched = {}
    if prior.exists():
        with prior.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("match_no") and r["match_no"] not in ("0", ""):
                    sched[(r["date"], r["stadium"])] = int(r["match_no"])
    for r in matches:
        if not r["match_no"]:
            key = (r["date"], r["stadium"])
            r["match_no"] = sched.get(key) or OPENERS.get(key) or 0
            tag = "prior" if key in sched else ("opener" if key in OPENERS else "UNRESOLVED")
            print(f"  recovered match_no {r['match_no']} ({tag}) for played "
                  f"{r['team1']}-{r['team2']} @ {r['stadium']} {r['date']}")


FIELDS = ["match_no", "stage", "group", "date", "time_local",
          "team1", "team2", "score1", "score2", "stadium", "city"]
CODE = re.compile(r"^[A-Z]{3}$")


def load_prior_matches():
    """The last-good matches.csv as a list of dict rows, or None if it doesn't exist yet (bootstrap)."""
    prior = DATA / "wc2026_matches.csv"
    if not prior.exists():
        return None
    with prior.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def merge_onto_prior(parsed, prior_rows):
    """Overlay this run's fresh parse onto the fixed 104-row schedule from the last-good CSV.

    WHY MERGE instead of writing the parse outright: the WC schedule is fixed (104 matches), but the
    Wikipedia source is NOT a stable 104-box snapshot during the tournament. Editors restructure the
    knockout article (the Round-of-32 football boxes vanished once R16 sub-sections appeared), and a
    single group fixture can briefly drop out mid-edit. A from-scratch parse therefore routinely returns
    <104 boxes — which would make the old strict fail-safe abort and freeze the live site for days. So we
    keep the prior CSV as the authoritative skeleton and only OVERLAY what this parse can see:
      • scores — updated only when BOTH are present, so a transient blank never wipes a stored result;
      • teams  — a placeholder ("Winner Match 73") is upgraded to a real 3-letter code once it resolves.
    Returns (rows, n_score_updates)."""
    by_no = {int(r["match_no"]): r for r in prior_rows if r.get("match_no", "").isdigit()}
    n = 0
    for p in parsed:
        base = by_no.get(p["match_no"]) if p["match_no"] else None
        if not base:
            continue
        if p["score1"] != "" and p["score2"] != "" and \
                (p["score1"], p["score2"]) != (base["score1"], base["score2"]):
            base["score1"], base["score2"] = p["score1"], p["score2"]
            n += 1
        for k in ("team1", "team2"):
            if CODE.match(p[k] or "") and not CODE.match(base[k] or ""):
                base[k] = p[k]
    return prior_rows, n


def main():
    groups, matches = {}, []
    for letter in "ABCDEFGHIJKL":
        rows, teams = parse_group(letter)
        groups[letter] = teams
        matches += rows
    ko = parse_knockout()
    matches += ko
    backfill_match_nos(matches)
    matches.sort(key=lambda r: (r["match_no"] or 999))

    ng = len(matches) - len(ko)
    groups_ok = sum(len(v) for v in groups.values()) == 48 and all(len(v) == 4 for v in groups.values())
    prior = load_prior_matches()

    # ── Two modes:
    #   BOOTSTRAP (no prior CSV): demand the full fixed shape — 12×4 teams, 104 matches (72 group + 32
    #     knockout) at the 16 known venues — and ABORT before writing if the parse falls short, so the
    #     repo never gets seeded with a broken first extract.
    #   MERGE (prior CSV exists): the prior CSV already holds the full 104-row schedule, so a short parse
    #     is normal (Wikipedia restructures the bracket mid-tournament). Overlay fresh scores/teams onto
    #     it and never abort — the worst case is a no-op that keeps last-good data. A short parse is just
    #     LOGGED as a heads-up (not failed), so genuine new scores still reach the live site.
    if prior is None:
        bad_venue = sorted({r["stadium"] for r in matches} - {v[0] for v in VENUES})
        problems = []
        if len(matches) != 104:
            problems.append(f"{len(matches)} matches (expected 104)")
        if ng != 72 or len(ko) != 32:
            problems.append(f"{ng} group + {len(ko)} knockout (expected 72 + 32)")
        if not groups_ok:
            problems.append("groups are not 12 × 4 teams")
        if bad_venue:
            problems.append(f"unknown venue(s): {bad_venue}")
        if problems:
            raise SystemExit("ABORT — the WC-2026 Wikipedia bootstrap parse looks broken ("
                             + "; ".join(problems) + "). Nothing written. Check the source articles.")
        out = matches
    else:
        out, n_upd = merge_onto_prior(matches, prior)
        if len(matches) != 104:
            print(f"NOTE: parse saw {len(matches)} of 104 boxes ({ng} group + {len(ko)} knockout) — "
                  f"normal mid-tournament; merged onto last-good schedule, {n_upd} score(s) updated.")
        else:
            print(f"Full 104-box parse; merged onto last-good schedule, {n_upd} score(s) updated.")

    # teams.csv (group order = draw position within the group). Only regenerated when the group parse is
    # complete (12×4); on a partial parse the existing teams.csv — which is correct — is left untouched.
    DATA.mkdir(parents=True, exist_ok=True)
    if groups_ok:
        with (DATA / "wc2026_teams.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["code", "name", "group", "pos", "confederation", "iso2", "flag"])
            for letter in "ABCDEFGHIJKL":
                for i, code in enumerate(groups[letter], 1):
                    name, iso2, conf = TEAMS.get(code, (code, "", "?"))
                    w.writerow([code, name, letter, i, conf, iso2, flag_emoji(iso2) if iso2 else ""])

    # Resolve knockout slot placeholders from the authoritative bracket template — the football boxes
    # keep "3rd Group …" until kickoff, so without this the third-placed R32 opponents fall back to a
    # projection (which can mis-assign which third plays whom). Upgrade a placeholder side to the real
    # code; never overwrite a code already present, mirroring the conservative merge.
    bracket = parse_bracket_teams()
    n_ko = 0
    for r in out:
        resolved = bracket.get((r["date"], r["city"]))
        if resolved:
            for k, code in zip(("team1", "team2"), resolved):
                if not CODE.match(r[k] or ""):
                    r[k] = code
                    n_ko += 1
    if n_ko:
        print(f"Bracket overlay: resolved {n_ko} knockout slot(s) to real teams from the bracket.")

    with (DATA / "wc2026_matches.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out)

    with (DATA / "wc2026_venues.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["stadium", "city", "country", "capacity"])
        w.writerows(VENUES)

    nteams = sum(len(v) for v in groups.values())
    played = sum(1 for r in out if r["score1"] != "" and r["score2"] != "")
    print(f"groups: {len(groups)} | teams: {nteams} | matches written: {len(out)} "
          f"({played} with scores) | venues: {len(VENUES)}")
    missing = {c for v in groups.values() for c in v if c not in TEAMS}
    if missing:
        print("WARNING unmapped team codes:", missing)
    for letter in "ABCDEFGHIJKL":
        print(f"  Group {letter}: " + ", ".join(
            f"{flag_emoji(TEAMS[c][1])} {TEAMS[c][0]}" for c in groups.get(letter, [])))


if __name__ == "__main__":
    main()
