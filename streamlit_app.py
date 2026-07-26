"""Mundial — every World Cup, 1930–2026 (standalone).

Built during the 2026 tournament as a live guide/bracket/predictor; refocused once it ended (Spain
1–0 Argentina a.e.t., Jul 19 2026) around the part that doesn't go stale — the complete archive.

  · Every World Cup — all 23 editions: champions, per-edition group tables + knockout bracket,
    the all-time table, any two nations' head-to-head, and records. Served by wchistory.py.
  · 2026 in depth — that edition's own bracket, group standings, 104-match schedule (with
    time-zone conversion), teams and venues. Served by wc2026.py from data/wc2026_*.csv.
  · Challenge — the "build your own bracket" predictor (share a code, score against real results),
    kept from the live build and now scoring against a finished tournament.

The live-refresh Action (.github/workflows/update-data.yml) is retired but intact; re-point
build/ingest.py and restore its cron to cover a future tournament.

Run:  streamlit run streamlit_app.py
"""
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

import ui
import wc2026 as wc
import wchistory as wch
import wcplayers as wpl
import wcreplay as wcrp

st.set_page_config(page_title="Mundial · Every World Cup, 1930–2026", page_icon="🏆", layout="wide")

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
            2010:"Spain",2014:"Germany",2018:"France",2022:"Argentina",2026:"Spain"}
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
table.wcg td { text-align:center; padding:3px 0; color:#cdd9ea; border-bottom:1px solid rgba(108,172,228,.07); white-space:nowrap; }
table.wcg th.tm, table.wcg td.tm { width:44%; text-align:left; white-space:nowrap; overflow:hidden;
    text-overflow:ellipsis; padding-left:3px; }
table.wcg img.gf { height:11px; width:16px; object-fit:cover; border-radius:2px;
    vertical-align:-1px; margin-right:4px; }
table.wcg td.pts, table.wcg th.pts { font-weight:700; color:#fff; }
h3, h4 { color:#dbe7f7; font-weight:700; letter-spacing:-.2px; }
hr { border-color:rgba(108,172,228,.15); }
/* The page paints a dark background but Streamlit's default text colour is the light-theme dark
   ink, which disappears on navy. Force readable light text for ordinary markdown + captions
   (inline-styled custom HTML keeps its own colour and is unaffected). */
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li { color:#d4dfef; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p,
[data-testid="stCaptionContainer"] span { color:#aebfd6 !important; }
</style>""", unsafe_allow_html=True)
ui.inject()


# ─────────────────────────────────────────────────────── WC bracket CSS + helpers
# WC_BRACKET_CSS is gone with the two-sided 2026 bracket it styled; the archive's funnel
# (WCH_CSS .wch-bracket) renders every edition, 1930's two semi-finals through 2026's 16 R32 ties.
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
/* ── Bracket fan-in: each match card is positioned absolutely at the vertical centre of its two
   feeders (the same (y+0.5)/span geometry as the 🏆 Bracket tab), so every R16 sits between its two
   R32, every QF between its two R16, etc. The per-match top:% rules are generated at render time
   (WC_PLAY_POS) from wc.bracket_layout(). space-around can't do this — the dense R32 column packs out
   of step with the sparse later rounds — which left the inner rounds visibly off-centre. */
.st-key-wcbr [data-testid="stHorizontalBlock"] { align-items: stretch; }
/* Fixed-height positioning context — ONLY the 9 round columns (their vertical block directly holds the
   match-card wrappers). The :has() guard is essential: a plain stColumn>stVerticalBlock selector also
   matches the flag/button sub-columns INSIDE every card, which would stretch each tie to the full
   column height (the Final's gold card then paints as a full-height bar). */
.st-key-wcbr [data-testid="stColumn"] > [data-testid="stVerticalBlock"]:has(
    > [data-testid="stLayoutWrapper"] > [class*="st-key-wcm"]) { position: relative; height: 1040px; }
.st-key-wcbr [data-testid="stLayoutWrapper"]:has(> [class*="st-key-wcm"]) {
    position: absolute; left: 0; right: 0; transform: translateY(-50%); }
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
/* .wch-count / .wch-champ (the kickoff countdown, then the 2026 champions badge) are gone — the hero
   no longer singles out one edition, so it has no right-hand badge at all. */
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
.wsm .tm.prov span { font-style:italic; color:#cdd9ea; }      /* projected from standings, not yet official */
.wsm .tm.prov img { opacity:.5; }
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
/* The .wcres-* / .wctoday chip strip is gone with the two 2026-only front-page rows it styled. */
.wclive { display:flex; flex-wrap:wrap; gap:8px; margin:.2rem 0 1rem; }
.wclive .s { display:flex; align-items:baseline; gap:6px; padding:5px 12px; border-radius:9px;
    background:linear-gradient(160deg,#1b2a47,#16223b); border:1px solid rgba(108,172,228,.16); }
.wclive .s .v { color:#fff; font-weight:800; font-size:1rem; line-height:1.1; }
.wclive .s .l { color:#9fb2cc; font-size:.72rem; font-weight:600; text-transform:uppercase; letter-spacing:.04em; }
/* Phone: the three side-by-side group tables are unreadable at ~120px wide — stack them one-per-row
   (`:has(.wgcard)` scopes this to the Groups block only) and bump the now-roomier table's type. */
@media (max-width: 640px) {
  [data-testid="stHorizontalBlock"]:has(.wgcard) { flex-wrap:wrap; }
  [data-testid="stHorizontalBlock"]:has(.wgcard) [data-testid="stColumn"] {
      flex:1 1 100% !important; width:100% !important; min-width:100% !important; }
  table.wcg { font-size:.86rem; }
  table.wcg th { font-size:.76rem; }
  table.wcg img.gf { height:13px; width:19px; }
  /* The archive is the landing tab — tighten the matter above it so champions are in view sooner. */
  .block-container { padding-top:1.1rem; }
  .wchero { padding:13px 16px; gap:13px; margin:.1rem 0 .7rem; }
  .wch-emblem { width:58px; height:58px; }
  .wch-body h1 { font-size:1.9rem; }
  .wclive { margin:.15rem 0 .6rem; }
}
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

# A shared ?r=<code> link loads that REPLAY bracket once (then it can be edited like your own).
st.session_state.setdefault("rp_picks", {})
st.session_state.setdefault("rp_reveal", set())
if "r" in st.query_params and not st.session_state.get("rp_param_loaded"):
    _dec = wcrp.decode(st.query_params["r"])
    if _dec:
        st.session_state.rp_picks[_dec[0]] = _dec[1]
        st.session_state["rp_year"] = _dec[0]          # jump the picker to that edition
    st.session_state.rp_param_loaded = True

st.markdown(WC_POLISH_CSS, unsafe_allow_html=True)

# No champion badge and no "who won 2026" line: this site is about all 23 tournaments, and singling
# out the newest one made the front page read as a 2026 site with an archive bolted on. The third
# line orients the visitor instead — what the archive lets them DO — which stays true every edition.
_eds, _tot = len(wch.years()), len(wch.matches())
st.markdown(
    f"<div class='wchero'><div class='wch-emblem'>🏆</div>"
    f"<div class='wch-body'><div class='wch-kick'>Editions · Champions · Records</div><h1>Mundial</h1>"
    f"<div class='wch-sub'>Every World Cup from <b>Uruguay 1930</b> to the 48-team "
    f"<b>North America 2026</b></div>"
    f"<div class='wch-dates'>🔎 Open any edition for its group tables and full knockout bracket "
    f"&nbsp;·&nbsp; compare any two nations head-to-head</div>"
    f"</div></div>", unsafe_allow_html=True)

# Archive-wide pulse. This used to be the LIVE 2026 tournament pulse (played/goals/now/days-to-final);
# with the tournament finished those all freeze, so the row now measures the whole 1930–2026 archive —
# figures that grow once every four years instead of going stale in a week. It sits above the tabs, so
# it shows on every one of them; the archive tab therefore does NOT repeat these as stat cards.
_rec = wch.records()
_pulse = [(str(_eds), "editions"), (f"{_tot:,}", "matches"), (f"{_rec['goals']:,}", "goals"),
          (str(_rec["nations"]), "nations"),
          (_rec["most_titles"], f"most titles · {_rec['most_titles_n']}×")]
st.markdown("<div class='wclive'>" + "".join(
    f"<div class='s'><span class='v'>{v}</span><span class='l'>{l}</span></div>" for v, l in _pulse)
    + "</div>", unsafe_allow_html=True)

# Two front-page rows used to live here and both were 2026-only, so both are gone: the live
# "Today's schedule / Next matches" row (which could only ever render empty now) and the closing
# "How 2026 finished" results strip (which made an all-editions archive look like a 2026 site).
# 2026's results are still one click away in its own tabs. Recover either from git history
# (pre-2026-07-25) if this is ever pointed at a live tournament again.

_HOSTS = {c["year"]: c["host"] for c in wch.champions()}

st.markdown(WC_TABS_CSS, unsafe_allow_html=True)
# The archive leads, then the game that works on ANY edition. The 2026 tabs that follow are one
# edition's deep dive (its own bracket, group tables, schedule and venues), which no other edition has.
t_history, t_nations, t_players, t_venues, t_squads, t_crowds, t_replay, t_play = st.tabs(
    ["📜 Every World Cup", "🏳️ Nations", "👤 Players", "🏟️ Venues", "👥 Squads", "🎟️ Crowds",
     "🔁 Replay", "🎮 2026 Challenge"], key="wc_tab")


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
    # card is absolutely positioned at the vertical centre of its two feeders so the halves converge
    # cleanly on the centre Final (CSS in .st-key-wcbr; per-match top:% generated just below).
    nodes = wc.bracket_layout()[0]
    col_matches = {x: [n for _, n in sorted((nodes[n]["y"], n) for n in nodes if nodes[n]["x"] == x)]
                   for x in range(9)}
    # Per-match vertical placement: centre = (y+0.5)/span of the column (matches the 🏆 Bracket tab).
    span = max(nodes[n]["y"] for n in nodes) + 1
    pos_css = "".join(
        f".st-key-wcbr [data-testid='stLayoutWrapper']:has(> .st-key-wcm{n})"
        f"{{top:{(nodes[n]['y'] + 0.5) / span * 100:.4f}%;}}" for n in nodes)
    st.markdown(f"<style>{pos_css}</style>", unsafe_allow_html=True)
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
.ven-pick { color:#9fc4ec; font-weight:800; font-size:.86rem; text-transform:uppercase; letter-spacing:.06em;
    margin:1.1rem 0 .2rem; padding-top:.7rem; border-top:1px solid rgba(108,172,228,.16); }
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
.wch-bm .aet { display:block; text-align:right; color:#7e8ba5; font-size:.6rem; font-weight:700;
    text-transform:uppercase; letter-spacing:.3px; margin-top:1px; }
/* 2026 only: a 16-card first round would run ~4x the height of a 1998-2022 bracket, so tighten the
   cards and let the columns sit top-aligned instead of spreading over that full height. */
.wch-bracket.r32 .wch-bm { padding:3px 7px; }
.wch-bracket.r32 .wch-bt { font-size:.73rem; padding:1px 0; gap:5px; }
.wch-bracket.r32 .wch-bcards { justify-content:space-evenly; gap:3px; }
.wch-bracket.r32 .wch-bcol { min-width:142px; }
.wch-third { display:inline-flex; align-items:center; gap:9px; margin:9px 0 2px; padding:5px 13px; border-radius:9px; font-size:.82rem;
    background:linear-gradient(160deg,#241c10,#16223b); border:1px solid rgba(205,127,50,.32); }
.wch-third .lbl { color:#cd9b5a; font-weight:700; font-size:.72rem; text-transform:uppercase; letter-spacing:.3px; }
</style>"""
_STAGE = {"group": "Group", "group-2": "2nd group", "final-round": "Final round",
          "round-of-32": "Round of 32", "round-of-16": "Round of 16",
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
    2026: ("🫎", "Maple, Zayu & Clutch", "a moose, a jaguar and a bald eagle — one per host nation"),
}
# Mascot photos intentionally OFF — every edition shows a clean name-only chip. (Polished mascot images
# are copyrighted logos we don't use; the free Commons photos looked amateurish.) To re-enable one,
# add  year: ("<image-url>", "<credit>")  here and it renders automatically.
WC_MASCOT_IMG = {}

with t_history:
    st.markdown(WCH_CSS, unsafe_allow_html=True)
    rec = wch.records()
    _yrs = wch.years()
    # No stat cards here: this is the DEFAULT tab, so the four figures would sit inches below the
    # identical ones in the pulse row above the tab bar. The pulse carries them for every tab.
    st.caption(f"The complete men's World Cup, {_yrs[0]}–{_yrs[-1]} — champions, all-time records and any "
               "nation's head-to-head. West Germany counts with Germany, Czech Republic with Czechia and "
               "Zaire with DR Congo; shootout knockouts count as draws.")

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

    def _aet(x):
        """'a.e.t.' tag for a tie settled in extra time without a shootout — otherwise a 1–0 gives no
        hint that it took 120 minutes (2026's final, and the 1966/1978/2010/2014 finals too)."""
        return ("<span class='aet'>a.e.t.</span>"
                if (getattr(x, "extra_time", "") == "Y" and pd.isna(x.pens_home)) else "")

    def _bmatch(x, gold=False):
        hw, aw, haspk = _bwin(x)

        def _row(team, gf, pk, win):
            pkt = f"<span class='pk'>({int(pk)})</span>" if (pk is not None and pd.notna(pk)) else ""
            return (f"<div class='wch-bt{' win' if win else ''}'><img src='{wch.flag_url(team)}'>"
                    f"<span class='nm'>{team}</span><span class='sc'>{gf}{pkt}</span></div>")
        return (f"<div class='wch-bm{' gold' if gold else ''}'>"
                + _row(x.home, x.home_score, x.pens_home if haspk else None, hw)
                + _row(x.away, x.away_score, x.pens_away if haspk else None, aw)
                + _aet(x) + "</div>")

    def _bracket_html(kos):
        by = {s: m for s, m in kos}
        lbl = {"round-of-32": "Round of 32", "round-of-16": "Round of 16", "quarter-final": "Quarter-finals",
               "semi-final": "Semi-finals", "final": "Final"}
        cols = ""
        for s in ("round-of-32", "round-of-16", "quarter-final", "semi-final", "final"):
            if s in by and len(by[s]):
                cards = "".join(_bmatch(x, gold=(s == "final")) for x in by[s].itertuples())
                cols += f"<div class='wch-bcol'><div class='wch-bct'>{lbl[s]}</div><div class='wch-bcards'>{cards}</div></div>"
        # 2026's 16-card first round makes the bracket ~4x taller than a 1998-2022 one; the extra class
        # lets the CSS tighten the cards so the whole thing still fits without a scroll cage.
        wide = " r32" if len(by.get("round-of-32", ())) else ""
        html = f"<div class='wch-bracket{wide}'>{cols}</div>"
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

# ── 🔁 Replay a World Cup ──────────────────────────────────────────────────────────────────────────
# The same idea as the 2026 Challenge, but it works on ANY of the 20 replayable editions: you are given
# the real knockout qualifiers and must call every tie, with your winners feeding the next round, then
# score the bracket against what actually happened. Logic lives in wcreplay.py (the tree is derived from
# results, so it fits every era's shape); this block is only the UI.
#
# Rounds are laid out as stacked rows rather than the archive tab's left-to-right funnel: Streamlit
# buttons need real width to stay legible, and 16 first-round ties in a narrow column would truncate
# every nation to a few characters. The archive tab already shows the funnel, read-only.
WCRP_CSS = """<style>
.rp-round { color:#9fc4ec; font-weight:800; font-size:.82rem; text-transform:uppercase; letter-spacing:.07em;
    margin:.9rem 0 .1rem 1px; display:flex; align-items:center; gap:9px; }
.rp-round .n { color:#7e8ba5; font-weight:700; font-size:.72rem; text-transform:none; letter-spacing:0; }
.rp-flag { width:26px; height:17px; object-fit:cover; border-radius:2px; box-shadow:0 0 0 1px rgba(0,0,0,.35); display:block; }
.rp-flag-x { width:26px; height:17px; border-radius:2px; background:rgba(255,255,255,.05); }
.rp-meta { color:#7e8ba5; font-size:.68rem; font-weight:700; text-align:right; margin-top:-2px; }
.rp-meta .rep { color:#e0a03b; }
/* scoreboard */
.rp-score { display:flex; align-items:center; gap:16px; flex-wrap:wrap; padding:13px 18px; border-radius:13px; margin:.3rem 0 .2rem;
    background:linear-gradient(160deg,#2c2a12,#1a2238); border:1px solid rgba(255,215,0,.45); }
.rp-score .tot { color:#FFD700; font-size:2rem; font-weight:800; line-height:1; }
.rp-score .of { color:#c9b25a; font-size:.9rem; font-weight:700; }
.rp-score .pct { color:#e7c95a; font-size:.72rem; font-weight:800; text-transform:uppercase; letter-spacing:.08em; }
.rp-bd { display:flex; flex-wrap:wrap; gap:7px; margin:.4rem 0 .2rem; }
.rp-bd .b { padding:5px 11px; border-radius:9px; font-size:.76rem; font-weight:700; color:#cfe0f5;
    background:linear-gradient(160deg,#1b2a47,#16223b); border:1px solid rgba(108,172,228,.16); }
.rp-bd .b i { color:#8aa0bd; font-style:normal; font-weight:600; }
.rp-champ { display:flex; align-items:center; gap:10px; padding:8px 14px; border-radius:10px; font-size:.9rem; font-weight:700;
    background:linear-gradient(160deg,#1b2a47,#16223b); border:1px solid rgba(108,172,228,.2); margin:.2rem 0 .1rem; }
.rp-champ img { width:28px; height:19px; object-fit:cover; border-radius:2px; }
.rp-champ.ok { border-color:rgba(78,201,138,.55); }
.rp-champ .ko { color:#e0563b; } .rp-champ .yes { color:#4ec98a; }
</style>"""


def _rp_pick(year, mid, team):
    """Button callback: record a knockout winner for one edition. Changing any pick invalidates a
    revealed score, so the player can't half-edit a bracket while still looking at the old total."""
    st.session_state.rp_picks.setdefault(year, {})[mid] = team
    st.session_state.rp_reveal.discard(year)


def _rp_clear(year):
    st.session_state.rp_picks[year] = {}
    st.session_state.rp_reveal.discard(year)


def _rp_reveal(year):
    st.session_state.rp_reveal.add(year)


st.session_state.setdefault("rp_picks", {})       # {year: {mid: team}} — kept per edition
st.session_state.setdefault("rp_reveal", set())   # editions whose score is currently shown
st.session_state.setdefault("rp_pool", [])        # friends' brackets for the leaderboard

with t_replay:
    st.markdown(WCRP_CSS, unsafe_allow_html=True)
    ui.section("🔁 Replay a World Cup",
               "you get the real qualifiers — call every knockout tie, then score your bracket against history")

    _eds = wcrp.replayable()
    _yrs = [y for y, _n, _lbl in _eds]
    _nmatch = {y: n for y, n, _lbl in _eds}
    _champs = {c["year"]: c for c in wch.champions()}

    _c = st.columns([2, 1, 1], vertical_alignment="bottom")
    year = _c[0].selectbox(
        "Edition", _yrs, index=len(_yrs) - 1, key="rp_year",
        format_func=lambda y: f"{y} · {_champs[y]['host']} — {_nmatch[y]} ties")
    picks = st.session_state.rp_picks.setdefault(year, {})
    _done = wcrp.picked_count(year, picks)
    _all = _nmatch[year]
    _c[1].button("🎲 Clear picks", key="rp_clear", width="stretch", on_click=_rp_clear, args=(year,),
                 disabled=not picks)
    _c[2].button("🏁 Reveal & score", key="rp_rev", width="stretch", type="primary",
                 on_click=_rp_reveal, args=(year,), disabled=_done < _all)

    if year not in st.session_state.rp_reveal:
        st.caption(f"**{_done} of {_all}** ties called. Results stay hidden until you reveal — though the "
                   f"📜 Every World Cup tab will spoil {year} if you open it.")
    _rounds = wcrp.resolve(year, picks)

    for _ri, _rd in enumerate(_rounds):
        _ms = _rd["matches"]
        st.markdown(f"<div class='rp-round'>{_rd['label']}"
                    f"<span class='n'>{len(_ms)} tie{'s' if len(_ms) != 1 else ''}</span></div>",
                    unsafe_allow_html=True)
        _per = 4 if len(_ms) > 2 else max(len(_ms), 1)          # 1 wide card for the Final, 2 for semis
        for _i in range(0, len(_ms), _per):
            _cols = st.columns(_per)
            for _j, _m in enumerate(_ms[_i:_i + _per]):
                with _cols[_j]:
                    with st.container(border=True, key=f"rpc_{year}_{_m['mid']}"):
                        for _side, _team in (("h", _m["p_home"]), ("a", _m["p_away"])):
                            _fl, _bt = st.columns([1, 4], vertical_alignment="center", gap="small")
                            _src = wcrp.flag(_team) if _team else ""
                            _fl.markdown(
                                f"<img class='rp-flag' src='{_src}'>" if _src else
                                "<div class='rp-flag-x'></div>", unsafe_allow_html=True)
                            if _team:
                                _bt.button(_team, key=f"rpb_{year}_{_m['mid']}_{_side}", width="stretch",
                                           type="primary" if _m["pick"] == _team else "secondary",
                                           on_click=_rp_pick, args=(year, _m["mid"], _team))
                            else:                              # upstream tie not called yet
                                _bt.button("—", key=f"rpb_{year}_{_m['mid']}_{_side}",
                                           width="stretch", disabled=True)
                        _rep = ("<span class='rep'>· replay</span>" if _m.get("legs", 1) > 1 else "")
                        _dt = str(_m["date"])
                        _day = f"{_dt[8:10]}.{_dt[5:7]}" if len(_dt) >= 10 else ""
                        st.markdown(f"<div class='rp-meta'>{_day} {_rep}</div>", unsafe_allow_html=True)

    if year in st.session_state.rp_reveal:
        sc = wcrp.score(year, picks)
        ui.section(f"🏁 Your {year} bracket, scored", "")
        st.markdown(
            f"<div class='rp-score'><span class='tot'>{sc['total']}</span>"
            f"<span class='of'>/ {sc['possible']} points</span>"
            f"<span class='pct'>{sc['pct']}% of a perfect bracket</span></div>", unsafe_allow_html=True)
        _bd = "".join(
            f"<div class='b'>{b['label']}: <b>{b['hit']}</b><i>/{b['of']} teams right · "
            f"{b['points']} pt{'s' if b['points'] != 1 else ''}</i></div>" for b in sc["breakdown"])
        _bd += (f"<div class='b'>Champion: <i>{sc['champion_points']}/{sc['champion_max']} pts</i></div>")
        st.markdown(f"<div class='rp-bd'>{_bd}</div>", unsafe_allow_html=True)
        _ok = sc["champion_correct"]
        st.markdown(
            f"<div class='rp-champ{' ok' if _ok else ''}'>"
            f"<img src='{wcrp.flag(sc['champion'])}'><span>You picked <b>{sc['champion']}</b></span>"
            f"<span class='{'yes' if _ok else 'ko'}'>{'✓ correct' if _ok else '✗'}</span>"
            + ("" if _ok else f"<span style='color:#9fb2cc'>— {year} was won by "
                              f"<b style='color:#fff'>{sc['actual_champion']}</b></span>")
            + "</div>", unsafe_allow_html=True)
        st.caption("Scored by **reach**: each round after the first awards a point per team you sent into "
                   "it that really got there, doubling every round, plus a champion bonus. So a bracket "
                   "that goes wrong early still earns for the teams it gets right later.")
        with st.expander(f"📜 What actually happened in {year}"):
            for _rd in wcrp.bracket(year):
                st.markdown(f"<div class='rp-round'>{_rd['label']}</div>", unsafe_allow_html=True)
                _rows = ""
                for _m in _rd["matches"]:
                    _mine = picks.get(_m["mid"])
                    _hit = _mine and _mine == _m["winner"]
                    _mark = ("<span style='color:#4ec98a'>✓</span>" if _hit else
                             "<span style='color:#e0563b'>✗</span>" if _mine else
                             "<span style='color:#7e8ba5'>–</span>")
                    _rows += (f"<div class='wch-mt'><span class='y'>{_mark}</span>"
                              f"<div class='tm r'><span>{_m['home']}</span>"
                              f"<img src='{wcrp.flag(_m['home'])}'></div>"
                              f"<span class='sc'>{_m['winner'] or 'drawn'}</span>"
                              f"<div class='tm'><img src='{wcrp.flag(_m['away'])}'>"
                              f"<span>{_m['away']}</span></div>"
                              f"<span class='st'>{'you: ' + _mine if _mine else ''}</span></div>")
                st.markdown(_rows, unsafe_allow_html=True)

    # ── Share & compare ───────────────────────────────────────────────────────────────────────────
    # Scores stay hidden until you reveal, so the pool lists loaded brackets by name first and only
    # ranks them afterwards — otherwise a friend's total would leak how well the favourites did.
    ui.section("🔗 Share & compare", "send your bracket as a code, paste in a friend's, then rank them")
    _code = wcrp.encode(year, picks)
    _sc1, _sc2 = st.columns([1, 1], gap="medium")
    with _sc1:
        st.markdown(f"**📋 Your {year} code**")
        st.code(_code, language=None)
        st.caption("One bit per tie, so it stays short and can only ever describe teams that really "
                   "were in this bracket. Append `?r=<code>` to the site URL to share a link.")
    with _sc2:
        st.markdown("**➕ Add a friend's bracket**")
        _fn = st.text_input("Their name", key="rp_fname", placeholder="Sebastián")
        _fc = st.text_input("Their code", key="rp_fcode", placeholder="RP1.1986.…")
        _b1, _b2 = st.columns(2)
        if _b1.button("Add", key="rp_add", width="stretch", disabled=not _fc.strip()):
            _dec = wcrp.decode(_fc)
            if not _dec:
                st.error("That code isn't valid.")
            elif _dec[0] != year:
                st.warning(f"That code is for **{_dec[0]}**, not {year}. Switch edition to compare it.")
            else:
                _nm = _fn.strip() or f"Bracket {len(st.session_state.rp_pool) + 2}"
                st.session_state.rp_pool.append({"name": _nm, "year": _dec[0], "picks": _dec[1]})
        if st.session_state.rp_pool and _b2.button("Clear pool", key="rp_clearpool", width="stretch"):
            st.session_state.rp_pool = []

    _pool = [e for e in st.session_state.rp_pool if e["year"] == year]
    if _pool:
        if year in st.session_state.rp_reveal:
            _board = [{"name": "You", "picks": picks}] + [
                {"name": e["name"], "picks": e["picks"]} for e in _pool]
            for _e in _board:
                _s = wcrp.score(year, _e["picks"])
                _e["total"], _e["pct"], _e["champ"] = _s["total"], _s["pct"], _s["champion"]
                _e["ok"] = _s["champion_correct"]
            _board.sort(key=lambda e: -e["total"])
            _rows2 = ""
            for _i, _e in enumerate(_board, 1):
                _me = " gold" if _e["name"] == "You" else ""
                _ch = (f"<span class='nt'>{_e['champ']}{' ✓' if _e['ok'] else ''}</span>"
                       if _e["champ"] else "<span class='nt'>no champion picked</span>")
                _rows2 += (f"<div class='pl-row{_me}'><span class='rk'>{_i}</span>"
                           f"<span class='nm'>{_e['name']}</span>{_ch}"
                           f"<span class='ed'>{_e['pct']}%</span>"
                           f"<span class='gl'>{_e['total']}</span></div>")
            st.markdown(_rows2, unsafe_allow_html=True)
        else:
            st.markdown("\n".join(f"- **{e['name']}** — bracket loaded"
                                   for e in _pool))
            st.caption("Ranked once you reveal your own score, so a friend's total can't tip you off.")


# ── 👤 Players ─────────────────────────────────────────────────────────────────────────────────────
# The goal and squad archives (3,028 goals · 12,213 squad places, 1930–2026) surfaced three ways:
# all-time scoring, an every-edition leading-scorer roll, and a per-player profile. Logic is in
# wcplayers.py. Two honesty constraints run through this whole tab:
#   · APPEARANCES DON'T EXIST in the source (match boxes carry no lineups), so nothing here may say
#     "played" or "caps at this World Cup" — squad rows mean "named in the squad", full stop.
#   · The leading-scorer roll is NOT the official Golden Boot, which used assists and minutes played
#     as tie-breaks in some years. It is "who scored most", and it says so.
WPL_CSS = """<style>
.pl-row { display:flex; align-items:center; gap:10px; padding:6px 11px; border-radius:9px; margin-bottom:5px;
    background:linear-gradient(160deg,#1b2a47,#16223b); border:1px solid rgba(108,172,228,.15); }
.pl-row .rk { color:#7e8ba5; font-weight:800; font-size:.74rem; width:22px; text-align:right; flex:0 0 auto; }
.pl-row img { width:26px; height:17px; object-fit:cover; border-radius:2px; flex:0 0 auto; box-shadow:0 0 0 1px rgba(0,0,0,.3); }
.pl-row .nm { color:#eaf1fb; font-weight:700; font-size:.9rem; flex:1 1 auto; min-width:0;
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.pl-row .nt { color:#8aa0bd; font-size:.76rem; font-weight:600; flex:0 0 auto; }
.pl-row .gl { color:#FFD700; font-weight:800; font-size:.95rem; flex:0 0 auto; min-width:26px; text-align:right; }
.pl-row .ed { color:#7e8ba5; font-size:.7rem; font-weight:700; flex:0 0 auto; }
.pl-row.gold { border-color:rgba(255,215,0,.45); background:linear-gradient(160deg,#2c2a12,#1a2238); }
.pl-gb { display:grid; grid-template-columns:repeat(auto-fill,minmax(215px,1fr)); gap:8px; }
.pl-gb .c { padding:7px 11px; border-radius:9px; background:linear-gradient(160deg,#1b2a47,#16223b);
    border:1px solid rgba(108,172,228,.15); }
.pl-gb .yr { color:#6CACE4; font-weight:800; font-size:.74rem; }
.pl-gb .who { color:#eaf1fb; font-weight:700; font-size:.86rem; display:flex; align-items:center; gap:6px; margin-top:2px; }
.pl-gb .who img { width:22px; height:14px; object-fit:cover; border-radius:2px; }
.pl-gb .n { color:#FFD700; font-weight:800; margin-left:auto; }
.pl-hero { display:flex; align-items:center; gap:15px; padding:13px 18px; border-radius:13px; margin:.2rem 0 .5rem;
    background:linear-gradient(160deg,#1b2a47,#16223b); border:1px solid rgba(108,172,228,.22); }
.pl-hero img.f { width:54px; height:36px; object-fit:cover; border-radius:3px; box-shadow:0 2px 9px rgba(0,0,0,.45); }
.pl-hero .nm { color:#fff; font-size:1.4rem; font-weight:800; line-height:1.1; }
.pl-hero .sub { color:#9fb2cc; font-size:.82rem; font-weight:600; margin-top:2px; }
.pl-hero .big { margin-left:auto; text-align:center; }
.pl-hero .big .v { color:#FFD700; font-size:1.9rem; font-weight:800; line-height:1; }
.pl-hero .big .l { color:#e7c95a; font-size:.62rem; font-weight:800; text-transform:uppercase; letter-spacing:.08em; }
.pl-gline { display:flex; align-items:center; gap:9px; padding:4px 10px; border-radius:8px; margin-bottom:4px; font-size:.82rem;
    background:rgba(108,172,228,.06); border:1px solid rgba(108,172,228,.12); }
.pl-gline .y { color:#6CACE4; font-weight:800; width:38px; flex:0 0 auto; }
.pl-gline .m { color:#FFD700; font-weight:800; width:52px; flex:0 0 auto; }
.pl-gline .o { color:#cfe0f5; flex:1 1 auto; }
.pl-gline .t { color:#7e8ba5; font-size:.72rem; }
.pl-note { color:#8aa0bd; font-size:.78rem; margin:.1rem 0 .5rem 1px; }
/* award rolls and the badges on a player profile */
.aw-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(250px,1fr)); gap:9px; }
.aw-card { padding:9px 12px; border-radius:10px; background:linear-gradient(160deg,#1b2a47,#16223b);
    border:1px solid rgba(108,172,228,.15); }
.aw-card .yr { color:#6CACE4; font-weight:800; font-size:.78rem; margin-bottom:3px; }
.aw-line { display:flex; align-items:center; gap:7px; font-size:.83rem; padding:1px 0; }
.aw-line .ic { width:17px; flex:0 0 auto; }
.aw-line .who { color:#eaf1fb; font-weight:700; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.aw-line .nat { color:#8aa0bd; font-size:.74rem; margin-left:auto; flex:0 0 auto; }
.aw-badge { display:inline-flex; align-items:center; gap:5px; padding:3px 10px; border-radius:8px; margin:0 5px 5px 0;
    font-size:.78rem; font-weight:700; color:#FFD700;
    background:linear-gradient(160deg,#2c2a12,#1a2238); border:1px solid rgba(255,215,0,.4); }
.aw-badge.r2 { color:#dfe6f0; border-color:rgba(192,192,200,.35); background:linear-gradient(160deg,#20242c,#16223b); }
.aw-badge.r3 { color:#e0a86a; border-color:rgba(205,127,50,.35); background:linear-gradient(160deg,#241c10,#16223b); }
</style>"""

with t_players:
    st.markdown(WPL_CSS, unsafe_allow_html=True)
    _prec = wpl.records()
    ui.stats([
        ("Goals", f"{_prec['goals']:,}", "1930 – 2026"),
        ("Scorers", f"{_prec['scorers']:,}", "have scored"),
        ("Squad places", f"{_prec['squad_players']:,}", "players named"),
        ("*Top scorer", _prec["top"][0], f"{_prec['top'][2]} goals"),
    ])
    st.caption("Every World Cup goal with its scorer and minute, plus every named squad. Own goals are "
               "recorded but never counted toward a player's tally. **Appearances aren't in the source** — "
               "the match reports carry no line-ups — so squad figures mean *named in the squad*, not *played*.")

    # Header BEFORE the control: st.columns renders where it is created, so building the column first
    # left the slider stranded above the section title with nothing to explain it.
    ui.section("⚽ All-time top scorers", "own goals excluded · search any of them under Player profile")
    _lim = st.columns([1, 2])[0].select_slider(
        "How many to show", [10, 25, 50, 100], value=25, key="pl_lim")
    _ts = wpl.top_scorers(_lim)
    _rows = ""
    for _i, _r in enumerate(_ts.itertuples(), 1):
        _pen = f" · {_r.penalties} pen" if _r.penalties else ""
        _span = f"{_r.first}" if _r.first == _r.last else f"{_r.first}–{_r.last}"
        _rows += (f"<div class='pl-row{' gold' if _i == 1 else ''}'><span class='rk'>{_i}</span>"
                  f"<img src='{wpl.flag(_r.nation)}'><span class='nm'>{_r.player}</span>"
                  f"<span class='nt'>{_r.nation}</span>"
                  f"<span class='ed'>{_span} · {_r.editions} ed{_pen}</span>"
                  f"<span class='gl'>{_r.goals}</span></div>")
    st.markdown(_rows, unsafe_allow_html=True)

    ui.section("🥇 Leading scorer, every edition", "")
    st.markdown("<div class='pl-note'>Who scored most in each tournament — <b>not</b> the official "
                "Golden Boot, which in some years used assists and minutes played as tie-breaks. "
                "Ties are all listed.</div>", unsafe_allow_html=True)
    _cards = ""
    for _e in reversed(wpl.golden_boots()):
        _who = "".join(
            f"<div class='who'><img src='{wpl.flag(_n)}'><span>{_p}</span>"
            f"<span class='n'>{_g}</span></div>" for _p, _n, _g in _e["players"])
        _cards += f"<div class='c'><div class='yr'>{_e['year']}</div>{_who}</div>"
    st.markdown(f"<div class='pl-gb'>{_cards}</div>", unsafe_allow_html=True)

    ui.section("🔎 Player profile", "search any of the 9,478 players in the archive")
    _q = st.text_input("Search", placeholder="Klose, Pelé, Maradona, Villalba…", key="pl_q",
                       label_visibility="collapsed")
    _hits = wpl.search(_q, limit=60)
    if _q and not _hits:
        st.info(f"No player matching “{_q}”.")
    elif _hits:
        _pick = st.selectbox(f"{len(_hits)} match{'es' if len(_hits) != 1 else ''}",
                             [k for _d, k in _hits],
                             format_func=lambda k: dict((k2, d2) for d2, k2 in _hits).get(k, k),
                             key="pl_pick")
        _p = wpl.profile(_pick)
        _dob = _p["dob"].strftime("%d %b %Y") if pd.notna(_p["dob"]) else "date of birth unknown"
        _pos = " · ".join(wpl.POS_NAME.get(x, x) for x in _p["positions"] if x)
        st.markdown(
            f"<div class='pl-hero'><img class='f' src='{wpl.flag(_p['nation'])}'>"
            f"<div><div class='nm'>{_p['player']}</div>"
            f"<div class='sub'>{_p['nation']}{' · ' + _pos if _pos else ''} · {_dob}</div></div>"
            f"<div class='big'><div class='v'>{_p['goals']}</div>"
            f"<div class='l'>World Cup goal{'s' if _p['goals'] != 1 else ''}</div></div></div>",
            unsafe_allow_html=True)

        _bits = []
        if _p["editions_squad"]:
            _bits.append(f"**Squads:** {', '.join(str(y) for y in _p['editions_squad'])}")
        if _p["captain_years"]:
            _bits.append(f"**Captain:** {', '.join(str(y) for y in _p['captain_years'])}")
        if _p["penalties"]:
            _bits.append(f"**Penalties:** {_p['penalties']}")
        if _p["own_goals"]:
            _bits.append(f"**Own goals:** {_p['own_goals']}")
        if _p["age_at_first_goal"]:
            _bits.append(f"**Age at first goal:** {_p['age_at_first_goal']:.1f}")
        if _p["clubs"]:
            _bits.append(f"**Clubs:** {', '.join(_p['clubs'])}")
        if _bits:
            st.markdown(" &nbsp;·&nbsp; ".join(_bits))

        _paw = wpl.player_awards(_pick)
        if _paw:
            _bd = "".join(
                f"<span class='aw-badge{'' if a['rank'] == 1 else ' r' + str(min(a['rank'], 3))}'>"
                f"{wpl.AWARD_ICON.get(a['award'], '🏅')} {a['award']} {a['year']}"
                + ("" if a["rank"] == 1 else f" · {a['rank']}{'nd' if a['rank'] == 2 else 'rd' if a['rank'] == 3 else 'th'}")
                + "</span>" for a in _paw)
            st.markdown(_bd, unsafe_allow_html=True)

        if _p["goals"]:
            _gl = ""
            for _g in _p["goal_rows"].itertuples():
                _mn = f"{int(_g.minute)}" + (f"+{int(_g.minute_extra)}" if pd.notna(_g.minute_extra) else "")
                _tag = " (pen)" if _g.penalty else ""
                _opp = wpl.nations().get(_g.opponent_code, _g.opponent_code)
                _gl += (f"<div class='pl-gline'><span class='y'>{_g.year}</span>"
                        f"<span class='m'>{_mn}'{_tag}</span>"
                        f"<span class='o'>v {_opp}</span>"
                        f"<span class='t'>{_STAGE.get(_g.stage, _g.stage)}</span></div>")
            with st.expander(f"⚽ All {_p['goals']} goal{'s' if _p['goals'] != 1 else ''}", expanded=True):
                st.markdown(_gl, unsafe_allow_html=True)
        elif _p["editions_squad"]:
            st.caption("Named in a squad but never scored. Whether he took the field at all isn't "
                       "recorded in this data.")

    ui.section("🏅 Awards, every edition", "the official individual awards, as recorded")
    st.markdown("<div class='pl-note'>Distinct from the leading-scorer roll above, which is computed "
                "from the goals. The <b>Golden Ball</b> dates from 1982, the <b>Golden Glove</b> from "
                "1994, and the <b>Golden Boot</b> only became an award in 1982 — earlier top scorers "
                "were recognised retroactively, so the pre-1982 tournaments carry few awards or none. "
                "1978's entry is the <b>journalists' vote</b> FIFA recognises in place of a Golden "
                "Ball, marked 🗳️ and not an official award.</div>", unsafe_allow_html=True)
    _acards = ""
    for _y in reversed(wpl.award_years()):
        _lines = ""
        for _a in wpl.edition_awards(_y).itertuples():
            _who = _a.nation_name if _a.is_team else _a.player_display
            _nat = "" if _a.is_team else f"<span class='nat'>{_a.nation_name}</span>"
            _ttl = wpl.AWARD_NOTE.get(_a.award, _a.award)
            _lines += (f"<div class='aw-line' title='{_ttl}'><span class='ic'>"
                       f"{wpl.AWARD_ICON.get(_a.award, '🏅')}</span>"
                       f"<span class='who'>{_who}</span>{_nat}</div>")
        _acards += f"<div class='aw-card'><div class='yr'>{_y}</div>{_lines}</div>"
    st.markdown(f"<div class='aw-grid'>{_acards}</div>", unsafe_allow_html=True)
    _gbl = wpl.award_leaders("Golden Ball", 3)
    if not _gbl.empty and int(_gbl.iloc[0]["wins"]) > 1:
        _r = _gbl.iloc[0]
        st.caption(f"Only **{_r['player']}** has won the Golden Ball more than once "
                   f"({', '.join(str(y) for y in _r['years'])}).")

    ui.section("🎯 Penalty shootouts", "39 shootouts since 1982 — who wins them, and who takes them")
    _shc = wpl.shootout_coverage()
    _s1, _s2 = st.columns([1, 1], gap="medium")
    with _s1:
        st.markdown("**By nation**")
        _r = ""
        for _i, _x in enumerate(wpl.shootout_records(10).itertuples(), 1):
            _perfect = " 💯" if _x.lost == 0 and _x.won > 1 else ""
            _r += (f"<div class='pl-row{' gold' if _i == 1 else ''}'><span class='rk'>{_i}</span>"
                   f"<img src='{wch.flag_url(_x.nation)}'>"
                   f"<span class='nm'>{_x.nation}{_perfect}</span>"
                   f"<span class='ed'>{_x.won}W {_x.lost}L</span>"
                   f"<span class='gl'>{_x.played}</span></div>")
        st.markdown(_r, unsafe_allow_html=True)
        st.caption("Outcomes cover **all 39** shootouts, taken from the match archive.")
    with _s2:
        # Nobody has taken more than two shootout kicks, so "most taken" would imply a
        # ranking that does not exist. Name what the list actually is.
        st.markdown("**Players who took kicks in two different shootouts**")
        _r = ""
        for _x in wpl.shootout_takers(10).itertuples():
            _miss = (f"<span style='color:#e0563b'>{_x.missed} missed</span>" if _x.missed
                     else "<span style='color:#4ec98a'>all scored</span>")
            _r += (f"<div class='pl-row'><span class='nm'>{_x.player}</span>"
                   f"<span class='nt'>{_x.nation}</span><span class='ed'>{_miss}</span>"
                   f"<span class='gl'>{_x.taken}</span></div>")
        st.markdown(_r, unsafe_allow_html=True)
        st.caption(f"No one has taken kicks in more than two. Individual kicks are recorded for "
                   f"**{_shc['with_takers']} of {_shc['total']}** shootouts — {_shc['kicks']} kicks, "
                   f"**{_shc['rate']:.0%}** converted; the other "
                   f"{_shc['total'] - _shc['with_takers']} have an outcome but no taker list.")
    with st.expander(f"🎯 All {_shc['total']} shootouts"):
        _r = ""
        for _x in wpl.shootouts():
            _r += (f"<div class='wch-mt'><span class='y'>{_x['year']}</span>"
                   f"<div class='tm r'><span>{_x['winner']}</span>"
                   f"<img src='{wch.flag_url(_x['winner'])}'></div>"
                   f"<span class='sc'>{_x['score']}</span>"
                   f"<div class='tm'><img src='{wch.flag_url(_x['loser'])}'>"
                   f"<span>{_x['loser']}</span></div>"
                   f"<span class='st'>{_STAGE.get(_x['stage'], _x['stage'])} · drew {_x['drawn']}</span>"
                   f"</div>")
        st.markdown(_r, unsafe_allow_html=True)

    ui.section("📊 Records", "computed from the archive, not hardcoded")
    _y, _o = _prec["youngest_scorer"], _prec["oldest_scorer"]
    _ys, _os = _prec["youngest_squad"], _prec["oldest_squad"]
    _bh = _prec["best_haul"]
    ui.features([
        {"icon": "🎯", "title": "Most goals in a match",
         "body": (f"<b>{_bh[0]}</b> scored <b>{_bh[1]}</b> v {_bh[2]} · {_bh[3]}" if _bh else "—"),
         "gold": True},
        {"icon": "🌍", "title": "Most tournaments scored in",
         "body": f"<b>{_prec['most_editions'][0]}</b> — {_prec['most_editions'][2]} editions"},
        {"icon": "🐣", "title": "Youngest scorer",
         "body": (f"<b>{_y[0]}</b> at <b>{_y[2]}</b> · {_y[1]} {_y[3]}" if _y else "—")},
        {"icon": "🧓", "title": "Oldest scorer",
         "body": (f"<b>{_o[0]}</b> at <b>{_o[2]}</b> · {_o[1]} {_o[3]}" if _o else "—")},
        {"icon": "📋", "title": "Youngest named in a squad",
         "body": (f"<b>{_ys[0]}</b> at <b>{_ys[2]}</b> · {_ys[1]} {_ys[3]}" if _ys else "—")},
        {"icon": "📋", "title": "Oldest named in a squad",
         "body": (f"<b>{_os[0]}</b> at <b>{_os[2]}</b> · {_os[1]} {_os[3]}" if _os else "—")},
        {"icon": "🥅", "title": "Penalties & own goals",
         "body": f"<b>{_prec['penalties']}</b> pens · <b>{_prec['own_goals']}</b> own goals"},
        {"icon": "⏱️", "title": "Scored in the 1st minute",
         "body": f"<b>{_prec['first_minute_goals']}</b> goals"},
    ])
    st.caption("Youngest/oldest **scorer** uses the goal's own date; youngest/oldest **named in a "
               "squad** is measured at mid-tournament. Both cover only players whose date of birth "
               "is in the source (54 squad places have none).")

    ui.section("⏱️ When goals are scored", "all 2,960 scoring goals by 15-minute band")
    _mb = wpl.minute_bands()
    _fig = go.Figure(go.Bar(x=_mb["band"], y=_mb["goals"], marker_color=SKY,
                            hovertemplate="%{x} min<br>%{y} goals<extra></extra>"))
    _fig.update_layout(template=PLOTLY_TMPL, height=270, showlegend=False,
                       xaxis_title="minute", yaxis_title="goals")
    st.plotly_chart(_fig, width="stretch", key="pl_min")
    st.caption("Stoppage-time goals count in the band of their base minute — a 90+8' goal is a 76–90 "
               "goal. The 91–120 bands are extra time only, which few matches reach.")

# ── 🏳️ Nations ──────────────────────────────────────────────────────────────────────────────────────
# One country's whole World Cup story on a page: honours, an all-time record, every edition it entered
# with how far it got, its leading scorers, and every match it has played. The archive tab's
# head-to-head compares TWO nations; this is the single-nation view that was missing.
#
# Historical sides fold in (asking for Germany covers West Germany, DR Congo covers Zaire) exactly as
# wchistory.all_time_table() aggregates them, and the page says which names it merged so a reader
# isn't left wondering where West Germany went.
WNAT_CSS = """<style>
.nt-hero { display:flex; align-items:center; gap:16px; padding:14px 19px; border-radius:13px; margin:.2rem 0 .6rem;
    background:linear-gradient(160deg,#1b2a47,#16223b); border:1px solid rgba(108,172,228,.22); }
.nt-hero img { width:62px; height:41px; object-fit:cover; border-radius:3px; box-shadow:0 2px 10px rgba(0,0,0,.5); }
.nt-hero .nm { color:#fff; font-size:1.5rem; font-weight:800; line-height:1.1; }
.nt-hero .sub { color:#9fb2cc; font-size:.83rem; font-weight:600; margin-top:3px; }
.nt-hero .tro { margin-left:auto; text-align:right; }
.nt-hero .tro .t { color:#FFD700; font-size:1.05rem; font-weight:800; letter-spacing:1px; }
.nt-hero .tro .l { color:#e7c95a; font-size:.62rem; font-weight:800; text-transform:uppercase; letter-spacing:.08em; }
.nt-ed { display:flex; align-items:center; gap:10px; padding:6px 12px; border-radius:9px; margin-bottom:5px; font-size:.85rem;
    background:linear-gradient(160deg,#1b2a47,#16223b); border:1px solid rgba(108,172,228,.14); }
.nt-ed .y { color:#6CACE4; font-weight:800; width:44px; flex:0 0 auto; }
.nt-ed .fin { font-weight:700; flex:1 1 auto; color:#cfe0f5; }
.nt-ed .rec { color:#8aa0bd; font-size:.78rem; font-weight:600; flex:0 0 auto; }
.nt-ed .gd { color:#7e8ba5; font-size:.75rem; flex:0 0 auto; width:64px; text-align:right; }
.nt-ed.win { border-color:rgba(255,215,0,.5); background:linear-gradient(160deg,#2c2a12,#1a2238); }
.nt-ed.win .fin { color:#FFD700; }
.nt-ed.run { border-color:rgba(192,192,200,.42); } .nt-ed.run .fin { color:#dfe6f0; }
.nt-ed.brz { border-color:rgba(205,127,50,.42); } .nt-ed.brz .fin { color:#e0a86a; }
.nt-names { color:#8aa0bd; font-size:.78rem; margin:.1rem 0 .5rem 1px; }
</style>"""

# Finish → card accent. Only the podium gets colour; everything else stays neutral so the honours
# actually stand out on a nation like Brazil with 23 rows.
_NT_CLS = {"Champions": " win", "Runners-up": " run", "Third place": " brz"}

with t_nations:
    st.markdown(WNAT_CSS, unsafe_allow_html=True)
    ui.section("🏳️ Nation profile", "every edition a country entered, how far it got, and who scored")
    _noms = wch.nations()
    _nsel = st.columns([2, 1])[0].selectbox(
        "Nation", _noms, index=_noms.index("Brazil") if "Brazil" in _noms else 0, key="nt_sel")
    _s = wch.nation_summary(_nsel)
    _hist = wch.nation_history(_nsel)

    _tro = ("<div class='tro'><div class='t'>" + ("🏆" * _s["titles"]) + "</div>"
            f"<div class='l'>{_s['titles']} title{'s' if _s['titles'] != 1 else ''}</div></div>"
            if _s["titles"] else "")
    _best = f"{_s['best']}" + (f" ({', '.join(str(y) for y in _s['best_years'][:4])})"
                               if _s["best_years"] and _s["best"] != "Champions" else "")
    st.markdown(
        f"<div class='nt-hero'><img src='{wch.flag_url(_nsel, 80)}' alt=''>"
        f"<div><div class='nm'>{_nsel}</div><div class='sub'>"
        f"{_s['editions']} edition{'s' if _s['editions'] != 1 else ''} · {_s['first']}–{_s['last']}"
        f" &nbsp;·&nbsp; best: <b>{_best}</b>"
        f" &nbsp;·&nbsp; {_s['finals']} final{'s' if _s['finals'] != 1 else ''} reached</div></div>"
        f"{_tro}</div>", unsafe_allow_html=True)
    if _s["names"]:
        st.markdown(f"<div class='nt-names'>Includes matches played as "
                    f"<b>{', '.join(_s['names'])}</b> — the same football association under an earlier "
                    f"name, folded together here and in the all-time table.</div>",
                    unsafe_allow_html=True)

    ui.stats([
        ("Played", str(_s["P"]), f"{_s['first']}–{_s['last']}"),
        ("Won", str(_s["W"]), f"{100 * _s['W'] / _s['P']:.0f}% of matches" if _s["P"] else ""),
        ("Drawn / Lost", f"{_s['D']} / {_s['L']}", "shootouts count as draws"),
        ("*Goals", f"{_s['GF']}:{_s['GA']}", f"{_s['GF'] - _s['GA']:+d} difference"),
    ])

    _sh = wpl.nation_shootouts(_nsel)
    if _sh["played"]:
        _verdict = ("a perfect record" if _sh["lost"] == 0 else
                    "never won one" if _sh["won"] == 0 else
                    f"{_sh['won']} of {_sh['played']}")
        st.markdown(f"🎯 **Penalty shootouts:** won **{_sh['won']}**, lost **{_sh['lost']}** "
                    f"&nbsp;·&nbsp; {_verdict}")

    _c1, _c2 = st.columns([1.15, 1], gap="medium")
    with _c1:
        st.markdown("**Every edition**")
        _rows = ""
        for _e in reversed(_hist):
            _rows += (f"<div class='nt-ed{_NT_CLS.get(_e['finish'], '')}'>"
                      f"<span class='y'>{_e['year']}</span>"
                      f"<span class='fin'>{_e['finish']}</span>"
                      f"<span class='rec'>{_e['W']}W {_e['D']}D {_e['L']}L</span>"
                      f"<span class='gd'>{_e['GF']}:{_e['GA']}</span></div>")
        st.markdown(_rows, unsafe_allow_html=True)
        _missed = len(wch.years()) - _s["editions"]
        if _missed:
            st.caption(f"Absent from {_missed} of the {len(wch.years())} tournaments.")
    with _c2:
        st.markdown("**Leading scorers**")
        _ns = wpl.nation_scorers(_nsel, 12)
        if _ns.empty:
            st.caption("No goals recorded for this nation.")
        else:
            _sr = ""
            for _i, _r in enumerate(_ns.itertuples(), 1):
                _span = f"{_r.first}" if _r.first == _r.last else f"{_r.first}–{_r.last}"
                _sr += (f"<div class='pl-row'><span class='rk'>{_i}</span>"
                        f"<span class='nm'>{_r.player}</span>"
                        f"<span class='ed'>{_span}</span>"
                        f"<span class='gl'>{_r.goals}</span></div>")
            st.markdown(_sr, unsafe_allow_html=True)
        _sq = wpl.nation_squad_players(_nsel, 6)
        if not _sq.empty:
            st.markdown("**Most squads named in**")
            st.caption("Squads named in — not appearances, which the source doesn't record.")
            _qr = ""
            for _r in _sq.itertuples():
                _span = f"{_r.first}" if _r.first == _r.last else f"{_r.first}–{_r.last}"
                _qr += (f"<div class='pl-row'><span class='nm'>{_r.player}</span>"
                        f"<span class='ed'>{_span}</span>"
                        f"<span class='gl'>{_r.squads}</span></div>")
            st.markdown(_qr, unsafe_allow_html=True)

    _nm = wch.nation_matches(_nsel)
    with st.expander(f"⚽ All {len(_nm)} matches"):
        _mr = ""
        for _x in _nm.itertuples():
            _pen = (f" <span style='color:#9fb2cc;font-size:.72rem'>({int(_x.pens_home)}-"
                    f"{int(_x.pens_away)}p)</span>" if pd.notna(_x.pens_home) else "")
            _mr += (f"<div class='wch-mt'><span class='y'>{int(_x.year)}</span>"
                    f"<div class='tm r'><span>{_x.home}</span>"
                    f"<img src='{wch.flag_url(_x.home)}'></div>"
                    f"<span class='sc'>{_x.home_score}–{_x.away_score}{_pen}</span>"
                    f"<div class='tm'><img src='{wch.flag_url(_x.away)}'><span>{_x.away}</span></div>"
                    f"<span class='st'>{_STAGE.get(_x.stage, _x.stage)}</span></div>")
        st.markdown(_mr, unsafe_allow_html=True)

# ── 🏟️ Venues ──────────────────────────────────────────────────────────────────────────────────────
# Was a 2026-only tab. Every match row 1930–2026 carries a venue and city, so it now covers all 23
# editions — 3 stadiums in Uruguay 1930, 20 across Korea/Japan 2002. Capacity and photographs exist
# only for 2026 (data/wc2026_venues.csv), so they enrich that edition and are simply absent elsewhere
# rather than blocking the other 22.
with t_venues:
    st.markdown(VENUE_CSS, unsafe_allow_html=True)
    ui.section("🏟️ Venues", "every stadium used at a World Cup, and what it hosted")
    _vy = st.columns([1, 2])[0].selectbox("Edition", list(reversed(wch.years())), key="ven_year",
                                          format_func=lambda y: f"{y} · {_HOSTS.get(y, '')}")
    _vens = wch.edition_venues(_vy)
    _cap = {}                                     # stadium → capacity, 2026 only
    if _vy == 2026:
        _cap = {r.stadium: int(r.capacity) for r in wc.venues().itertuples()}
    # Average crowd per stadium for this edition, from the match metadata.
    _vm = wpl.matchmeta()
    _vm = _vm[(_vm["year"] == _vy) & _vm["attendance"].notna()]
    _vavg = _vm.groupby("stadium")["attendance"].mean().to_dict()
    # The metadata's stadium string is "Name, City"; the archive's venue is just the name.
    _vavg = {k.split(",")[0].strip(): v for k, v in _vavg.items()}
    _tot = sum(v["matches"] for v in _vens)
    ui.stats([
        ("Stadiums", str(len(_vens)), f"{_vy}"),
        ("Matches", str(_tot), "hosted"),
        ("Busiest", _vens[0]["venue"][:22] if _vens else "—",
         f"{_vens[0]['matches']} matches" if _vens else ""),
        ("*Cities", str(len({v["city"] for v in _vens if v["city"]})), "host cities"),
    ])
    _rows = ""
    for _v in _vens:
        _hosted = ""
        if "final" in _v["finals"]:
            _hosted = "<span style='color:#FFD700;font-weight:800'>🏆 Final</span>"
        elif "third-place" in _v["finals"]:
            _hosted = "<span style='color:#e0a86a'>🥉 Third place</span>"
        elif "semi-final" in _v["finals"]:
            _hosted = "<span style='color:#9fc4ec'>Semi-final</span>"
        _c = f" · {_cap[_v['venue']]:,} seats" if _v["venue"] in _cap else ""
        _avg = _vavg.get(_v["venue"])
        _c += f" · avg crowd {_avg:,.0f}" if _avg else ""
        _rows += (f"<div class='ven-head'><div><div class='nm'>{_v['venue']}</div>"
                  f"<div class='loc'>{_v['city']}{_c}</div></div>"
                  f"<div class='meta'><b>{_v['matches']}</b> match"
                  f"{'es' if _v['matches'] != 1 else ''} &nbsp; {_hosted}</div></div>")
    st.markdown(_rows, unsafe_allow_html=True)

    # Stadiums that have hosted more than one World Cup — only visible once every edition is in scope.
    _multi = {}
    for _y in wch.years():
        for _v in wch.edition_venues(_y):
            _multi.setdefault(_v["venue"], []).append(_y)
    _rep = sorted(((len(ys), v, ys) for v, ys in _multi.items() if len(ys) > 1), reverse=True)
    ui.section("♻️ Stadiums used at more than one World Cup", f"{len(_multi)} stadiums have been used in all")
    st.markdown("".join(
        f"<div class='pl-row'><span class='nm'>{v}</span>"
        f"<span class='ed'>{', '.join(str(y) for y in ys)}</span>"
        f"<span class='gl'>{n}</span></div>" for n, v, ys in _rep[:20]), unsafe_allow_html=True)

# ── 👥 Squads ──────────────────────────────────────────────────────────────────────────────────────
# Was a 2026-only "Teams" tab. build/players.py now provides squads for ALL 23 editions (12,213 named
# places), so any nation in any tournament can be listed. Ages are shown as at mid-tournament, and the
# tab says these are NAMED squads — the source has no line-ups, so it cannot say who played.
with t_squads:
    ui.section("👥 Squads", "any nation's named squad, from 1930 to 2026")
    _sc = st.columns([1, 1.4])
    _sy = _sc[0].selectbox("Edition", list(reversed(wpl.squad_years())), key="sq_year",
                           format_func=lambda y: f"{y} · {_HOSTS.get(y, '')}")
    _snoms = wpl.squad_nations(_sy)
    _sn = _sc[1].selectbox("Nation", _snoms, key="sq_nation")
    _sq = wpl.edition_squad(_sy, _sn)
    _ages = wpl.squad_ages(_sy, _sn)
    ui.stats([
        ("Players", str(len(_sq)), f"{_sn} {_sy}"),
        ("Average age", f"{_ages['mean']:.1f}" if _ages["mean"] else "—", "at mid-tournament"),
        ("Youngest", _ages["young"] or "—", f"{_ages['young_age']:.1f}" if _ages["young_age"] else ""),
        ("*Oldest", _ages["old"] or "—", f"{_ages['old_age']:.1f}" if _ages["old_age"] else ""),
    ])
    _gsc = wpl.nation_edition_scorers(_sy, _sn)
    _by_pos = {}
    for _r in _sq.itertuples():
        _by_pos.setdefault(_r.pos or "—", []).append(_r)
    _cols = st.columns(4)
    for _i, _pos in enumerate(["GK", "DF", "MF", "FW"]):
        with _cols[_i]:
            st.markdown(f"**{wpl.POS_NAME.get(_pos, _pos)}s**")
            _cards = ""
            for _r in _by_pos.get(_pos, []):
                _no = f"{int(_r.shirt_no)}. " if pd.notna(_r.shirt_no) else ""
                _cap_ = " <span style='color:#FFD700'>(c)</span>" if _r.captain else ""
                _g = _gsc.get(_r.player_key, 0)
                _gtag = (f" <span style='color:#FFD700;font-weight:800'>{_g}⚽</span>" if _g else "")
                _cards += (f"<div class='wtcard'><div><div class='nm'>{_no}"
                           f"{wpl.short_name(_r.player_key)}{_cap_}{_gtag}</div>"
                           f"<div class='mt'>{_r.club or '—'}</div></div></div>")
            st.markdown(_cards or "<div class='mt'>—</div>", unsafe_allow_html=True)
    st.caption("These are **named squads**, not appearances — the match reports carry no line-ups, so "
               "who actually took the field isn't in this data. ⚽ marks goals scored in this "
               "tournament; (c) marks the captain. Ages are at mid-tournament.")

# ── 🎟️ Crowds & officials ───────────────────────────────────────────────────────────────────────────
# Attendance and referee were sitting in every match box that build/players.py already fetched and
# parsed; it simply discarded them. wc_matchmeta.csv keeps them now — 1,068 matches, exactly the
# archive's count with no per-year mismatch, and 100% coverage on both fields.
with t_crowds:
    ui.section("🎟️ Crowds & officials", "who watched, and who refereed — every match, 1930–2026")
    _mm = wpl.matchmeta()
    _att = _mm.dropna(subset=["attendance"])
    _abe = wpl.attendance_by_edition()
    _big = wpl.crowds(1).iloc[0]
    _refs = wpl.referees()
    ui.stats([
        ("Total attendance", f"{int(_att['attendance'].sum()) / 1e6:.1f}M", "across 23 editions"),
        ("Average crowd", f"{int(_att['attendance'].mean()):,}", "per match, all-time"),
        ("Biggest", f"{int(_big.attendance):,}", f"{_big.year} · {_big.stadium.split(',')[0]}"),
        ("*Most matches refereed", _refs.iloc[0]["referee"], f"{int(_refs.iloc[0]['matches'])} matches"),
    ])
    st.caption("Attendance is as the source records it. The 1950 decider's **173,850** is the official "
               "figure; contemporary estimates of that crowd run to around 200,000, which would make "
               "it the largest ever to watch a football match.")

    ui.section("📈 Average crowd by edition", "the clearest measure of how the tournament grew")
    _fig2 = go.Figure(go.Bar(x=_abe["year"].astype(str), y=_abe["mean"], marker_color=SKY,
                             customdata=_abe[["matches", "total"]],
                             hovertemplate="%{x}<br>%{y:,.0f} average<br>"
                                           "%{customdata[0]} matches · %{customdata[1]:,.0f} total"
                                           "<extra></extra>"))
    _fig2.update_layout(template=PLOTLY_TMPL, height=280, showlegend=False,
                        xaxis_title="edition", yaxis_title="average crowd")
    st.plotly_chart(_fig2, width="stretch", key="cr_att")

    _cc1, _cc2 = st.columns(2, gap="medium")
    with _cc1:
        st.markdown("**🥇 Biggest crowds**")
        _r = ""
        for _i, _x in enumerate(wpl.crowds(12).itertuples(), 1):
            _r += (f"<div class='pl-row{' gold' if _i == 1 else ''}'><span class='rk'>{_i}</span>"
                   f"<span class='nm'>{_x.team1_code_name} {_x.score1}–{_x.score2} "
                   f"{_x.team2_code_name}</span>"
                   f"<span class='ed'>{_x.year}</span>"
                   f"<span class='gl'>{int(_x.attendance):,}</span></div>")
        st.markdown(_r, unsafe_allow_html=True)
    with _cc2:
        st.markdown("**🔻 Smallest crowds**")
        _r = ""
        for _i, _x in enumerate(wpl.crowds(12, biggest=False).itertuples(), 1):
            _r += (f"<div class='pl-row'><span class='rk'>{_i}</span>"
                   f"<span class='nm'>{_x.team1_code_name} {_x.score1}–{_x.score2} "
                   f"{_x.team2_code_name}</span>"
                   f"<span class='ed'>{_x.year}</span>"
                   f"<span class='gl'>{int(_x.attendance):,}</span></div>")
        st.markdown(_r, unsafe_allow_html=True)

    ui.section("🧑‍⚖️ Referees", "by matches taken charge of · 'best' is the furthest round reached")
    _rc1, _rc2 = st.columns([1.5, 1], gap="medium")
    with _rc1:
        _r = ""
        for _i, _x in enumerate(_refs.head(15).itertuples(), 1):
            _span = (f"{_x.years[0]}" if len(_x.years) == 1
                     else f"{_x.years[0]}–{_x.years[-1]}")
            _fl = wch.flag_url(_x.nation) if _x.nation else ""
            _img = f"<img src='{_fl}'>" if _fl else ""
            _r += (f"<div class='pl-row{' gold' if _i == 1 else ''}'><span class='rk'>{_i}</span>"
                   f"{_img}<span class='nm'>{_x.referee}</span>"
                   f"<span class='nt'>{_STAGE.get(_x.best, _x.best)}</span>"
                   f"<span class='ed'>{_span}</span>"
                   f"<span class='gl'>{int(_x.matches)}</span></div>")
        st.markdown(_r, unsafe_allow_html=True)
    with _rc2:
        st.markdown("**Which countries supply referees**")
        _r = ""
        for _x in wpl.referee_nations(12).itertuples():
            _fl = wch.flag_url(_x.referee_nation)
            _img = f"<img src='{_fl}'>" if _fl else ""
            _r += (f"<div class='pl-row'>{_img}<span class='nm'>{_x.referee_nation}</span>"
                   f"<span class='ed'>{int(_x.officials)} officials</span>"
                   f"<span class='gl'>{int(_x.matches)}</span></div>")
        st.markdown(_r, unsafe_allow_html=True)
    st.caption("Referee nations come from the source's own parenthetical, so an official listed without "
               "a country is counted in the table above but not in this breakdown.")
