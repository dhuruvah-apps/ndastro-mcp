"""MCP server exposing ndastro-engine calculations as tools."""

import argparse
from datetime import datetime, timezone
from typing import Annotated, Any, Literal, get_args

from mcp.server.fastmcp import FastMCP
from ndastro_engine.ayanamsa import AyanamsaSystem, get_ayanamsa
from ndastro_engine.combustion import find_combust_periods, is_planet_in_combust
from ndastro_engine.constants import DEGREE_PER_NAKSHATRA, DEGREE_PER_RASI
from ndastro_engine.core import (
    get_ascendent_position,
    get_lunar_node_positions,
    get_planet_position,
    get_planet_rise_set,
    get_sunrise_sunset,
)
from ndastro_engine.dasa import (
    DasaContext,
    DasaPeriod,
    DasaQuery,
    get_dasa_birth_info,
    get_dasa_timeline,
    get_running_dasa,
    get_supported_dasa_types,
)
from ndastro_engine.enums import Nakshatras, Planets, Rasis
from ndastro_engine.retrograde import find_retrograde_periods, is_planet_in_retrograde
from ndastro_engine.utils import normalize_degree, parse_iso_datetime
from pydantic import Field

from ndastro_mcp import tamil

mcp = FastMCP(
    "ndastro",
    instructions=(
        "Vedic astrology calculations from ndastro-engine. Datetimes are ISO 8601; a missing timezone means UTC. "
        "Longitudes are ecliptic degrees. Planets accept English names (e.g. 'saturn', 'ketu'), codes (e.g. 'SA', 'KE'), "
        "or Tamil names (e.g. 'சனி', 'கேது'). When the user writes in Tamil or asks for Tamil, pass language='ta' to get "
        "Tamil names in *_ta fields and reply to the user in Tamil."
    ),
)

_MAX_SCAN_DAYS = 3660
_RETROGRADE_PLANETS = frozenset({Planets.MARS, Planets.MERCURY, Planets.JUPITER, Planets.VENUS, Planets.SATURN})
_PLANET_ALIASES = {"KETU": Planets.KETHU, "LAGNA": Planets.ASCENDANT}

Latitude = Annotated[float, Field(ge=-90, le=90, description="Latitude in decimal degrees")]
Longitude = Annotated[float, Field(ge=-180, le=180, description="Longitude in decimal degrees")]
Language = Annotated[Literal["en", "ta"], Field(description="'ta' adds Tamil names in *_ta fields")]


def _planet(value: str) -> Planets:
    tamil_planet = tamil.PLANET_INPUTS.get(value.strip())
    if tamil_planet is not None:
        return tamil_planet
    key = value.strip().upper()
    planet = Planets.__members__.get(key) or _PLANET_ALIASES.get(key) or Planets.from_code(key)  # type: ignore[arg-type]
    if planet is Planets.EMPTY:
        msg = f"Unknown planet {value!r}. Use a name like 'saturn', a code like 'SA', or a Tamil name like 'சனி'."
        raise ValueError(msg)
    return planet


def _utc(value: str) -> datetime:
    return parse_iso_datetime(value).astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).isoformat() if value else None


def _scan_range(start: str, end: str) -> tuple[datetime, datetime]:
    start_dt, end_dt = _utc(start), _utc(end)
    if end_dt <= start_dt:
        msg = "end must be after start"
        raise ValueError(msg)
    if (end_dt - start_dt).days > _MAX_SCAN_DAYS:
        msg = f"Range must not exceed {_MAX_SCAN_DAYS} days"
        raise ValueError(msg)
    return start_dt, end_dt


