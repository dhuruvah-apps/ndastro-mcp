"""MCP tools backed by ndastro-api's higher-level predictions."""

from typing import TYPE_CHECKING, Annotated, Any, Literal

from ndastro_engine.ayanamsa import AyanamsaSystem
from pydantic import BaseModel, Field

from ndastro_mcp import api
from ndastro_mcp.api import Language

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

Latitude = Annotated[float, Field(ge=-90, le=90, description="Birth latitude in decimal degrees")]
Longitude = Annotated[float, Field(ge=-180, le=180, description="Birth longitude in decimal degrees")]
BirthDatetime = Annotated[str, Field(description="Birth datetime in ISO 8601 with timezone, e.g. 1985-07-31T04:25:00+05:30")]
Gender = Annotated[Literal["male", "female"] | None, Field(description="Used for gender-specific age windows such as marriage")]
Event = Annotated[str, Field(description="Life event, e.g. marriage, job_joining, land_purchase, property_purchase, education, travel")]
Relation = Literal["mother", "father", "maternal_relative", "paternal_relative", "sibling", "friend", "neighbor"]
LanguageParam = Annotated[Language, Field(description="Language for names; reply to the user in this language")]


class KnownEvent(BaseModel):
    """A past life event with its actual date."""

    event: Event
    actual_event_datetime: Annotated[str, Field(description="When it happened, ISO 8601")]


def get_glossary(language: LanguageParam = "ta") -> dict[str, Any]:
    """Return localized names for planet, rasi, nakshatra, and dasa level codes (e.g. SA, R07, N16, maha)."""
    return api.glossary(language)


def get_life_stages(birth_datetime: BirthDatetime, lat: Latitude, lon: Longitude, language: LanguageParam = "en") -> Any:  # noqa: ANN401
    """Plain-language positives, challenges, and focus for each life stage from birth, without astrology jargon."""
    return api.request("GET", "/life-timeline/life-stages", params={"birth_datetime": birth_datetime, "lat": lat, "lon": lon, "lang": language})


def get_event_timing(  # noqa: PLR0913
    birth_datetime: BirthDatetime,
    lat: Latitude,
    lon: Longitude,
    event: Event,
    gender: Gender = None,
    actual_event_datetime: Annotated[str | None, Field(description="If the event already happened, its date to validate the prediction")] = None,
    ayanamsa: AyanamsaSystem = "lahiri",
    language: LanguageParam = "en",
) -> Any:  # noqa: ANN401
    """Best-supported date window for a life event from the birth chart, with reasons and person's age."""
    params = {
        "birth_datetime": birth_datetime,
        "lat": lat,
        "lon": lon,
        "event": event,
        "gender": gender,
        "actual_event_datetime": actual_event_datetime,
        "ayanamsa": ayanamsa,
        "lang": language,
    }
    return api.request("GET", "/life-timeline/event-timing", params=params)


def get_difficult_periods(  # noqa: PLR0913
    birth_datetime: BirthDatetime,
    lat: Latitude,
    lon: Longitude,
    relation: Annotated[Relation | None, Field(description="Assess periods for a relative from the person's own chart")] = None,
    start_datetime: Annotated[str | None, Field(description="Window start, ISO 8601; defaults to birth")] = None,
    end_datetime: Annotated[str | None, Field(description="Window end, ISO 8601")] = None,
    *,
    include_transits: Annotated[bool, Field(description="Add transit evidence; limits the window to 400 days")] = False,
    language: LanguageParam = "en",
) -> Any:  # noqa: ANN401
    """Find comparatively challenging periods for preparation, not certain negative events. Never present them as predictions of death."""
    params = {
        "birth_datetime": birth_datetime,
        "lat": lat,
        "lon": lon,
        "relation": relation,
        "start_datetime": start_datetime,
        "end_datetime": end_datetime,
        "include_transits": include_transits,
        "lang": language,
    }
    return api.request("GET", "/life-timeline/difficult-periods", params=params)


def calibrate_with_known_events(
    birth_datetime: BirthDatetime,
    lat: Latitude,
    lon: Longitude,
    events: Annotated[list[KnownEvent], Field(min_length=1, description="Past events the person already experienced")],
    gender: Gender = None,
) -> Any:  # noqa: ANN401
    """Check how well the calculated timeline matches events that already happened in the person's life."""
    body = {
        "birth_datetime": birth_datetime,
        "lat": lat,
        "lon": lon,
        "gender": gender,
        "events": [event.model_dump() for event in events],
    }
    return api.request("POST", "/life-timeline/calibrate", json=body)


def correct_birth_datetime(  # noqa: PLR0913
    birth_datetime: BirthDatetime,
    lat: Latitude,
    lon: Longitude,
    events: Annotated[list[KnownEvent], Field(min_length=1, description="Past events used to test candidate birth times")],
    gender: Gender = None,
    search_minutes: Annotated[int, Field(ge=0, le=180, description="Minutes to search before and after the recorded time")] = 60,
    step_minutes: Annotated[int, Field(ge=1, le=60)] = 5,
) -> Any:  # noqa: ANN401
    """Suggest a corrected birth time by testing nearby times against known past events."""
    body = {
        "birth_datetime": birth_datetime,
        "lat": lat,
        "lon": lon,
        "gender": gender,
        "search_minutes_before": search_minutes,
        "search_minutes_after": search_minutes,
        "step_minutes": step_minutes,
        "events": [event.model_dump() for event in events],
    }
    return api.request("POST", "/life-timeline/birth-datetime-correction", json=body, timeout=600.0)


def find_auspicious_dates(  # noqa: PLR0913
    event: Event,
    start_date: Annotated[str, Field(description="YYYY-MM-DD")],
    end_date: Annotated[str, Field(description="YYYY-MM-DD, at most 365 days after start")],
    lat: Annotated[float, Field(ge=-90, le=90, description="Latitude of the event location")],
    lon: Annotated[float, Field(ge=-180, le=180, description="Longitude of the event location")],
    janma_nakshatra: Annotated[int | None, Field(ge=1, le=27, description="Person's birth nakshatra number, enables Tara Bala")] = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 10,
    language: LanguageParam = "en",
) -> Any:  # noqa: ANN401
    """Rank the most auspicious dates (muhurta) for an event within a date range."""
    params = {
        "event": event,
        "start_date": start_date,
        "end_date": end_date,
        "lat": lat,
        "lon": lon,
        "janma_nakshatra": janma_nakshatra,
        "limit": limit,
        "lang": language,
    }
    return api.request("GET", "/muhurta/auspicious-range", params=params)


def register(mcp: "FastMCP") -> None:
    """Register the ndastro-api tools."""
    for tool in (
        get_glossary,
        get_life_stages,
        get_event_timing,
        get_difficult_periods,
        calibrate_with_known_events,
        correct_birth_datetime,
        find_auspicious_dates,
    ):
        mcp.add_tool(tool)
