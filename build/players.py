"""Ingest PLAYER-level World Cup data (goalscorers + squads) for all 23 editions, 1930–2026, from
the per-group / knockout / squads English Wikipedia articles (CC BY-SA 4.0).

Companion to build/ingest.py (which does 2026 fixtures) and to data/worldcup_matches.csv (the
match archive). Same fetch/cache conventions, same _clean() helper, stdlib only.

Writes:
  data/wc_goals.csv    one row per GOAL  (year, stage, date, scorer, team, minute, pen/o.g. flags)
  data/wc_squads.csv   one row per SQUAD PLAYER (year, team, shirt no, pos, dob, caps, club)

Run: .venv/bin/python build/players.py        (cache under sources/players/, WCP_REFRESH=1 re-fetches)

──────────────────────────────────────────────────────────────────────────────────────────────────
WHY this file is more defensive than build/ingest.py: ingest.py reads ONE tournament whose articles
were all written by the same editors in the same year. Here we read 96 years of Wikipedia, and the
source markup drifted repeatedly. The four drifts that actually matter:

 1. TWO match-box template flavours with identical named fields. Pre-2020-ish articles use the old
    wrapper `{{Football box`; articles migrated to the Lua module use `{{#invoke:Football box|main`
    (capital F in 1930/1950/2026, lowercase elsewhere — hence the case-insensitive regex). Both are
    terminated by a line STARTING with `}}` — not a line that is exactly `}}`, because the closer is
    routinely glued to a wrapper tag: `}}</onlyinclude>` (1930), `}}<section end=QF1 />` (1970),
    `}}<section end="R32-1" />` (2026).

 2. TWO goal-minute syntaxes. Historic articles use the {{goal}} template (`{{goal|63||76}}`), the
    2026 articles write minutes as plain text (`48', 66'`). Both can yield SEVERAL goals per line.

 3. REDIRECT SPRAWL. `allpages` returns case/punctuation variants that are redirects to the same
    article ("1930 FIFA World Cup Final" + "1930 FIFA World Cup final"; "1986 … Knockout Stage" +
    "… knockout stage"; "2018 … Squads" + "… squads"). Fetching both would double every goal, so we
    resolve redirects through the API and fetch each CANONICAL title exactly once.

 4. OWN GOALS ARE FILED UNDER THE BENEFICIARY. Wikipedia lists an own goal in the goals list of the
    team it benefited, so a goal appearing in `goals1` and flagged `o.g.` was scored by a team2
    player. We flip team/opponent for those rows; getting this backwards would silently corrupt
    every per-nation tally (e.g. 1970 ITA 4–1 MEX: Javier Guzmán's 25' o.g. is a MEX player's goal).

 5. SECTION TRANSCLUSION. Many matches are not written in their stage article at all — the article
    pulls them from a standalone match page ({{#lst:Italy v West Germany (1970 FIFA World Cup)|SF2}}),
    which the "<year> FIFA World Cup" title prefix cannot discover. That accounted for 102 goals
    across 20 matches, including several of the most famous in the tournament's history (the Battle
    of Berne, the Disgrace of Gijón, Brazil 1–7 Germany) and, decisively, the goals that made Klose
    parse 15 instead of his record 16 and Müller 12 instead of 14. So _lst_pages() follows those
    transclusions one level deep, OUTWARD FROM THE PATTERN-MATCHED PAGES ONLY: those pages are the
    authoritative list of an edition's rounds, so anything they transclude is a match of that
    tournament and the transcluding section pins its stage (a standalone title like "Battle of Berne"
    says nothing about being a 1954 quarter-final). Chasing links out of the standalone articles
    instead would wander into rivalry and "see also" pages with no stage context.

    Double counting is prevented at discovery: a transclusion target already in the pattern set is
    never added. That matters most for 2026, whose knockout article transcludes the round-of-32
    article sixteen times.

COVERAGE, verified against the match archive rather than asserted: every one of the 23 editions now
parses exactly as many goals as its scorelines contain (3,028 total), and every (year, stage) pair
agrees too — the stricter check, since it catches goals filed under the wrong round. main() prints
both tables, so a future source change shows up as a delta instead of passing silently.
"""
import csv
import json
import os
import re
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "sources" / "players"
DATA = ROOT / "data"
UA = {"User-Agent": "mundial26/1.0 (scalonico@ucdavis.edu)"}
REFRESH = bool(os.environ.get("WCP_REFRESH"))

YEARS = [1930, 1934, 1938] + list(range(1950, 2027, 4))


# ──────────────────────────────────────────────────────────────────────────── fetching / caching ──
def _api(**params):
    """One api.php GET returning parsed JSON. Politeness sleep lives in the two callers that hit the
    network; this is the only place we open a socket."""
    params.setdefault("format", "json")
    url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return json.load(r)


def wikitext(page):
    """Cached wikitext for a Wikipedia page (fetch once, then reuse offline). Same shape as
    build/ingest.py's fetcher; WCP_REFRESH=1 bypasses the cache. Cache filename is the page title
    with spaces -> underscores, so the cache is human-browsable and matches source_page."""
    fn = CACHE / (page.replace(" ", "_").replace("/", "%2F") + ".wikitext")
    if fn.exists() and not REFRESH:
        return fn.read_text(encoding="utf-8")
    txt = _api(action="parse", page=page, prop="wikitext", redirects=1)["parse"]["wikitext"]["*"]
    CACHE.mkdir(parents=True, exist_ok=True)
    fn.write_text(txt, encoding="utf-8")
    time.sleep(0.3)
    return txt


def _clean(s):
    """build/ingest.py's cleaner verbatim: drop comments/refs, unwrap wikilinks to their DISPLAY
    text, kill leftover templates and tags, squeeze whitespace."""
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[\[([^\]]*)\]\]", r"\1", s)
    s = s.replace("&nbsp;", " ")
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


# ─────────────────────────────────────────────────────────────────────────────── page discovery ──
# Only these three article families carry player data. Anchored + case-insensitive because the same
# article exists under several capitalisations (all but one of which are redirects).
def _patterns(year):
    return [re.compile(p % year, re.I) for p in (
        r"^%d FIFA World Cup Group [0-9A-L]$",
        r"^%d FIFA World Cup (?:knockout stage|round of 32|round of 16|quarterfinals|"
        r"semi-finals|final round|final)$",
        # 2006 also exists as "2006 FIFA World Cup (squads)" and 2014 as "… squad" — both redirects
        # to the canonical "… squads", but accept them so a title rename can't silently drop an
        # edition's whole squad list.
        r"^%d FIFA World Cup \(?squads?\)?$",
    )]


