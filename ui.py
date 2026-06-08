"""Small UI component kit for the app — design tokens + HTML/CSS helpers.

The idea: write the design-heavy, *static* parts of a page as clean, self-contained HTML/CSS that we
fully control, instead of reverse-engineering Streamlit's internal DOM. Each helper returns nothing and
renders via st.markdown(..., unsafe_allow_html=True). Call ui.inject() once per run to load the CSS.
"""
import streamlit as st

# ── Design tokens + components ──────────────────────────────────────────────────────────────────
CSS = """<style>
:root{
  --sky:#6CACE4; --sky-d:#3a78b5; --gold:#FFD700; --ink:#eaf1fb; --muted:#90a4c2;
  --card:#16223b; --card-2:#1b2a47; --line:rgba(108,172,228,.16); --line-2:rgba(108,172,228,.34);
  --r:14px;
}
/* stat row -------------------------------------------------------------------------------------- */
.ui-stats{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin:.1rem 0 1rem; }
.ui-stat{ position:relative; overflow:hidden; background:linear-gradient(150deg,var(--card-2),var(--card));
  border:1px solid var(--line); border-radius:var(--r); padding:14px 16px 13px; box-shadow:0 2px 12px rgba(0,0,0,.22); }
.ui-stat::before{ content:''; position:absolute; left:0; top:0; bottom:0; width:3px;
  background:linear-gradient(var(--sky),var(--sky-d)); }
.ui-stat.gold::before{ background:linear-gradient(var(--gold),#b9930b); }
.ui-stat .lbl{ color:var(--muted); font-size:.72rem; font-weight:700; text-transform:uppercase; letter-spacing:.06em; }
.ui-stat .val{ color:#fff; font-size:1.7rem; font-weight:800; line-height:1.08; margin-top:4px; letter-spacing:-.6px; }
.ui-stat .sub{ color:var(--sky); font-size:.76rem; font-weight:600; margin-top:3px; }
.ui-stat.gold .sub{ color:var(--gold); }
/* feature grid ---------------------------------------------------------------------------------- */
.ui-grid{ display:grid; grid-template-columns:repeat(auto-fit,minmax(232px,1fr)); gap:14px; margin:.5rem 0 1rem; }
.ui-feat{ display:block; text-decoration:none; background:linear-gradient(160deg,var(--card-2),var(--card));
  border:1px solid var(--line); border-radius:var(--r); padding:15px 16px 14px; box-shadow:0 2px 12px rgba(0,0,0,.22);
  transition:transform .14s ease, border-color .14s ease, box-shadow .14s ease; }
.ui-feat:hover{ transform:translateY(-3px); border-color:var(--line-2); box-shadow:0 11px 26px rgba(0,0,0,.36); }
.ui-feat .ic{ font-size:1.5rem; line-height:1; }
.ui-feat .ti{ color:var(--ink); font-weight:700; font-size:1.02rem; margin:9px 0 4px; letter-spacing:-.2px; }
.ui-feat .bd{ color:#aebdd6; font-size:.86rem; line-height:1.42; }
.ui-feat .bd b{ color:var(--sky); font-weight:700; }
.ui-feat.gold{ border-color:rgba(255,215,0,.40); background:linear-gradient(160deg,#26240e,#161f30); }
.ui-feat.gold:hover{ border-color:var(--gold); box-shadow:0 11px 26px rgba(255,215,0,.20); }
.ui-feat.gold .ti{ color:var(--gold); }
.ui-feat.gold .bd b{ color:var(--gold); }
/* photo cards (e.g. stadiums) ------------------------------------------------------------------- */
.ui-pgrid{ display:grid; grid-template-columns:repeat(auto-fit,minmax(212px,1fr)); gap:14px; margin:.5rem 0 1rem; }
.ui-pcard{ overflow:hidden; border:1px solid var(--line); border-radius:var(--r); background:var(--card);
  box-shadow:0 2px 12px rgba(0,0,0,.22); transition:transform .14s ease, border-color .14s ease, box-shadow .14s ease; }
.ui-pcard:hover{ transform:translateY(-3px); border-color:var(--line-2); box-shadow:0 11px 26px rgba(0,0,0,.36); }
.ui-pcard .ph{ position:relative; aspect-ratio:16/10; background-size:cover; background-position:center; }
.ui-pcard .ph::after{ content:''; position:absolute; inset:0;
  background:linear-gradient(to top, rgba(11,19,32,.88), rgba(11,19,32,0) 58%); }
.ui-pcard .cap{ position:absolute; left:11px; right:11px; bottom:7px; z-index:1; color:#fff;
  font-weight:700; font-size:.92rem; line-height:1.2; text-shadow:0 1px 5px rgba(0,0,0,.7); }
.ui-pcard .bd{ display:flex; align-items:baseline; justify-content:space-between; gap:8px; padding:8px 12px 10px; }
.ui-pcard .meta{ color:var(--muted); font-size:.8rem; }
.ui-pcard .badge{ color:var(--sky); font-weight:700; font-size:.82rem; white-space:nowrap; }
/* callout / note -------------------------------------------------------------------------------- */
.ui-note{ background:linear-gradient(160deg,var(--card-2),var(--card)); border:1px solid var(--line);
  border-left:3px solid var(--sky); border-radius:var(--r); padding:12px 15px; box-shadow:0 2px 12px rgba(0,0,0,.2); }
.ui-note .nt-t{ color:var(--ink); font-weight:700; font-size:.96rem; margin-bottom:3px; }
.ui-note .nt-b{ color:#aebdd6; font-size:.86rem; line-height:1.45; }
.ui-note .nt-b b{ color:var(--sky); }
/* section header -------------------------------------------------------------------------------- */
.ui-sec{ display:flex; align-items:baseline; gap:10px; margin:1.2rem 0 .2rem; flex-wrap:wrap; }
.ui-sec h3{ color:var(--ink); font-weight:800; font-size:1.2rem; margin:0; letter-spacing:-.3px; }
.ui-sec .h-sub{ color:var(--muted); font-size:.92rem; font-style:italic; }
/* medal / champion cards (high-contrast alt to a dim st.dataframe for highlight rows) ----------- */
.md-grid{ display:grid; grid-template-columns:repeat(auto-fit,minmax(184px,1fr)); gap:12px; margin:.4rem 0 1rem; }
.md-card{ background:linear-gradient(160deg,var(--card-2),var(--card)); border:1px solid var(--line);
  border-radius:var(--r); padding:11px 14px 12px; box-shadow:0 2px 12px rgba(0,0,0,.22); }
.md-tag{ color:var(--muted); font-size:.74rem; font-weight:800; text-transform:uppercase; letter-spacing:.07em; }
.md-body{ display:flex; align-items:center; gap:10px; margin:7px 0 4px; }
.md-crest{ width:30px; height:30px; object-fit:contain; flex:0 0 auto; }
.md-name{ color:#fff; font-weight:800; font-size:1.05rem; line-height:1.12; letter-spacing:-.2px; }
.md-sub{ color:#aebdd6; font-size:.84rem; font-weight:600; }
.md-note{ color:var(--muted); font-size:.74rem; margin-top:3px; font-style:italic; }
</style>"""


