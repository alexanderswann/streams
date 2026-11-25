"""The data sources that exist only for some places, and where each one covers (2026-11-23).

Every other source the pipeline reads is national (3DEP, NHD, NHDPlus, WBD, PRISM, WQP, NLCD, Sentinel-2, NIFC, PAD-US,
OSM, iNaturalist, GBIF, GNIS by state). A source here is on for an area when the area's outline meets its coverage:
  states  the area reaches into one of these states (derive.states: the TIGER state outlines, a sliver of 0.1 km2 counts)
  boxes   and, where given, the outline meets one of these lon/lat rectangles (w, s, e, n): a park, a county, a forest,
          a trail corridor or one lake. They are rough and drawn generously: a source switched on where it has
          nothing finds nothing, one switched off loses its data. The source registry (B13) replaces them with the
          units' own outlines.
  hand    not worked out from the outline yet: on only where config.py lists it (late_summer_green: the climate test
          that decides it is the new-area plan's B7).
00_area.py works out each area's list (derive.sources) and writes it to data/derived/<area>/_shared/area.json. An area
whose config entry lists sources by hand keeps that list: the 12 maps of 2026-11-22 do, and 00_area.py prints how
the worked-out list differs (the agenda of B2, which switches them over once the differences are measured).

HAND below holds the 12 maps' other per-area tables as they stood on 2026-11-22 (the states whose GNIS falls 02f
reads, the depth-survey adapters lake_bathymetry.py runs, the states whose lake lists lakesources.py reads), so that
the change to worked-out values alters no input on those maps; a new area takes the worked-out values. pick() is the
one place that chooses.
"""

