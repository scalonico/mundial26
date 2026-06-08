"""World Cup history archive — openfootball layer (1930–1982, COMPLETE).

openfootball/world-cup files are complete (group + knockouts) for 1930–1982 and Public Domain;
cached under build/history/sources/openfootball-world-cup/<YYYY--host>/cup.txt. Layout:
  '▪ <stage>' section headers · date lines ('July 13') · match lines
  'HOME  H-A (HT)  AWAY  @ Venue, City'  (a.e.t./pen. tails on knockouts) · scorer lines in parens.

Parses EVERY match (all nations) into the worldcup_matches schema. 1986–2026 come from a separate
Wikipedia/RSSSF layer. (Parser lifted from the futbol DB's openfootball_nt_ingest, minus its
Argentina-only filter.) Run:  python build/history/openfootball_wc.py
"""
import csv
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]                     # mundial26/
SRC = Path(__file__).resolve().parent / "sources" / "openfootball-world-cup"
OUT = ROOT / "data" / "worldcup_matches.csv"

MONTHS = {}
for _i, _full in enumerate(["January", "February", "March", "April", "May", "June", "July",
                            "August", "September", "October", "November", "December"], 1):
    MONTHS[_full.lower()] = _i
    MONTHS[_full[:3].lower()] = _i
WD = r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*"
RE_BULLET = re.compile(r"^▪\s*(.+?)\s*$")
RE_DATE = re.compile(rf"^\s*(?:{WD}\s+)?(?:([A-Za-z]{{3,9}})\s+(\d{{1,2}})|(\d{{1,2}})\s+([A-Za-z]{{3,9}}))\b")
RE_SCORE = re.compile(
    r"\d+-\d+(?:[\s,]+(?:a\.e\.t\.?|pen\.?|\([\d,\s-]+\)|\d+-\d+))*")   # FT + any HT()/a.e.t./pen. tail
RE_TIME = re.compile(r"^\s*\d{1,2}:\d{2}(?:\s+UTC[+-]?\d*)?\s+")        # '17:00 UTC+3 ' kickoff prefix (1986+)

COLS = ["year", "host", "stage", "group", "date", "home", "away", "home_score", "away_score",
        "extra_time", "pens_home", "pens_away", "venue", "city", "source"]


def stage_of(label):
    l = label.lower()
    if "final round" in l or "final group" in l:
        return "final-round"                          # 1950's round-robin decider (incl. the Maracanazo)
    if "group" in l:
        return "group"
    if "round of 16" in l or "eighth" in l or "preliminary" in l:
        return "round-of-16"                          # 1934's 'preliminary round' = its round of 16
    if "quarter" in l:
        return "quarter-final"
    if "semi" in l:
        return "semi-final"
    if "third" in l or "3rd" in l:
        return "third-place"
    if "final" in l:
        return "final"
    if "first round" in l:
        return "group"
    if "second round" in l or "second group" in l:
        return "group-2"
    return re.sub(r"[^a-z0-9]+", "-", l).strip("-")


def group_of(label):
    m = re.match(r"\s*Group\s+(\S+)", label, re.I)
    return m.group(1) if m else ""


def parse_score(s):
    """-> (home_score, away_score, extra_time, pens_home, pens_away). FT = first non-shootout pair
    (the '(HT)' pair is ignored); the shootout pair is the N-N immediately before 'pen'."""
    pairs = [(int(m.group()[:m.group().index("-")]), int(m.group()[m.group().index("-") + 1:]),
              m.start(), m.end()) for m in re.finditer(r"\d+-\d+", s)]
    if not pairs:
        return None, None, "", "", ""
    et = "Y" if "a.e.t" in s.lower() else ""
    ph = pa = ""
    pen = re.search(r"pen", s, re.I)
    rem = pairs
    if pen:
        before = [p for p in pairs if p[3] <= pen.start()]
        pp = before[-1] if before else pairs[0]
        ph, pa = pp[0], pp[1]
        rem = [p for p in pairs if p is not pp]
    ft = rem[0] if rem else (None, None)
    return ft[0], ft[1], et, ph, pa


