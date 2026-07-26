# Mundial — every World Cup, 1930–2026

### 🔗 Live: **[mundial26-wc.streamlit.app](https://mundial26-wc.streamlit.app)**

An interactive archive of the men's World Cup — all **23 editions**, from Uruguay 1930 to the first 48-team tournament in North America 2026.

It began as a live companion for 2026 and was refocused when that tournament ended (**Spain 1–0 Argentina** after extra time, 19 July 2026) around the part that doesn't go stale.

| | |
|---|---|
| 📜 **Every World Cup** | champions from 1930 on; open any edition for its group tables and knockout bracket, plus the all-time table, any two nations' head-to-head, and records |
| 🏳️ **Nations** | one country's whole story — honours, all-time record, every edition entered and how far it got, leading scorers, every match played |
| 👤 **Players** | all-time top scorers, the leading scorer of every edition, the official awards, a searchable profile for any of 9,478 players, and records |
| 🏟️ **Venues** | every stadium used at a World Cup — 3 in Uruguay 1930, 20 across Korea/Japan 2002 — and the ones used more than once (Estadio Azteca in 1970, 1986 *and* 2026) |
| 👥 **Squads** | any nation's named squad in any edition, by position, with clubs, captains and goals scored |
| 🎟️ **Crowds** | attendance for all 1,068 matches, how the average grew, and every referee |
| 🔁 **Replay** | pick any of 20 editions, call the whole knockout bracket blind, then score it against history — share it as a code and rank against friends |
| 🎮 **2026 Challenge** | the original predictor: call the 2026 group stage and knockouts, share a code, climb a leaderboard |

Built with Streamlit + Plotly. Single page, no backend.

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Data

Five datasets, all built by scripts in `build/` and joined at load time. Wikipedia pages are cached under `sources/`, so every build after the first is fully offline.

| Data | File | Built by | From |
|---|---|---|---|
| Matches 1930–2022 | `data/worldcup_matches.csv` | `build/history/openfootball_wc.py` | [openfootball](https://github.com/openfootball/world-cup) (Public Domain) |
| Matches 2026 | `data/wc2026_*.csv` | `build/ingest.py` | English Wikipedia |
| Goals · squads · crowds | `data/wc_goals.csv`, `wc_squads.csv`, `wc_matchmeta.csv` | `build/players.py` | English Wikipedia |
| Awards | `data/wc_awards.csv` | `build/awards.py` | English Wikipedia |

**Coverage is verified, not asserted.** `build/players.py` prints a table comparing its output against the archive's scorelines: all 23 editions and all 120 (year, stage) pairs agree — 3,028 goals across 1,068 matches. The canonical records then fall out unaided, which is the real test: Klose 16, Ronaldo 15, Müller 14, Fontaine 13, Pelé 12.

**2026 is deliberately not baked into `worldcup_matches.csv`.** That builder opens the file with `"w"` and rewrites 1930–2022 from scratch, so appended rows would be silently wiped. `wchistory.matches()` derives the 48-team edition from the 2026 CSVs instead — one source of truth per tournament.

### Conventions worth knowing

- National names are **historically accurate** in the data (West Germany, Soviet Union, Yugoslavia, Czechoslovakia, Zaire, Dutch East Indies…). All-time aggregates fold only four continuations — West Germany → Germany, USA → United States, Czech Republic → Czechia, Zaire → DR Congo. **Czechoslovakia is not folded** into Czechia: that was a state that split, not a rename.
- Shootout knockouts count as **draws** (FIFA convention); titles are tracked separately.
- **Own goals** are recorded but never counted toward a player's tally. Wikipedia files them under the team they *benefited*, so `build/players.py` re-attributes them to the scorer's real nation — getting that backwards would corrupt every per-nation total.
- Player identity is the Wikipedia **link target**, not the displayed name, which is often a bare surname — otherwise Brazil's "Ronaldo" collides with Cristiano Ronaldo. `wcplayers._KEY_ALIAS` reconciles the titles the goal and squad pages disagree on (99.3% join rate; six are left unmatched on purpose rather than guessed at).
- The **leading-scorer roll is computed from the goals** and is not the official Golden Boot, which used assists and minutes as tie-breaks in some years. The awards section carries the official winners separately.

### What this data does *not* contain

Worth knowing before building on it: **no appearances or minutes played** (the match reports carry no line-ups), **no cards**, and **no assists**. Anything squad-derived therefore means *named in the squad*, never *played* — including the youngest and oldest records.

## Reviving the live refresh for a future tournament

`.github/workflows/update-data.yml` polled Wikipedia during 2026 and committed changed CSVs, with Streamlit Cloud redeploying on each push. Its cron is **retired** (manual dispatch only) but the covering-loop logic is intact — point `build/ingest.py` at the new tournament's pages and restore the `schedule:` block.

## Deploy (Streamlit Community Cloud — free)

1. Push this folder to a GitHub repo.
2. On [share.streamlit.io](https://share.streamlit.io), create an app pointing at `streamlit_app.py`.

`.streamlit/config.toml` sets a dark base theme — without it Streamlit's light default shows through on every native widget.

## Attribution

Match, squad, award and attendance data from **English Wikipedia** (CC BY-SA 4.0) and **openfootball** (Public Domain), cached under `sources/` for offline, reproducible builds. Flags via **flagcdn.com**; stadium photos via **Wikimedia Commons**. Bracket predictions are session-only — codes carry the whole bracket, no accounts, nothing stored. **Not affiliated with or endorsed by FIFA.**
