import asyncio
from datetime import datetime, timezone

import pytest
from ndastro_engine.constants import DEGREE_PER_RASI
from ndastro_engine.enums import Nakshatras, Planets, Rasis
from ndastro_engine.retrograde import is_planet_in_retrograde

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
        "get_birth_chart",
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
        assert 1 <= row["nakshatra_pada"] <= 4
        assert 1 <= row["house"] <= 12


def test_houses_are_whole_sign_from_lagna():
    rows = server.get_planet_positions(_BIRTH, _LAT, _LON)
    lagna_rasi = int(next(row for row in rows if row["planet"] == "ascendant")["sidereal_longitude"] // DEGREE_PER_RASI)

    for row in rows:
        assert row["house"] == (int(row["sidereal_longitude"] // DEGREE_PER_RASI) - lagna_rasi) % 12 + 1
    assert next(row for row in rows if row["planet"] == "ascendant")["house"] == 1


@pytest.mark.parametrize("moment", ["2026-08-01T00:00:00Z", "2026-02-15T00:00:00Z"])
@pytest.mark.parametrize("planet", ["mercury", "saturn", "jupiter"])
def test_retrograde_flag_matches_engine(planet: str, moment: str):
    row = server.get_planet_positions(moment, _LAT, _LON, planets=[planet])[0]
    when = datetime.fromisoformat(moment.replace("Z", "+00:00")).astimezone(timezone.utc)
    expected, _, _ = is_planet_in_retrograde(when, server._planet(planet).astronomical_code, _LAT, _LON)

    assert row["is_retrograde"] is expected


def test_nodes_are_always_retrograde_and_luminaries_never():
    rows = {row["planet"]: row for row in server.get_planet_positions(_BIRTH, _LAT, _LON)}

    assert rows["rahu"]["is_retrograde"]
    assert rows["kethu"]["is_retrograde"]
    assert not rows["sun"]["is_retrograde"]
    assert not rows["moon"]["is_retrograde"]


def test_birth_chart_combines_lagna_grahas_and_dasa():
    chart = server.get_birth_chart(_BIRTH, _LAT, _LON, at_datetime="2026-01-01T00:00:00Z", language="ta")

    assert chart["house_system"] == "whole_sign"
    assert chart["lagna"]["rasi_ta"]
    assert [row["planet"] for row in chart["grahas"]] == [p.name.lower() for p in Planets if p not in (Planets.EMPTY, Planets.ASCENDANT)]
    assert all("house" in row and "is_retrograde" in row for row in chart["grahas"])
    assert chart["birth_details"]["janma_nakshatra"]
    assert set(chart["current_dasa"]) == {"maha", "antara", "pratyantara", "sookshma"}
    assert chart["current_dasa"]["maha"]["level_ta"] == "தசை"


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