# A stage article can hold a match by REFERENCE instead of by value: 20 famous matches across 14
# editions live on their own article and are pulled in with {{#lst:Article|section}} (labelled
# section transclusion). {{#lstx:}} and {{Section transclusion|…}} are the same mechanism, and 1950
# wraps one in {{#invoke:transcludable section|…|text={{#lst:…}}}} — the inner #lst still matches.
# The parent's wikitext contains only the CALL, never the box, so these matches are invisible to a
# parse of the stage articles alone: that was the entire 102-goal shortfall, and it is why our
# all-time top-scorer list had Klose on 15 instead of 16 and Müller on 12 instead of 14.
LST = re.compile(r"\{\{\s*(?:#lstx?\s*:|Section transclusion\s*\|)\s*([^|}\n]+?)\s*\|", re.I)


def discover():
    """{year: [(canonical title, matched title, forced stage or None)]} — allpages by prefix,
    filtered to the three families, redirect-resolved, de-duplicated, then extended with the
    {{#lst:}} targets those pages transclude.

    The first two titles are both kept because a redirect can land on an article whose NAME no longer
    says what round it is: "1950 FIFA World Cup final" redirects to "Uruguay v Brazil (1950 FIFA
    World Cup)" and "1938 FIFA World Cup knockout stage" to "1938 FIFA World Cup final tournament".
    We fetch the canonical title (and cite it as source_page) but derive the STAGE from the title that
    matched our pattern, which is the one that actually names the round.

    The third element is how a transcluded match gets its stage. "Battle of Berne" and "Disgrace of
    Gijón" name a match, not a round, so their own titles are useless for staging; the authority is
    the section of the PARENT that transcludes them ("Battle of Berne" sits under the 1954 knockout
    article's ==Quarter-finals==, so it is a quarter-final). We resolve that at discovery time and
    pin it, so the standalone article's own headings can never override it.

    WHY the redirect round-trip: `allpages` lists REDIRECTS as if they were articles. For 1930 it
    returns both "…Final" and "…final" and both "…Semi-finals" and "…semi-finals"; without resolving
    them we would fetch (and count) the same football boxes two or three times. Resolution is also
    how the 1930/1934/1938 "…final" pages get correctly folded in or out — we never assume.

    The discovery result is cached as JSON so re-runs are fully offline (WCP_REFRESH=1 redoes it)."""
    cachefile = CACHE / "_titles.json"
    if cachefile.exists() and not REFRESH:
        cached = json.loads(cachefile.read_text())
        return {int(y): [tuple(p) for p in v] for y, v in cached.items()}

    CACHE.mkdir(parents=True, exist_ok=True)
    out = {}
    for year in YEARS:
        # aplimit=200 is NOT enough for the busy editions (2006 returns exactly 200 = truncated, and
        # that silently loses "2006 FIFA World Cup squads"), so follow apcontinue to exhaustion.
        titles, cont = [], None
        while True:
            q = dict(action="query", list="allpages", apprefix=f"{year} FIFA World Cup",
                     apnamespace=0, aplimit=200)
            if cont:
                q["apcontinue"] = cont
            d = _api(**q)
            titles += [p["title"] for p in d["query"]["allpages"]]
            time.sleep(0.3)
            cont = d.get("continue", {}).get("apcontinue")
            if not cont:
                break
        pats = _patterns(year)
        keep = [t for t in titles if any(p.match(t) for p in pats)]

        # Resolve redirects in batches of 50 (API cap) and keep insertion-ordered unique targets.
        # When SEVERAL matched titles land on the same page, the page's OWN name wins as the stage
        # source: 1950 had four groups, so "1950 FIFA World Cup Group 5" is a redirect to
        # "1950 FIFA World Cup final round" — and it sorts first in allpages, so first-wins would
        # label the whole final round as 'group'.
        canon, best = [], {}
        for i in range(0, len(keep), 50):
            batch = keep[i:i + 50]
            d = _api(action="query", titles="|".join(batch), redirects=1)
            time.sleep(0.3)
            redir = {r["from"]: r["to"] for r in d["query"].get("redirects", [])}
            missing = {p["title"] for p in d["query"].get("pages", {}).values() if "missing" in p}
            for origin in batch:
                # a redirect can chain; follow it (bounded) to the final target
                t, seen = origin, set()
                while t in redir and t not in seen:
                    seen.add(t)
                    t = redir[t]
                if t in missing:
                    continue
                if t not in best:
                    best[t] = origin
                    canon.append(t)
                elif origin.lower() == t.lower():
                    best[t] = origin
        out[year] = [(t, best[t], None) for t in canon]
        out[year] += _lst_pages(year, out[year])
    cachefile.write_text(json.dumps({str(k): v for k, v in out.items()}, indent=1))
    return out


def _lst_pages(year, pattern_pages):
    """[(canonical title, matched title, stage)] for the {{#lst:}} targets of this edition's stage
    articles — the standalone match articles that the pattern set cannot reach.

    ONE level deep, and only outward from the pattern-matched pages. That is deliberate: those pages
    are the authoritative list of an edition's rounds, so a target they transclude is a match of this
    tournament and the transcluding SECTION gives its stage. Chasing links out of the standalone
    articles in turn would wander off into rivalry and 'see also' articles with no stage context.
    Targets already in the pattern set are skipped — that is what keeps 2026 from being counted
    twice, since its knockout article transcludes '2026 FIFA World Cup round of 32' (a page we
    already fetch) sixteen times."""
    known = {t.lower() for t, _, _ in pattern_pages}
    found, order = {}, []
    for title, origin, _ in pattern_pages:
        if re.search(r"squads?\)?$", origin, re.I):
            continue
        wt = wikitext(title)
        default = title_stage(year, origin)
        stages = stage_index(wt, default if default != "knockout" else "final")
        for m in LST.finditer(wt):
            tgt = m.group(1).strip()
            if tgt.lower() in known or tgt.lower() in found:
                continue                 # each target is transcluded twice (box + line-ups)
            stage = default
            for pos, s in stages:
                if pos <= m.start():
                    stage = s
            found[tgt.lower()] = (tgt, stage)
            order.append(tgt.lower())
    if not found:
        return []
    # resolve redirects on the targets too, and drop any that collide with a page we already have
    titles = [found[k][0] for k in order]
    out = []
    for i in range(0, len(titles), 50):
        batch = titles[i:i + 50]
        d = _api(action="query", titles="|".join(batch), redirects=1)
        time.sleep(0.3)
        redir = {r["from"]: r["to"] for r in d["query"].get("redirects", [])}
        missing = {p["title"] for p in d["query"].get("pages", {}).values() if "missing" in p}
        for origin in batch:
            t, seen = origin, set()
            while t in redir and t not in seen:
                seen.add(t)
                t = redir[t]
            if t in missing or t.lower() in known:
                continue
            known.add(t.lower())
            out.append((t, origin, found[origin.lower()][1]))
    return out


