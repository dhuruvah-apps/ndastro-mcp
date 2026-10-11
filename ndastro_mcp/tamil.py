"""Tamil names for planets, rasis, nakshatras, and dasa levels."""

from ndastro_engine.enums import Nakshatras, Planets, Rasis

# Planet and rasi names match ndastro-api's locales/ta/LC_MESSAGES/messages.po.
PLANETS: dict[Planets, str] = {
    Planets.ASCENDANT: "லக்னம்",
    Planets.SUN: "சூரியன்",
    Planets.MOON: "சந்திரன்",
    Planets.MARS: "செவ்வாய்",
    Planets.MERCURY: "புதன்",
    Planets.JUPITER: "குரு",
    Planets.VENUS: "சுக்ரன்",
    Planets.SATURN: "சனி",
    Planets.RAHU: "ராகு",
    Planets.KETHU: "கேது",
}

RASIS: dict[Rasis, str] = {
    Rasis.ARIES: "மேஷம்",
    Rasis.TAURUS: "ரிஷபம்",
    Rasis.GEMINI: "மிதுனம்",
    Rasis.CANCER: "கடகம்",
    Rasis.LEO: "சிம்மம்",
    Rasis.VIRGO: "கன்னி",
    Rasis.LIBRA: "துலாம்",
    Rasis.SCORPIO: "விருச்சிகம்",
    Rasis.SAGITTARIUS: "தனுசு",
    Rasis.CAPRICORN: "மகரம்",
    Rasis.AQUARIUS: "கும்பம்",
    Rasis.PISCES: "மீனம்",
}

NAKSHATRAS: dict[Nakshatras, str] = {
    Nakshatras.ASWINNI: "அஸ்வினி",
    Nakshatras.BHARANI: "பரணி",
    Nakshatras.KAARTHIKAI: "கார்த்திகை",
    Nakshatras.ROGHINI: "ரோகிணி",
    Nakshatras.MIRUGASIRISAM: "மிருகசீரிஷம்",
    Nakshatras.THIRUVAATHIRAI: "திருவாதிரை",
    Nakshatras.PUNARPOOSAM: "புனர்பூசம்",
    Nakshatras.POOSAM: "பூசம்",
    Nakshatras.AAYILYAM: "ஆயில்யம்",
    Nakshatras.MAGAM: "மகம்",
    Nakshatras.POORAM: "பூரம்",
    Nakshatras.UTHTHIRAM: "உத்திரம்",
    Nakshatras.ASTHTHAM: "அஸ்தம்",
    Nakshatras.CHITHTHIRAI: "சித்திரை",
    Nakshatras.SUVAATHI: "சுவாதி",
    Nakshatras.VISAAGAM: "விசாகம்",
    Nakshatras.ANUSHAM: "அனுஷம்",
    Nakshatras.KETTAI: "கேட்டை",
    Nakshatras.MOOLAM: "மூலம்",
    Nakshatras.POORAADAM: "பூராடம்",
    Nakshatras.UTHTHIRAADAM: "உத்திராடம்",
    Nakshatras.THIRUVONAM: "திருவோணம்",
    Nakshatras.AVITTAM: "அவிட்டம்",
    Nakshatras.SHATHAYAM: "சதயம்",
    Nakshatras.POORATTAATHI: "பூரட்டாதி",
    Nakshatras.UTHTHIRATTAATHI: "உத்திரட்டாதி",
    Nakshatras.REVATHI: "ரேவதி",
}

DASA_LEVELS: dict[str, str] = {
    "maha": "தசை",
    "antara": "புக்தி",
    "pratyantara": "அந்தரம்",
    "sookshma": "சூட்சுமம்",
}

PLANET_INPUTS: dict[str, Planets] = {name: planet for planet, name in PLANETS.items()} | {"சுக்கிரன்": Planets.VENUS}
