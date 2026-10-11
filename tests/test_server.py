import asyncio

import pytest
from ndastro_engine.enums import Nakshatras, Planets, Rasis

from ndastro_mcp import api, server

_LAT = 13.0827
_LON = 80.2707
_BIRTH = "1990-06-15T10:30:00+05:30"
_TAMIL_PLANETS = {"SU": "சூரியன்", "JU": "குரு", "SA": "சனி"}


def _fake_glossary(language: str) -> dict[str, dict[str, str]]:
    return {
        "planets": {p.code: _TAMIL_PLANETS.get(p.code, f"{language}-{p.code}") for p in Planets if p is not Planets.EMPTY},
        "rasis": {r.code: f"{language}-{r.code}" for r in Rasis},
        "nakshatras": {n.code: f"{language}-{n.code}" for n in Nakshatras},
        "dasa_levels": {level: f"{language}-{level}" for level in ("maha", "antara", "pratyantara", "sookshma")},
    }


@pytest.fixture
def fake_glossary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "glossary", _fake_glossary)


def test_all_tools_are_registered():
    names = {tool.name for tool in asyncio.run(server.mcp.list_tools())}
    assert {
        "list_ayanamsa_systems",
        "get_ayanamsa_value",
        "get_planet_positions",
        "get_ascendant",
        "get_lunar_nodes",
        "get_sun_rise_set",
        "get_planet_rise_set_times",
        "list_dasa_types",
        "get_dasa_birth_details",
        "get_dasa_periods",
        "get_current_dasa",
        "get_retrograde_periods",
        "check_retrograde",
        "get_combustion_periods",
        "check_combustion",
        "get_glossary",
        "get_life_stages",
        "get_event_timing",
        "get_difficult_periods",
        "calibrate_with_known_events",
        "correct_birth_datetime",
        "find_auspicious_dates",
    } <= names


@pytest.mark.parametrize(("value", "expected"), [("saturn", Planets.SATURN), ("SA", Planets.SATURN), ("ketu", Planets.KETHU), (" mo ", Planets.MOON)])
def test_planet_accepts_names_codes_and_aliases(value: str, expected: Planets):
    assert server._planet(value) is expected


def test_planet_rejects_unknown_names():
    with pytest.raises(ValueError, match="Unknown planet"):
        server._planet("pluto")


def test_planet_positions_include_sidereal_details():
    rows = server.get_planet_positions("2000-01-01T12:00:00Z", _LAT, _LON, planets=["sun", "MO"])

    assert [row["planet"] for row in rows] == ["sun", "moon"]
    for row in rows:
        assert 0 <= row["sidereal_longitude"] < 360
        assert row["rasi"]
        assert row["nakshatra"]


def test_dasa_periods_respect_levels():
    periods = server.get_dasa_periods(_BIRTH, _LAT, _LON, levels=2, years=20)

    assert periods
    assert all(period["level"] == "maha" for period in periods)
    assert all(child["level"] == "antara" and "children" not in child for child in periods[0]["children"])


def test_current_dasa_returns_all_levels():
    running = server.get_current_dasa(_BIRTH, _LAT, _LON, at_datetime="2026-01-01T00:00:00Z")

    assert set(running) == {"maha", "antara", "pratyantara", "sookshma"}
    assert all(level is not None and "children" not in level for level in running.values())


def test_retrograde_rejects_unsupported_planet():
    with pytest.raises(ValueError, match="Retrograde periods"):
        server.get_retrograde_periods("sun", "2026-01-01", "2026-12-31", _LAT, _LON)


def test_scan_range_is_bounded():
    with pytest.raises(ValueError, match="must not exceed"):
        server.get_combustion_periods("mercury", "2000-01-01", "2030-01-01", _LAT, _LON)


@pytest.mark.usefixtures("fake_glossary")
@pytest.mark.parametrize(("value", "expected"), [("சனி", Planets.SATURN), (" குரு ", Planets.JUPITER)])
def test_planet_accepts_localized_names(value: str, expected: Planets):
    assert server._planet(value) is expected


def test_english_results_do_not_call_the_api(monkeypatch: pytest.MonkeyPatch):
    def fail(_language: str) -> None:
        pytest.fail("English results must not need ndastro-api")

    monkeypatch.setattr(api, "glossary", fail)
    row = server.get_planet_positions("2000-01-01T12:00:00Z", _LAT, _LON, planets=["sun"])[0]

    assert not any(key.endswith("_local") for key in row)


@pytest.mark.usefixtures("fake_glossary")
def test_planet_positions_add_localized_fields():
    row = server.get_planet_positions("2000-01-01T12:00:00Z", _LAT, _LON, planets=["சூரியன்"], language="ta")[0]

    assert row["planet"] == "sun"
    assert row["planet_local"] == "சூரியன்"
    assert row["rasi_local"] == f"ta-{Rasis[row['rasi'].upper()].code}"
    assert row["nakshatra_local"] == f"ta-{Nakshatras[row['nakshatra'].upper()].code}"


@pytest.mark.usefixtures("fake_glossary")
def test_current_dasa_adds_localized_fields():
    running = server.get_current_dasa(_BIRTH, _LAT, _LON, at_datetime="2026-01-01T00:00:00Z", language="ta")

    assert running["maha"]["level_local"] == "ta-maha"
    assert running["antara"]["level_local"] == "ta-antara"
    assert running["maha"]["lord_local"] == _fake_glossary("ta")["planets"][Planets[running["maha"]["lord"].upper()].code]