# ───────────────────────────────────────────────────────────────────── wikitext micro-parsers ──
def _tmpl_body(s, i):
    """Body of the {{…}} template starting at s[i] (== '{{'), brace-depth matched, plus the index
    just past its closer. Needed because {{nat fs player}} nests {{Birth date and age2}} — a lazy
    regex to the first '}}' would truncate the parameter list mid-way."""
    depth, j = 0, i
    while j < len(s):
        if s.startswith("{{", j):
            depth += 1
            j += 2
        elif s.startswith("}}", j):
            depth -= 1
            j += 2
            if depth == 0:
                return s[i + 2:j - 2], j
        else:
            j += 1
    return s[i + 2:], len(s)


def _split_params(body):
    """Split a template body on TOP-LEVEL '|' only, ignoring pipes inside nested {{…}} and [[…|…]].
    Every squad row needs this: `club=[[C.D. Guadalajara|Guadalajara]]` and
    `age={{Birth date and age2|df=yes|1970|5|31|1943|12|13}}` are single parameters containing pipes."""
    parts, buf, d, b, i = [], [], 0, 0, 0
    while i < len(body):
        if body.startswith("{{", i):
            d += 1
            buf.append("{{")
            i += 2
        elif body.startswith("}}", i):
            d -= 1
            buf.append("}}")
            i += 2
        elif body.startswith("[[", i):
            b += 1
            buf.append("[[")
            i += 2
        elif body.startswith("]]", i):
            b -= 1
            buf.append("]]")
            i += 2
        elif body[i] == "|" and d <= 0 and b <= 0:
            parts.append("".join(buf))
            buf = []
            i += 1
        else:
            buf.append(body[i])
            i += 1
    parts.append("".join(buf))
    return parts


LINK = re.compile(r"\[\[\s*([^\]|]+?)\s*(?:\|\s*([^\]]*?)\s*)?\]\]")


def _player(text):
    """(player_key, player_display) from a fragment containing a wikilink.

    THE IDENTITY RULE (deliberate, user-chosen): the key is the wikilink TARGET, not the label —
    `[[Gigi Riva|Riva]]` -> ("Gigi Riva", "Riva"), `[[Neymar]]` -> ("Neymar", "Neymar"). Targets are
    globally unique on Wikipedia and stable across editions, whereas labels are surnames that
    collide constantly ("Rodríguez" appears in a dozen squads). A pipe-less link has no separate
    label, so key == display. An unlinked name (a few 1930s scorers) falls back to its plain text,
    which is the best key available for it."""
    m = LINK.search(text)
    if not m:
        return "", ""
    key = m.group(1).split("#")[0].lstrip(":").strip()
    disp = (m.group(2) or m.group(1)).strip()
    return key, _clean(disp)


# ────────────────────────────────────────────────────────────────────────────── match box parsing ──
# Both flavours in one pattern (see docstring drift #1). `(?s:.*?)` up to a line that STARTS with
# '}}' — the closer is often glued to </onlyinclude> or <section end=… />.
FBOX = re.compile(r"\{\{\s*(?:#invoke:\s*)?football box\s*(?:\|\s*main)?(.*?)\n\}\}", re.S | re.I)

START_DATE = re.compile(r"\{\{\s*start date\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})", re.I)
MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], 1)}
DMY = re.compile(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})")
MDY = re.compile(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})")


def _fields(box_body):
    """{name: value} for a football box. Fields are one-per-line and start with '|', while VALUES
    may span lines (a goals list is several '*' lines), so we split on newline-pipe — never on bare
    '|', which would shred `[[Estadio Nemesio Díez|Estadio Luis Dosal]]`."""
    segs = re.split(r"\n\s*\|", box_body)
    if segs and segs[0].startswith("|"):
        segs[0] = segs[0][1:]
    out = {}
    for seg in segs:
        name, sep, val = seg.partition("=")
        if sep and re.fullmatch(r"[A-Za-z0-9_ -]{1,20}", name.strip()):
            out.setdefault(name.strip().lower(), val)
    return out


# A handful of team fields name the nation instead of passing a FIFA code. All of them, corpus-wide
# (verified by scanning every football box in all 23 editions):
#   {{fb|US|1960}}                                     1998 + 2006  -> USA
#   {{fb|FR Yugoslavia|name=FR Yugoslavia}}            1998         -> YUG
#   {{fb-rt|Kingdom of Yugoslavia}}                    1930         -> YUG
#   {{flagicon|…}} [[Yugoslavia national football team|Yugoslavia]]         1930 -> YUG
#   {{flagicon|…}} [[Indonesia national football team|Dutch East Indies]]   1938 -> DEI
# Left unmapped these fields yield no code at all, which silently DROPS the whole match (that is how
# 1998 USA vs Iran and its 3 goals went missing on the first run).
NAME_CODE = {
    "US": "USA", "UNITED STATES": "USA",
    "FR YUGOSLAVIA": "YUG", "KINGDOM OF YUGOSLAVIA": "YUG", "YUGOSLAVIA": "YUG",
    "DUTCH EAST INDIES": "DEI", "DUTCH EAST INDIA COMPANY": "DEI",
}
FB_ARG = re.compile(r"\{\{\s*(?:#invoke:\s*flagg?\s*\|[^|}]*\|)?(?:avar=)?"
                    r"(?:fb[a-z-]*|flagicon)\s*\|\s*([^|}\n]+)", re.I)


def _code(field):
    """The 3-letter FIFA code out of any team field flavour: {{fb-rt|URS|1955}}, {{fb|URU}},
    {{#invoke:flag|fb-rt|SUI}}, {{#invoke:flagg|main|unpre|avar=fb|ARG}}, {{nowrap|{{fb|FRG}}}}.
    Every surrounding token is lowercase or hyphenated, so the first bare uppercase triple IS the
    code — that covers ~99.5% of boxes. The rest name the nation in words; fall back to NAME_CODE on
    the flag template's first argument and then on the plain-text rendering of the whole field."""
    field = re.sub(r"<!--.*?-->", "", field, flags=re.S)
    m = re.search(r"\b([A-Z]{3})\b", field)
    if m:
        return m.group(1)
    for cand in FB_ARG.findall(field) + [_clean(field)]:
        cand = re.sub(r"\s+national football team$", "", cand.strip(), flags=re.I)
        if cand.upper() in NAME_CODE:
            return NAME_CODE[cand.upper()]
    return ""


