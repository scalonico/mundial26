"""Mundial 26 — World Cup 2026 guide, bracket & predictor game (standalone).

Groups · full 104-match schedule (with time-zone conversion) · a visual knockout bracket · an
interactive "build your own bracket" predictor (share a code, score live against real results) ·
venues · teams. Reads data/wc2026_*.csv; re-run build/ingest.py during the tournament to pull live
scores → standings + bracket fill in automatically.

Run:  streamlit run streamlit_app.py
"""
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

import ui
import wc2026 as wc
import wchistory as wch

st.set_page_config(page_title="Mundial 26 · World Cup bracket & guide", page_icon="🏆", layout="wide")

SKY = "#6CACE4"
GOLD = "#FFD700"
GREEN = "#4ec98a"

# Plotly template — transparent (sits on the app's navy), Inter font, no gold in the colorway.
_tmpl = go.layout.Template()
_axis = dict(gridcolor="rgba(255,255,255,.05)", zerolinecolor="rgba(255,255,255,.12)",
             linecolor="rgba(255,255,255,.10)", title_font=dict(size=11, color="#90a4c2"),
             tickfont=dict(size=11, color="#9fb2cc"))
_tmpl.layout = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#cdd9ea", family="Inter, system-ui, sans-serif", size=12),
    colorway=[SKY, "#5BD1A0", "#E0563B", "#B388FF", "#F5A623", "#33B6A6"],
    title=dict(font=dict(size=15, color="#eaf1fb")),
    xaxis=_axis, yaxis=_axis,
    hoverlabel=dict(bgcolor="#16223b", bordercolor=SKY, font_size=12, font_family="Inter"),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11, color="#aebdd6")),
    margin=dict(l=10, r=10, t=10, b=10))
pio.templates["argentina"] = _tmpl
PLOTLY_TMPL = "plotly_dark+argentina"

# World Cup champions → "N× 🏆" badges on the Teams tab (West Germany folded into Germany).
WC_CHAMP = {1930:"Uruguay",1934:"Italy",1938:"Italy",1950:"Uruguay",1954:"West Germany",1958:"Brazil",
            1962:"Brazil",1966:"England",1970:"Brazil",1974:"West Germany",1978:"Argentina",1982:"Italy",
            1986:"Argentina",1990:"West Germany",1994:"Brazil",1998:"France",2002:"Brazil",2006:"Italy",
            2010:"Spain",2014:"Germany",2018:"France",2022:"Argentina"}
WC_TITLES = {}
for _yr, _w in WC_CHAMP.items():
    _n = "Germany" if _w == "West Germany" else _w
    WC_TITLES[_n] = WC_TITLES.get(_n, 0) + 1

