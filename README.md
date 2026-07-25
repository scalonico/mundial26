# Mundial — every World Cup, 1930–2026

### 🔗 Live: **[mundial26-wc.streamlit.app](https://mundial26-wc.streamlit.app)**

**Mundial** is an interactive archive of the men's World Cup — all **23 editions**, from Uruguay 1930 to the first 48-team tournament in North America 2026.

It began as a live companion for 2026 and was refocused when that tournament ended (**Spain 1–0 Argentina** after extra time, July 19 2026) around the part that doesn't go stale.

- **📜 Every World Cup** — champions from 1930 on; open any edition for its **group tables** and **knockout bracket**; the **all-time table** (titles · finals · W-D-L · goals); any two nations' **head-to-head**; and records
- **🏆 2026 in depth** — that edition's own two-sided bracket (Round of 32 → Final), group standings, all 104 fixtures with **time-zone conversion**, teams and venues
- **🎮 Bracket challenge** — build a bracket (pick group winners → call every knockout), **share a code with friends**, and see it scored against what actually happened

Built with Streamlit + Plotly. Single page, no backend.

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Data

Two archives, joined at load time by `wchistory.matches()`:

| Editions | File | Source |
|---|---|---|
| 1930–2022 | `data/worldcup_matches.csv` | built by `build/history/openfootball_wc.py` from [openfootball](https://github.com/openfootball/world-cup) (Public Domain) |
| 2026 | `data/wc2026_*.csv` | built by `build/ingest.py` from English Wikipedia |

2026 is deliberately **not** copied into `worldcup_matches.csv` — that builder rewrites the file from scratch, which would wipe appended rows. Deriving it at load time keeps one source of truth per tournament.

National names are kept **historically accurate** in the data (West Germany, Soviet Union, Yugoslavia, Czechoslovakia, Zaire, Dutch East Indies…). All-time aggregates fold only the four uncontroversial continuations — West Germany → Germany, USA → United States, Czech Republic → Czechia, Zaire → DR Congo. Czechoslovakia is *not* folded into Czechia: that was a state that split, not a rename. Shootout knockouts count as **draws** (FIFA convention); titles are tracked separately.

## Reviving the live refresh for a future tournament

`.github/workflows/update-data.yml` polled Wikipedia during 2026 and committed changed CSVs, with Streamlit Cloud redeploying on each push. Its cron is **retired** (the workflow now runs only on manual dispatch) but the covering-loop logic is intact — point `build/ingest.py` at the new tournament's pages and restore the `schedule:` block.

## Deploy (Streamlit Community Cloud — free)

1. Push this folder to a GitHub repo.
2. On [share.streamlit.io](https://share.streamlit.io), create an app pointing at `streamlit_app.py`.

## Attribution

Match, draw and venue data from **English Wikipedia** (CC BY-SA 4.0) and **openfootball** (Public Domain); cached under `sources/` for offline, reproducible builds. Flags via **flagcdn.com**; stadium photos via **Wikimedia Commons**. The bracket pool is session-only (codes carry the whole prediction; no accounts, no stored data). **Not affiliated with or endorsed by FIFA.**
