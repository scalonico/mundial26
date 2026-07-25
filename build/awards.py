"""Ingest the INDIVIDUAL and TEAM AWARDS of all 23 World Cups (1930–2026) from the Awards section of
each edition's main English Wikipedia article (CC BY-SA 4.0).

Companion to build/players.py (goalscorers + squads). Same fetch/cache conventions, same _clean() /
_player() / _tmpl_body() / _split_params() helpers, stdlib only.

Writes:
  data/wc_awards.csv   one row per WINNER
                       (year, award, rank, player_key, player_display, nation, is_team, heading)

Run: .venv/bin/python build/awards.py        (cache under sources/awards/, WCA_REFRESH=1 re-fetches)

──────────────────────────────────────────────────────────────────────────────────────────────────
WHY THE SOURCE IS THE MAIN ARTICLE. There is no usable per-edition awards article: "<year> FIFA
World Cup awards" 404s for most years and is a one-line #REDIRECT for 2014/2022. The awards live in
the Awards section of "<year> FIFA World Cup" — at level 2 in some editions (``== Awards ==``, with
spaces) and level 3 in others (``===Awards===``), and in 1978 as ``===Awards (Unofficial winner)===``
nested under ==Statistics==. Hence a case-insensitive 2–4 ``=`` match that allows a parenthetical
tail, cut at the next heading of the SAME OR SHALLOWER level.

player_key IS THE WIKIPEDIA LINK TARGET, exactly as in data/wc_goals.csv and data/wc_squads.csv:
``[[Paolo Rossi]]`` -> "Paolo Rossi", ``[[Paulo Roberto Falcão|Falcão]]`` -> "Paulo Roberto Falcão".
That is the ONLY thing that lets an award join to a goal or a squad row; using the display label
instead would key 1982's Golden Ball runner-up as "Falcão", which matches nothing.

────────────────────────────────────────────────────────── the five table shapes, all verified ──
The section holds free text, bullet lists and/or ``{| class="wikitable"`` tables. Five distinct
layouts appear across the corpus, and a single sequential row walk handles all of them because in
every one a HEADER row (re)defines the column layout for the data rows that follow it:

 1. COLUMN-PER-AWARD (1982-t1, 1986-t1, 1990-t1, 1994, 1998, 2002, 2006). One header row naming the
    awards, one data row of winners.
 2. RANKED (1982-t2, 1986-t2, 1990-t2, 2010). One award with placings: the award name comes from a
    spanning header row (``!colspan="2"|Golden Ball``) or from the table CAPTION (``|+Golden Ball``,
    2010), then a ``Rank | Player | Points`` header and one row per placing. Only 1st is the winner,
    so the rank column is load-bearing, not cosmetic.
 3. ROW-PER-AWARD (2014). ``Award | Winner | Other nominees``. The nominees column MUST be dropped —
    reading it would credit Neymar with a Golden Ball.
 4. INTERLEAVED HEADER/DATA BLOCKS (2018, 2022, 2026). One table whose header rows alternate with
    data rows: ``Golden Ball | Silver Ball | Bronze Ball`` is not three awards but ranks 1/2/3 of
    ONE award, and ``!colspan="3"|Golden Glove`` + ``|colspan="3"|<player>`` is a single winner.
 5. BULLET LIST (1970, and 2010's four non-Golden-Ball awards). ``* [[…|Golden Boot]]: {{flagicon|GER}}
    [[Gerd Müller]] (…)``.

Four traps that silently corrupt the output if missed, each hit by a real edition:

 a. SQUAD LISTS MASQUERADING AS AWARDS. ``====All-star team====`` (1990) and ``===All-Star Team===`` /
    ``===Dream Team===`` (2010, 2018) are SUBSECTIONS OF the Awards section, so cutting at the next
    same-or-shallower heading does not remove them. They are eleven-name squads, not awards, and
    would add ~50 bogus rows. They are excised by heading name before any table is parsed.

 b. NATION WINNERS THAT LOOK LIKE PLAYERS. Fair Play and Most Entertaining Team are won by a country.
    Usually the cell is a bare ``{{fb|BRA}}`` with no wikilink at all — but 1970 writes
    ``{{flagicon|PER|state}} [[Peru national football team|Peru]]``, a wikilink that is NOT a person.
    Detection is therefore evidence-based (no player link, or a link whose target is a national team),
    and main() cross-checks it against which awards are known to be team awards.

 c. DESCRIPTIONS THAT PARSE AS BULLET AWARDS. 2026 lists the awards twice: first as glossary bullets
    ("* Golden Ball: Awarded to the best overall player of the tournament."), then as the real table.
    A bullet is only accepted if its value carries a flag template, which every real winner has and
    no description does. 2014's ``;Technical Study Group`` roster is excluded by the same test's
    sibling — those bullets have no "<award>:" label at all.

 d. <br> MEANS TWO DIFFERENT THINGS. In 1994's Golden Shoe (Stoichkov + Salenko) and 1998/2006's Fair
    Play it separates JOINT winners, who share rank 1. In 2014 it separates PLACINGS, marked
    ``{{gold1}}/{{silver2}}/{{bronze3}}``. So <br>-parts default to the same rank and only a medal
    template moves them — the reverse default would demote Salenko to runner-up.

COVERAGE, reported rather than asserted: 10 of the 23 editions have no Awards section at all
(1930–1966 except 1958's stray All-Star Team, plus 1974). That is expected — the Golden Ball dates
from 1982, the Golden Glove from 1994 — and main() prints those years as blanks instead of inventing
winners for them. main() also prints every header string that did not normalise to a canonical award
name, and the fraction of player keys that join to data/wc_squads.csv, because a key that joins to
nothing is the failure mode this file exists to avoid.
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
CACHE = ROOT / "sources" / "awards"
DATA = ROOT / "data"
UA = {"User-Agent": "mundial26/1.0 (scalonico@ucdavis.edu)"}
REFRESH = bool(os.environ.get("WCA_REFRESH"))

YEARS = [1930, 1934, 1938] + list(range(1950, 2027, 4))


# ──────────────────────────────────────────────────────────────────────────── fetching / caching ──
def _api(**params):
    """One api.php GET returning parsed JSON. Politeness sleep lives in wikitext(), the only caller
    that hits the network."""
    params.setdefault("format", "json")
    url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return json.load(r)


def wikitext(page):
    """Cached wikitext for a Wikipedia page (fetch once, then reuse offline) — build/players.py's
    fetcher verbatim, pointed at sources/awards/. WCA_REFRESH=1 bypasses the cache. Cache filename is
    the page title with spaces -> underscores, so the cache is human-browsable."""
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


def _strip_noise(s):
    """Refs, comments and {{refn|…}} wrappers gone. Run BEFORE any parsing: 2002 hangs a
    ``<ref name="awards">`` on every single header cell and 2022's intro wraps five refs in
    ``{{refn|…}}``, and a ref body contains pipes, braces and newlines that would otherwise be read
    as table syntax (one 2022 ref even contains ``{{!}}``, a literal pipe)."""
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"<ref[^>]*/>", "", s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    # {{refn|…}} nests templates, so match it brace-balanced rather than with a lazy regex
    out, i = [], 0
    while True:
        m = re.compile(r"\{\{\s*(?:refn|efn|sfn|notetag)\b", re.I).search(s, i)
        if not m:
            out.append(s[i:])
            break
        out.append(s[i:m.start()])
        _, i = _tmpl_body(s, m.start())
    return "".join(out)


# ───────────────────────────────────────────────────────────────────── wikitext micro-parsers ──
def _tmpl_body(s, i):
    """Body of the {{…}} template starting at s[i] (== '{{'), brace-depth matched, plus the index
    just past its closer. build/players.py's helper verbatim; needed here because
    ``{{#invoke:flagg|main|pxxl|avar=fb|ARG}}`` and ``{{refn|<ref>…</ref>}}`` nest."""
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
    build/players.py's helper verbatim."""
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
    """(player_key, player_display) from a fragment containing a wikilink — build/players.py's
    helper verbatim, and the reason awards can be joined to goals and squads at all.

    THE IDENTITY RULE: the key is the wikilink TARGET, not the label. ``[[Paulo Roberto Falcão|Falcão]]``
    -> ("Paulo Roberto Falcão", "Falcão"); ``[[Rodri (footballer, born 1996)|Rodri]]`` ->
    ("Rodri (footballer, born 1996)", "Rodri"). Targets are globally unique and stable across
    editions; labels are surnames that collide."""
    m = LINK.search(text)
    if not m:
        return "", ""
    key = m.group(1).split("#")[0].lstrip(":").strip()
    disp = (m.group(2) or m.group(1)).strip()
    return key, _clean(disp)


# Every flag/nation template flavour in the corpus. {{flagicon}} and {{fb}} in the older editions,
# {{fbicon}} in 1978/2010/2014/2018, and the Lua module in 2022 ({{#invoke:flagg|main|pxxl|avar=fb|ARG}})
# and 2026 ({{#invoke:flag|fbicon|ESP}}). Anchored on the template NAME so it cannot fire on the
# {{gold1}}/{{silver2}}/{{bronze3}} medal markers that sit right beside it in 2014.
#
# The #invoke branch deliberately stops at the module name and does NOT then require a known function:
# 2026 calls flag's `fbicon` but 2022 calls flagg's `main`, and demanding a template-like function name
# is what first made 2022 come out with an empty nation on all seven of its rows and lose its Fair Play
# Trophy row entirely (a nation winner with no player link and no nation is indistinguishable from an
# empty cell). The unwanted positional words are filtered by FLAG_NOISE instead.
FLAG_TMPL = re.compile(r"\{\{\s*(?:#invoke:\s*flagg?\s*\|"
                       r"|(?:fbicon|fb-rt|fb|flagicon|flagg|flag)\s*\|)", re.I)
# Positional parameters that are NOT the nation: template/module/function names, size and rendering
# switches, and the flag-VARIANT year ({{flagicon|ITA|1946}} is Italy's 1946 flag, not a nation).
FLAG_NOISE = {"fb", "fbicon", "fb-rt", "flagicon", "flag", "flagg", "main", "pxxl", "pxl", "px",
              "unpe", "unpre", "state", "size", "nowrap", "noredlink", "#invoke:flag",
              "#invoke:flagg"}


def _nation(frag):
    """The nation as the template gives it: 'GER', 'BRA', 'HOL', 'Soviet Union'.

    Kept RAW on purpose (per spec) — 2010 uses {{fbicon|HOL}} and {{fbicon|SPA}} where every other
    edition uses NED/ESP, and 1982 writes {{flagicon|Soviet Union|1955}} in words. Normalising here
    would hide that drift; reporting it lets the caller decide.

    Read out of the flag template's parameter list rather than by scanning the cell for three capital
    letters, so a player's name can never be mistaken for a country code."""
    m = FLAG_TMPL.search(frag)
    if not m:
        return ""
    body, _ = _tmpl_body(frag, m.start())
    for p in _split_params(body):
        p = p.strip()
        if not p or "=" in p:                      # named params: avar=fb, name=…, size=…
            continue
        if p.lower() in FLAG_NOISE or re.fullmatch(r"\d{4}", p):
            continue
        return p
    return ""


# A wikilink to a NATIONAL TEAM is a country, not a person. 1970's Fair Play cell is
# ``{{flagicon|PER|state}} [[Peru national football team|Peru]]`` — the only wikilinked team winner in
# the corpus, and without this test it would be filed as a player named "Peru national football team".
NAT_TEAM = re.compile(r"national (?:football|soccer) team$", re.I)


# ───────────────────────────────────────────────────────────────────────── section extraction ──
# Level 2–4, optional spaces inside the ``=``, case-insensitive, and an optional parenthetical tail so
# 1978's ``===Awards (Unofficial winner)===`` is found. ``[^=\n]*`` (not ``.*``) keeps the closing
# ``=`` run out of the title.
AWARDS_HDR = re.compile(r"^(={2,4})[ \t]*(Awards\b[^=\n]*?)[ \t]*\1[ \t]*$", re.I | re.M)
ANY_HDR = re.compile(r"^(={2,6})[ \t]*([^=\n].*?)[ \t]*\1[ \t]*$", re.M)
# Subsections of Awards that are not awards at all (trap (a) in the module docstring): the eleven-name
# squad lists, and 2018's ===Prize money===, whose 'Position | Amount (million USD)' table sits inside
# ==Awards== and yielded five phantom "awards" named 'Position', 'Amount', 'Per team', 'Total', '400'.
NOT_AN_AWARD = re.compile(r"^(?:all[- ]?star team|dream team|team of the tournament|"
                          r"technical study group|prize money|prizes?)", re.I)


def awards_sections(wt):
    """[(heading as written, section body with squad subsections removed)] for one edition.

    Cut at the next heading of the SAME OR SHALLOWER level, then excise any DEEPER subsection whose
    title names a squad (All-Star Team / Dream Team). 1990 nests ``====All-star team====`` inside
    ``===Awards===`` and 2010 nests two such subsections inside ``==Awards==``; both survive the
    outer cut, and both are eleven-name tables that would otherwise be read as award winners."""
    out = []
    for m in AWARDS_HDR.finditer(wt):
        lvl = len(m.group(1))
        end = len(wt)
        for h in ANY_HDR.finditer(wt, m.end()):
            if len(h.group(1)) <= lvl:
                end = h.start()
                break
        sec = wt[m.end():end]
        # drop each squad subsection, from its heading to the next heading of its own level or above
        keep, cut_to = [], 0
        subs = list(ANY_HDR.finditer(sec))
        for i, h in enumerate(subs):
            if not NOT_AN_AWARD.match(_clean(h.group(2))):
                continue
            sublvl = len(h.group(1))
            stop = len(sec)
            for h2 in subs[i + 1:]:
                if len(h2.group(1)) <= sublvl:
                    stop = h2.start()
                    break
            keep.append(sec[cut_to:h.start()])
            cut_to = max(cut_to, stop)
        keep.append(sec[cut_to:])
        out.append((m.group(0).strip(), _strip_noise("".join(keep))))
    return out


# ─────────────────────────────────────────────────────────────────────────── award vocabulary ──
# Header text -> canonical award. Matched on the header cell's PLAIN TEXT (wikilinks unwrapped to
# their label), lower-cased, punctuation-squeezed. The variants below are every spelling that occurs:
#   Golden Boot            "Golden Boot", "Golden Boot Winner", and 1994/1998's adidas "Golden Shoe"
#   Golden Glove           "Yashin Award" (1994–2006), "Golden Glove" (2010+)
#   Best Young Player      "Best Young Player", "Young Player Award", "FIFA Young Player Award"
#   Fair Play Trophy       with and without the "FIFA" prefix
AWARD_RX = [
    (re.compile(r"^(?:fifa |world cup |adidas )*golden ball(?: award| winner)?$"), "Golden Ball"),
    (re.compile(r"^(?:fifa |world cup |adidas )*golden (?:boot|shoe)(?: award| winner)?$"),
     "Golden Boot"),
    (re.compile(r"^(?:fifa |world cup |adidas |lev )*(?:golden glove|yashin(?: award)?)"
                r"(?: award| winner)?$"), "Golden Glove"),
    (re.compile(r"^(?:fifa |world cup )*(?:best young player|young player)(?: award| winner)?$"),
     "Best Young Player"),
    (re.compile(r"^(?:fifa |world cup )*fair play(?: trophy| award| winner)?$"), "Fair Play Trophy"),
    (re.compile(r"^(?:fifa |world cup )*most entertaining team$"), "Most Entertaining Team"),
]
# The two awards a NATION wins. Used only to cross-check the evidence-based is_team detection, never
# to set it — see main()'s "team-award consistency" block.
TEAM_AWARDS = {"Fair Play Trophy", "Most Entertaining Team"}

# Header cells that are not awards but COLUMN ROLES, and the rank labels.
ROLE = {"rank": "rank", "rank:": "rank", "#": "rank", "place": "rank", "pos": "rank",
        "player": "player", "player:": "player", "name": "player",
        "points": "skip", "votes": "skip", "goals": "skip", "%": "skip",
        "award": "award", "other nominees": "skip", "nominees": "skip", "runners-up": "skip"}
ORDINAL = re.compile(r"^(\d{1,2})(?:st|nd|rd|th)?$")
# Rank labels that carry no award name of their own and attach to the award to their LEFT (or to the
# table caption). "Silver Ball"/"Bronze Boot" are 2018/2022/2026; "Runner-up"/"Third place" are 1978.
RANK_WORD = [(re.compile(r"^(?:winner|gold(?:en)?(?: ball| boot| shoe| medal)?|1st place|champion)$"), 1),
             (re.compile(r"^(?:runner[- ]?up|silver(?: ball| boot| shoe| medal)?|2nd place)$"), 2),
             (re.compile(r"^(?:third place|3rd place|bronze(?: ball| boot| shoe| medal)?)$"), 3)]


def norm_header(txt):
    """(canonical award or None, rank or None, role or None, normalised text) for a header cell.

    A cell can be an AWARD ("Golden Boot"), a bare RANK that borrows the award to its left
    ("Silver Ball", "Runner-up", "2nd"), a column ROLE ("Rank", "Player", "Other nominees"), or
    nothing recognisable — in which case the normalised text is returned so main() can report it
    instead of the parser guessing."""
    t = _clean(txt)
    t = re.sub(r"\s*\(.*?\)\s*$", "", t)                      # "(awarded retrospectively)"
    t = re.sub(r"[–—]", "-", t).strip().strip(":").strip()
    low = re.sub(r"\s+", " ", t.lower())
    if not low:
        return None, None, None, ""
    if low in ROLE:
        return None, None, ROLE[low], t
    for rx, canon in AWARD_RX:
        if rx.match(low):
            # "Golden Ball" is both an award name and a rank-1 label; as an award it wins.
            return canon, 1, None, t
    for rx, rank in RANK_WORD:
        if rx.match(low):
            return None, rank, None, t
    m = ORDINAL.match(low)
    if m:
        return None, int(m.group(1)), None, t
    return None, None, None, t


# ─────────────────────────────────────────────────────────────────────────── wikitable parsing ──
def _split_cells(line, sep):
    """Split one table line on '||' or '!!' at TOP LEVEL — outside {{…}}, [[…]] and <ref>. A lazy
    str.split() would shred nothing in this corpus today, but 2022's Lua flag calls are full of
    pipes and one more layer of nesting is all it takes."""
    parts, buf, d, b, i = [], [], 0, 0, 0
    while i < len(line):
        if line.startswith("{{", i):
            d += 1
            buf.append("{{")
            i += 2
        elif line.startswith("}}", i):
            d -= 1
            buf.append("}}")
            i += 2
        elif line.startswith("[[", i):
            b += 1
            buf.append("[[")
            i += 2
        elif line.startswith("]]", i):
            b -= 1
            buf.append("]]")
            i += 2
        elif line.startswith(sep, i) and d <= 0 and b <= 0:
            parts.append("".join(buf))
            buf = []
            i += 2
        else:
            buf.append(line[i])
            i += 1
    parts.append("".join(buf))
    return parts


# HTML attributes in front of a cell's content: ``align=center|``, ``valign="top"|``, ``colspan="3"|``,
# ``scope=col style="background-color: gold" |``. Stripped so the content starts at the flag template.
ATTRS = re.compile(r'^\s*(?:[A-Za-z-]+\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s|]*)\s*)+\|(?!\|)')


def _cell(raw):
    """A cell's content with its attribute prefix removed."""
    m = ATTRS.match(raw)
    return (raw[m.end():] if m else raw).strip()


def tables(sec):
    """[(caption, rows)] for the ``{| … |}`` tables in a section, where rows is
    [[(is_header, content), …]].

    Hand-rolled rather than regex-per-row because a cell's content routinely CONTINUES onto following
    lines: 2014's winner column is ``|valign="top"|`` followed by three ``<br>{{gold1}} …`` lines, and
    2022's Golden Boot cells carry a ``----8 goals, 2 assists`` footer line. Those lines start with
    neither '|' nor '!' and belong to the cell above."""
    out, i = [], 0
    lines = sec.split("\n")
    while i < len(lines):
        if not lines[i].strip().startswith("{|"):
            i += 1
            continue
        caption, rows, depth = "", [], 1
        i += 1
        while i < len(lines) and depth:
            ln = lines[i].rstrip()
            s = ln.strip()
            if s.startswith("{|"):
                depth += 1                    # no nested tables in this corpus, but do not fall out
            elif s.startswith("|}"):
                depth -= 1
            elif depth == 1 and s.startswith("|+"):
                caption = s[2:]
            elif depth == 1 and re.match(r"^\|-", s):
                rows.append([])
            elif depth == 1 and s.startswith("!"):
                rows = rows or [[]]
                rows[-1] += [(True, _cell(c)) for c in _split_cells(s[1:], "!!")]
            elif depth == 1 and s.startswith("|"):
                rows = rows or [[]]
                rows[-1] += [(False, _cell(c)) for c in _split_cells(s[1:], "||")]
            elif depth == 1 and rows and rows[-1]:
                h, c = rows[-1][-1]
                rows[-1][-1] = (h, (c + "\n" + ln).strip())
            i += 1
        out.append((caption, [r for r in rows if r]))
    return out


# {{gold1}}/{{silver2}}/{{bronze3}} — 2014's medal markers, the ONLY thing that turns <br>-separated
# entries in one cell from JOINT winners into PLACINGS (trap (d)).
MEDAL = [(re.compile(r"\{\{\s*gold1?\s*\}\}", re.I), 1),
         (re.compile(r"\{\{\s*silver2?\s*\}\}", re.I), 2),
         (re.compile(r"\{\{\s*bronze3?\s*\}\}", re.I), 3)]
BR = re.compile(r"<br\s*/?>", re.I)


def winners(cell, rank):
    """[(player_key, player_display, nation, is_team, rank)] for one winner cell.

    <br> splits JOINT winners who share `rank` (1994 Golden Shoe: Stoichkov and Salenko; 1998 and
    2006 Fair Play: two nations each) — unless a medal template overrides it (2014, where the three
    <br>-parts are 1st/2nd/3rd). A part with no PERSON wikilink is a nation winner: either a bare
    ``{{fb|BRA}}`` or 1970's ``[[Peru national football team|Peru]]``."""
    rows = []
    for part in BR.split(cell):
        if not part.strip():
            continue
        r = rank
        for rx, mr in MEDAL:
            if rx.search(part):
                r = mr
                break
        key, disp = _player(part)
        if key and NAT_TEAM.search(key):
            key = disp = ""                       # a country, not a person
        nation = _nation(part)
        if not key:
            if not nation:
                continue                          # empty / prose-only cell: nothing to record
            rows.append(("", "", nation, 1, r))
        else:
            rows.append((key, disp, nation, 0, r))
    return rows


def parse_table(caption, rows, report):
    """[(award, rank, key, display, nation, is_team)] for one wikitable.

    ONE sequential walk over the rows, because in all five layouts a HEADER row (re)defines the column
    layout for the data rows beneath it — that is what lets 2018/2022/2026's interleaved
    header/data/header/data table be read with the same code as 1994's single header + single data row.

    Layouts, decided from the header row's own cells:
      columns      cell i names an award (rank 1) or a bare rank that inherits the award to its left
                   -> the data row's cell i is that award's winner
      ranked       a 'Rank'/'#' role column is present -> one placing per data row, the award coming
                   from a spanning header row above or from the caption
      row_per_away an 'Award' role column is present   -> award and winner both read per data row
    """
    cap_award, _, _, cap_txt = norm_header(caption) if caption else (None, None, None, "")
    # An unrecognised caption is still the award's NAME, so pass it through verbatim (and report it)
    # rather than dropping the table: 1978's only table is captioned 'Best player' — the unofficial
    # best-player vote FIFA recognises — with Winner/Runner-up/Third place as its column headers, so
    # without this fallback the whole edition parses to zero rows.
    if cap_txt and not cap_award:
        report["unmapped"][cap_txt] += 1
    current, layout, last_rank, out = cap_award or cap_txt, None, None, []

    for row in rows:
        if all(h for h, _ in row):                                        # ── a header row ──
            cells = [norm_header(c) for _, c in row]
            roles = [c[2] for c in cells]
            if "award" in roles:
                # 2014: Award | Winner | Other nominees. The winner column is the one labelled with a
                # rank (Winner == rank 1); fall back to the column right of the award column.
                ai = roles.index("award")
                wi = next((i for i, c in enumerate(cells) if c[1] and i != ai), ai + 1)
                layout = ("row_per_award", ai, wi)
            elif "rank" in roles:
                # 1982/1986/1990/2010: Rank | Player | Points. The player column may be unlabelled
                # (1982 writes 'Player:'), so fall back to "the column after the rank column".
                ri = roles.index("rank")
                pi = roles.index("player") if "player" in roles else ri + 1
                layout = ("ranked", ri, pi)
            elif any(c[0] or c[1] for c in cells):
                cols, award = [], current
                for canon, rank, _, txt in cells:
                    if canon:
                        award = canon
                    elif rank is None:
                        # an unrecognised header inside an otherwise readable row: report and skip the
                        # column rather than attach its winner to the award next door
                        if txt:
                            report["unmapped"][txt] += 1
                        cols.append((None, None))
                        continue
                    cols.append((award, rank or 1))
                if len(cells) == 1 and cells[0][0]:
                    # ``!colspan="3"|Golden Glove`` — names the award for what follows, and is itself
                    # a one-column layout for the ``|colspan="3"|<player>`` row underneath.
                    current = cells[0][0]
                layout = ("columns", cols, None)
            else:
                for canon, rank, role, txt in cells:
                    if txt and role is None and canon is None and rank is None:
                        report["unmapped"][txt] += 1
            continue

        # ── a data row ──
        if layout is None:
            if any(_player(c)[0] or _nation(c) for _, c in row):
                report["orphan_rows"] += 1
            continue
        kind = layout[0]
        if kind == "columns":
            for i, (_, c) in enumerate(row):
                if i >= len(layout[1]):
                    break
                award, rank = layout[1][i]
                if not award:
                    continue
                for key, disp, nat, team, r in winners(c, rank):
                    out.append((award, r, key, disp, nat, team))
        elif kind == "ranked":
            _, ri, pi = layout
            # rowspan makes the rank cell disappear on continuation rows (1986's joint 4th place), so
            # take the rank from whichever cell carries an ordinal and inherit it when none does.
            rank = None
            for _, c in row:
                o = norm_header(c)
                if o[1] is not None and not _player(c)[0]:
                    rank = o[1]
                    break
            if rank is None:
                rank = last_rank or 1
            last_rank = rank
            cand = [c for _, c in row if _player(c)[0] or _nation(c)]
            if not cand:
                continue
            if not current:
                report["no_award_name"] += 1
                continue
            for key, disp, nat, team, r in winners(cand[0], rank):
                out.append((current, r, key, disp, nat, team))
        elif kind == "row_per_award":
            _, ai, wi = layout
            if ai >= len(row) or wi >= len(row):
                continue
            canon, _, _, txt = norm_header(row[ai][1])
            award = canon or txt
            if not canon and txt:
                report["unmapped"][txt] += 1
            if not award:
                continue
            for key, disp, nat, team, r in winners(row[wi][1], 1):
                out.append((award, r, key, disp, nat, team))
    return out


# ──────────────────────────────────────────────────────────────────────────── bullet-list awards ──
# 1970 and 2010 write (some of) their awards as a list: ``* [[…|Golden Boot]]: {{flagicon|GER}}
# [[Gerd Müller]] (…)``. Two gates keep prose out: the VALUE must carry a flag template — which is what
# rejects 2026's glossary ("* Golden Ball: Awarded to the best overall player of the tournament.",
# trap (c)) — and the LABEL must normalise to a real award (or at least mention one).
#
# The length limit is on the CLEANED label, never on the raw markup: the raw label is usually a piped
# wikilink to the awards article, and
# ``[[FIFA World Cup awards#FIFA Young Player Award|Best Young Player]]`` is 67 characters of markup
# for 17 characters of text. Measuring the markup silently dropped 1970's Fair Play Trophy and Young
# Player rows and 2010's Young Player row.
BULLET = re.compile(r"^\*+\s*([^:\n]{2,200}?)\s*:\s*(\S.*)$")
AWARD_ISH = re.compile(r"\b(?:award|trophy|ball|boot|shoe|glove|yashin|young player|fair play|"
                       r"best player|entertaining)\b", re.I)


def parse_bullets(sec, report):
    """[(award, rank, key, display, nation, is_team)] for the bullet-list awards in a section, with
    the ``{| … |}`` tables masked out first so a bullet inside a cell is not read twice."""
    masked, i, lines = [], 0, sec.split("\n")
    depth = 0
    for ln in lines:
        s = ln.strip()
        if s.startswith("{|"):
            depth += 1
        if depth:
            if s.startswith("|}"):
                depth -= 1
            continue
        masked.append(ln)
    out = []
    for ln in masked:
        m = BULLET.match(ln.strip())
        if not m:
            continue
        label, value = m.group(1), m.group(2)
        if FLAG_TMPL.search(label) or not FLAG_TMPL.search(value):
            continue                     # a description, a caveat, or prose — not a winner
        canon, _, _, txt = norm_header(label)
        if not canon:
            # An unknown label is only treated as an award if it actually reads like one; a prose
            # sentence that happens to contain a colon and a flag template is silently ignored, not
            # reported, because reporting it would bury the header drift this report exists to surface.
            if not (txt and len(txt) <= 60 and AWARD_ISH.search(txt)):
                continue
            report["unmapped"][txt] += 1
        award = canon or txt
        for key, disp, nat, team, r in winners(value, 1):
            out.append((award, r, key, disp, nat, team))
    return out


# ─────────────────────────────────────────────────────────────────────────────────────── output ──
FIELDS = ["year", "award", "rank", "player_key", "player_display", "nation", "is_team",
          "source_heading"]


def collect():
    """(rows, {year: [heading, …]}, report) for all 23 editions."""
    rows, headings = [], defaultdict(list)
    report = {"unmapped": Counter(), "orphan_rows": 0, "no_award_name": 0, "failures": []}
    for year in YEARS:
        page = f"{year} FIFA World Cup"
        try:
            wt = wikitext(page)
        except Exception as e:
            report["failures"].append((page, f"{type(e).__name__}: {e}"))
            continue
        for heading, sec in awards_sections(wt):
            headings[year].append(heading)
            found = list(parse_bullets(sec, report))
            for caption, trows in tables(sec):
                found += parse_table(caption, trows, report)
            for award, rank, key, disp, nat, team in found:
                rows.append({"year": year, "award": award, "rank": rank, "player_key": key,
                             "player_display": disp, "nation": nat, "is_team": team,
                             "source_heading": heading})
    # Dedupe identical rows (a shared cell can repeat a winner; a table can repeat a header block).
    seen, uniq = set(), []
    for r in rows:
        k = tuple(r[f] for f in FIELDS)
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    uniq.sort(key=lambda r: (r["year"], r["award"], r["rank"], r["player_key"], r["nation"]))
    return uniq, headings, report


def squad_keys():
    """{player_key} from data/wc_squads.csv — the join target that makes these rows useful."""
    fn = DATA / "wc_squads.csv"
    if not fn.exists():
        return set()
    with fn.open(encoding="utf-8") as f:
        return {r["player_key"] for r in csv.DictReader(f)}


# The published record, checked against the parse rather than trusted. A failure here means the CSV
# is wrong, not that the check is stale.
KNOWN = [(2022, "Golden Ball", "Lionel Messi"), (2022, "Golden Boot", "Kylian Mbappé"),
         (2018, "Golden Ball", "Luka Modrić"), (2014, "Golden Ball", "Lionel Messi"),
         (2006, "Golden Ball", "Zinedine Zidane"), (2006, "Golden Boot", "Miroslav Klose"),
         (2006, "Golden Glove", "Gianluigi Buffon"), (2006, "Best Young Player", "Lukas Podolski"),
         (1982, "Golden Ball", "Paolo Rossi"), (1982, "Golden Boot", "Paolo Rossi")]

CANON = ["Golden Ball", "Golden Boot", "Golden Glove", "Best Young Player", "Fair Play Trophy",
         "Most Entertaining Team"]


def main():
    rows, headings, report = collect()
    DATA.mkdir(parents=True, exist_ok=True)
    with (DATA / "wc_awards.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote data/wc_awards.csv ({len(rows)} rows)")

    # ─────────────────────────────────────────────────────────────────────── 1. coverage table ──
    byya = defaultdict(set)
    for r in rows:
        byya[r["year"]].add(r["award"])
    extra = sorted({r["award"] for r in rows} - set(CANON))
    cols = CANON + extra
    head = ["GBall", "GBoot", "GGlove", "YoungP", "FairPl", "MostEnt"] + extra
    print("\n1. COVERAGE  (n = rows for that award; '.' = award absent; blank line = no Awards section)")
    print("year  " + "  ".join(f"{h:>7}" for h in head) + "   heading(s)")
    for year in YEARS:
        if year not in headings:
            print(f"{year}  " + "  ".join(f"{'-':>7}" for _ in cols) + "   NO AWARDS SECTION")
            continue
        cnt = Counter(r["award"] for r in rows if r["year"] == year)
        print(f"{year}  " + "  ".join(f"{(cnt[c] or '.'):>7}" for c in cols)
              + "   " + " ; ".join(headings[year]))

    # ────────────────────────────────────────────────────────── 2. totals per award / per type ──
    print(f"\n2. TOTALS: {len(rows)} rows over {len(byya)} editions with an Awards section")
    for award, n in Counter(r["award"] for r in rows).most_common():
        w1 = sum(1 for r in rows if r["award"] == award and r["rank"] == 1)
        team = sum(1 for r in rows if r["award"] == award and r["is_team"])
        print(f"   {award:22} {n:4d} rows  ({w1} rank-1, {n - w1} lower placings, {team} team rows)")
    print(f"   {'is_team=1':22} {sum(r['is_team'] for r in rows):4d} rows")

    # ───────────────────────────────────────────────── 3. header text that did not normalise ──
    print("\n3. UNNORMALISED HEADER TEXT (passed through verbatim as the award name):")
    if report["unmapped"]:
        for txt, n in report["unmapped"].most_common():
            print(f"   {txt!r}  x{n}")
    else:
        print("   none")
    if report["orphan_rows"] or report["no_award_name"]:
        print(f"   (skipped: {report['orphan_rows']} data row(s) with no header above them, "
              f"{report['no_award_name']} ranked row(s) with no award name)")

    # ─────────────────────────────────────────────────────── 4. validation against known facts ──
    print("\n4. VALIDATION against the published record:")
    idx = {(r["year"], r["award"]): [] for r in rows}
    for r in rows:
        if r["rank"] == 1:
            idx[(r["year"], r["award"])].append(r)
    npass = 0
    for year, award, who in KNOWN:
        got = idx.get((year, award), [])
        keys = [g["player_key"] for g in got]
        ok = who in keys
        npass += ok
        print(f"   {'PASS' if ok else 'FAIL'}  {year} {award:18} expected {who!r}"
              f"  got {keys if keys else 'NOTHING'}")
    print(f"   -> {npass}/{len(KNOWN)} pass")

    # team-award consistency: is_team is detected from the CELL (no person link), so compare it with
    # which awards are known to be won by a nation. A disagreement is a real parse bug.
    bad = [r for r in rows
           if (r["award"] in TEAM_AWARDS) != bool(r["is_team"]) and r["award"] in CANON]
    print(f"   team-award consistency: {'PASS' if not bad else 'FAIL'} "
          f"({len(bad)} row(s) where is_team disagrees with the award type)")
    for r in bad[:10]:
        print(f"      {r['year']} {r['award']} is_team={r['is_team']} "
              f"key={r['player_key']!r} nation={r['nation']!r}")
    miss = [r for r in rows if not r["is_team"] and not r["player_key"]]
    print(f"   player rows with an empty player_key: {len(miss)}")
    nonat = [r for r in rows if not r["nation"]]
    print(f"   rows with an empty nation: {len(nonat)}"
          + ("" if not nonat else "  " + str([(r["year"], r["award"], r["player_key"])
                                              for r in nonat[:10]])))

    # ──────────────────────────────────────────────────────────── 5. join check against squads ──
    sq = squad_keys()
    people = [r for r in rows if not r["is_team"] and r["player_key"]]
    keys = {r["player_key"] for r in people}
    hit = {k for k in keys if k in sq}
    print(f"\n5. JOIN CHECK vs data/wc_squads.csv player_key "
          f"({len(sq)} distinct squad keys):")
    print(f"   distinct non-team player_key values: {len(keys)}")
    print(f"   found in wc_squads.csv:              {len(hit)}  "
          f"({100.0 * len(hit) / len(keys):.1f}%)")
    print(f"   rows affected: {sum(1 for r in people if r['player_key'] in sq)}/{len(people)} "
          f"({100.0 * sum(1 for r in people if r['player_key'] in sq) / len(people):.1f}%)")
    missing = sorted(keys - hit)
    print(f"   NOT in wc_squads.csv ({len(missing)}) — title-drift candidates for an alias table:")
    for k in missing:
        where = sorted({(r["year"], r["award"], r["nation"]) for r in people
                        if r["player_key"] == k})
        print(f"      {k!r}  {where}")

    if report["failures"]:
        print("\nPAGES THAT FAILED:")
        for t, why in report["failures"]:
            print(f"   {t}: {why}")


if __name__ == "__main__":
    main()