# Host-country flags (the standalone app has only the 3 host nations — no pycountry needed).
HOST_ISO = {"Canada": "ca", "Mexico": "mx", "United States": "us"}
def host_flag(country, w=40):
    return wc.flag_url(HOST_ISO.get(country, ""), w)

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
html, body, [data-testid="stAppViewContainer"], [class*="css"] { font-family:'Inter',system-ui,sans-serif; }
#MainMenu, footer {visibility:hidden;}
header[data-testid="stHeader"] { background:transparent; }
.stApp {
    background:
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='28' height='49'%3E%3Cg fill='%236CACE4' fill-opacity='.05'%3E%3Cpath d='M13.99 9.25l13 7.5v15l-13 7.5L1 31.75v-15l12.99-7.5zM3 17.9v12.7l10.99 6.34 11-6.35V17.9l-11-6.34L3 17.9zM0 15l12.98-7.5V0h-2v6.35L0 12.69v2.3zm0 18.5L12.98 41v8h-2v-6.85L0 35.81v-2.3zM15 0v7.5L27.99 15H28v-2.31h-.01L17 6.35V0h-2zm0 49v-8l12.99-7.5H28v2.31h-.01L17 42.15V49h-2z'/%3E%3C/g%3E%3C/svg%3E"),
        radial-gradient(760px 420px at 50% -10%, rgba(124,186,238,.34), transparent 62%),     /* sky spotlight behind the hero */
        radial-gradient(960px 560px at 0% 2%, rgba(46,201,138,.30), transparent 56%),           /* emerald — pitch */
        radial-gradient(920px 540px at 100% 6%, rgba(245,176,65,.24), transparent 54%),          /* amber — warmth */
        radial-gradient(880px 620px at 62% 112%, rgba(46,201,138,.16), transparent 60%),         /* emerald lift, bottom */
        linear-gradient(168deg, #16345f 0%, #112744 40%, #0c1c34 72%, #0a1424 100%);             /* deep navy base */
    background-attachment: fixed;
}
.block-container { padding-top: 2.0rem; max-width: 1180px; }
[data-testid="stMetric"] { position:relative; overflow:hidden;
    background:linear-gradient(150deg,#1b2a47,#16223b); border:1px solid rgba(108,172,228,.16);
    border-radius:14px; padding:13px 16px 12px; box-shadow:0 2px 12px rgba(0,0,0,.22); }
[data-testid="stMetric"]::before { content:''; position:absolute; left:0; top:0; bottom:0; width:3px;
    background:linear-gradient(#6CACE4,#3a78b5); }
[data-testid="stMetricValue"] { color:#fff; font-weight:800; letter-spacing:-.5px; }
[data-testid="stMetricLabel"] p { color:#90a4c2; font-weight:700; text-transform:uppercase;
    letter-spacing:.05em; font-size:.72rem !important; }
table.wcg { width:100%; border-collapse:collapse; table-layout:fixed; font-size:.72rem; margin:.1rem 0 .35rem; }
table.wcg th { color:#8aa0bd; font-weight:700; text-align:center; padding:2px 0; font-size:.66rem; white-space:nowrap;
    border-bottom:1px solid rgba(108,172,228,.22); }
table.wcg td { text-align:center; padding:3px 0; color:#cdd9ea; border-bottom:1px solid rgba(108,172,228,.07); }
table.wcg th.tm, table.wcg td.tm { width:44%; text-align:left; white-space:nowrap; overflow:hidden;
    text-overflow:ellipsis; padding-left:3px; }
table.wcg img.gf { height:11px; width:16px; object-fit:cover; border-radius:2px;
    vertical-align:-1px; margin-right:4px; }
table.wcg td.pts, table.wcg th.pts { font-weight:700; color:#fff; }
h3, h4 { color:#dbe7f7; font-weight:700; letter-spacing:-.2px; }
hr { border-color:rgba(108,172,228,.15); }
</style>""", unsafe_allow_html=True)
ui.inject()


# ─────────────────────────────────────────────────────── WC bracket CSS + helpers
WC_BRACKET_CSS = f"""<style>
.wcbr {{ display:flex; gap:7px; height:780px; overflow-x:auto; padding:4px 2px 18px; }}
.wccol {{ display:flex; flex-direction:column; min-width:126px; }}
.wcch {{ font-size:.62rem; letter-spacing:.08em; text-transform:uppercase; color:#9fc4ec;
         font-weight:800; text-align:center; margin-bottom:8px; }}
.wccards {{ flex:1; display:flex; flex-direction:column; justify-content:space-around; gap:6px; }}
.wcmt {{ background:linear-gradient(160deg,#1d2d4c,#16223b); border:1px solid rgba(108,172,228,.20);
         border-radius:10px; padding:6px 9px; box-shadow:0 2px 9px rgba(0,0,0,.26); }}
.wctr {{ display:flex; justify-content:space-between; align-items:center; font-size:.80rem;
         color:#dce6f4; padding:2px 0; white-space:nowrap; }}
.wctr + .wctr {{ border-top:1px solid rgba(108,172,228,.10); }}
.wctm {{ display:flex; align-items:center; gap:6px; min-width:0; overflow:hidden; }}
.wctm img.wcf {{ width:18px; height:12px; object-fit:cover; border-radius:2px;
                 box-shadow:0 0 0 1px rgba(0,0,0,.3); flex:0 0 auto; }}
.wctm span {{ white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.wctm.wcp {{ color:#8aa0bd; font-weight:600; }}
.wcsc {{ font-weight:800; color:#fff; margin-left:6px; flex:0 0 auto; }}
.wcmeta {{ font-size:.66rem; color:#9fb2cc; font-weight:600; margin-top:4px; text-align:center; }}
.wcfin {{ background:linear-gradient(160deg,rgba(255,215,0,.15),#16223b); border:1px solid {GOLD};
          box-shadow:0 0 0 1px rgba(255,215,0,.4), 0 6px 20px rgba(255,215,0,.18); }}
.wcfin .wctr {{ color:{GOLD}; font-weight:700; }}
.wcfin .wcsc {{ color:{GOLD}; }}
</style>"""


def wc_bracket_html():
    """Two-sided knockout bracket as flexbox columns (R32→SF · Final · SF→R32). Each column is ordered
    top-to-bottom by the layout y, and `justify-content:space-around` fans each round in so every match
    sits between its two feeders. Returns (html, third_place_match_row)."""
    nodes, edges, third = wc.bracket_layout()
    lbl = {"R32": "Round of 32", "R16": "Round of 16", "QF": "Quarter-finals",
           "SF": "Semi-finals", "F": "Final"}

    def slot(x):                                          # flag image for a resolved team, else placeholder
        f = wc.code_flag(x)
        if f:
            return f"<span class='wctm'><img class='wcf' src='{f}'><span>{x}</span></span>"
        return f"<span class='wctm wcp'><span>{wc.short_slot(x)}</span></span>"

    def card(n, d):
        sc1 = "" if pd.isna(d["s1"]) else f"<span class='wcsc'>{int(d['s1'])}</span>"
        sc2 = "" if pd.isna(d["s2"]) else f"<span class='wcsc'>{int(d['s2'])}</span>"
        dt = pd.Timestamp(d["date"])
        cls = "wcmt wcfin" if d["stage"] == "F" else "wcmt"
        return (f"<div class='{cls}'>"
                f"<div class='wctr'>{slot(d['t1'])}{sc1}</div>"
                f"<div class='wctr'>{slot(d['t2'])}{sc2}</div>"
                f"<div class='wcmeta'>#{n} · {dt.strftime('%b')} {dt.day} · {d['city']}</div></div>")

    cols = []
    for x in range(9):
        cn = sorted((d["y"], n, d) for n, d in nodes.items() if d["x"] == x)
        if not cn:
            continue
        cards = "".join(card(n, d) for _, n, d in cn)
        cols.append(f"<div class='wccol'><div class='wcch'>{lbl[cn[0][2]['stage']]}</div>"
                    f"<div class='wccards'>{cards}</div></div>")
    return "<div class='wcbr'>" + "".join(cols) + "</div>", third


# ─────────────────────────────────────────────── World Cup bracket game ("Bracket challenge")
# Built from native st.button widgets so each pick is a normal rerun (session_state + active tab
# survive). The bracket re-solves from the predicted group order + explicit winners on every render.
GREEN = "#4ec98a"
WC_PLAY_CSS = """<style>
.wpch { font-size:.62rem; letter-spacing:.04em; text-transform:uppercase; color:#8aa0bd;
        font-weight:700; text-align:center; margin:0 0 4px; }
.wpmeta { font-size:.72rem; color:#aebfd6; font-weight:600; text-align:center; margin:2px 0 0; }
.wpstep { font-size:.86rem; color:#cdd9ea; background:rgba(108,172,228,.07); border-left:3px solid #6CACE4;
          border-radius:0 8px 8px 0; padding:7px 11px; margin:12px 0 9px; }
.wpstep b { color:#eaf1fb; }
/* ── Bracket fan-in: each round-column fills the tallest column's height (align-items:stretch) and
   space-arounds its match cards. The cards (keyed .st-key-wcm<match#>) are forced to flex:0 0 auto so
   they keep their NATURAL, compact, uniform height — only their POSITIONS converge toward the centre
   Final (no more giant stretched boxes in the sparse later rounds). */
.st-key-wcbr [data-testid="stHorizontalBlock"] { align-items: stretch; }
.st-key-wcbr [data-testid="stColumn"] > [data-testid="stVerticalBlock"] { height: 100%; }
.st-key-wcbr [data-testid="stVerticalBlock"]:has(> [data-testid="stLayoutWrapper"] > [class*="st-key-wcm"]) {
    justify-content: space-around; }
.st-key-wcbr [data-testid="stLayoutWrapper"]:has(> [class*="st-key-wcm"]),
.st-key-wcbr [class*="st-key-wcm"] { flex: 0 0 auto !important; }
/* compact bracket cards + buttons */
.st-key-wcbr [data-testid="stVerticalBlockBorderWrapper"] { border-radius: 7px; }
.st-key-wcbr [data-testid="stVerticalBlockBorderWrapper"] > div > [data-testid="stVerticalBlock"] { gap: 1px; }
.st-key-wcbr [data-testid="stElementContainer"] { margin: 0 !important; }
.st-key-wcbr .stButton button { padding: 1px 6px; min-height: 0; line-height: 1.45; font-size: .80rem;
    white-space: nowrap; overflow: hidden; }
.st-key-wcbr .stButton button p { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin: 0; }
.st-key-wcbr [data-testid="stColumn"] { padding: 0 1px; }
.st-key-wcbr .wpflagw { display: flex; align-items: center; justify-content: center; height: 24px; }
.st-key-wcbr img.wpflag { width: 100%; max-width: 20px; height: 13px; object-fit: cover;
    border-radius: 2px; box-shadow: 0 0 0 1px rgba(0,0,0,.35); display: block; }
.st-key-wcbr .wpflag-x { width: 20px; height: 13px; border-radius: 2px; background: rgba(108,172,228,.10); }
.st-key-wcbr [data-testid="stElementContainer"] { margin: 0 !important; }
/* flag+code sit tight: kill the default 16px gap between the two inner columns, and re-center the
   inner row (the outer fan-in rule sets align-items:stretch, which would top-align the flag). */
.st-key-wcbr [data-testid="stColumn"] [data-testid="stHorizontalBlock"] { gap: .2rem; align-items: center; }
.st-key-wcbr [data-testid="stColumn"] [data-testid="stColumn"] { padding: 0; }
/* ── The Final, spotlit: a gold, trophy-crowned card that's bigger & raised above the semi-finals. */
.st-key-wcm104 { position: relative; border: 1px solid #FFD700 !important;
    background: linear-gradient(160deg, rgba(255,215,0,.16), rgba(22,34,59,.55)) !important;
    box-shadow: 0 0 0 1px rgba(255,215,0,.55), 0 6px 22px rgba(255,215,0,.22) !important;
    padding: 7px 8px 6px !important; transform: translateY(-26px) scale(1.08); overflow: visible !important; }
.st-key-wcm104::before { content: "🏆"; position: absolute; top: -27px; left: 0; right: 0;
    text-align: center; font-size: 24px; line-height: 1; filter: drop-shadow(0 2px 4px rgba(0,0,0,.55)); }
.st-key-wcm104 .wpfin-h { text-align: center; color: #FFD700; font-weight: 800; font-size: .62rem;
    letter-spacing: .12em; margin: 0 0 3px; text-shadow: 0 1px 3px rgba(0,0,0,.4); }
.st-key-wcm104 .wpmeta { color: #e7c95a; }
/* the centre column header turns gold to match */
.wpch.wpch-final { color: #FFD700; font-size: .72rem; }
/* compact group-winner picker */
.st-key-wcgp .stButton button { padding: 0 6px; min-height: 0; line-height: 1.2; font-size: .74rem; text-align: left;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.st-key-wcgp [data-testid="stElementContainer"] { margin: 0 !important; }
.st-key-wcgp [data-testid="stVerticalBlock"] { gap: 1px; }
.st-key-wcgp [data-testid="stColumn"] { padding: 0 5px; }
/* the label's markdown container carries a -16px bottom margin (Streamlit quirk) that pulled the
   first button up over the label — zero it so the group letter sits cleanly above its list */
.st-key-wcgp [data-testid="stMarkdownContainer"] { margin-bottom: 0 !important; }
.st-key-wcgp .wpch { margin: 0; padding: 3px 0 1px; line-height: 1.1; }
/* Picks & bracket winners are GREEN (not the theme's sky) so the Play tab is green+gold, never blue+yellow.
   The single gold element stays the Final card (.st-key-wcm104). Cover both Streamlit primary-button selectors. */
.st-key-wcbr .stButton button[kind="primary"], .st-key-wcgp .stButton button[kind="primary"],
.st-key-wcbr button[data-testid="stBaseButton-primary"], .st-key-wcgp button[data-testid="stBaseButton-primary"] {
    background-color: #2f7355; border-color: #5aa982; color: #eafff3; }
.st-key-wcbr .stButton button[kind="primary"]:hover, .st-key-wcgp .stButton button[kind="primary"]:hover,
.st-key-wcbr button[data-testid="stBaseButton-primary"]:hover, .st-key-wcgp button[data-testid="stBaseButton-primary"]:hover {
    background-color: #39875f; border-color: #6dbf95; color: #ffffff; }
</style>"""

# The World Cup section tabs were faint 14px text that got lost beneath the bold stat boxes. Restyle them
# into a prominent full-width segmented pill bar (6 equal card-pills; active = filled sky, dark bold text).
# Scoped to .st-key-wc_tab (the st.tabs(key="wc_tab") wrapper) so no other tabs are affected.
WC_TABS_CSS = """<style>
.st-key-wc_tab [data-baseweb="tab-list"] { gap: 7px; margin-top: .55rem; border-bottom: none; }
.st-key-wc_tab [data-baseweb="tab-highlight"], .st-key-wc_tab [data-baseweb="tab-border"] { display: none !important; }
.st-key-wc_tab button[role="tab"] { flex: 1; justify-content: center; min-height: 0; padding: 10px 8px;
    background: linear-gradient(150deg, #1b2a47, #16223b); border: 1px solid rgba(108,172,228,.18);
    border-radius: 11px; color: #aebfd6; box-shadow: 0 2px 10px rgba(0,0,0,.20);
    transition: transform .12s ease, border-color .12s ease, background .12s ease, color .12s ease; }
.st-key-wc_tab button[role="tab"] p { font-size: .96rem; font-weight: 700; color: inherit; letter-spacing: -.1px; }
.st-key-wc_tab button[role="tab"]:hover { border-color: rgba(108,172,228,.48); color: #dbe7f7; transform: translateY(-2px); }
.st-key-wc_tab button[role="tab"][aria-selected="true"] { background: linear-gradient(150deg, #7fbaee, #5aa0d8);
    border-color: #6CACE4; color: #08111e; box-shadow: 0 6px 18px rgba(108,172,228,.32); }
.st-key-wc_tab button[role="tab"][aria-selected="true"] p { color: #08111e; font-weight: 800; }
</style>"""

# Polish for the World Cup page: a designed hero band, group-standings cards with qualification-zone
# shading, and a matchday-grouped schedule list. Plain string (CSS braces are literal). Injected once
# at the top of the WC page branch.
WC_POLISH_CSS = """<style>
.wchero { position:relative; overflow:hidden; display:flex; align-items:center; gap:22px; padding:18px 26px; margin:.1rem 0 1rem;
    background:
        radial-gradient(440px 200px at 13% 38%, rgba(255,215,0,.13), transparent 70%),
        radial-gradient(680px 280px at 90% 18%, rgba(90,201,160,.13), transparent 66%),
        linear-gradient(118deg,#0f2c57 0%, #1e4f88 36%, #173a68 64%, #122a4e 100%);
    border:1px solid rgba(124,186,238,.36); border-radius:16px;
    box-shadow:0 10px 34px rgba(0,0,0,.42), inset 0 1px 0 rgba(255,255,255,.07); }
.wch-emblem { width:90px; height:90px; flex:0 0 auto; display:flex; align-items:center; justify-content:center;
    font-size:58px; line-height:1; filter:drop-shadow(0 3px 9px rgba(0,0,0,.55)); }
.wch-body { flex:1 1 auto; min-width:0; }
.wch-kick { color:#9fc4ec; font-size:.78rem; font-weight:800; letter-spacing:.24em; text-transform:uppercase; }
.wch-body h1 { color:#fff; font-size:2.6rem; font-weight:800; letter-spacing:-1.2px; line-height:1; margin:.06rem 0 .22rem; }
.wch-sub { color:#dce8f7; font-size:1.02rem; }
.wch-sub b { color:#fff; }
.wch-sub img { vertical-align:-2px; border-radius:2px; margin:0 1px; }
.wch-dates { color:#9fb2cc; font-size:.9rem; font-weight:600; margin-top:.34rem; }
.wch-count { flex:0 0 auto; text-align:center; padding:11px 20px; border-radius:14px;
    background:linear-gradient(160deg,#3a2f00,#1b2438); border:1px solid rgba(255,215,0,.5); box-shadow:0 4px 16px rgba(0,0,0,.3); }
.wch-count .n { color:#FFD700; font-size:2.15rem; font-weight:800; line-height:1; }
.wch-count .l { color:#e7c95a; font-size:.66rem; font-weight:800; text-transform:uppercase; letter-spacing:.08em; margin-top:4px; }
.wgcard { background:linear-gradient(160deg,#1b2a47,#16223b); border:1px solid rgba(108,172,228,.18);
    border-radius:12px; padding:9px 11px 7px; box-shadow:0 2px 12px rgba(0,0,0,.22); margin-bottom:12px; }
.wgc-h { color:#dbe7f7; font-weight:800; font-size:1.02rem; letter-spacing:-.2px; margin:0 0 6px 1px; }
table.wcg td.rk, table.wcg th.rk { width:8%; color:#8aa0bd; font-weight:700; text-align:center; }
table.wcg tr.q1 td { background:rgba(90,169,130,.14); }
table.wcg tr.q1 td.rk { box-shadow:inset 3px 0 0 #5aa982; color:#bfe6cf; }
table.wcg tr.q3 td { background:rgba(201,154,58,.11); }
table.wcg tr.q3 td.rk { box-shadow:inset 3px 0 0 #c79a2e; color:#e3c483; }
table.wcg td.pts, table.wcg th.pts { width:10%; }
table.wcg-pre td:not(.tm) { color:#5d6b88; }            /* pre-kickoff: dim the all-zero stat columns */
table.wcg-pre td.pts { color:#8493ad; }
.wgkey { color:#8aa0bd; font-size:.78rem; margin:.1rem 0 .7rem 1px; }
.wgkey b.k-q { color:#7fcfa3; } .wgkey b.k-3 { color:#dcb45e; }
.wsched { margin-top:.5rem; }
.wsd-day { color:#9fc4ec; font-weight:800; font-size:.8rem; text-transform:uppercase; letter-spacing:.07em;
    margin:15px 0 7px; padding-bottom:4px; border-bottom:1px solid rgba(108,172,228,.20); }
.wsm { display:grid; grid-template-columns:56px 92px 1fr 70px 1fr 1.15fr; align-items:center; gap:9px;
    padding:7px 11px; margin-bottom:5px; border-radius:9px; background:linear-gradient(160deg,#1b2a47,#16223b);
    border:1px solid rgba(108,172,228,.13); }
.wsm .wsm-t { color:#cdd9ea; font-weight:700; font-size:.82rem; }
.wsm .wsm-rnd { color:#8aa0bd; font-size:.72rem; font-weight:700; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.wsm .tm { display:flex; align-items:center; gap:8px; color:#eaf1fb; font-weight:600; font-size:.9rem; min-width:0; }
.wsm .tm.home { justify-content:flex-end; text-align:right; }
.wsm .tm img { width:23px; height:15px; object-fit:cover; border-radius:2px; box-shadow:0 0 0 1px rgba(0,0,0,.3); flex:0 0 auto; }
.wsm .tm span { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.wsm .tm.ph span { color:#8aa0bd; font-weight:600; font-size:.82rem; }
.wsm .wsm-sc { text-align:center; font-weight:800; color:#fff; font-size:.86rem;
    background:rgba(108,172,228,.13); border-radius:6px; padding:3px 0; }
.wsm .wsm-ven { color:#8aa0bd; font-size:.76rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.wtgrid { display:grid; grid-template-columns:repeat(auto-fill,minmax(156px,1fr)); gap:9px; margin:.3rem 0 1.1rem; }
.wtcard { display:flex; align-items:center; gap:9px; padding:8px 11px; border-radius:10px;
    background:linear-gradient(160deg,#1b2a47,#16223b); border:1px solid rgba(108,172,228,.16); box-shadow:0 2px 9px rgba(0,0,0,.2); }
.wtcard img { width:30px; height:20px; object-fit:cover; border-radius:3px; box-shadow:0 0 0 1px rgba(0,0,0,.35); flex:0 0 auto; }
.wtcard > div { min-width:0; }
.wtcard .nm { color:#eaf1fb; font-weight:700; font-size:.9rem; line-height:1.12; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.wtcard .mt { color:#8aa0bd; font-size:.72rem; font-weight:600; margin-top:1px; }
.wcres-wrap { margin:.1rem 0 1.1rem; }
.wcres-h { color:#9fc4ec; font-weight:800; font-size:.8rem; text-transform:uppercase; letter-spacing:.07em; margin:0 0 8px 1px; }
.wcres { display:flex; flex-wrap:wrap; gap:9px; }
.wcres-chip { display:flex; align-items:center; gap:7px; padding:7px 12px; border-radius:10px;
    background:linear-gradient(160deg,#1b2a47,#16223b); border:1px solid rgba(108,172,228,.16); box-shadow:0 2px 9px rgba(0,0,0,.2); }
.wcres-chip img { width:22px; height:14px; object-fit:cover; border-radius:2px; box-shadow:0 0 0 1px rgba(0,0,0,.3); flex:0 0 auto; }
.wcres-chip .t { color:#a9bbd4; font-weight:700; font-size:.82rem; }
.wcres-chip .t.w { color:#fff; }                         /* winner stands out */
.wcres-chip .sc { color:#FFD700; font-weight:800; font-size:.84rem; padding:0 3px; }
.wcres-chip .dt { color:#7e90ad; font-size:.7rem; font-weight:700; margin-left:3px; }
</style>"""


def _wcp_pick(mno, code):
    """Button callback: record a knockout winner (a normal rerun re-solves the bracket forward).
    Mark it as a manual pick so the quick-fill strategies keep it while re-rolling the rest."""
    st.session_state.wcp_wins[mno] = code
    st.session_state.setdefault("wcp_manual", set()).add(mno)


def _wcp_qual(letter, code):
    """Button callback: toggle a team as a group qualifier — 1st, then 2nd, click again to clear
    (a 3rd tap replaces the runner-up). Two picks per group is all the game asks for."""
    q = st.session_state.wcp_q.setdefault(letter, [])
    if code in q:
        q.remove(code)
    elif len(q) < 2:
        q.append(code)
    else:
        q[1] = code


def wc_play_match(mno, d, is_final):
    """Render one knockout tie as a bordered card. When both teams are known it's two clickable buttons
    (the picked winner is highlighted green); until both feeders are decided it shows faded placeholders —
    so the bracket visibly fills in as winners are chosen."""
    t1, t2, w = d.get("t1"), d.get("t2"), d.get("winner")
    ready = bool(t1 and t2)
    with st.container(border=True, key=f"wcm{mno}"):
        if is_final:
            st.markdown("<div class='wpfin-h'>FINAL</div>", unsafe_allow_html=True)
        for side, (code, slot) in enumerate(((t1, d.get("slot1", "")), (t2, d.get("slot2", "")))):
            third = "³" if str(slot).startswith("3rd") else ""       # mark a 3rd-place qualifier
            fl, bt = st.columns([1, 5], vertical_alignment="center", gap="small")
            flag = wc.code_flag(code) if code else ""
            inner = (f"<img class='wpflag' src='{flag}'>" if flag else "<div class='wpflag-x'></div>")
            fl.markdown(f"<div class='wpflagw'>{inner}</div>", unsafe_allow_html=True)
            if ready:
                bt.button(f"{code}{third}", key=f"wk_{mno}_{side}", width="stretch",
                          type="primary" if code == w else "secondary",
                          on_click=_wcp_pick, args=(mno, code))
            else:
                bt.button(f"{code}{third}" if code else wc.short_slot(slot),
                          key=f"wk_{mno}_{side}", width="stretch", disabled=True)
        dt = pd.Timestamp(d.get("date"))
        st.markdown(f"<div class='wpmeta'>#{mno} · {dt.strftime('%b')} {dt.day}</div>",
                    unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════ THE PAGE
teams_df, ms, ven = wc.teams(), wc.matches(), wc.venues()
codes = set(teams_df["code"])
d2k = wc.days_to_kickoff()

# ── Bracket game: persisted prediction state (picks are made with native buttons → normal rerun,
# which preserves session_state and the active tab; callbacks live at module scope, see _wcp_pick).
# wcp_q[group] = [1st, 2nd] qualifiers; wcp_wins[match_no] = chosen knockout winner.
st.session_state.setdefault("wcp_q", {})
st.session_state.setdefault("wcp_wins", {})
st.session_state.setdefault("wcp_manual", set())       # match_nos picked by hand (kept across re-rolls)
st.session_state.setdefault("wcp_pool", [])           # friends' brackets loaded for the leaderboard

# A shared ?b=<code> link loads that bracket into the predictor once (then you can edit it).
if "b" in st.query_params and not st.session_state.get("wcp_param_loaded"):
    dec = wc.decode_picks(st.query_params["b"])
    if dec:
        st.session_state.wcp_q, st.session_state.wcp_wins = dec[0], dec[1]
        st.session_state.wcp_manual = set(dec[1])      # a loaded bracket's picks are all "given"
    st.session_state.wcp_param_loaded = True

if d2k > 0:
    tag = f"<span style='color:{GOLD};font-weight:700'>⏱ Kicks off in {d2k} days</span>"
elif d2k > -40:
    tag = f"<span style='color:{GOLD};font-weight:700'>🎉 Tournament underway</span>"
else:
    tag = ""
hosts = " &nbsp;·&nbsp; ".join(
    f"<img src='{wc.flag_url(c, 40)}' height='14' style='vertical-align:-2px;border-radius:2px'> {n}"
    for c, n in [("CA", "Canada"), ("MX", "Mexico"), ("US", "United States")])
st.markdown(WC_POLISH_CSS, unsafe_allow_html=True)
if d2k > 0:
    cnt = f"<div class='wch-count'><div class='n'>{d2k}</div><div class='l'>days to kickoff</div></div>"
elif d2k > -40:
    cnt = "<div class='wch-count'><div class='n'>🎉</div><div class='l'>underway</div></div>"
else:
    cnt = ""
st.markdown(
    f"<div class='wchero'><div class='wch-emblem'>🏆</div>"
    f"<div class='wch-body'><div class='wch-kick'>Bracket · Schedule · Predictor</div><h1>Mundial 26</h1>"
    f"<div class='wch-sub'>The first <b>48-team</b> World Cup &nbsp;·&nbsp; hosted by {hosts}</div>"
    f"<div class='wch-dates'>📅 June 11 – July 19, 2026 &nbsp;·&nbsp; 🏆 Final at MetLife Stadium, New York</div>"
    f"</div>{cnt}</div>", unsafe_allow_html=True)

ui.stats([
    ("Teams", "48", "6 confederations"),
    ("Groups", "12", "of 4 teams each"),
    ("Matches", str(len(ms)), "incl. knockouts"),
    ("Venues", "16", "3 host nations"),
])

# Latest results — surfaces the live scores at a glance once play begins (hidden pre-kickoff and when
# nothing has been played yet). Newest first; the winning side is brightened, gold scoreline.
done = ms[ms["played"]].sort_values(["date", "match_no"], ascending=[False, False])
if len(done):
    chips = []
    for r in done.head(8).itertuples():
        s1, s2 = int(r.score1), int(r.score2)
        w1 = " w" if s1 > s2 else ""
        w2 = " w" if s2 > s1 else ""
        day = (r.date.strftime("%b ") + str(r.date.day)) if pd.notna(r.date) else ""
        chips.append(
            f"<div class='wcres-chip'>"
            f"<img src='{wc.code_flag(r.team1)}'><span class='t{w1}'>{r.team1}</span>"
            f"<span class='sc'>{s1}–{s2}</span>"
            f"<span class='t{w2}'>{r.team2}</span><img src='{wc.code_flag(r.team2)}'>"
            f"<span class='dt'>{day}</span></div>")
    st.markdown(f"<div class='wcres-wrap'><div class='wcres-h'>⚽ Latest results</div>"
                f"<div class='wcres'>{''.join(chips)}</div></div>", unsafe_allow_html=True)

st.markdown(WC_TABS_CSS, unsafe_allow_html=True)
t_groups, t_sched, t_bracket, t_play, t_venues, t_teams, t_history = st.tabs(
    ["🗓️ Groups", "📋 Schedule", "🏆 Bracket", "🎮 Challenge", "🏟️ Venues", "🌍 Teams", "📜 History"], key="wc_tab")

def _koteam(x):
    return wc.team_label(x) if x in codes else wc.short_slot(x)

with t_groups:
    st.markdown(
        "<div class='wgkey'>Twelve groups of four — the <b>top two</b> of each, plus the <b>eight best "
        "third-placed</b> teams, advance to a 32-team knockout. Ranks and "
        "<b class='k-q'>green</b>/<b class='k-3'>amber</b> qualification shading appear once matches "
        "kick off (June 11).</div>", unsafe_allow_html=True)
    letters = list("ABCDEFGHIJKL")
    for r0 in range(0, 12, 4):
        for col, letter in zip(st.columns(4), letters[r0:r0 + 4]):
            with col:
                tbl = wc.group_standings(letter)
                # Full FIFA-style standings as a tight custom HTML card (st.dataframe can't fit this
                # many columns at 4-wide; flag IMAGE leads the Team cell — emoji flags fail on Windows).
                # The rank column + qualification shading appear ONLY once the group has played a match —
                # before kickoff every team is 0-0-0, so an ordering would be meaningless.
                gdf = lambda v: f"+{v}" if v > 0 else str(v)
                live = int(tbl["P"].sum()) > 0
                zc = {0: "q1", 1: "q1", 2: "q3"}
                rows = []
                for i, r in enumerate(tbl.itertuples()):
                    cls = zc.get(i, "") if live else ""
                    rk = f"<td class='rk'>{i + 1}</td>" if live else ""
                    rows.append(
                        f"<tr class='{cls}'>{rk}"
                        f"<td class='tm' title='{r.team}'><img class='gf' src='{r.flag_url}'> {wc.short_name(r.team)}</td>"
                        f"<td>{r.P}</td><td>{r.W}</td><td>{r.D}</td><td>{r.L}</td>"
                        f"<td>{r.GF}</td><td>{r.GA}</td><td>{gdf(r.GD)}</td>"
                        f"<td class='pts'>{r.Pts}</td></tr>")
                rkhead = "<th class='rk'>#</th>" if live else ""
                tcls = "wcg" if live else "wcg wcg-pre"   # dim the all-zero numbers before kickoff
                st.markdown(
                    f"<div class='wgcard'><div class='wgc-h'>Group {letter}</div>"
                    f"<table class='{tcls}'><thead><tr>{rkhead}<th class='tm'>Team</th>"
                    "<th>P</th><th>W</th><th>D</th><th>L</th><th>GF</th><th>GA</th>"
                    "<th>GD</th><th class='pts'>Pts</th></tr></thead>"
                    f"<tbody>{''.join(rows)}</tbody></table></div>", unsafe_allow_html=True)

with t_sched:
    fc = st.columns([1.2, 1.5, 1, 1.3])
    gsel = fc[0].selectbox("Group", ["All groups"] + [f"Group {l}" for l in "ABCDEFGHIJKL"], key="wc_grp")
    tsel = fc[1].selectbox("Team", ["All teams"] + sorted(teams_df["flag"] + " " + teams_df["name"]),
                           key="wc_team")
    ssel = fc[2].selectbox("Stage", ["All stages", "Group stage", "Knockout"], key="wc_stage")
    tzsel = fc[3].selectbox("Time zone", list(wc.TIMEZONES), key="wc_tz")
    tzname = wc.TIMEZONES[tzsel]
    d = ms
    if gsel != "All groups":
        d = d[d["group"] == gsel[-1]]
    if ssel == "Group stage":
        d = d[d["stage"] == "group"]
    elif ssel == "Knockout":
        d = d[d["stage"] != "group"]
    if tsel != "All teams":
        d = d[(d["team1_label"] == tsel) | (d["team2_label"] == tsel)]
    if d.empty:
        st.info("No matches match that filter.")
    else:
        if tzname:                                       # convert the absolute kickoff to the chosen zone
            conv = d["kickoff_utc"].dt.tz_convert(tzname)
            date_col = conv.dt.strftime("%a %b ") + conv.dt.day.astype(str)
            time_col = [f"{(t.hour % 12 or 12)}:{t.minute:02d} {'AM' if t.hour < 12 else 'PM'}"
                        if pd.notna(t) else "" for t in conv]
            tzcap = f"shown in **{tzsel.split(' ', 1)[-1]}** time"
        else:
            date_col = d["date"].dt.strftime("%a %b ") + d["date"].dt.day.astype(str)
            time_col = d["time_local"]
            tzcap = "local to each venue"
        nm = lambda x: wc.team_name(x) if x in codes else wc.short_slot(x)

        def tcell(x, side):                              # flag image + name; placeholder for unresolved KO slots
            f = wc.code_flag(x)
            name = f"<span>{nm(x)}</span>"
            if not f:
                return f"<div class='tm {side} ph'>{name}</div>"
            img = f"<img src='{f}'>"
            return f"<div class='tm {side}'>{name + img if side == 'home' else img + name}</div>"

        st.caption(f"{len(d)} matches · kickoff times {tzcap}.")
        dates, times = list(date_col), list(time_col)
        parts, last = ["<div class='wsched'>"], None
        for i, r in enumerate(d.itertuples()):
            if dates[i] != last:
                parts.append(f"<div class='wsd-day'>{dates[i]}</div>"); last = dates[i]
            rnd = f"Group {r.group}" if r.stage == "group" else r.stage_name
            sc = "vs" if pd.isna(r.score1) else f"{int(r.score1)}–{int(r.score2)}"
            parts.append(
                f"<div class='wsm'><span class='wsm-t'>{times[i]}</span>"
                f"<span class='wsm-rnd'>{rnd}</span>{tcell(r.team1, 'home')}"
                f"<span class='wsm-sc'>{sc}</span>{tcell(r.team2, 'away')}"
                f"<span class='wsm-ven'>{r.stadium}, {r.city}</span></div>")
        parts.append("</div>")
        st.markdown("".join(parts), unsafe_allow_html=True)

with t_bracket:
    st.caption("The 32-team knockout — two halves converging on the **Final** at MetLife Stadium "
               "(Jul 19). Slots fill as the groups finish: **1A** = Group A winner · **2B** = runner-up "
               "· **3rd …** = one of the eight best third-placed teams · **W73** = winner of match 73. "
               "Scroll sideways if the bracket runs wider than your screen.")
    st.markdown("👉 Want to call it yourself? The **🎮 Bracket challenge** tab turns this into a "
                "fill-in-your-own bracket — pick every winner through to the title.")
    bracket_html, third = wc_bracket_html()
    st.markdown(WC_BRACKET_CSS + bracket_html, unsafe_allow_html=True)
    if third is not None:
        td = pd.Timestamp(third.date)
        st.markdown(f"🥉 **Third-place play-off** — match #{int(third.match_no)} · "
                    f"{td.strftime('%b')} {td.day} · {third.city}: "
                    f"{wc.box_slot(third.team1)} vs {wc.box_slot(third.team2)}")

with t_play:
    wcp_q = st.session_state.wcp_q
    wcp_wins = st.session_state.wcp_wins
    order = wc.order_from_quals(wcp_q)
    res = wc.resolve_bracket(order, wcp_wins, fill_defaults=False)
    champ, runner, third3 = res[104]["winner"], res[104]["loser"], res[103]["winner"]
    n_groups = sum(1 for L in wc.GROUP_LETTERS if len(wcp_q.get(L, [])) == 2)
    npicks = sum(1 for m in res if m != 103 and m in wcp_wins and res[m]["winner"])

    st.markdown(WC_PLAY_CSS, unsafe_allow_html=True)
    st.caption("Predict the whole tournament in **3 steps** — then share your bracket and compete with friends.")
    ui.features([
        {"icon": "1️⃣", "title": "Pick the groups",
         "body": "Tap who finishes <b>1st &amp; 2nd</b> in each of the 12 groups."},
        {"icon": "2️⃣", "title": "Call the knockouts",
         "body": "Click the winner of every tie — the bracket <b>fills in live</b> down to your champion."},
        {"icon": "3️⃣", "title": "Challenge your friends",
         "body": "Share your bracket as a code and climb a <b>live leaderboard</b> as results come in "
                 "— <b>set up below ↓</b>.", "gold": True},
    ])

    # ── Group winners (collapsible) — sets who reaches the Round of 32; the bracket updates instantly
    with st.expander(f"1️⃣  Group winners — tap 1st & 2nd in each group   ·   {n_groups}/12 set",
                     expanded=(n_groups < 12 and npicks == 0)):
        st.caption("Tap a team for **1st** (①), tap another for **2nd** (②); tap again to undo. "
                   "The eight best 3rd-placed teams fill the rest of the Round of 32 automatically (³).")
        with st.container(key="wcgp"):
            for row0 in range(0, 12, 4):
                for letter, gcol in zip(wc.GROUP_LETTERS[row0:row0 + 4], st.columns(4)):
                    with gcol:
                        q = wcp_q.get(letter, [])
                        st.markdown(f"<div class='wpch' style='text-align:left'>Group {letter}</div>",
                                    unsafe_allow_html=True)
                        for code in wc.seed_order()[letter]:
                            rank = q.index(code) + 1 if code in q else 0
                            badge = {1: "①", 2: "②"}.get(rank, "")
                            st.button(f"{badge} {wc.team_name(code)}".strip(), key=f"q_{letter}_{code}",
                                      width="stretch", type="primary" if rank else "secondary",
                                      on_click=_wcp_qual, args=(letter, code))
        if st.button("🧹 Clear group picks"):
            st.session_state.wcp_q = {}
            st.rerun()

    # ── Step 2 label + champion banner (auto-updates) + bracket controls
    st.markdown("<div class='wpstep'><b>2️⃣ &nbsp;Knockouts</b> — click the winner of each tie in the "
                "bracket below (or use ⚡ Quick-fill); your champion updates live.</div>",
                unsafe_allow_html=True)
    if champ:
        fimg = (f"<img src='{wc.code_flag(champ)}' height='40' style='vertical-align:-8px;"
                f"border-radius:4px;box-shadow:0 2px 8px rgba(0,0,0,.4)'>")
        sub = (f"def. <b>{wc.team_name(runner)}</b> in the Final"
               + (f" &nbsp;·&nbsp; 🥉 {wc.team_name(third3)}" if third3 else ""))
        st.markdown(
            f"<div style='text-align:center;padding:12px 8px 7px;background:linear-gradient(160deg,"
            f"rgba(58,47,0,.55),rgba(22,34,59,.4));border:1px solid {GOLD};border-radius:12px;"
            f"margin:4px 0 10px'><div style='font-size:.7rem;letter-spacing:.12em;"
            f"text-transform:uppercase;color:#9fb2cc'>Your world champion</div>"
            f"<div style='font-size:1.8rem;font-weight:800;color:{GOLD};margin:3px 0'>"
            f"🏆 {fimg} &nbsp;{wc.team_name(champ)}</div>"
            f"<div style='font-size:.84rem;color:#cdd9ea'>{sub}</div></div>", unsafe_allow_html=True)
    else:
        st.markdown(
            f"<div style='text-align:center;padding:9px 8px;border:1px dashed rgba(255,215,0,.45);"
            f"border-radius:12px;margin:4px 0 10px;color:#9fb2cc'>🏆 <b>Your champion</b> — "
            f"click winners down to the Final to crown one</div>", unsafe_allow_html=True)

    st.markdown("⚡ **Quick-fill** the undecided ties:")
    cbar = st.columns([1, 1, 1, 0.9, 1.2, 2])
    fill = None
    if cbar[0].button("⭐ Favourites", width="stretch", help="Undecided ties → the stronger-seeded team"):
        fill = "fav"
    if cbar[1].button("🐣 Underdogs", width="stretch", help="Undecided ties → the weaker-seeded team (upsets!)"):
        fill = "underdog"
    if cbar[2].button("🎲 Random", width="stretch", help="Undecided ties → a coin flip (clear first for a fresh roll)"):
        fill = "random"
    if cbar[3].button("🧹 Clear", width="stretch", help="Undo all knockout picks"):
        st.session_state.wcp_wins = {}
        st.session_state.wcp_manual = set()
        st.rerun()
    cbar[4].metric("Picks", f"{npicks}/31")
    if fill:
        manual = st.session_state.get("wcp_manual", set())
        base = {m: w for m, w in wcp_wins.items() if m in manual}   # keep hand-picks, re-roll the rest
        st.session_state.wcp_wins = wc.autofill_wins(order, base, fill)
        st.rerun()

    # ── The bracket: native buttons in a TWO-SIDED shape (R32→SF · Final · SF→R32), mirroring the
    # 🏆 Bracket tab. Geometry from wc.bracket_layout() (x = 0..8 columns, y = vertical order); each
    # round-column spreads its cards (CSS space-around in .st-key-wcbr) so every match sits between
    # its two feeders and the two halves converge on the centre Final.
    nodes = wc.bracket_layout()[0]
    col_matches = {x: [n for _, n in sorted((nodes[n]["y"], n) for n in nodes if nodes[n]["x"] == x)]
                   for x in range(9)}
    hdr = ["R32", "R16", "QF", "SF", "Final", "SF", "QF", "R16", "R32"]
    for i, (label, hc) in enumerate(zip(hdr, st.columns(9, gap="small"))):
        hc.markdown(f"<div class='wpch{' wpch-final' if i == 4 else ''}'>{label}</div>",
                    unsafe_allow_html=True)
    with st.container(key="wcbr"):
        for x, col in zip(range(9), st.columns(9, gap="small")):
            with col:
                for mno in col_matches[x]:
                    wc_play_match(mno, res[mno], nodes[mno]["stage"] == "F")
    if res[103]["t1"] and res[103]["t2"]:
        st.markdown(f"<div style='font-size:.82rem;color:#9fb2cc;margin-top:8px'>"
                    f"🥉 Third-place play-off (#103): {wc.box_slot(res[103]['t1'])} vs "
                    f"{wc.box_slot(res[103]['t2'])} → 🏅 <b>{wc.team_name(third3)}</b></div>",
                    unsafe_allow_html=True)
    st.caption("**³** marks a 3rd-placed qualifier (auto-slotted by seeding — a stand-in for the "
               "official best-thirds table). Picks live only in your browser session.")

    # ── Bracket pool: share your bracket as a code, paste friends' codes, and see a leaderboard
    # scored against real results (live as the tournament plays out). No backend — codes carry the
    # whole prediction, and the "pool" is the set of brackets loaded into this session.
    st.divider()
    st.markdown("#### 3️⃣ Challenge your friends 🏆")
    st.caption("This is the **bracket pool** — copy your code below and send it to friends, paste theirs "
               "back, and everyone's bracket is **scored live** against the real results as games are "
               "played (**kickoff Jun 11**). No sign-up; the code carries your whole prediction.")
    mycode = wc.encode_picks(wcp_q, wcp_wins)
    pc1, pc2 = st.columns(2)
    with pc1:
        st.markdown("**📋 Your bracket code**")
        st.code(mycode, language=None)
        st.caption("Click the copy icon, then share it (or append `?b=…` to the app URL for a link).")
    with pc2:
        st.markdown("**➕ Add a friend's bracket**")
        fname = st.text_input("Name", key="wcp_fname", placeholder="their name, e.g. Alex",
                              label_visibility="collapsed")
        fcode = st.text_input("Code", key="wcp_fcode", placeholder="paste their WC1.… code",
                              label_visibility="collapsed")
        ac1, ac2 = st.columns([1, 1])
        if ac1.button("Add to pool", width="stretch"):
            dec = wc.decode_picks(fcode)
            if dec:
                nm = fname.strip() or f"Bracket {len(st.session_state.wcp_pool) + 2}"
                st.session_state.wcp_pool.append({"name": nm, "q": dec[0], "w": dec[1]})
                st.rerun()
            else:
                st.warning("That code didn't decode — make sure you copied all of it.")
        if st.session_state.wcp_pool and ac2.button("Clear pool", width="stretch"):
            st.session_state.wcp_pool = []
            st.rerun()

    entries = [{"name": "You", "q": wcp_q, "w": wcp_wins}] + st.session_state.wcp_pool
    lb = []
    for e in entries:
        sc = wc.score_picks(wc.order_from_quals(e["q"]), e["w"])
        ch = sc["champion"]
        lb.append({"": wc.code_flag(ch) if ch else "", "Bracket": e["name"],
                   "Champion pick": wc.team_name(ch) if ch else "—",
                   "Score": sc["total"], "_has": sc["has_results"]})
    any_results = any(r["_has"] for r in lb)
    lbdf = pd.DataFrame([{k: v for k, v in r.items() if k != "_has"} for r in lb]) \
        .sort_values(["Score", "Bracket"], ascending=[False, True]).reset_index(drop=True)
    st.dataframe(lbdf, hide_index=True, width="stretch",
                 column_config={"": st.column_config.ImageColumn("", width="small")})
    if not any_results:
        st.caption("Scoring — group qualifier **1** · reach R16 **1** · QF **2** · SF **4** · "
                   "Final **8** · correct champion **16** (max 104). Scores stay 0 until results "
                   "come in; for now, compare everyone's predicted champion.")
    else:
        st.caption("Scoring — group qualifier 1 · reach R16 1 · QF 2 · SF 4 · Final 8 · champion 16. "
                   "Updates live as results come in.")

VENUE_CSS = """<style>
.st-key-venuegrid [data-testid="stColumn"] { padding:0 5px; }
.st-key-venuegrid .stButton button, .st-key-venuegrid button {
    width:100%; min-height:108px; border-radius:12px; padding:10px 12px; border:1px solid rgba(108,172,228,.22);
    color:#fff !important; font-weight:800; font-size:.9rem; line-height:1.12; text-align:left; white-space:normal;
    display:flex; align-items:flex-end; justify-content:flex-start; background-color:#16223b;
    background-size:cover !important; background-position:center !important;
    box-shadow:0 3px 12px rgba(0,0,0,.32); transition:transform .12s ease, box-shadow .12s ease; }
.st-key-venuegrid button p { margin:0; text-shadow:0 1px 4px rgba(0,0,0,.8); }
.st-key-venuegrid button:hover { transform:translateY(-2px); box-shadow:0 8px 20px rgba(0,0,0,.42); border-color:#6CACE4; }
.ven-head { display:flex; align-items:center; flex-wrap:wrap; gap:12px; margin:.7rem 0 .5rem; padding:12px 16px;
    border-radius:13px; background:linear-gradient(150deg,rgba(20,42,74,.72),rgba(22,34,59,.94)); border:1px solid rgba(108,172,228,.26); }
.ven-head .nm { font-size:1.3rem; font-weight:800; color:#fff; letter-spacing:-.4px; }
.ven-head .loc { color:#9fb2cc; font-size:.84rem; margin-top:1px; }
.ven-head .meta { color:#cfe0f5; font-size:.86rem; margin-left:auto; white-space:nowrap; }
.ven-head .meta b { color:#6CACE4; }
.ven-sub { color:#6CACE4; font-weight:800; font-size:.95rem; margin:.7rem 0 .35rem; }
.ven-mt { display:grid; grid-template-columns:60px 1fr 46px 1fr 104px; align-items:center; gap:8px;
    padding:6px 12px; margin-bottom:4px; border-radius:8px; background:linear-gradient(160deg,#1b2a47,#16223b); border:1px solid rgba(108,172,228,.13); }
.ven-mt .dt { color:#8aa0bd; font-weight:700; font-size:.74rem; white-space:nowrap; }
.ven-mt .vs { text-align:center; color:#9fb2cc; font-weight:800; font-size:.8rem; }
.ven-mt .tmc { display:flex; align-items:center; gap:7px; color:#eaf1fb; font-weight:600; font-size:.86rem; min-width:0; }
.ven-mt .tmc.r { justify-content:flex-end; text-align:right; }
.ven-mt .tmc img { width:21px; height:14px; object-fit:cover; border-radius:2px; flex:0 0 auto; }
.ven-mt .tmc span { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.ven-mt .tmc .slot { color:#9fb2cc; font-weight:600; font-size:.8rem; }
.ven-mt .tag { color:#7e8ba5; font-size:.72rem; text-align:right; white-space:nowrap; }
</style>"""

with t_venues:
    st.markdown(VENUE_CSS, unsafe_allow_html=True)
    ui.stats([
        ("Venues", "16", "stadiums"),
        ("Host countries", "3", "Canada · Mexico · USA"),
        ("Biggest", "Estadio Azteca", "Mexico City · 83,264"),
        ("*Total seats", f"{int(ven['capacity'].sum()):,}", "across all 16"),
    ])
    st.caption("16 stadiums across Canada, Mexico and the USA — the **Final** at MetLife, the **opening "
               "match** at the iconic Estadio Azteca. **Tap any stadium** to see its full fixture list — "
               "group games and knockouts.")

    def _slug(s):
        return "".join(ch if ch.isalnum() else "_" for ch in str(s).lower())

    st.markdown("<style>" + "".join(
        f".st-key-ven_{_slug(r.stadium)} button{{background-image:"
        f"linear-gradient(180deg,rgba(11,18,32,.05) 24%,rgba(11,18,32,.93)),url('{wc.venue_photo(r.stadium)}') !important;}}"
        for r in ven.itertuples()) + "</style>", unsafe_allow_html=True)
    if st.session_state.get("sel_venue") not in set(ven["stadium"]):
        st.session_state["sel_venue"] = "MetLife Stadium"          # hosts the Final

    with st.container(key="venuegrid"):
        for country in ven.groupby("country")["capacity"].count().sort_values(ascending=False).index:
            cv = list(ven[ven.country == country].sort_values("capacity", ascending=False).itertuples())
            flag = f"<img src='{host_flag(country, 40)}' height='15' " \
                   "style='vertical-align:-2px;border-radius:2px;box-shadow:0 0 0 1px rgba(0,0,0,.3)'>"
            ui.section(f"{flag} &nbsp;{country}", f"{len(cv)} venue{'s' if len(cv) != 1 else ''}")
            for k in range(0, len(cv), 4):
                cols = st.columns(4)
                for j, r in enumerate(cv[k:k + 4]):
                    with cols[j]:
                        n = int((ms.stadium == r.stadium).sum())
                        if st.button(r.stadium, key=f"ven_{_slug(r.stadium)}",
                                     help=f"{int(r.capacity):,} seats · {n} matches"):
                            st.session_state["sel_venue"] = r.stadium

    sel = st.session_state["sel_venue"]
    st.markdown(f"<style>.st-key-ven_{_slug(sel)} button{{outline:2px solid #FFD700;outline-offset:-2px;"
                f"border-color:#FFD700 !important;}}</style>", unsafe_allow_html=True)

    vr = ven[ven.stadium == sel].iloc[0]
    vm = ms[ms.stadium == sel].sort_values("match_no")
    st.markdown(f"<div class='ven-head'><div><div class='nm'>🏟️ {sel}</div>"
                f"<div class='loc'>{vr.city}, {vr.country}</div></div>"
                f"<div class='meta'><b>{int(vr.capacity):,}</b> seats &nbsp;·&nbsp; <b>{len(vm)}</b> matches</div></div>",
                unsafe_allow_html=True)

    def _vmrow(x):
        def cell(val, right):
            fl = wc.code_flag(val)
            inner = (f"<img src='{fl}'><span>{wc.team_name(val)}</span>" if fl
                     else f"<span class='slot'>{val}</span>")
            return f"<div class='tmc{' r' if right else ''}'>{inner}</div>"
        dt = f"{x.date.day} {x.date.strftime('%b')}" if pd.notna(x.date) else ""
        mid = f"{int(x.score1)}–{int(x.score2)}" if x.played else "v"
        tag = f"Group {x.group}" if x.stage == "group" else x.stage_name
        return (f"<div class='ven-mt'><span class='dt'>{dt}</span>{cell(x.team1, True)}"
                f"<span class='vs'>{mid}</span>{cell(x.team2, False)}<span class='tag'>{tag}</span></div>")

    gm = vm[vm.stage == "group"]
    ko = vm[vm.stage != "group"]
    if len(gm):
        st.markdown("<div class='ven-sub'>⚽ Group stage</div>", unsafe_allow_html=True)
        st.markdown("".join(_vmrow(x) for x in gm.itertuples()), unsafe_allow_html=True)
    if len(ko):
        st.markdown("<div class='ven-sub'>🏆 Knockout stage</div>", unsafe_allow_html=True)
        st.markdown("".join(_vmrow(x) for x in ko.itertuples()), unsafe_allow_html=True)

with t_teams:
    conf = wc.confederation_counts()
    cc = st.columns([1.5, 1])
    fig = go.Figure(go.Bar(x=conf.values, y=conf.index, orientation="h",
                           marker_color=[wc.CONF_COLOR.get(c, SKY) for c in conf.index],
                           text=conf.values, textposition="outside", cliponaxis=False))
    fig.update_layout(template=PLOTLY_TMPL, height=240, margin=dict(l=10, r=30, t=8, b=10),
                      yaxis=dict(autorange="reversed"), xaxis_title="teams qualified")
    cc[0].markdown("**By confederation**"); cc[0].plotly_chart(fig, width="stretch")
    with cc[1]:
        ui.callout("🗓️ The format",
                   "<b>48 teams</b> · 12 groups of 4 · the top two of each group <b>plus the eight "
                   "best third-placed teams</b> reach a 32-team knockout, from the Round of 32 to "
                   "the Final at MetLife Stadium on <b>July 19</b>.")
    csel = st.selectbox("Confederation", ["All"] + list(conf.index), key="wc_conf")
    st.caption("48 teams. 🏆 = senior men's World Cup titles (8 nations have ever won; West Germany's "
               "three count as Germany). Head to **🎮 Bracket challenge** to predict how they'll finish.")
    for cfd in (list(conf.index) if csel == "All" else [csel]):
        sub = teams_df[teams_df["confederation"] == cfd].sort_values(["group", "name"])
        if sub.empty:
            continue
        ui.section(cfd, f"{len(sub)} team{'s' if len(sub) != 1 else ''}")
        cards = []
        for r in sub.itertuples():
            t = WC_TITLES.get(r.name, 0)
            meta = f"Group {r.group}" + (f" · {t}× 🏆" if t else "")
            cards.append(f"<div class='wtcard'><img src='{wc.flag_url(r.iso2)}'>"
                         f"<div><div class='nm' title='{r.name}'>{wc.short_name(r.name)}</div>"
                         f"<div class='mt'>{meta}</div></div></div>")
        st.markdown(f"<div class='wtgrid'>{''.join(cards)}</div>", unsafe_allow_html=True)

# ── 📜 History — the complete 1930–2022 archive (data + queries in wchistory.py)
WCH_CSS = """<style>
.wch-champs { display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); gap:11px; margin:.4rem 0 .7rem; }
.wch-champ { text-align:center; padding:13px 10px 11px; border-radius:13px; position:relative;
    background:linear-gradient(165deg,rgba(58,47,0,.42),rgba(22,34,59,.92)); border:1px solid rgba(255,215,0,.34);
    box-shadow:0 3px 14px rgba(0,0,0,.28); transition:transform .12s ease, box-shadow .12s ease; }
.wch-champ:hover { transform:translateY(-3px); box-shadow:0 8px 22px rgba(255,215,0,.18); }
.wch-yr { color:#FFD700; font-weight:800; font-size:1.06rem; letter-spacing:-.4px; }
.wch-cfl { width:48px; height:32px; object-fit:cover; border-radius:4px; margin:7px 0 6px; box-shadow:0 2px 8px rgba(0,0,0,.45); }
.wch-cnm { color:#fff; font-weight:800; font-size:.95rem; line-height:1.08; }
.wch-csc { color:#9fb2cc; font-size:.71rem; margin-top:4px; line-height:1.28; }
.wch-chost { color:#7e8ba5; font-size:.68rem; margin-top:6px; }
.wch-chost img { height:9px; border-radius:1px; margin-right:3px; vertical-align:0; }
.wch-h2h { text-align:center; font-size:1.45rem; font-weight:800; color:#eaf1fb; margin:.55rem 0 .55rem; }
.wch-h2h b { color:#6CACE4; } .wch-h2h .d { color:#9aa3b2; font-size:1rem; font-weight:700; }
.wch-mt { display:grid; grid-template-columns:48px 1fr 96px 1fr 1.05fr; align-items:center; gap:9px;
    padding:6px 12px; margin-bottom:4px; border-radius:8px; background:linear-gradient(160deg,#1b2a47,#16223b);
    border:1px solid rgba(108,172,228,.13); }
.wch-mt .y { color:#8aa0bd; font-weight:700; font-size:.76rem; }
.wch-mt .sc { font-weight:800; color:#fff; background:rgba(108,172,228,.14); border-radius:6px; padding:3px 0; text-align:center; font-size:.84rem; }
.wch-mt .tm { display:flex; align-items:center; gap:7px; color:#eaf1fb; font-weight:600; font-size:.88rem; min-width:0; }
.wch-mt .tm.r { justify-content:flex-end; text-align:right; }
.wch-mt .tm img { width:21px; height:14px; object-fit:cover; border-radius:2px; flex:0 0 auto; }
.wch-mt .tm span { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.wch-mt .st { color:#7e8ba5; font-size:.72rem; white-space:nowrap; text-align:right; overflow:hidden; text-overflow:ellipsis; }
.wch-edhead { display:flex; align-items:center; flex-wrap:wrap; gap:12px; margin:.2rem 0 .6rem; padding:11px 16px;
    border-radius:13px; background:linear-gradient(150deg,rgba(58,47,0,.30),rgba(22,34,59,.93)); border:1px solid rgba(255,215,0,.26); }
.wch-edttl { font-size:1.3rem; font-weight:800; color:#fff; letter-spacing:-.5px; }
.wch-edttl span { color:#9fb2cc; font-weight:600; font-size:.92rem; }
.wch-edmeta { display:flex; gap:15px; margin-left:auto; align-items:center; color:#cfe0f5; font-size:.85rem; white-space:nowrap; }
.wch-edmeta b { color:#FFD700; } .wch-edmeta img { height:13px; border-radius:2px; vertical-align:-2px; margin:0 4px 0 2px; }
.wch-mascot { display:inline-flex; align-items:center; gap:10px; margin:0 0 .5rem; padding:7px 14px 7px 11px; border-radius:10px;
    background:linear-gradient(160deg,#1f2d4a,#16223b); border:1px solid rgba(108,172,228,.2); }
.wch-mascot .mpic { height:48px; width:auto; max-width:68px; object-fit:contain; border-radius:5px; box-shadow:0 2px 7px rgba(0,0,0,.4); }
.wch-mascot .lbl { color:#6CACE4; font-weight:700; font-size:.66rem; text-transform:uppercase; letter-spacing:.4px; }
.wch-mascot .nm { color:#fff; font-weight:800; font-size:.95rem; }
.wch-mascot .cr { color:#6f7e98; font-size:.63rem; display:block; margin-top:1px; }
.wch-stagehd { color:#6CACE4; font-weight:800; font-size:.98rem; margin:.75rem 0 .35rem; }
.wch-grpwrap { display:grid; grid-template-columns:repeat(auto-fill,minmax(256px,1fr)); gap:10px; margin:.2rem 0 .5rem; }
.wch-grp { background:linear-gradient(160deg,#1b2a47,#16223b); border:1px solid rgba(108,172,228,.14); border-radius:11px; padding:8px 11px 9px; }
.wch-grphd { color:#6CACE4; font-weight:800; font-size:.8rem; margin-bottom:4px; }
.wch-gt { width:100%; border-collapse:collapse; font-size:.77rem; }
.wch-gt th { color:#7e8ba5; font-weight:700; font-size:.62rem; text-transform:uppercase; text-align:center; padding:1px 2px; }
.wch-gt th:first-child { text-align:left; }
.wch-gt td { padding:2px 2px; text-align:center; color:#cfe0f5; }
.wch-gt td.tm { text-align:left; color:#eaf1fb; font-weight:600; white-space:nowrap; overflow:hidden; max-width:130px; }
.wch-gt td.tm img { width:18px; height:12px; object-fit:cover; border-radius:2px; margin-right:6px; vertical-align:-1px; }
.wch-gt td.pts { color:#fff; font-weight:800; }
.wch-gt tr.lead td { background:rgba(108,172,228,.10); }
.wch-koround { color:#8aa0bd; font-weight:700; font-size:.78rem; text-transform:uppercase; letter-spacing:.4px; margin:.55rem 0 .25rem; }
/* clickable champions grid (the year opens that edition) */
.wch-cv { text-align:center; padding:1px 1px 0; }
.wch-cv img { width:44px; height:29px; object-fit:cover; border-radius:3px; box-shadow:0 2px 7px rgba(0,0,0,.45); }
.wch-cv .nm { color:#cfe0f5; font-size:.71rem; font-weight:600; margin-top:3px; line-height:1.04; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.st-key-champsgrid [data-testid="stColumn"] { padding:0 3px; }
.st-key-champsgrid .stButton button, .st-key-champsgrid button { width:100%; padding:1px 0 2px; min-height:0; border-radius:8px;
    font-weight:800; font-size:.94rem; color:#FFD700; background:linear-gradient(165deg,rgba(58,47,0,.34),rgba(22,34,59,.82)); border:1px solid rgba(255,215,0,.30); }
.st-key-champsgrid .stButton button:hover, .st-key-champsgrid button:hover { border-color:#FFD700; color:#fff; }
/* knockout bracket (funnel) */
.wch-bracket { display:flex; gap:13px; align-items:stretch; overflow-x:auto; padding:6px 2px 2px; }
.wch-bcol { display:flex; flex-direction:column; min-width:158px; flex:1 1 0; }
.wch-bct { color:#8aa0bd; font-weight:700; font-size:.7rem; text-transform:uppercase; letter-spacing:.4px; text-align:center; margin-bottom:6px; flex:0 0 auto; }
.wch-bcards { flex:1 1 auto; display:flex; flex-direction:column; justify-content:space-around; }
.wch-bm { background:linear-gradient(160deg,#1b2a47,#16223b); border:1px solid rgba(108,172,228,.16); border-radius:8px; padding:5px 8px; }
.wch-bm.gold { border-color:rgba(255,215,0,.55); background:linear-gradient(160deg,#2c2a12,#1a2238); box-shadow:0 2px 16px rgba(255,215,0,.16); }
.wch-bt { display:grid; grid-template-columns:18px 1fr auto; align-items:center; gap:6px; padding:2px 0; color:#9fb2cc; font-size:.79rem; }
.wch-bt.win { color:#fff; font-weight:800; }
.wch-bt img { width:18px; height:12px; object-fit:cover; border-radius:2px; }
.wch-bt .nm { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.wch-bt .sc { font-weight:700; } .wch-bt .pk { color:#9fb2cc; font-size:.66rem; margin-left:1px; font-weight:600; }
.wch-third { display:inline-flex; align-items:center; gap:9px; margin:9px 0 2px; padding:5px 13px; border-radius:9px; font-size:.82rem;
    background:linear-gradient(160deg,#241c10,#16223b); border:1px solid rgba(205,127,50,.32); }
.wch-third .lbl { color:#cd9b5a; font-weight:700; font-size:.72rem; text-transform:uppercase; letter-spacing:.3px; }
</style>"""
_STAGE = {"group": "Group", "group-2": "2nd group", "final-round": "Final round", "round-of-16": "Round of 16",
          "quarter-final": "Quarter-final", "semi-final": "Semi-final", "third-place": "3rd place", "final": "Final"}
# Official World Cup mascots (emoji · name · what it is). Mascots began in 1966; 1930–62 had none.
# Kept HERE in the main script (not wchistory) so a Streamlit Cloud module-cache miss can't break it,
# and emoji-only (the real mascot artwork is trademarked — consistent with avoiding FIFA marks).
WC_MASCOTS = {
    1966: ("🦁", "World Cup Willie", "a lion in a Union-Jack shirt — the first-ever World Cup mascot"),
    1970: ("🧒", "Juanito", "a boy in Mexico's kit and a sombrero"),
    1974: ("👦", "Tip & Tap", "two boys in West Germany shirts reading WM and 74"),
    1978: ("🧒", "Gauchito", "a boy in Argentina's kit with a gaucho hat and whip"),
    1982: ("🍊", "Naranjito", "a smiling orange in Spain's kit"),
    1986: ("🌶️", "Pique", "a jalapeño pepper with a sombrero and moustache"),
    1990: ("⚽", "Ciao", "a stick figure with a football head in Italy's colours"),
    1994: ("🐶", "Striker", "a dog in a USA kit — 'the World Cup Pup'"),
    1998: ("🐓", "Footix", "a blue cockerel, the emblem of France"),
    2002: ("🛸", "The Spheriks", "Ato, Kaz & Nik — futuristic computer-generated creatures"),
    2006: ("🦁", "Goleo VI", "a lion, alongside a talking football named Pille"),
    2010: ("🐆", "Zakumi", "a leopard with green hair"),
    2014: ("🦔", "Fuleco", "a three-banded armadillo, an endangered Brazilian species"),
    2018: ("🐺", "Zabivaka", "a wolf — 'the one who scores' in Russian"),
    2022: ("🧞", "La'eeb", "a floating keffiyeh — 'super-skilled player' in Arabic"),
}
# Mascot photos intentionally OFF — every edition shows a clean name-only chip. (Polished mascot images
# are copyrighted logos we don't use; the free Commons photos looked amateurish.) To re-enable one,
# add  year: ("<image-url>", "<credit>")  here and it renders automatically.
WC_MASCOT_IMG = {}

with t_history:
    st.markdown(WCH_CSS, unsafe_allow_html=True)
    rec = wch.records()
    ui.stats([
        ("Editions", "22", "1930 – 2022"),
        ("Matches", f"{rec['matches']:,}", "all-time"),
        ("Nations", str(rec["nations"]), "have competed"),
        ("*Most titles", rec["most_titles"], f"{rec['most_titles_n']} World Cups"),
    ])
    st.caption("The complete men's World Cup, archived from 1930 — champions, all-time records and any "
               "nation's head-to-head. West Germany counts with Germany; shootout knockouts count as draws.")

    ui.section("🏆 Champions", "tap a year to open that World Cup below — group tables + knockout bracket")
    champs_desc = list(reversed(wch.champions()))           # newest first
    _yset = {c["year"] for c in champs_desc}
    if st.session_state.get("hist_year") not in _yset:
        st.session_state["hist_year"] = champs_desc[0]["year"]   # default: most recent
    with st.container(key="champsgrid"):
        for _r in range(0, len(champs_desc), 6):
            _cols = st.columns(6)
            for _j, c in enumerate(champs_desc[_r:_r + 6]):
                with _cols[_j]:
                    st.markdown(f"<div class='wch-cv'><img src='{wch.flag_url(c['champion'], 80)}'>"
                                f"<div class='nm'>{c['champion']}</div></div>", unsafe_allow_html=True)
                    if st.button(str(c["year"]), key=f"hy_{c['year']}"):
                        st.session_state["hist_year"] = c["year"]
    sel = st.session_state["hist_year"]
    st.markdown(f"<style>.st-key-hy_{sel} button{{background:linear-gradient(165deg,rgba(255,215,0,.24),#16223b)!important;"
                f"border-color:#FFD700!important;color:#fff!important;box-shadow:0 0 0 1px #FFD700 inset;}}</style>",
                unsafe_allow_html=True)

    def _s(v):                                              # NaN-safe string cell
        return v if isinstance(v, str) else ""

    def _mt_row(x):
        pen = (f" <span style='color:#9fb2cc;font-size:.72rem'>({int(x.pens_home)}-{int(x.pens_away)}p)</span>"
               if pd.notna(x.pens_home) else "")
        dt = f"{x.date[8:10]}.{x.date[5:7]}" if (isinstance(x.date, str) and len(x.date) == 10) else ""
        place = _s(x.city) or _s(x.venue)
        return (f"<div class='wch-mt'><span class='y'>{dt}</span>"
                f"<div class='tm r'><span>{x.home}</span><img src='{wch.flag_url(x.home)}'></div>"
                f"<span class='sc'>{x.home_score}–{x.away_score}{pen}</span>"
                f"<div class='tm'><img src='{wch.flag_url(x.away)}'><span>{x.away}</span></div>"
                f"<span class='st'>{place}</span></div>")

    def _std_table(stage, g, tbl, qual):
        head = f"Group {g}" if g else ("Final pool" if stage == "final-round" else "Group")
        body = ""
        for i, r in enumerate(tbl.itertuples()):
            advanced = (r.team in qual) if qual else (i == 0)   # final pool (nothing downstream) → mark winner
            lead = " class='lead'" if advanced else ""
            body += (f"<tr{lead}><td class='tm'><img src='{wch.flag_url(r.team)}'>{r.team}</td>"
                     f"<td>{r.P}</td><td>{r.W}</td><td>{r.D}</td><td>{r.L}</td>"
                     f"<td>{r.GF}</td><td>{r.GA}</td><td class='pts'>{r.Pts}</td></tr>")
        return (f"<div class='wch-grp'><div class='wch-grphd'>{head}</div><table class='wch-gt'>"
                f"<tr><th>Team</th><th>P</th><th>W</th><th>D</th><th>L</th><th>GF</th><th>GA</th><th>Pts</th></tr>"
                f"{body}</table></div>")

    def _bwin(x):                                           # (home_won, away_won, has_shootout)
        haspk = pd.notna(x.pens_home)
        hw = (x.home_score > x.away_score) or (haspk and x.pens_home > x.pens_away)
        aw = (x.away_score > x.home_score) or (haspk and x.pens_away > x.pens_home)
        return hw, aw, haspk

    def _bmatch(x, gold=False):
        hw, aw, haspk = _bwin(x)

        def _row(team, gf, pk, win):
            pkt = f"<span class='pk'>({int(pk)})</span>" if (pk is not None and pd.notna(pk)) else ""
            return (f"<div class='wch-bt{' win' if win else ''}'><img src='{wch.flag_url(team)}'>"
                    f"<span class='nm'>{team}</span><span class='sc'>{gf}{pkt}</span></div>")
        return (f"<div class='wch-bm{' gold' if gold else ''}'>"
                + _row(x.home, x.home_score, x.pens_home if haspk else None, hw)
                + _row(x.away, x.away_score, x.pens_away if haspk else None, aw) + "</div>")

    def _bracket_html(kos):
        by = {s: m for s, m in kos}
        lbl = {"round-of-16": "Round of 16", "quarter-final": "Quarter-finals",
               "semi-final": "Semi-finals", "final": "Final"}
        cols = ""
        for s in ("round-of-16", "quarter-final", "semi-final", "final"):
            if s in by and len(by[s]):
                cards = "".join(_bmatch(x, gold=(s == "final")) for x in by[s].itertuples())
                cols += f"<div class='wch-bcol'><div class='wch-bct'>{lbl[s]}</div><div class='wch-bcards'>{cards}</div></div>"
        html = f"<div class='wch-bracket'>{cols}</div>"
        if "third-place" in by and len(by["third-place"]):
            x = next(by["third-place"].itertuples())
            hw, aw, _ = _bwin(x)
            html += (f"<div class='wch-third'><span class='lbl'>🥉 Third place</span>"
                     f"<span style='color:{'#fff' if hw else '#9fb2cc'}'>{x.home} {x.home_score}</span>"
                     f"<span style='color:#7e8ba5'>–</span>"
                     f"<span style='color:{'#fff' if aw else '#9fb2cc'}'>{x.away_score} {x.away}</span></div>")
        return html

    try:                                                    # never let the explorer crash the page (Cloud-safe)
        ov = wch.edition_overview(sel)
        cfl = wch.flag_url(ov["champion"], 40) if ov["champion"] else ""
        champ = f"🏆 <img src='{cfl}'><b>{ov['champion']}</b>" if ov["champion"] else ""
        st.markdown(f"<div class='wch-edhead'><div class='wch-edttl'>{sel} <span>· {ov['host']}</span></div>"
                    f"<div class='wch-edmeta'><span>{champ}</span><span>{ov['matches']} matches</span>"
                    f"<span>{ov['goals']} goals</span></div></div>", unsafe_allow_html=True)

        _ms = WC_MASCOTS.get(int(sel))
        if _ms:
            _img = WC_MASCOT_IMG.get(int(sel))
            if _img:
                st.markdown(f"<div class='wch-mascot'><img class='mpic' src='{_img[0]}' "
                            f"title='Photo: {_img[1]} · CC BY-SA · Wikimedia Commons'>"
                            f"<span><span class='lbl'>Mascot</span> <span class='nm'>{_ms[1]}</span>"
                            f"<span class='cr'>photo by {_img[1]} · CC BY-SA</span></span></div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='wch-mascot'><span class='lbl'>Mascot</span> "
                            f"<span class='nm'>{_ms[1]}</span></div>", unsafe_allow_html=True)
        elif int(sel) < 1966:
            st.caption("No official mascot this year — World Cup mascots began with World Cup Willie in 1966.")

        gts = wch.edition_group_tables(sel)
        _STG = {"group": "⚽ Group stage", "group-2": "⚽ Second group stage", "final-round": "🏆 Final round"}
        by_stage = {}
        for stage, g, tbl, gm in gts:
            by_stage.setdefault(stage, []).append((g, tbl))
        for stage in ("group", "group-2", "final-round"):
            if stage in by_stage:
                qual = wch.advanced_from(sel, stage)
                st.markdown(f"<div class='wch-stagehd'>{_STG[stage]}</div>", unsafe_allow_html=True)
                st.markdown("<div class='wch-grpwrap'>"
                            + "".join(_std_table(stage, g, tbl, qual) for g, tbl in by_stage[stage])
                            + "</div>", unsafe_allow_html=True)

        kos = wch.edition_knockouts(sel)
        if kos:
            st.markdown("<div class='wch-stagehd'>🏆 Knockout bracket</div>", unsafe_allow_html=True)
            st.markdown(_bracket_html(kos), unsafe_allow_html=True)

        if gts:
            ngm = sum(len(gm) for *_, gm in gts)
            with st.expander(f"🔎 All {ngm} group-stage matches"):
                for stage, g, tbl, gm in gts:
                    lbl = f"Group {g}" if g else _STG.get(stage, stage)
                    st.markdown(f"<div class='wch-koround'>{lbl}</div>", unsafe_allow_html=True)
                    st.markdown("".join(_mt_row(x) for x in gm.itertuples()), unsafe_allow_html=True)
    except Exception as _ed_err:                            # degrade gracefully; surface the trace for diagnosis
        st.warning("⚠️ The edition explorer is temporarily unavailable — the rest of this page works normally.")
        with st.expander("technical details"):
            st.exception(_ed_err)

    ui.section("🏛️ All-time table", "by titles · penalties = draws · West Germany folds into Germany")
    at = wch.all_time_table().copy()
    at.insert(0, " ", [wch.flag_url(n) for n in at["nation"]])
    at = at.rename(columns={"nation": "Nation", "titles": "🏆", "finals": "Finals", "editions": "Eds"})
    st.dataframe(at[[" ", "Nation", "🏆", "Finals", "Eds", "P", "W", "D", "L", "GF", "GA", "GD"]],
                 hide_index=True, width="stretch", height=430,
                 column_config={" ": st.column_config.ImageColumn(" ", width="small")})

    ui.section("⚔️ Head-to-head", "every World Cup meeting between two nations")
    noms = wch.nations()
    hc = st.columns(2)
    a = hc[0].selectbox("Nation A", noms, index=noms.index("Argentina"), key="wch_a")
    b = hc[1].selectbox("Nation B", noms, index=noms.index("Brazil"), key="wch_b")
    if a == b:
        st.info("Pick two different nations.")
    else:
        hh = wch.head_to_head(a, b)
        if hh.empty:
            st.info(f"{a} and {b} have never met at a World Cup.")
        else:
            wa = wb = dr = 0
            for x in hh.itertuples():
                if x.home_score > x.away_score:
                    w = x.home
                elif x.away_score > x.home_score:
                    w = x.away
                elif pd.notna(x.pens_home) and x.pens_home != x.pens_away:
                    w = x.home if x.pens_home > x.pens_away else x.away
                else:
                    w = None
                fw = wch.fold(w) if w else None
                wa += fw == a
                wb += fw == b
                dr += fw is None
            st.markdown(f"<div class='wch-h2h'><b>{a}</b> {wa} <span class='d'>– {dr} –</span> {wb} <b>{b}</b>"
                        f"<span style='display:block;font-size:.78rem;color:#8aa0bd;font-weight:600'>"
                        f"{len(hh)} World Cup meeting{'s' if len(hh) != 1 else ''}</span></div>", unsafe_allow_html=True)
            rows = ""
            for x in hh.itertuples():
                pen = (f" <span style='color:#9fb2cc;font-size:.72rem'>({int(x.pens_home)}-{int(x.pens_away)}p)</span>"
                       if pd.notna(x.pens_home) else "")
                rows += (f"<div class='wch-mt'><span class='y'>{int(x.year)}</span>"
                         f"<div class='tm r'><span>{x.home}</span><img src='{wch.flag_url(x.home)}'></div>"
                         f"<span class='sc'>{x.home_score}–{x.away_score}{pen}</span>"
                         f"<div class='tm'><img src='{wch.flag_url(x.away)}'><span>{x.away}</span></div>"
                         f"<span class='st'>{_STAGE.get(x.stage, x.stage)}</span></div>")
            st.markdown(rows, unsafe_allow_html=True)

    ui.section("📊 Records", "")
    bw, hg = rec["biggest"], rec["highest"]
    ui.features([
        {"icon": "💥", "title": "Biggest win", "body": f"<b>{bw[0]} {bw[1]}–{bw[2]} {bw[3]}</b> · {bw[4]}"},
        {"icon": "⚽", "title": "Highest-scoring", "body": f"<b>{hg[0]} {hg[1]}–{hg[2]} {hg[3]}</b> · {hg[4]}"},
        {"icon": "🌍", "title": "Ever-present", "body": f"<b>{rec['most_apps']}</b> — all {rec['most_apps_n']} editions"},
        {"icon": "🥅", "title": "Goals", "body": f"<b>{rec['goals']:,}</b> in {rec['matches']} matches", "gold": True},
    ])
