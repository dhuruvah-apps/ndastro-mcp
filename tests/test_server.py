import asyncio

import pytest
from ndastro_engine.enums import Nakshatras, Planets, Rasis

from ndastro_mcp import server, tamil

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


def test_tamil_names_cover_every_engine_value():
    assert set(tamil.PLANETS) == {p for p in Planets if p is not Planets.EMPTY}
    assert set(tamil.RASIS) == set(Rasis)
    assert set(tamil.NAKSHATRAS) == set(Nakshatras)
    assert set(tamil.DASA_LEVELS) == {"maha", "antara", "pratyantara", "sookshma"}


@pytest.mark.parametrize(("value", "expected"), [("சனி", Planets.SATURN), ("குரு", Planets.JUPITER), ("சுக்கிரன்", Planets.VENUS)])
def test_planet_accepts_tamil_names(value: str, expected: Planets):
    assert server._planet(value) is expected


def test_planet_positions_add_tamil_fields_only_when_requested():
    english = server.get_planet_positions("2000-01-01T12:00:00Z", _LAT, _LON, planets=["சூரியன்"])
    tamil_rows = server.get_planet_positions("2000-01-01T12:00:00Z", _LAT, _LON, planets=["சூரியன்"], language="ta")

    assert not any(key.endswith("_ta") for key in english[0])
    assert tamil_rows[0]["planet"] == "sun"
    assert tamil_rows[0]["planet_ta"] == "சூரியன்"
    assert tamil_rows[0]["rasi_ta"] == tamil.RASIS[Rasis[tamil_rows[0]["rasi"].upper()]]
    assert tamil_rows[0]["nakshatra_ta"] == tamil.NAKSHATRAS[Nakshatras[tamil_rows[0]["nakshatra"].upper()]]


def test_current_dasa_in_tamil():
    running = server.get_current_dasa(_BIRTH, _LAT, _LON, at_datetime="2026-01-01T00:00:00Z", language="ta")

    assert running["maha"]["level_ta"] == "தசை"
    assert running["antara"]["level_ta"] == "புக்தி"
    assert running["maha"]["lord_ta"] == tamil.PLANETS[Planets[running["maha"]["lord"].upper()]]