def _date(field):
    """YYYY-MM-DD from {{Start date|Y|M|D|df=y}}, '14 June 1970', or 'June 28, 2026'."""
    m = START_DATE.search(field)
    if m:
        return "%s-%02d-%02d" % (m.group(1), int(m.group(2)), int(m.group(3)))
    txt = _clean(field)
    m = DMY.search(txt)
    if m and m.group(2).lower() in MONTHS:
        return "%s-%02d-%02d" % (m.group(3), MONTHS[m.group(2).lower()], int(m.group(1)))
    m = MDY.search(txt)
    if m and m.group(1).lower() in MONTHS:
        return "%s-%02d-%02d" % (m.group(3), MONTHS[m.group(1).lower()], int(m.group(2)))
    return ""


MIN_TOKEN = re.compile(r"^(\d{1,3})(?:\s*\+\s*(\d{1,2}))?$")
_FLAG_RX = r"o\.?\s?g\.?|og|pen\.?|p\.?k\.?"
# plain syntax, apostrophe REQUIRED: 48'   90+10' pen.   45+1',   87' (o.g.)
PLAIN_MIN = re.compile(r"(\d{1,3})(?:\s*\+\s*(\d{1,3}))?\s*[''′’]"
                       r"(?:\s*\(?\s*(%s)\s*\)?)?" % _FLAG_RX, re.I)
# …and apostrophe OPTIONAL, for the 2026 articles that write bare numbers ("Larin]] 16",
# "J. David]] 29, 45+3, 90+2", "Xhaka]] 90+7 pen"). A bare-number pattern is far too greedy to run
# on arbitrary text, so it is used ONLY when the whole tail after the player link is nothing but a
# minute list (MIN_LIST below) — otherwise any stray year or squad number would become a goal.
PLAIN_MIN_LOOSE = re.compile(r"(\d{1,3})(?:\s*\+\s*(\d{1,3}))?\s*[''′’]?"
                             r"(?:\s*\(?\s*(%s)\s*\)?)?" % _FLAG_RX, re.I)
_MIN_ITEM = r"\d{1,3}(?:\s*\+\s*\d{1,3})?\s*[''′’]?\s*(?:\(?\s*(?:%s)\s*\)?)?" % _FLAG_RX
MIN_LIST = re.compile(r"^(?:%s)(?:\s*[,;]\s*|\s+)?(?:(?:%s)(?:\s*[,;]\s*|\s+)?)*[.,;]?$"
                      % (_MIN_ITEM, _MIN_ITEM), re.I)


def _flag(tok):
    """('pen'|'og'|None) for a non-numeric goal annotation. Wikipedia writes these as `pen.`,
    `o.g.`, occasionally `og`/`pen`; anything else (a footnote marker, a stray '?') is ignored."""
    t = tok.strip().lower().replace(" ", "")
    if t.startswith("o.g") or t == "og":
        return "og"
    if t.startswith("pen") or t.startswith("p.k") or t == "pk":
        return "pen"
    return None


def parse_goals_field(field):
    """[(player_key, player_display, minute, minute_extra, penalty, own_goal)] for one goals1/goals2
    value. One '*' line can yield SEVERAL goal rows — a hat-trick is a single line.

    Two minute syntaxes (drift #2):
      {{goal}} template — numeric params are minutes ('90+8' allowed); EMPTY params are cosmetic
        separators and must be skipped (`{{goal|63||76}}` is 63' and 76', not three goals); other
        params are FLAGS that attach to the minute they follow (`{{goal|25|o.g.}}`). {{golden goal}}
        (1998 Blanc, 2002 Ahn/Mansız) is the same template with a different name.
      plain text     — `48', 66'` / `90+10' pen.` / `37', 45+1', 87' pen.`, and in some 2026 group
        articles the apostrophe is simply omitted: `29, 45+3, 90+2` / `90+7 pen`.
    Most scorer lines are list items ('*…'), but four 2026 lines omit the bullet and start straight
    at the wikilink, so both forms are accepted.
    """
    field = re.sub(r"<!--.*?-->", "", field, flags=re.S)
    field = re.sub(r"<ref[^>]*/>", "", field)
    field = re.sub(r"<ref[^>]*>.*?</ref>", "", field, flags=re.S)
    field = re.sub(r"\{\{\s*(?:efn|sfn|refn|note|NoteTag)[^{}]*\}\}", "", field, flags=re.I)
    rows = []
    for line in field.split("\n"):
        line = line.strip()
        if not (line.startswith("*") or line.startswith("[[")):
            continue
        line = line.lstrip("*").strip()
        key, disp = _player(line)
        m = LINK.search(line)
        tail = line[m.end():] if m else line
        if not key:
            # unlinked scorer: the name is whatever precedes the first minute marker
            cut = re.search(r"\{\{\s*(?:golden |silver )?goal|\d{1,3}\s*[''′]", line, re.I)
            key = disp = _clean(line[:cut.start()] if cut else line)
            tail = line[cut.start():] if cut else ""
        if not key:
            continue

        goals = []          # [minute, extra, pen, og]
        GOAL_TMPL = r"\{\{\s*(?:golden |silver )?goal\b"
        gm = re.search(GOAL_TMPL, line, re.I)
        if gm:
            # every {{goal}} on the line (a line may carry more than one)
            pos = 0
            while True:
                gm = re.search(GOAL_TMPL, line[pos:], re.I)
                if not gm:
                    break
                body, nxt = _tmpl_body(line, pos + gm.start())
                pos = nxt
                params = _split_params(body)[1:]     # [0] is the template name
                for p in params:
                    p = _clean(p) if ("[[" in p or "{{" in p) else p.strip()
                    if not p:
                        continue                     # cosmetic separator
                    mt = MIN_TOKEN.match(p)
                    if mt:
                        goals.append([int(mt.group(1)), mt.group(2) or "", 0, 0])
                    else:
                        f = _flag(p)
                        if f and goals:
                            goals[-1][2 if f == "pen" else 3] = 1
        else:
            txt = _clean(tail)
            rx = PLAIN_MIN_LOOSE if MIN_LIST.match(txt) else PLAIN_MIN
            for mt in rx.finditer(txt):
                f = _flag(mt.group(3) or "")
                goals.append([int(mt.group(1)), mt.group(2) or "",
                              1 if f == "pen" else 0, 1 if f == "og" else 0])
        for minute, extra, pen, og in goals:
            rows.append((key, disp, minute, extra, pen, og))
    return rows


