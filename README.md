# World Cup 2026 — Bracket & Guide

An interactive companion for the **2026 FIFA World Cup** — the first 48-team edition (Canada · Mexico · USA, June 11 – July 19, 2026).

- **Groups** — all 12 groups with live-ready standings
- **Schedule** — every one of the 104 fixtures, filterable, with **time-zone conversion**
- **Bracket** — a two-sided visual knockout bracket (Round of 32 → Final)
- **🎮 Bracket challenge** — build your own bracket (pick group winners → call every knockout), then **share a code with friends** and watch a leaderboard scored live against the real results
- **Venues** & **Teams**

Built with Streamlit + Plotly. Single page, no backend.

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Live data

The app reads `data/wc2026_*.csv`. During the tournament, re-run the ingest to pull the latest scores — standings and the bracket fill in automatically:

```bash
python build/ingest.py
```

It parses the public Wikipedia tournament articles (cached under `sources/` for offline, reproducible builds).

## Deploy (Streamlit Community Cloud — free)

1. Push this folder to a GitHub repo.
2. On [share.streamlit.io](https://share.streamlit.io), create an app pointing at `streamlit_app.py`.
3. *(Optional, for live results)* add a GitHub Action on a cron that runs `python build/ingest.py` and commits the updated CSVs — the deployed app redeploys and shows the latest scores.

## Data & attribution

Draw, fixtures and venue data parsed from **English Wikipedia** (CC BY-SA 4.0). Flags via **flagcdn.com**; stadium photos via **Wikimedia Commons**. The bracket pool is session-only (codes carry the whole prediction; no accounts, no stored data). **Not affiliated with or endorsed by FIFA.**

*Proof of concept — June 2026.*