# ---- area-specific sources: name -> what it is, the steps that read it, its coverage ----
_EBTJV = ("ME", "NH", "VT", "MA", "CT", "RI", "NY", "NJ", "PA", "DE", "MD", "VA", "WV", "NC", "SC", "GA", "TN", "KY", "OH")
SOURCES = {
    "cdfw_pad": dict(what="CDFW Passage Assessment Database natural barriers", steps="05_score", states=("CA",)),
    "tnc_flows": dict(what="The Nature Conservancy's California Natural Flows model", steps="02b, 05b", states=("CA",)),
    "cdfw_trout": dict(what="CDFW trout surveys, stocking and Wild / Heritage Trout Waters", steps="11_context",
                       states=("CA",)),
    "cal_fire": dict(what="CAL FIRE historic fire perimeters", steps="11_context", states=("CA",)),
    "cpad": dict(what="California Protected Areas Database access", steps="11_context", states=("CA",)),
    "cdec": dict(what="CDEC gauges", steps="11_context", states=("CA",)),
    "ca_closures": dict(what="Caltrans and county road closures", steps="07_road_closures", states=("CA",)),
    "pct": dict(what="the Pacific Crest Trail layer (no step tests it: 02c_pct.py runs where config gives long_trail)",
                steps="", states=("CA", "OR", "WA")),
    "la_trail_layers": dict(what="NPS Santa Monica Mountains, State Parks and LA County Eaton Fire trail layers",
                            steps="02d, 02e", states=("CA",), boxes=((-119.10, 33.70, -117.60, 34.85),)),
    "late_summer_green": dict(what="Sentinel-2 greenness along each channel in late summer", steps="02g, 05b",
                              hand=True),
    "ct_trout": dict(what="Connecticut DEEP trout surveys, stocking and trout waters", steps="troutdata", states=("CT",)),
    "vt_trout": dict(what="Vermont F&W trout data", steps="troutdata", states=("VT",)),
    "va_trout": dict(what="Virginia DWR trout data", steps="troutdata", states=("VA",)),
    "ga_trout": dict(what="Georgia DNR trout data", steps="troutdata", states=("GA",)),
    "wy_trout": dict(what="Wyoming Game & Fish trout data", steps="troutdata", states=("WY",)),
    "pa_trout": dict(what="PFBC trout data", steps="troutdata", states=("PA",)),
    "de_trout": dict(what="Delaware DNREC trout data", steps="troutdata", states=("DE",)),
    "id_trout": dict(what="Idaho Fish & Game's Yellowstone cutthroat trout streams (StreamNet)", steps="troutdata",
                     states=("ID",)),
    "nc_trout": dict(what="North Carolina WRC's mountain trout waters", steps="troutdata", states=("NC",)),
    "tn_trout": dict(what="Tennessee WRA's stocking sites and fish samples", steps="troutdata", states=("TN",)),
    "ny_trout": dict(what="New York DEC trout streams and classes", steps="troutdata", states=("NY",),
                     terms="DEC ArcGIS: secondary distribution not allowed; the user asked DEC for permission "
                           "(2026-11-22), the Adirondack pages keep the layers meanwhile"),
    # Great Smoky Mountains National Park (83.04-84.02 W, 35.43-35.79 N)
    "grsm_trout": dict(what="Great Smoky Mountains NP's trout distribution", steps="troutdata",
                       boxes=((-84.05, 35.40, -83.00, 35.82),)),
    "grsm_falls": dict(what="Great Smoky Mountains NP's waterfalls layer", steps="02f",
                       boxes=((-84.05, 35.40, -83.00, 35.82),)),
    "grsm_roads": dict(what="Great Smoky Mountains NP road closures", steps="07_road_closures",
                       boxes=((-84.05, 35.40, -83.00, 35.82),)),
    # the Qualla Boundary at Cherokee and the Snowbird tract
    "ebci_trout": dict(what="the Eastern Band of Cherokee's tribal fishing zones", steps="troutdata", states=("NC",),
                       boxes=((-83.45, 35.38, -83.15, 35.62), (-83.92, 35.26, -83.76, 35.38))),
    "tu_brook_trout": dict(what="Trout Unlimited / EBTJV wild brook trout patches (the eastern brook trout's range)",
                           steps="troutdata", states=_EBTJV),
    # Grand Teton National Park; Teton County, Wyoming
    "grte_roads": dict(what="Grand Teton NP road status", steps="07_road_closures", states=("WY",),
                       boxes=((-110.97, 43.52, -110.40, 44.12),)),
    "teton_county": dict(what="Teton County, Wyoming road closures", steps="07_road_closures", states=("WY",),
                         boxes=((-111.06, 43.20, -109.90, 44.67),)),
    "gdot_511": dict(what="Georgia DOT 511 closures", steps="07_road_closures", states=("GA",)),
    "vdot_511": dict(what="Virginia DOT 511 closures", steps="07_road_closures", states=("VA",)),
    "id_511": dict(what="Idaho 511 closures", steps="07_road_closures", states=("ID",)),
    "ncdot_tims": dict(what="North Carolina DOT TIMS closures", steps="07_road_closures", states=("NC",)),
    "tdot_smartway": dict(what="Tennessee DOT SmartWay closures", steps="07_road_closures", states=("TN",)),
    "ne_compass": dict(what="New England Compass (511) closures for Maine, New Hampshire and Vermont",
                       steps="07_road_closures", states=("ME", "NH", "VT")),
    # the Blue Ridge Parkway, Rockfish Gap to Cherokee: its Virginia and North Carolina stretches
    "blri_roads": dict(what="Blue Ridge Parkway closures (milepost sections)", steps="07_road_closures",
                       boxes=((-80.95, 36.54, -78.80, 38.06), (-83.36, 35.40, -80.88, 36.62))),
    # the Cherokee National Forest, Tennessee's side of the southern Appalachians
    "cherokee_nf": dict(what="Cherokee National Forest road closures", steps="07_road_closures", states=("TN",),
                        boxes=((-85.00, 34.98, -81.65, 36.62),)),
    # New York's Forest Preserve: the Adirondack and Catskill parks
    "nys_forest_preserve": dict(what="New York DEC lands (Forest Preserve, no-bike areas)", steps="geomatch",
                                states=("NY",), boxes=((-75.45, 43.00, -73.25, 44.90), (-74.80, 41.75, -74.00, 42.40)),
                                terms="DEC ArcGIS: secondary distribution not allowed; the user asked DEC for permission "
                                      "(2026-11-22)"),
}