# ─────────────────────────────────────────────────────────────────────────────── stage vocabulary ──
# Same vocabulary as data/worldcup_matches.csv (group, group-2, final-round, round-of-32,
# round-of-16, quarter-final, semi-final, third-place, final).
KO_HDR = [
    (re.compile(r"^round of 32$", re.I), "round-of-32"),
    (re.compile(r"^round of 16$", re.I), "round-of-16"),
    (re.compile(r"^quarter[- ]?finals?$", re.I), "quarter-final"),
    (re.compile(r"^semi[- ]?finals?$", re.I), "semi-final"),
    (re.compile(r"^(?:match for third place|third[- ]place(?: (?:play-?off|match))?|"
                r"bronze medal match)$", re.I), "third-place"),
    (re.compile(r"^final round$", re.I), "final-round"),
    (re.compile(r"^final$", re.I), "final"),
]
# 1974/1978/1982 ran TWO group series: numbered groups are the first stage, lettered groups the
# second — the reverse of 1986+, where letters ARE the first stage. Same convention as the archive.
TWO_STAGE_GROUPS = {1974, 1978, 1982}


def title_stage(year, title):
    """Default stage for every box on a page, from its (canonical) title."""
    t = title.lower().replace(f"{year} fifa world cup", "").strip()
    m = re.fullmatch(r"group ([0-9a-l])", t)
    if m:
        if year in TWO_STAGE_GROUPS and m.group(1).isalpha():
            return "group-2"
        return "group"
    for rx, stage in KO_HDR:
        if rx.match(t):
            # 1950 is the one edition with NO final match: the title was decided inside a four-team
            # final round-robin, and the archive files all six of those matches as 'final-round'.
            # "1950 FIFA World Cup Final" redirects to the deciding Uruguay v Brazil article, so
            # without this it would come out as the only 'final' of 1950.
            return "final-round" if (year == 1950 and stage == "final") else stage
    if t == "knockout stage":
        return "knockout"          # placeholder: resolved per-box from the section headings
    return t.replace(" ", "-") or "unknown"


H2 = re.compile(r"^==\s*([^=].*?)\s*==\s*$", re.M)


def stage_index(wt, default):
    """[(char offset, stage)] for the level-2 headings that name a knockout round, so each football
    box takes the stage of the heading above it. A 'knockout stage' article mixes rounds, so the
    title alone is not enough; group articles have no such headings and keep the default."""
    idx = []
    for h in H2.finditer(wt):
        for rx, stage in KO_HDR:
            if rx.match(h.group(1)):
                idx.append((h.start(), stage))
                break
    return idx or [(0, default)]


VS_HDR = re.compile(r"^===\s*(?:Replay:\s*)?(.+?)\s+vs?\.?\s+(.+?)\s*===\s*$", re.M | re.I)


SCORE = re.compile(r"(\d+)\s*[–—-]\s*(\d+)")


def _box_score(field):
    """(s1, s2) from the box's own score field. Once a match is played the score is the LABEL of
    {{score link|<anchor>|4–1}}, so read the label; a bare '4–1' works too. This is the per-match
    ground truth we audit the scorer lists against — independent of data/worldcup_matches.csv."""
    m = re.search(r"\{\{\s*score link\s*\|[^|}]*\|([^}]*)\}\}", field, re.I)
    m2 = SCORE.search(m.group(1) if m else field)
    return (int(m2.group(1)), int(m2.group(2))) if m2 else (None, None)


ATT = re.compile(r"([\d][\d,.\s]*\d|\d)")
# "[[Laurens van Ravens]] ([[Royal Dutch Football Association|Netherlands]])" -> name + nation. _clean()
# has already flattened the wikilinks by the time this sees it, so the nation is the LAST parenthetical
# — last, not first, because a name can itself carry one ("Ali Bin Nasser (referee)").
REF_NAT = re.compile(r"^(.*?)\s*\(([^()]*)\)\s*$")


def _attendance(v):
    """Crowd as an int. Sources write '26,085', '73 000', 'N/A', or leave it blank; anything without a
    plausible number becomes empty rather than a guess, and 0 is treated as absent (a few boxes use it
    for 'behind closed doors' or simply unknown)."""
    t = _clean(v)
    m = ATT.search(t)
    if not m:
        return ""
    n = re.sub(r"[^\d]", "", m.group(1))
    if not n:
        return ""
    n = int(n)
    return "" if n == 0 or n > 300000 else n          # 1950's Maracanã ~200k is the real ceiling


def _referee(v):
    """(name, nation) from the referee field; nation empty when the source names only the official."""
    t = _clean(v)
    if not t:
        return "", ""
    m = REF_NAT.match(t)
    if not m:
        return t, ""
    name, nat = m.group(1).strip(), m.group(2).strip()
    # A trailing "(referee)" is a disambiguator, not a country.
    return (t, "") if nat.lower() in ("referee", "footballer") else (name, nat)


# Shootout takers. 1986 writes the outcome as a template ({{pengoal}}/{{penmiss}}), 2026 as bare words
# — same field, same order, so accept both. The ORDER of the bullets is the order the kicks were taken,
# which is the only place that sequence is recorded.
PEN_TAKER = re.compile(r"^\*\s*(.+?)\s*(?:\{\{\s*)?(pengoal|penmiss)(?:\s*\}\})?\s*$",
                       re.I | re.M)


def parse_shootout_field(field, team, opponent, year, date):
    """[(order, player_key, display, scored)] for one side's penalty list."""
    out = []
    for n, m in enumerate(PEN_TAKER.finditer(field or ""), 1):
        key, disp = _player(m.group(1))
        if not key:
            continue
        out.append({"year": year, "date": date, "team_code": team, "opponent_code": opponent,
                    "order": n, "player_key": key, "player_display": disp,
                    "scored": 1 if m.group(2).lower() == "pengoal" else 0})
    return out


