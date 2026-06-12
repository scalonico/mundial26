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

    # ── Fail-safe for the unattended tournament cron. WC-2026 has a FIXED shape: 12 groups × 4 teams,
    # 104 matches (72 group + 32 knockout), all played at the 16 known venues. If a Wikipedia structure
    # change ever makes the parse fall short, ABORT before writing anything — the cron then commits no
    # change, the live site keeps its last-good data, and the run shows red in the Actions tab as a
    # heads-up. (Scores filling in during play do NOT change these counts, so this never false-trips.)
    ng = len(matches) - len(ko)
    bad_venue = sorted({r["stadium"] for r in matches} - {v[0] for v in VENUES})
    problems = []
    if len(matches) != 104:
        problems.append(f"{len(matches)} matches (expected 104)")
    if ng != 72 or len(ko) != 32:
        problems.append(f"{ng} group + {len(ko)} knockout (expected 72 + 32)")
    if sum(len(v) for v in groups.values()) != 48 or any(len(v) != 4 for v in groups.values()):
        problems.append("groups are not 12 × 4 teams")
    if bad_venue:
        problems.append(f"unknown venue(s): {bad_venue}")
    if problems:
        raise SystemExit("ABORT — the WC-2026 Wikipedia parse looks broken (" + "; ".join(problems)
                         + "). Nothing written; last-good data kept. Check the source articles.")

    # teams.csv (group order = draw position within the group)
    DATA.mkdir(parents=True, exist_ok=True)
    with (DATA / "wc2026_teams.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["code", "name", "group", "pos", "confederation", "iso2", "flag"])
        for letter in "ABCDEFGHIJKL":
            for i, code in enumerate(groups[letter], 1):
                name, iso2, conf = TEAMS.get(code, (code, "", "?"))
                w.writerow([code, name, letter, i, conf, iso2, flag_emoji(iso2) if iso2 else ""])

    with (DATA / "wc2026_matches.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["match_no", "stage", "group", "date", "time_local",
                                          "team1", "team2", "score1", "score2", "stadium", "city"])
        w.writeheader()
        w.writerows(matches)

    with (DATA / "wc2026_venues.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["stadium", "city", "country", "capacity"])
        w.writerows(VENUES)

    nteams = sum(len(v) for v in groups.values())
    print(f"groups: {len(groups)} | teams: {nteams} | matches: {len(matches)} "
          f"(group {len(matches) - len(ko)}, knockout {len(ko)}) | venues: {len(VENUES)}")
    missing = {c for v in groups.values() for c in v if c not in TEAMS}
    if missing:
        print("WARNING unmapped team codes:", missing)
    for letter in "ABCDEFGHIJKL":
        print(f"  Group {letter}: " + ", ".join(
            f"{flag_emoji(TEAMS[c][1])} {TEAMS[c][0]}" for c in groups[letter]))


if __name__ == "__main__":
    main()