# ---- lake depth surveys read by lake_bathymetry.py, by the adapter's name ----
BATHYMETRY = {
    "ct_contours": dict(what="Connecticut DEEP lake depth contours", states=("CT",)),
    "vt_soundings": dict(what="Vermont DEC lake soundings", states=("VT",)),
    "noaa_champlain": dict(what="NOAA chart soundings of Lake Champlain", boxes=((-73.46, 43.53, -73.04, 45.10),)),
    "usgs_little_rock": dict(what="USGS survey of Little Rock Reservoir (LA)", boxes=((-118.06, 34.46, -117.98, 34.50),)),
    "dcnr_bands": dict(what="Pennsylvania DCNR depth bands", states=("PA",)),
    "usgs_chambers": dict(what="USGS survey of Chambers Lake (PA)", boxes=((-75.88, 40.01, -75.82, 40.05),)),
}

# ---- the states whose own lake lists lakesources.py reads (access, rules, designations; listed trout lakes) ----
LAKE_LISTS = {"CT": "CT DEEP boat launches, management areas, lake rules and stocked trout lakes",
              "VT": "Vermont F&W lake access and rules",
              "VA": "Virginia DWR public fishing lakes",
              "PA": "PFBC lake access, rules and stocked lakes",
              "NY": "New York's lake lists on data.ny.gov (stocking, fishing guide, facilities)",
              "NC": "NCWRC boating access, public fishing areas and mountain trout impoundments; with Tennessee's",
              "TN": "TWRA access sites, TVA ramps and the NC-TN reciprocal licence; with North Carolina's"}

# ---- the 12 maps' per-area values as they stood on 2026-11-22 (see the docstring) ----
_TWELVE = ("la", "jackson", "n_georgia", "central_vt", "ne_ct", "lexington_va", "se_pa", "smokies", "adk_high_peaks",
           "adk_northwest", "adk_southwest", "adk_southeast")
HAND = {
    # states each area's boxes reach into, for GNIS (02f_known_falls.py's STATES until 2026-11-23)
    "gnis_states": {"la": ("CA",), "jackson": ("WY", "ID"), "n_georgia": ("GA", "NC", "SC", "TN"),
                    "central_vt": ("VT",), "ne_ct": ("CT", "MA", "RI"), "lexington_va": ("VA", "WV"),
                    "se_pa": ("PA", "DE", "MD", "NJ"), "smokies": ("TN", "NC"),
                    # the Adirondack maps' east edges cross Lake Champlain to the Vermont shore
                    "adk_high_peaks": ("NY", "VT"), "adk_northwest": ("NY",), "adk_southwest": ("NY",),
                    "adk_southeast": ("NY", "VT")},
    # lake_bathymetry.py's ADAPTERS until 2026-11-23
    "bathymetry": {"ne_ct": ("ct_contours",), "central_vt": ("vt_soundings", "noaa_champlain"),
                   "la": ("usgs_little_rock",), "se_pa": ("dcnr_bands", "usgs_chambers"),
                   "adk_high_peaks": ("noaa_champlain",), "adk_southeast": ("noaa_champlain",),
                   "jackson": (), "n_georgia": (), "lexington_va": (), "smokies": (), "adk_northwest": (),
                   "adk_southwest": ()},
    # the states whose lake lists lakesources.py read for each map (its branches by area name until 2026-11-23)
    "lake_states": {"ne_ct": ("CT",), "central_vt": ("VT",), "lexington_va": ("VA",), "se_pa": ("PA",),
                    "smokies": ("NC", "TN"), "adk_high_peaks": ("NY",), "adk_northwest": ("NY",),
                    "adk_southwest": ("NY",), "adk_southeast": ("NY",), "la": (), "jackson": (), "n_georgia": ()},
}
assert all(set(t) == set(_TWELVE) for t in HAND.values())


def pick(kind, area, derived):
    """The value an area uses: the hand value for the 12 maps of 2026-11-22, else the worked-out one."""
    return tuple(HAND[kind][area]) if area in HAND[kind] else tuple(derived)


def _meets(entry, states, boxes_hit):
    if entry.get("hand"):
        return False
    if "states" in entry and not set(entry["states"]) & set(states):
        return False
    if "boxes" in entry and not boxes_hit(entry["boxes"]):
        return False
    return True


def covering(table, states, boxes_hit):
    """The names in `table` (SOURCES or BATHYMETRY) whose coverage the area meets, in the table's order.
    states: the area's states; boxes_hit(boxes) -> True when the area's outline meets one of the lon/lat boxes."""
    return tuple(n for n, e in table.items() if _meets(e, states, boxes_hit))