def parse_match_page(title, year, wt, origin=None, forced_stage=None):
    """(goal rows, {team name: code}, audit rows) for one group/knockout/final article.

    The audit rows ((year, date, c1, c2, s1, s2, n_goals_parsed) per box) exist so main() can say
    WHY an edition is short of the archive total — a match with a score but an empty scorer list is
    a different failure from a match whose list is partial, and neither should be papered over.

    The name->code side-product is why we can put a team_code on squad rows: squad articles head each
    block with a NAME only ("Soviet Union"), never a FIFA code, while match boxes carry the code and
    sit under a '===Soviet Union vs Uruguay===' heading. Pairing heading side with box side is a
    data-driven mapping — no hand-maintained alias table to rot."""
    default = forced_stage or title_stage(year, origin or title)
    # A pinned stage comes from the transcluding section of the stage article and outranks anything
    # on the standalone page: "Brazil v Germany (2014 FIFA World Cup)" has its own ==Match== and
    # ==Aftermath== headings, and its title says nothing about being a semi-final.
    stages = [(0, default)] if forced_stage else \
        stage_index(wt, default if default != "knockout" else "final")
    # nearest '=== A vs B ===' heading above each box gives the two teams' article-spelled names
    vs_hdrs = [(m.start(), m.group(1), m.group(2)) for m in VS_HDR.finditer(wt)]

    def before(pos, seq):
        hit = None
        for item in seq:
            if item[0] <= pos:
                hit = item
            else:
                break
        return hit

    goals, names, audit, meta, pens = [], {}, [], [], []
    for m in FBOX.finditer(wt):
        f = _fields(m.group(1))
        c1, c2 = _code(f.get("team1", "")), _code(f.get("team2", ""))
        if not (c1 and c2):
            continue
        st = before(m.start(), stages)
        stage = st[1] if st else default
        date = _date(f.get("date", ""))
        h = before(m.start(), vs_hdrs)
        if h:
            names.setdefault(_clean(h[1]), c1)
            names.setdefault(_clean(h[2]), c2)
        # goals1 is credited TO team1 — but an OWN goal in that list was struck by a team2 player
        # (drift #4). Swap the player's team for those rows; the flag itself is preserved.
        n = 0
        for side, (own, opp) in (("goals1", (c1, c2)), ("goals2", (c2, c1))):
            for key, disp, minute, extra, pen, og in parse_goals_field(f.get(side, "")):
                team, other = (opp, own) if og else (own, opp)
                n += 1
                goals.append({
                    "year": year, "stage": stage, "date": date,
                    "player_key": key, "player_display": disp,
                    "team_code": team, "opponent_code": other,
                    "minute": minute, "minute_extra": extra,
                    "penalty": pen, "own_goal": og, "source_page": title})
        s1, s2 = _box_score(f.get("score", ""))
        audit.append((year, date, c1, c2, s1, s2, n, stage, title))
        # Attendance and referee were parsed out of every box from the start and thrown away; emitting
        # them costs nothing extra because the fetch, the box scan and the stage attribution are shared
        # with the goal rows, which is also why they cannot disagree about which match they describe.
        ref, ref_nat = _referee(f.get("referee", ""))
        for _pf, _t, _o in (("penalties1", c1, c2), ("penalties2", c2, c1)):
            pens += parse_shootout_field(f.get(_pf, ""), _t, _o, year, date)
        meta.append({"year": year, "stage": stage, "date": date,
                     "team1_code": c1, "team2_code": c2, "score1": s1, "score2": s2,
                     "attendance": _attendance(f.get("attendance", "")),
                     "referee": ref, "referee_nation": ref_nat,
                     "stadium": _clean(f.get("stadium", "")), "source_page": title})
    return goals, names, audit, meta, pens


# ──────────────────────────────────────────────────────────────────────────────── squad parsing ──
# THREE squad-row template names across the corpus, all with the same parameters:
#   {{nat fs player}}                  1930–2002, 2010
#   {{National football squad player}} 2006 and 2014 only (the pre-rename long form — missing this
#                                      name is why those two editions first came out with 0 squads)
#   {{nat fs g player}}                2018–2026 (adds a goals= column)
NATFS = re.compile(r"\{\{\s*(?:nat fs (?:g )?player|national football squad player)\b", re.I)
BIRTH = re.compile(r"\{\{\s*birth date(?: and age)?2?\b", re.I)
# Any heading level 2–4 can name a squad's nation: 1934/1938 had no group stage so their squad pages
# head each nation at level 2 (==Italy==), every other edition nests nations at level 3 inside a
# level-2 group heading (==Group 1== / ===Mexico===). So take the nearest preceding heading of ANY
# level and just skip the group headings themselves.
ANY_HDR = re.compile(r"^(={2,4})\s*([^=].*?)\s*\1\s*$", re.M)
GROUP_HDR = re.compile(r"^group [0-9a-l]$", re.I)


def _dob(age_field):
    """YYYY-MM-DD birth date out of the age= parameter.

    {{Birth date and age2|df=yes|<tournament date>|<birth date>}} carries TWO date triples and the
    SECOND one is the date of birth (the first is the reference date the age is computed at — the
    tournament's opening day). {{Birth date and age|Y|M|D}} carries only ONE triple, which IS the
    dob. So: take the numeric params in order; six or more -> use params 4-6, three to five -> use
    1-3, fewer -> give up and leave dob empty rather than invent one."""
    m = BIRTH.search(age_field)
    if not m:
        # A few early-edition entries write the date as prose instead of a template
        # ('age=27 December 1947 (aged 27)'). A FULL date is safe to read; 'age=Unknown' and
        # year-only forms ('age=1907 (aged 22–23)') deliberately yield nothing.
        return _date(age_field)
    body, _ = _tmpl_body(age_field, m.start())
    nums = [p.strip() for p in _split_params(body)[1:]
            if "=" not in p and p.strip().isdigit()]
    trip = nums[3:6] if len(nums) >= 6 else (nums[0:3] if len(nums) >= 3 else [])
    if len(trip) != 3 or not (1850 < int(trip[0]) < 2020):
        return ""
    try:
        return "%04d-%02d-%02d" % (int(trip[0]), int(trip[1]), int(trip[2]))
    except ValueError:
        return ""


def parse_squads_page(title, year, wt):
    """One row per squad-row template (see NATFS for the three names it goes by). Each player belongs
    to the nearest preceding non-group heading = his nation. The heading name is kept RAW (per spec,
    no mapping to the archive's spelling) — team_code is filled later from the match-page name->code
    map, and captaincy comes either from other=captain or from a '(c)' tacked onto the name."""
    heads = [(m.start(), _clean(m.group(2))) for m in ANY_HDR.finditer(wt)
             if not GROUP_HDR.match(_clean(m.group(2)))]
    rows = []
    pos = 0
    while True:
        m = NATFS.search(wt, pos)
        if not m:
            break
        body, pos = _tmpl_body(wt, m.start())
        p = {}
        for seg in _split_params(body)[1:]:
            k, sep, v = seg.partition("=")
            if sep:
                p.setdefault(k.strip().lower(), v.strip())
        team = ""
        for start, name in heads:
            if start <= m.start():
                team = name
            else:
                break
        key, disp = _player(p.get("name", ""))
        if not key:
            key = disp = _clean(p.get("name", ""))
        if not key:
            continue
        rows.append({
            "year": year, "team_code": "", "team_name": team,
            "shirt_no": _clean(p.get("no", "")), "pos": _clean(p.get("pos", "")),
            "player_key": key, "player_display": disp,
            "dob": _dob(p.get("age", "")), "caps": _clean(p.get("caps", "")),
            "club": _clean(p.get("club", "")), "club_nat": _clean(p.get("clubnat", "")),
            # 2006/2014 don't use other=captain; they append ([[Captain (association football)|c]])
            # to the name. _player() takes the FIRST wikilink so the display name is unaffected.
            "captain": 1 if ("captain" in p.get("other", "").lower()
                             or "captain (association football)" in p.get("name", "").lower()
                             or re.search(r"\(c\)$", _clean(p.get("name", "")))) else 0})
    return rows


