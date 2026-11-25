"""Which names of land holdings the maps print (2026-11-24): never a private individual's.

PAD-US names private land after its owners: "Last, First" on a conservation easement, a family's surname on a parcel
a land trust bought or was given ("Tupper Hill (Ennis)"), a bare surname. The maps print a PAD-US holding's name
only where both hold:
  - the land is held by a public body, a tribe or a non-profit: PAD-US's manager type is federal, state, local, a
    regional district, joint or territorial, tribal, or a non-governmental organization; not an easement (that is
    private land, named for its owner); not land PAD-US designates as private ("Private Conservation" and the like)
    unless a non-profit manages it (a land trust's own preserve). Where PAD-US doesn't know the manager (most of
    Connecticut), the name itself has to say a public body holds it ("Natchaug State Forest", "Milton Town Forest");
  - the name reads as a place's: it begins or ends with a place word (Forest, Preserve, Lake, Wildlife Management
    Area, Road...: "Lake George", "Jenks Swamp", not "Coon Mountain Moon", a place with its seller's surname after
    it), as does each part of it after a slash or a dash unless it's an organization's initials, and it isn't a
    person's "Last, First". Words in brackets are left out (a parcel's former owner). Parcel words (Tract, Farm,
    Lands, Estates, Property...) don't count as place words: they usually follow the owner's or seller's surname.
Otherwise the map gives the land's status alone ("No Public Access"). The same rules for every area, from PAD-US's own
fields; a public place named after a person ("John Muir Wilderness") keeps its name.
Used by 11_context.py (the access flags and the restricted-access layer) and maplakes.py (a lake's land line, from
05d_lakes.py's PAD-US label: that label has the manager's name but not the holding's kind, so there an easement is
told by its name)."""
import re

PUBLIC_TYPES = ("Federal", "State", "Local Government", "Regional Agency Special District", "Joint", "Territorial")
NONPROFIT = "Non-Governmental Organization"
# a place word: land units, water, landforms, roads, public works (not parcel words: see above); a public body's
# "County Lands" is a place too
WORDS = (r"forests?|woods?|woodlands?|parks?|parkway|preserves?|reserves?|reservations?|sanctuary|santuary|refuges?|"
         r"wilderness|wildlife|management|natural|nature|recreation(?:al)?|conservation|areas?|units?|corridor|sites?|"
         r"lakes?|ponds?|rivers?|brooks?|creeks?|runs?|streams?|springs?|swamps?|marsh(?:es)?|bogs?|fens?|meadows?|"
         r"wetlands?|floodplain|flood plain|confluence|headwaters|watersheds?|reservoirs?|dams?|basin|channel|wash|"
         r"mountains?|mount|mt|hills?|ridges?|notch|gap|gorge|ravine|canyon|falls|islands?|beach(?:es)?|points?|shores?|"
         r"shoreline|lakeshore|riverfront|waterfront|bay|cove|harbou?r|inlet|valley|hollow|glen|groves?|flats?|plains?|"
         r"barrens|highlands?|uplands?|ledges?|rocks?|bluffs?|knobs?|peaks?|summit|slopes?|trails?|trailhead|greenways?|"
         r"greenspace|open space|commons?|green|access|landing|launch|ferry|hatchery|range|game|camps?|campground|"
         r"centers?|county|city|town|township|borough|village|state|national|federal|municipal|public|memorial|"
         r"battlefield|fort|station|base|school|college|university|cemetery|canal|mill|furnace|road|rd|street|avenue|"
         r"ave|drive|lane|court|highway|hwy|route|pike|turnpike|boulevard|"
         r"(?:county|city|town|township|borough|village|state|municipal|public) lands?")
PLACE = re.compile(rf"(?i)\b({WORDS})\b")
PLACE_START = re.compile(rf"(?i)^({WORDS})\b")
PLACE_END = re.compile(rf"(?i)\b({WORDS})$")
TAIL = re.compile(r"(?:\s+(?:#?\d+[A-Za-z]?|[IVX]+|[A-Z]{1,6}))+$")    # "2", "IV", "NY", "#052" after the name
# the name itself says a public body holds the land (for holdings whose manager PAD-US doesn't know)
PUBLIC_NAME = re.compile(r"(?i)\b(state|national|federal|commonwealth|county|town|township|borough|village|city|"
                         r"municipal|public|wildlife management area|game lands?)\b")