def parse_edition(text, yr, host):
    rows, cur_date, stage, grp, had_numbered_group = [], None, "", "", False
    for raw in text.splitlines():
        line = re.sub(r"\s+#.*$", "", raw)                     # drop inline comments
        if not line.strip() or line.lstrip().startswith(("#", "=")):
            continue
        b = RE_BULLET.match(line)
        if b:
            head = b.group(1).split("|", 1)[0].strip()         # text before any "| date-range"
            if re.match(r"Matchday\s+\d", head, re.I):          # the schedule block (▪ Matchday N | dates) — skip
                continue
            grp = group_of(head)
            stg = stage_of(head)
            if stg == "group" and grp[:1].isalpha() and had_numbered_group:
                stg = "group-2"                                # 1974/78/82: lettered groups AFTER numbered = 2nd round
            had_numbered_group = had_numbered_group or grp[:1].isdigit()
            stage = stg
            continue
        if "|" in line:                                        # group-roster lines
            continue
        rest = line
        d = RE_DATE.match(rest)
        if d:
            mon = (d.group(1) or d.group(4)).lower()
            day = d.group(2) or d.group(3)
            if mon in MONTHS:
                try:
                    cur_date = date(yr, MONTHS[mon], int(day)).isoformat()
                except ValueError:
                    cur_date = None
                rest = rest[d.end():]
        t = RE_TIME.match(rest)                                # strip a kickoff-time prefix (1986+ files)
        if t:
            rest = rest[t.end():]
        if rest.strip().startswith("("):                       # scorer line, not a match
            continue
        sm = RE_SCORE.search(rest)
        if not sm:
            continue
        pre = rest[:sm.start()]
        if " v " in pre:                                       # "HOME v AWAY  SCORE  @ venue" (e.g. 2014)
            home, away = pre.split(" v ", 1)
            tail = rest[sm.end():]
            venue = tail.split("@", 1)[1] if "@" in tail else ""
        else:                                                  # "HOME  SCORE  AWAY  @ venue" (most editions)
            home = pre
            tail = rest[sm.end():]
            away, venue = (tail.split("@", 1) + [""])[:2] if "@" in tail else (tail, "")
        home, away, venue = home.strip(), away.strip(), venue.strip()
        if not home or not away:
            continue
        hs, as_, et, ph, pa = parse_score(sm.group())
        venue2, city = (venue.rsplit(",", 1) + [""])[:2] if "," in venue else (venue, "")
        rows.append({"year": yr, "host": host, "stage": stage, "group": grp, "date": cur_date or "",
                     "home": home, "away": away, "home_score": "" if hs is None else hs,
                     "away_score": "" if as_ is None else as_, "extra_time": et,
                     "pens_home": ph, "pens_away": pa, "venue": venue2.strip(), "city": city.strip(),
                     "source": "openfootball"})
    return rows


def main():
    all_rows = []
    for d in sorted(SRC.iterdir()):
        if not d.is_dir():
            continue
        yr = int(d.name.split("--")[0])
        host = d.name.split("--", 1)[1].replace("-", " ").title()
        host = {"Usa": "USA", "South Korea N Japan": "South Korea & Japan"}.get(host, host)
        rows = parse_edition((d / "cup.txt").read_text(encoding="utf-8"), yr, host)
        finals = d / "cup_finals.txt"                          # 1986+ split the knockouts into a 2nd file
        if finals.exists():
            rows += parse_edition(finals.read_text(encoding="utf-8"), yr, host)
        all_rows += rows
        print(f"  {yr} ({host}): {len(rows)} matches")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(all_rows)
    print(f"\nWrote {OUT.relative_to(ROOT)} ({len(all_rows)} matches · 1930–2022)")


if __name__ == "__main__":
    main()
