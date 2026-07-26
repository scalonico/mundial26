"""The app must execute top to bottom with no exception on EVERY tab.

Streamlit renders all tabs in one script run, so a single AppTest run covers them all. This is the
cheapest possible guard against a rename or a deleted helper breaking a page that nothing else tests.
"""
import pytest

from streamlit.testing.v1 import AppTest

TABS = ["📜 Every World Cup", "🏳️ Nations", "👤 Players", "🏟️ Venues", "👥 Squads",
        "🎟️ Crowds", "🔁 Replay", "🎮 2026 Challenge"]


@pytest.fixture(scope="module")
def app():
    return AppTest.from_file("streamlit_app.py", default_timeout=300).run()


def test_app_runs_clean(app):
    assert not app.exception, [str(e.value) for e in app.exception]
    assert not app.warning, [w.value for w in app.warning]


def test_expected_tabs(app):
    assert [t.label for t in app.tabs] == TABS


@pytest.mark.parametrize("year", [1930, 1934, 1950, 1982, 2002, 2026])
def test_edition_explorer_renders_every_era(year):
    """1934 had no group stage, 1950 no Final, 1982 a second group stage, 2026 a round of 32."""
    at = AppTest.from_file("streamlit_app.py", default_timeout=300).run()
    at.button(key=f"hy_{year}").click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert not at.warning, [w.value for w in at.warning]


def test_player_search_and_profile():
    at = AppTest.from_file("streamlit_app.py", default_timeout=300).run()
    at.text_input(key="pl_q").set_value("Klose").run()
    assert not at.exception
    assert at.selectbox(key="pl_pick").value == "Miroslav Klose"


def test_squads_handles_a_defunct_nation():
    at = AppTest.from_file("streamlit_app.py", default_timeout=300).run()
    at.selectbox(key="sq_year").set_value(1938).run()
    at.selectbox(key="sq_nation").set_value("Dutch East Indies").run()
    assert not at.exception, [str(e.value) for e in at.exception]