ACRONYM = re.compile(r"^[A-Z]{2,6}$")                       # TNC, MCLT: an organization's initials
BRACKETS = re.compile(r"\s*\([^)]*\)")
PARTS = re.compile(r"\s*/\s*|\s+[-–]\s*|\s*[-–]\s+")       # "A / B", "A - B", "A- B" (not "Ti-Hague")
EASEMENT = re.compile(r"(?i)\beasements?\b|\bCE\b|conservation restriction")
SHORE = " (its shore; PAD-US leaves out the water)"          # 05d_lakes.py's note on a lake's label
UNKNOWN = "PAD-US land, manager unknown"                     # 05d_lakes.py's label when PAD-US knows neither


def place_name(name):
    """The name as a map may print it (bracketed words left out), or None when it doesn't read as a place's: it has
    to begin or end with a place word ("Lake George", "Jenks Swamp"), so a place with a surname after it ("Coon
    Mountain Moon", a parcel named for its seller) doesn't, and neither does any part after a slash or a dash."""
    if not isinstance(name, str):
        return None
    n = re.sub(r"\s+", " ", BRACKETS.sub("", name)).strip(" -–/,")
    if not n or not PLACE.search(n):
        return None
    head = n.split(",")[0]
    if "," in n and len(head.split()) <= 2 and not PLACE.search(head):      # "Last, First", "Last, First & First"
        return None
    for part in PARTS.split(n):
        p = TAIL.sub("", part).strip()
        if part and not ACRONYM.match(part) and not (PLACE_START.search(p) or PLACE_END.search(p)):
            return None
    return n


def _held_openly(manager_type, designation):
    """True / False: the manager type says a public body, a tribe or a non-profit holds the land; None: unknown."""
    if not isinstance(manager_type, str) or manager_type in ("Unknown", ""):
        return None
    nonprofit = manager_type == NONPROFIT
    if isinstance(designation, str) and designation.startswith("Private") and not nonprofit:
        return False                                         # private land a public body manages
    return manager_type in PUBLIC_TYPES or nonprofit or re.search(r"(?i)tribal|indian|native", manager_type) is not None


def holding_name(name, kind, manager_type, designation=None):
    """The name a map prints for a PAD-US holding (FeatClass, MngTp_Desc, DesTp_Desc), or None: its status alone."""
    if kind == "Easement" or (isinstance(name, str) and EASEMENT.search(name)):
        return None
    held = _held_openly(manager_type, designation)
    if held is False:
        return None
    n = place_name(name)
    if n is None or (held is None and not PUBLIC_NAME.search(n)):
        return None
    return n


def lake_land(label):
    """05d_lakes.py's land label as a lake's popup prints it: "<manager>: <unit>" keeps the unit only where
    holding_name's rules allow, as far as the label tells them (the manager's name, PAD-US's Mang_Name; no holding
    kind: an easement by its name); a unit alone (PAD-US doesn't know the manager) stays only when its name says a
    public body holds it, else it reads "PAD-US land, manager unknown"; a manager alone stays."""
    if not isinstance(label, str):
        return label
    shore = SHORE if label.endswith(SHORE) else ""
    core = label[:len(label) - len(shore)]
    if core == UNKNOWN or core in ("Private", "Joint", "Unknown"):
        return label
    if ": " in core:
        manager, unit = core.split(": ", 1)
        mtype = ("Private" if manager == "Private" else NONPROFIT if manager == NONPROFIT
                 else "Unknown" if re.match(r"(?i)unknown$|other$", manager) else "State")   # an agency: public
        n = holding_name(unit, None, mtype)
        return (f"{manager}: {n}" if n else manager + (" (easement)" if EASEMENT.search(unit) else "")) + shore
    n = holding_name(core, None, None)                       # a unit alone, its manager unknown
    if n is not None:
        return n + shore
    # a manager's name alone ("City Land", "Other or Unknown State Land") reads as a public body's: kept
    return (core if PUBLIC_NAME.search(core) and not EASEMENT.search(core) and place_name(core) == core else UNKNOWN) + shore
