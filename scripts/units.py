"""Imperial units for everything the maps, popups, profiles and GPX files show: feet, miles, square miles, acres
and degrees Fahrenheit (the owner's choice, 2026-11-19). The pipeline itself keeps working in metres, km, km2, ha and
degrees C, and its files keep those units (columns named *_m, *_km, *_km2, *_ha); only what a person reads is
converted, here. The pages' own scripts (map_drainages.js, map3d.html, profiles.html, 13_overview.py and
14_portable.py) carry the same few conversions in JavaScript."""
import math
import re

FT_PER_M = 3.28084
MI_PER_KM = 0.621371
SQMI_PER_KM2 = 0.386102
ACRES_PER_HA = 2.47105


def _bad(v):
    return v is None or (isinstance(v, float) and math.isnan(v))


def ft(m, nd=0):
    """Metres as feet: '6,037 ft'."""
    return "?" if _bad(m) else f"{float(m) * FT_PER_M:,.{nd}f} ft"


def mi(km):
    """Kilometres as miles: '0.4 mi', '9.6 mi', '73 mi'."""
    if _bad(km):
        return "?"
    v = float(km) * MI_PER_KM
    return f"{v:,.0f} mi" if v >= 10 else f"{v:.1f} mi"


def sqmi(km2):
    """Square kilometres as square miles: '0.56 sq mi', '5.2 sq mi', '188 sq mi'."""
    if _bad(km2):
        return "?"
    v = float(km2) * SQMI_PER_KM2
    return f"{v:,.0f} sq mi" if v >= 100 else f"{v:.1f} sq mi" if v >= 1 else f"{v:.2f} sq mi"


def acres(ha):
    """Hectares as acres: '1.5 acres', '71 acres', '26,831 acres'."""
    if _bad(ha):
        return "?"
    v = float(ha) * ACRES_PER_HA
    return f"{v:,.0f} acres" if v >= 10 else f"{v:.1f} acres"


def degf(c, nd=0):
    """A temperature in degrees C as degrees F: '64 °F'."""
    return "?" if _bad(c) else f"{float(c) * 9 / 5 + 32:.{nd}f} °F"


def degf_diff(dc, nd=0):
    """A temperature difference (an error, a spread) in degrees C as degrees F: 3 -> '5 °F'."""
    return "?" if _bad(dc) else f"{float(dc) * 9 / 5:.{nd}f} °F"


# Text quoted from a source (CDFW's surveyors write "2.5 meters wide by 2.5 feet high", a site is named "3m high
# Bedrock barrier") keeps its words; each metric figure gets the imperial one in brackets after it:
# "2.5 meters [8.2 ft] wide", "Jump height 1.98 m [6.5 ft]", "approx. 5700m [3.5 mi] upstream". A figure that
# already has an imperial one beside it ("60 miles (97 km)", "3 m (10 ft)") is left alone, and so is text done before.
_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_METRIC = re.compile(rf"(?<![\w.,])({_NUM})(?:\s?(?:-|–|to)\s?({_NUM}))?\s?-?"
                     r"(km|kilomet(?:er|re)s?|cm|centimet(?:er|re)s?|mm|millimet(?:er|re)s?|met(?:er|re)s?|m|°\s?C)"
                     r"(?![\w²³/])")
_IMP = r"(?:ft|feet|foot|mi|miles?|in|inch(?:es)?|yards?|yds?|°\s?F)\b\.?"
_IMP_BEFORE = re.compile(rf"{_IMP}\s*[(\[]\s*(?:about |approx\.? |~)?$")
_IMP_AFTER = re.compile(rf"\s*[(\[]\s*(?:about |approx\.? |~)?[\d.,]+(?:\s?(?:-|–|to)\s?[\d.,]+)?\s?-?{_IMP}")


def _imperial(vals, unit):
    """'[8.2 ft]', '[3.5 mi]', '[16 in]', '[10–16 ft]', '[64 °F]' for metric figures in the unit named."""
    u = unit.lower().replace(" ", "")
    if u.startswith("°"):
        return "[" + "–".join(f"{v * 9 / 5 + 32:.0f}" for v in vals) + " °F]"
    metres = [v * (1000 if u.startswith("k") else 0.01 if u.startswith("c") else 0.001 if u.startswith("mm") or
                   u.startswith("milli") else 1) for v in vals]
    top = max(metres)
    to, name = (1 / 1609.344, "mi") if top >= 1000 else (1 / 0.0254, "in") if top < 0.3 else (FT_PER_M, "ft")
    num = lambda x: f"{x:.1f}".rstrip("0").rstrip(".") if x < 10 else f"{x:,.0f}"
    return "[" + "–".join(num(m * to) for m in metres) + f" {name}]"


def imperial_text(s):
    """Source text with the imperial figure in brackets after each metric one; anything not a string comes back as is."""
    if not isinstance(s, str) or not s:
        return s

    def add(m):
        if _IMP_BEFORE.search(m.string[:m.start()]) or _IMP_AFTER.match(m.string, m.end()):
            return m.group(0)
        vals = [float(g.replace(",", "")) for g in (m.group(1), m.group(2)) if g]
        return f"{m.group(0)} {_imperial(vals, m.group(3))}"
    return _METRIC.sub(add, s)
