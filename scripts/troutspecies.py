"""Which trout species a trout record or a designated trout water names, for the maps' species filter (the user,
2026-11-25: a "Species" choice beside the fish score and the drainage; "never imply a species the data doesn't name").

named(text) reads the words the pipeline already writes and the popups show: a record's label (troutdata.py, CDFW's
surveys and iNaturalist's sightings in 11_context.py) or a water's designation. A species counts only where the text
names it:
  - "<kind> trout", one kind or a list of them: "wild brook trout (51)", "brown trout, rainbow trout",
    "rainbow, brook and brown trout", "(mixed brook/brown trout)", "(brook, rainbow trout)", "Coastal Rainbow Trout",
    "snake river fine-spotted cutthroat trout", "lake trout";
  - cutthroat by itself: Wyoming's "snake river cutthroat", "Native Snake River Cutthroat water";
  - counts before the kind (Pennsylvania's stocking: "(450 brown, 2,050 rainbow, 20 golden)");
  - Vermont's stocking codes: BKT, BNT, RBT, LAT (and BRT);
  - a scientific name, where iNaturalist gave no common one ("oncorhynchus mykiss irideus").
Not counted: a hybrid ("tiger trout", "splake"), steelhead, Pennsylvania's "golden" (golden rainbow trout) and
California's golden trout, bull trout, whitefish, salmon: none is one of the five, and none is read as one. "trout" alone
("stocked with trout") names no species. A water a source lists for wild brook trout (troutdata.py's wild_brook: a brook
trout patch, Vermont's catchments with wild brook trout or mixed wild trout) names brook trout: 11_context.py adds it.
"""
import re

SPECIES = ("brook", "brown", "rainbow", "cutthroat", "lake")     # the maps' choices, in their order
NAMES = {"brook": "brook trout", "brown": "brown trout", "rainbow": "rainbow trout", "cutthroat": "cutthroat trout",
         "lake": "lake trout"}
CODE = {"brook": "B", "brown": "N", "rainbow": "R", "cutthroat": "C", "lake": "L"}   # the pages' "sp" (06_map.py)

_KIND = r"(?:brook|brown|rainbow|cutthroat|lake|tiger|golden|bull)"
_LIST = re.compile(rf"(?i)\b({_KIND}(?:\s*(?:,|/|&|\band\b|\bor\b)\s*{_KIND})*)\s+trout\b")
_COUNTED = re.compile(r"(?i)\b\d[\d,]*\s+(brook|brown|rainbow|lake)\b(?!\s+trout)")
_CUTT = re.compile(r"(?i)\bcutthroat\b")
_VT = {"BKT": "brook", "BNT": "brown", "BRT": "brown", "RBT": "rainbow", "LAT": "lake"}
_VT_RE = re.compile(r"\b(BKT|BNT|BRT|RBT|LAT)\b")
_SCI = {"salvelinus fontinalis": "brook", "salmo trutta": "brown", "oncorhynchus mykiss": "rainbow",
        "oncorhynchus clarkii": "cutthroat", "oncorhynchus virginalis": "cutthroat", "oncorhynchus lewisi": "cutthroat",
        "oncorhynchus henshawi": "cutthroat", "salvelinus namaycush": "lake"}
_SCI_RE = re.compile(r"(?i)\b(" + "|".join(_SCI) + r")\b")


def named(text):
    """The species of SPECIES a record's label or a water's designation names (a set; empty when it names none)."""
    if not isinstance(text, str) or not text:
        return set()
    out = set()
    for m in _LIST.finditer(text):
        out |= {w.lower() for w in re.findall(rf"(?i){_KIND}", m.group(1))}
    out |= {m.group(1).lower() for m in _COUNTED.finditer(text)}
    if _CUTT.search(text):
        out.add("cutthroat")
    out |= {_VT[m.group(1)] for m in _VT_RE.finditer(text)}
    out |= {_SCI[m.group(1).lower()] for m in _SCI_RE.finditer(text)}
    return out & set(SPECIES)


def ordered(spp):
    """Species in the maps' order."""
    return [s for s in SPECIES if s in spp]