# ───────────────────────────────────────────────────────────────────────────────────── validation ──
def archive_goals():
    """{year: total goals scored} from data/worldcup_matches.csv, for the coverage cross-check."""
    tot = Counter()
    with (DATA / "worldcup_matches.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["home_score"].strip() and r["away_score"].strip():
                tot[int(r["year"])] += int(r["home_score"]) + int(r["away_score"])
    return tot


def wc2026_goals():
    """2026 is NOT in worldcup_matches.csv (it lives in wc2026_matches.csv, different scope)."""
    fn = DATA / "wc2026_matches.csv"
    if not fn.exists():
        return 0
    with fn.open(encoding="utf-8") as f:
        return sum(int(r["score1"]) + int(r["score2"]) for r in csv.DictReader(f)
                   if r["score1"].strip() and r["score2"].strip())


GOAL_FIELDS = ["year", "stage", "date", "player_key", "player_display", "team_code",
               "opponent_code", "minute", "minute_extra", "penalty", "own_goal", "source_page"]
PEN_FIELDS = ["year", "date", "team_code", "opponent_code", "order", "player_key",
              "player_display", "scored"]
META_FIELDS = ["year", "stage", "date", "team1_code", "team2_code", "score1", "score2",
               "attendance", "referee", "referee_nation", "stadium", "source_page"]
SQUAD_FIELDS = ["year", "team_code", "team_name", "shirt_no", "pos", "player_key",
                "player_display", "dob", "caps", "club", "club_nat", "captain"]


def main():
    pages = discover()
    goals, squads, failures, audit, meta, pens = [], [], [], [], [], []
    names_by_year = defaultdict(dict)
    pages_by_year = defaultdict(list)

    for year in YEARS:
        for title, origin, forced in pages.get(year, []):
            try:
                wt = wikitext(title)
            except Exception as e:                        # network / missing page
                failures.append((title, f"fetch: {type(e).__name__}: {e}"))
                continue
            pages_by_year[year].append(title)
            try:
                if re.search(r"squads?\)?$", origin, re.I):
                    squads += parse_squads_page(title, year, wt)
                else:
                    g, nm, au, mt, pn = parse_match_page(title, year, wt, origin, forced)
                    goals += g
                    audit += au
                    meta += mt
                    pens += pn
                    for n, c in nm.items():
                        names_by_year[year].setdefault(n, c)
            except Exception as e:
                failures.append((title, f"parse: {type(e).__name__}: {e}"))

    # A canonical title is fetched once, but a match can still appear twice (an edition's final lives
    # both in the 'final' article and, transcluded, in 'knockout stage' — and a rerun of a restructured
    # article can duplicate a box). Dedupe on the goal's natural identity.
    seen, uniq = set(), []
    for g in goals:
        k = (g["year"], g["date"], g["player_key"], g["minute"], g["minute_extra"], g["team_code"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(g)
    ndup = len(goals) - len(uniq)
    goals = sorted(uniq, key=lambda g: (g["year"], g["date"], g["minute"],
                                        str(g["minute_extra"]), g["player_key"]))

    # team_code for squads: exact heading match first, then a case/punctuation-folded match, then a
    # global (any-year) fallback for teams whose only appearance is under a differently-spelled
    # heading. Anything still unresolved is reported, never guessed.
    def fold(s):
        return re.sub(r"[^a-z]", "", s.lower())

    global_map, folded = {}, defaultdict(dict)
    for y, nm in names_by_year.items():
        for n, c in nm.items():
            global_map.setdefault(n, c)
            folded[y].setdefault(fold(n), c)
    global_folded = {fold(n): c for n, c in global_map.items()}
    unmapped = Counter()
    for r in squads:
        y, n = r["year"], r["team_name"]
        code = (names_by_year[y].get(n) or folded[y].get(fold(n))
                or global_map.get(n) or global_folded.get(fold(n), ""))
        if not code:
            # Last resort: a squad heading can be a longer form of the match-article heading
            # ("China PR" vs "China"). Accept a containment match only when it is UNAMBIGUOUS
            # within the edition — two candidates means we do not know, so leave it blank.
            f = fold(n)
            hits = {c for k, c in folded[y].items() if k and (k in f or f in k)}
            code = hits.pop() if len(hits) == 1 else ""
        r["team_code"] = code
        if not code:
            unmapped[(y, n)] += 1
    squads.sort(key=lambda r: (r["year"], r["team_name"],
                               int(r["shirt_no"]) if str(r["shirt_no"]).isdigit() else 99,
                               r["player_key"]))

    DATA.mkdir(parents=True, exist_ok=True)
    with (DATA / "wc_goals.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=GOAL_FIELDS)
        w.writeheader()
        w.writerows(goals)
    with (DATA / "wc_squads.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SQUAD_FIELDS)
        w.writeheader()
        w.writerows(squads)
    # One row per MATCH (not per goal), deduped the same way: a match transcluded into a stage article
    # would otherwise appear twice.
    seen_m, meta_rows = set(), []
    for r in meta:
        # Skip UNCONTESTED fixtures. 1938 has a box for Sweden v Austria that was never played —
        # Austria was annexed and withdrew, so Sweden advanced on a bye — and it carries no score,
        # attendance or referee. Keeping it would put 19 "matches" in an 18-match edition.
        if r["score1"] is None and r["score2"] is None:
            continue
        k = (r["year"], r["date"], tuple(sorted((r["team1_code"], r["team2_code"]))))
        if k in seen_m:
            continue
        seen_m.add(k)
        meta_rows.append(r)
    meta_rows.sort(key=lambda r: (r["year"], r["date"], r["team1_code"]))
    with (DATA / "wc_matchmeta.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=META_FIELDS)
        w.writeheader()
        w.writerows(meta_rows)
    seen_p, pen_rows = set(), []
    for r in pens:
        k = (r["year"], r["date"], r["team_code"], r["order"], r["player_key"])
        if k in seen_p:
            continue
        seen_p.add(k)
        pen_rows.append(r)
    pen_rows.sort(key=lambda r: (r["year"], r["date"], r["team_code"], r["order"]))
    with (DATA / "wc_shootouts.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=PEN_FIELDS)
        w.writeheader()
        w.writerows(pen_rows)

    # ───────────────────────────────────────────────────────────────────── coverage summary ──
    arch = archive_goals()
    arch[2026] = wc2026_goals()
    gy, sy = Counter(g["year"] for g in goals), Counter(r["year"] for r in squads)
    print(f"\nwrote data/wc_goals.csv ({len(goals)} rows, {ndup} duplicate goal rows dropped)")
    print(f"wrote data/wc_squads.csv ({len(squads)} rows)")
    _att = sum(1 for r in meta_rows if r["attendance"] != "")
    _ref = sum(1 for r in meta_rows if r["referee"])
    print(f"wrote data/wc_matchmeta.csv ({len(meta_rows)} matches · {_att} with attendance · "
          f"{_ref} with a referee)")
    _sh = len({(r["year"], r["date"]) for r in pen_rows})
    print(f"wrote data/wc_shootouts.csv ({len(pen_rows)} kicks across {_sh} shootouts — the source "
          f"records takers for only some of them)\n")
    print("year  pages  goals  archive  delta   squads  teams")
    print("----  -----  -----  -------  -----   ------  -----")
    zero = []
    for year in YEARS:
        nteams = len({r["team_name"] for r in squads if r["year"] == year})
        print(f"{year}  {len(pages_by_year[year]):5d}  {gy[year]:5d}  {arch[year]:7d}  "
              f"{gy[year] - arch[year]:+5d}   {sy[year]:6d}  {nteams:5d}")
        if gy[year] == 0:
            zero.append(year)
    print(f"----  -----  -----  -------  -----   ------  -----")
    print(f"TOT   {sum(len(v) for v in pages_by_year.values()):5d}  {len(goals):5d}  "
          f"{sum(arch[y] for y in YEARS):7d}  {len(goals) - sum(arch[y] for y in YEARS):+5d}   "
          f"{len(squads):6d}")
    print(f"\neditions with ZERO goals parsed: {zero or 'none'}")

    # ── WHERE the shortfall comes from. Every football box we saw carries its own score, so we can
    # split the gap into three causes without touching the archive:
    #   missing box  — the article never contained the match (it is transcluded from a standalone
    #                  match page that our title prefix cannot discover: 'Italy v West Germany
    #                  (1970 FIFA World Cup)', 'Uruguay v Brazil (1950 FIFA World Cup)', …)
    #   empty list   — box present, score > 0, but goals1/goals2 are blank (no scorer data written)
    #   partial list — box present, scorer list shorter than the score
    # MATCH-LEVEL double-count guard. Following {{#lst:}} means we now fetch articles that the stage
    # pages also reference, so a match could in principle be read from two pages. Key every box on
    # (year, date, unordered team pair) and report every key seen more than once, naming both source
    # pages — an empty list is the proof that no match was read twice.
    boxes_at = defaultdict(list)
    for a in audit:
        boxes_at[(a[0], a[1], tuple(sorted((a[2], a[3]))))].append(a)
    ubox = [v[0] for v in boxes_at.values()]
    dupe_boxes = {k: v for k, v in boxes_at.items() if len(v) > 1}
    print(f"\nmatch-level duplicate check: {len(audit)} boxes parsed over "
          f"{len(boxes_at)} distinct matches -> "
          + ("NO match read twice" if not dupe_boxes else f"{len(dupe_boxes)} DUPLICATED:"))
    for k, v in sorted(dupe_boxes.items()):
        print(f"  {k[0]} {k[1]} {k[2]} read from: " + " | ".join(f"{a[8]} ({a[7]})" for a in v))
    print("\nshortfall breakdown (per edition), from each box's OWN score field:")
    print("year  boxes  boxscore  parsed  empty-list  partial-list  missing-box-goals")
    for year in YEARS:
        rows = [a for a in ubox if a[0] == year]
        bs = sum((a[4] or 0) + (a[5] or 0) for a in rows)
        pg = sum(a[6] for a in rows)
        empty = [a for a in rows if a[6] == 0 and ((a[4] or 0) + (a[5] or 0)) > 0]
        part = [a for a in rows if 0 < a[6] < (a[4] or 0) + (a[5] or 0)]
        print(f"{year}  {len(rows):5d}  {bs:8d}  {pg:6d}  {len(empty):10d}  {len(part):12d}"
              f"  {arch[year] - bs:+17d}")
    print("  (missing-box-goals = archive total minus the boxes we found = matches whose box lives\n"
          "   only on a standalone match article, undiscoverable from the '<year> FIFA World Cup' prefix)")
    worst = [a for a in ubox if a[6] < (a[4] or 0) + (a[5] or 0)]
    if worst:
        print(f"\n  {len(worst)} box(es) with an incomplete scorer list; first 25:")
        for a in worst[:25]:
            print(f"    {a[0]} {a[1]} {a[2]}-{a[3]} {a[4]}–{a[5]} parsed={a[6]} ({a[7]})")

    print("\ntop 15 all-time goalscorers (parsed):")
    sc = Counter()
    disp = {}
    for g in goals:
        if g["own_goal"]:
            continue                        # own goals are not credited to the scorer's tally
        sc[g["player_key"]] += 1
        disp[g["player_key"]] = g["player_display"]
    for i, (k, n) in enumerate(sc.most_common(15), 1):
        print(f"  {i:2d}. {n:3d}  {k}")

    print("\nown-goal check — 1970 Italy 4-1 Mexico, Guzmán 25':")
    for g in goals:
        if g["year"] == 1970 and g["own_goal"] and "Guzmán" in g["player_key"]:
            print(f"  {g['player_key']}  minute={g['minute']}  team={g['team_code']}  "
                  f"opponent={g['opponent_code']}  own_goal={g['own_goal']}  ({g['stage']})")
    print(f"  own-goal rows total: {sum(1 for g in goals if g['own_goal'])}"
          f" | penalties: {sum(1 for g in goals if g['penalty'])}")

    if unmapped:
        print("\nsquad team headings with NO code (left blank):")
        for (y, n), c in sorted(unmapped.items()):
            print(f"  {y} {n!r} ({c} players)")
    print(f"\nsquad rows missing dob: {sum(1 for r in squads if not r['dob'])}")
    if failures:
        print("\nPAGES THAT FAILED:")
        for t, why in failures:
            print(f"  {t}: {why}")
    else:
        print("\nno page failed to fetch/parse.")


if __name__ == "__main__":
    main()
