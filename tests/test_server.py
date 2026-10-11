import asyncio

import pytest
from ndastro_engine.enums import Planets

from ndastro_mcp import server

_LAT = 13.0827
_LON = 80.2707
_BIRTH = "1990-06-15T10:30:00+05:30"


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