def inject():
    """Load the component CSS (call once per run)."""
    st.markdown(CSS, unsafe_allow_html=True)


def stats(items):
    """A responsive row of stat cards. items: list of (label, value, sub) — sub & a leading '*' on
    the label for the gold accent are both optional. e.g. ('*Span', '1916–2026', '110 years')."""
    cells = ""
    for label, value, *rest in items:
        sub = rest[0] if rest else ""
        gold = label.startswith("*")
        cells += (f"<div class='ui-stat{' gold' if gold else ''}'>"
                  f"<div class='lbl'>{label.lstrip('*')}</div><div class='val'>{value}</div>"
                  f"{f'<div class=\"sub\">{sub}</div>' if sub else ''}</div>")
    st.markdown(f"<div class='ui-stats'>{cells}</div>", unsafe_allow_html=True)


def features(items):
    """A responsive grid of feature cards. items: list of dict(icon, title, body[, gold])."""
    cards = ""
    for it in items:
        cards += (f"<div class='ui-feat{' gold' if it.get('gold') else ''}'>"
                  f"<div class='ic'>{it['icon']}</div><div class='ti'>{it['title']}</div>"
                  f"<div class='bd'>{it['body']}</div></div>")
    st.markdown(f"<div class='ui-grid'>{cards}</div>", unsafe_allow_html=True)


def photo_cards(items):
    """A responsive grid of image cards. items: list of dict(photo, title, sub, badge) — the title
    overlays the photo (with a gradient scrim); sub/badge sit in a small footer row."""
    cards = ""
    for it in items:
        cards += (f"<div class='ui-pcard'>"
                  f"<div class='ph' style=\"background-image:url('{it.get('photo', '')}')\">"
                  f"<span class='cap'>{it['title']}</span></div>"
                  f"<div class='bd'><span class='meta'>{it.get('sub', '')}</span>"
                  f"<span class='badge'>{it.get('badge', '')}</span></div></div>")
    st.markdown(f"<div class='ui-pgrid'>{cards}</div>", unsafe_allow_html=True)


def callout(title, body):
    """A highlighted info block (sky left-accent). body takes inline HTML <b>."""
    st.markdown(f"<div class='ui-note'><div class='nt-t'>{title}</div><div class='nt-b'>{body}</div></div>",
                unsafe_allow_html=True)


def section(title, sub=""):
    st.markdown(f"<div class='ui-sec'><h3>{title}</h3>"
                f"{f'<span class=\"h-sub\">{sub}</span>' if sub else ''}</div>", unsafe_allow_html=True)


def medals(items):
    """A responsive grid of 'champion' cards — high-contrast HTML, an alternative to a dim st.dataframe
    for short highlight rows. items: list of dict(tag, img, name, sub[, note]): tag = small eyebrow label
    (e.g. a decade), img = crest URL, name = bold title, sub = a detail line, note = optional footnote."""
    cards = ""
    for it in items:
        img = f"<img class='md-crest' src='{it['img']}'>" if it.get("img") else ""
        note = f"<div class='md-note'>{it['note']}</div>" if it.get("note") else ""
        cards += (f"<div class='md-card'><div class='md-tag'>{it.get('tag', '')}</div>"
                  f"<div class='md-body'>{img}<span class='md-name'>{it['name']}</span></div>"
                  f"<div class='md-sub'>{it.get('sub', '')}</div>{note}</div>")
    st.markdown(f"<div class='md-grid'>{cards}</div>", unsafe_allow_html=True)