def _sidereal(tropical: float, ayanamsa: float, language: str = "en") -> dict[str, Any]:
    longitude = normalize_degree(tropical - ayanamsa)
    rasi = Rasis(int(longitude // DEGREE_PER_RASI) + 1)
    nakshatra = Nakshatras(int(longitude // DEGREE_PER_NAKSHATRA) + 1)
    data: dict[str, Any] = {
        "sidereal_longitude": round(longitude, 6),
        "rasi": rasi.name.lower(),
        "degree_in_rasi": round(longitude % DEGREE_PER_RASI, 6),
        "nakshatra": nakshatra.name.lower(),
    }
    if language == "ta":
        data["rasi_ta"] = tamil.RASIS[rasi]
        data["nakshatra_ta"] = tamil.NAKSHATRAS[nakshatra]
    return data


def _period(period: DasaPeriod, language: str = "en", *, include_children: bool = True) -> dict[str, Any]:
    data: dict[str, Any] = {
        "level": period.level_name,
        "lord": period.lord.lower(),
        "start_utc": _iso(period.start_utc),
        "end_utc": _iso(period.end_utc),
    }
    if language == "ta":
        data["level_ta"] = tamil.DASA_LEVELS[period.level_name]
        data["lord_ta"] = tamil.PLANETS[Planets[period.lord]]
    if include_children and period.children:
        data["children"] = [_period(child, language) for child in period.children]
    return data


@mcp.tool()
def list_ayanamsa_systems() -> list[str]:
    """List supported ayanamsa (sidereal correction) systems."""
    return list(get_args(AyanamsaSystem))


@mcp.tool()
def get_ayanamsa_value(datetime_iso: str, system: AyanamsaSystem = "lahiri") -> float:
    """Return the ayanamsa in degrees for a moment and system."""
    return get_ayanamsa(_utc(datetime_iso), system)


@mcp.tool()
def get_planet_positions(  # noqa: PLR0913
    datetime_iso: str,
    lat: Latitude,
    lon: Longitude,
    ayanamsa: AyanamsaSystem = "lahiri",
    planets: list[str] | None = None,
    language: Language = "en",
) -> list[dict[str, Any]]:
    """Return tropical and sidereal positions, rasi, and nakshatra of the grahas and ascendant.

    Omit `planets` to get all nine grahas plus the ascendant.
    """
    dt = _utc(datetime_iso)
    selected = [_planet(name) for name in planets] if planets else [p for p in Planets if p is not Planets.EMPTY]
    ayanamsa_value = get_ayanamsa(dt, ayanamsa)
    results = []
    for planet in selected:
        position = get_planet_position(planet, lat, lon, dt)
        row: dict[str, Any] = {"planet": planet.name.lower(), "code": planet.code}
        if language == "ta":
            row["planet_ta"] = tamil.PLANETS[planet]
        results.append(
            {
                **row,
                "tropical_longitude": round(position.longitude, 6),
                **_sidereal(position.longitude, ayanamsa_value, language),
                "ecliptic_latitude": round(position.latitude, 6),
                "speed_longitude_per_day": round(position.speed_longitude, 6),
            }
        )
    return results


@mcp.tool()
def get_ascendant(
    datetime_iso: str,
    lat: Latitude,
    lon: Longitude,
    ayanamsa: AyanamsaSystem = "lahiri",
    language: Language = "en",
) -> dict[str, Any]:
    """Return the tropical and sidereal ascendant (lagna)."""
    dt = _utc(datetime_iso)
    tropical = get_ascendent_position(lat, lon, dt)
    return {"tropical_longitude": round(tropical, 6), **_sidereal(tropical, get_ayanamsa(dt, ayanamsa), language)}


@mcp.tool()
def get_lunar_nodes(datetime_iso: str, ayanamsa: AyanamsaSystem = "lahiri", language: Language = "en") -> dict[str, Any]:
    """Return Rahu and Ketu positions."""
    dt = _utc(datetime_iso)
    rahu, kethu = get_lunar_node_positions(dt)
    ayanamsa_value = get_ayanamsa(dt, ayanamsa)
    return {
        "rahu": {"tropical_longitude": round(rahu, 6), **_sidereal(rahu, ayanamsa_value, language)},
        "kethu": {"tropical_longitude": round(kethu, 6), **_sidereal(kethu, ayanamsa_value, language)},
    }


@mcp.tool()
def get_sun_rise_set(date_iso: str, lat: Latitude, lon: Longitude, elevation_m: float | None = None) -> dict[str, str | None]:
    """Return UTC sunrise and sunset for a date. Omit `elevation_m` to look elevation up online."""
    sunrise, sunset = get_sunrise_sunset(lat, lon, _utc(date_iso), elevation_m)
    return {"sunrise_utc": _iso(sunrise), "sunset_utc": _iso(sunset)}


@mcp.tool()
def get_planet_rise_set_times(
    planet: str,
    date_iso: str,
    lat: Latitude,
    lon: Longitude,
    elevation_m: float | None = None,
) -> dict[str, str | None]:
    """Return UTC rise and set times of a planet for a date (none for Rahu, Ketu, or ascendant)."""
    rise, set_ = get_planet_rise_set(_planet(planet), lat, lon, _utc(date_iso), elevation_m)
    return {"rise_utc": _iso(rise), "set_utc": _iso(set_)}


@mcp.tool()
def list_dasa_types() -> list[str]:
    """List supported dasa systems."""
    return list(get_supported_dasa_types())


@mcp.tool()
def get_dasa_birth_details(  # noqa: PLR0913
    birth_datetime: str,
    lat: Latitude,
    lon: Longitude,
    ayanamsa: AyanamsaSystem = "lahiri",
    dasa_type: str = "vimshottari",
    language: Language = "en",
) -> dict[str, Any]:
    """Return the birth nakshatra, Moon longitude, and starting dasa lord."""
    info = get_dasa_birth_info(DasaContext(_utc(birth_datetime), lat, lon, ayanamsa, dasa_type))
    data: dict[str, Any] = {
        "sidereal_moon_longitude": round(info.sidereal_moon_longitude, 6),
        "janma_nakshatra": info.janma_nakshatra.name.lower(),
        "nakshatra_progress_fraction": round(info.nakshatra_progress_fraction, 6),
        "nakshatra_remaining_fraction": round(info.nakshatra_remaining_fraction, 6),
        "start_lord": info.start_lord.lower(),
    }
    if language == "ta":
        data["janma_nakshatra_ta"] = tamil.NAKSHATRAS[info.janma_nakshatra]
        data["start_lord_ta"] = tamil.PLANETS[Planets[info.start_lord]]
    return data


@mcp.tool()
def get_dasa_periods(  # noqa: PLR0913
    birth_datetime: str,
    lat: Latitude,
    lon: Longitude,
    ayanamsa: AyanamsaSystem = "lahiri",
    dasa_type: str = "vimshottari",
    levels: Annotated[int, Field(ge=1, le=4, description="1=maha, 2=antara, 3=pratyantara, 4=sookshma")] = 2,
    years: Annotated[float | None, Field(gt=0, description="Years from birth to cover; defaults to the full cycle")] = None,
    language: Language = "en",
) -> list[dict[str, Any]]:
    """Return the nested dasa timeline from birth."""
    context = DasaContext(_utc(birth_datetime), lat, lon, ayanamsa, dasa_type)
    return [_period(period, language) for period in get_dasa_timeline(context, DasaQuery(levels=levels, years=years))]


@mcp.tool()
def get_current_dasa(  # noqa: PLR0913
    birth_datetime: str,
    lat: Latitude,
    lon: Longitude,
    at_datetime: str | None = None,
    ayanamsa: AyanamsaSystem = "lahiri",
    dasa_type: str = "vimshottari",
    language: Language = "en",
) -> dict[str, Any]:
    """Return the running maha, antara, pratyantara, and sookshma dasa at a moment (defaults to now)."""
    query_dt = _utc(at_datetime) if at_datetime else datetime.now(timezone.utc)
    running = get_running_dasa(query_dt, DasaContext(_utc(birth_datetime), lat, lon, ayanamsa, dasa_type))
    return {
        level: _period(period, language, include_children=False) if period else None
        for level, period in (
            ("maha", running.maha),
            ("antara", running.antara),
            ("pratyantara", running.pratyantara),
            ("sookshma", running.sookshma),
        )
    }


@mcp.tool()
def get_retrograde_periods(planet: str, start_iso: str, end_iso: str, lat: Latitude, lon: Longitude) -> list[dict[str, str | None]]:
    """Return retrograde periods of Mars, Mercury, Jupiter, Venus, or Saturn within a range (max ~10 years)."""
    selected = _planet(planet)
    if selected not in _RETROGRADE_PLANETS:
        msg = "Retrograde periods are available for mars, mercury, jupiter, venus, and saturn"
        raise ValueError(msg)
    start, end = _scan_range(start_iso, end_iso)
    return [{"start_utc": _iso(s), "end_utc": _iso(e)} for s, e in find_retrograde_periods(start, end, selected.astronomical_code, lat, lon)]


@mcp.tool()
def check_retrograde(planet: str, datetime_iso: str, lat: Latitude, lon: Longitude) -> dict[str, Any]:
    """Return whether a planet is retrograde at a moment and the surrounding retrograde period."""
    is_retro, start, end = is_planet_in_retrograde(_utc(datetime_iso), _planet(planet).astronomical_code, lat, lon)
    return {"is_retrograde": is_retro, "period_start_utc": _iso(start), "period_end_utc": _iso(end)}


@mcp.tool()
def get_combustion_periods(planet: str, start_iso: str, end_iso: str, lat: Latitude, lon: Longitude) -> list[dict[str, str | None]]:
    """Return periods when a planet is combust (too close to the Sun) within a range (max ~10 years)."""
    start, end = _scan_range(start_iso, end_iso)
    return [{"start_utc": _iso(s), "end_utc": _iso(e)} for s, e in find_combust_periods(start, end, _planet(planet).astronomical_code, lat, lon)]


@mcp.tool()
def check_combustion(planet: str, datetime_iso: str, lat: Latitude, lon: Longitude) -> dict[str, Any]:
    """Return whether a planet is combust at a moment and the surrounding combustion period."""
    is_combust, start, end = is_planet_in_combust(_utc(datetime_iso), _planet(planet).astronomical_code, lat, lon)
    return {"is_combust": is_combust, "period_start_utc": _iso(start), "period_end_utc": _iso(end)}


def main() -> None:
    """Run the MCP server."""
    parser = argparse.ArgumentParser(description="ndastro-engine MCP server")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio")
    transport: Literal["stdio", "sse", "streamable-http"] = parser.parse_args().transport
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
