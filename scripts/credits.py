"""Where the maps' data come from: the credits page (credits.html at the site root), and the check that every download
has an entry.

SOURCES is the one list of sources: what each is, what the maps use it for, who publishes it, its licence or terms and
the credit it asks for, the maps it covers, and the web addresses it is read from. 13_overview.py writes the page with
write() beside the map of all areas (output/credits.html; publish_site.sh copies it to the site root); the maps' one-line
credits link to it (06_map.py, 14_portable.py), as do the map of all areas and the creek profiles. When a step starts
reading a new source, add it here; the build names any that is missing:
  unlisted()  web addresses written in scripts/ (the downloads, which all go through netfetch.py, and the pages' map
              tiles) that no source's `hosts` and no LINKS entry cover. 13_overview.py prints a NOTE for each, and
              audit/scripts/credits_hosts.py lists them and fails
  guides()    the waterfall guides named in data/known_falls_curated*.csv, with the points each gave; a guide not in
              GUIDES is listed with no terms, and gets a NOTE too
Terms are as each publisher's own pages state them (read on TERMS_READ); where they state none, the entry says so.
Maps: "all", area keys (fnmatch patterns: "adk_*"), "src:<key>" (an area's config.py source) or "cfg:<key>" (a config.py
setting an area has, as clip_state). Hidden areas (config.py hidden=True) and the sources only they use are left off
the page, as everywhere else on the site; they come back with the flag.
"""
import datetime as dt, fnmatch, glob, html, os, re
import pandas as pd
from config import AREAS, ROOT
from flowlib import GREEN_YEARS     # the late summers of Sentinel-2 greenness (02g_greenness.py)
from accesspoints import LEFT_OUT as _ACC_OUT     # access sources left out for their terms (accesspoints.py)
_acc = lambda key, text: "" if key in _ACC_OUT else text

HERE = os.path.dirname(os.path.abspath(__file__))
TERMS_READ = dt.date(2026, 11, 24)      # when the publishers' terms pages were read for the entries below
RAW = f"{ROOT}/data/raw"

USGS_TERMS = "https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits"
NPS_TERMS = "https://www.nps.gov/aboutus/disclaimer.htm"
USFS_TERMS = "https://data.fs.usda.gov/geodata/edw/datasets.php"
ODBL = "https://opendatacommons.org/licenses/odbl/1-0/"
CC_BY = "https://creativecommons.org/licenses/by/4.0/"
PUBLIC_USGS = "Public domain: USGS data may be used freely, and USGS asks to be credited."
GOV_NO_TERMS = "Published by a federal agency; its pages state no licence, only a disclaimer."
NPS_PUBLIC = "Generally public domain (NPS); a citation of the Park Service as the source is appreciated."
NONE_STATED = "No licence or terms stated on the data's own pages."

GROUPS = [
    ("streams", "Streams, drainages and creek profiles",
     "The stream lines and their names, sizes and colours, the drainage outlines, the drops found in the terrain and "
     "the creek profiles."),
    ("flow", "Summer flow", "Which creeks run in summer: the flow classes (year-round, usually flows, seasonal...), "
     "the flow figures and the gauges."),
    ("temp", "Water temperature, shade and heat", "The summer water-temperature estimate, the shade on each creek and "
     "the heat limit in the fish score."),
    ("trout", "Trout waters and trout records", "Designated and documented trout water, and the surveys, stocking and "
     "sightings named in the popups. The fish score draws on these and on most of the sections here."),
    ("lakes", "Lakes, depths and lake access", "Lake outlines, levels, depth contours, fish and the ways onto them."),
    ("falls", "Waterfalls and swimming holes", "The known falls and swimming holes; the drops the terrain shows are "
     "under Streams."),
    ("trails", "Trails, roads, parking and fishing access", "Trails and fire roads, mountain bike access, the long trail, "
     "roads and parking, and the agencies' fishing access sites and boat ramps."),
    ("closures", "Road closures and approach times", "Closed roads, and the drive and walk times to each creek."),
    ("fires", "Fires", "Fire perimeters, burn severity and debris-flow hazard."),
    ("land", "Land, access and protected habitat", "Who owns the land, where public access is restricted, wilderness, "
     "and critical habitat."),
    ("cell", "Cell coverage", "Where each mobile carrier reports 4G or 5G signal outdoors, to know where to save a "
     "map before heading out."),
    ("base", "Base maps, terrain and place labels", "The maps under the data: light gray, topographic and satellite "
     "views, terrain shading, the 3D terrain and the place and road labels."),
    ("software", "Software", "The code that draws the maps (not data, listed for its licences). The site serves its "
     "own copy of each, with its licence, so a map saved on a phone works with no connection."),
]


def _span(years):
    """2022–2024 for years that run on, else 2021, 2023."""
    y = sorted(years)
    return f"{y[0]}–{y[-1]}" if len(y) > 1 and y == list(range(y[0], y[-1] + 1)) else ", ".join(map(str, y))


def _years(years):
    y = [str(v) for v in sorted(years)]
    return y[0] if len(y) == 1 else ", ".join(y[:-1]) + " and " + y[-1]


def S(key, group, name, by, url, what, use, maps, terms, terms_url=None, credit=None, note=None, hosts=(), also=(),
      accessed=(), odbl=False):
    """odbl: the source is under the ODbL, so what the maps make from it is offered under the ODbL too (_odbl())."""
    return dict(key=key, group=group, name=name, by=by, url=url, what=what, use=use, maps=maps, terms=terms,
                terms_url=terms_url, credit=credit, note=note, hosts=tuple(hosts), also=tuple(also),
                accessed=tuple(accessed), odbl=odbl)


# The user's decisions on sources' terms, so that no later session asks again:
# - 2026-11-25 (relayed word for word by the overview session):
#   - Esri's base maps: "Keep as is" (licensed under Esri's Master License Agreement; drawn with no account or key).
#   - ODbL: "Add the ODbL notice". The data the maps make from OpenStreetMap, and LA's flow figures made from TNC's
#     California Natural Flows Database, are offered under the ODbL (_odbl(): the page's "Data shared under the ODbL").
#   - Trail Finder, The Outbound, komoot and freearenas.com (Lareau Swim Hole, Darby Wind Cave Falls, Wigwam Falls, the
#     Jennings Creek swimming holes): "Keep them", credited and linked as before.
#   - California State Parks: "Keep + credit": named in LA's one-line map credits (06_map.py's LBL["credits"]).
#   - StreamNet: "Keep, and email IDFG": kept and credited; the user writes to Idaho Fish and Game and StreamNet.
#   - NYSDEC (the hidden Adirondack maps): unchanged while the user's own request to DEC is pending.
# - 2026-11-22: the World Waterfall Database and nnywaterfalls.com consented; gawaterfalls.com and the guide sites with
#   no terms on record "Keep as is"; Google and Apple Maps places may be used, looked up by hand and named in each popup.
SOURCES = [
    # ---- streams ----
    S("3dep", "streams", "3D Elevation Program (3DEP), 1/3 arc-second elevation", "U.S. Geological Survey",
      "https://www.usgs.gov/3d-elevation-program",
      "The national elevation model, about 33 ft (10 m) cells, from lidar and older surveys.",
      "Draws every stream: water is routed over this terrain, which gives each creek its path, drainage area, "
      "gradient and order, the drops and possible waterfalls, the creek profiles, the DEM colour relief, sun and "
      "shade on the water, and the walking times.",
      "all", PUBLIC_USGS, USGS_TERMS, "U.S. Geological Survey, 3D Elevation Program",
      hosts=("elevation.nationalmap.gov",), also=("temp", "closures")),
    S("nhd", "streams", "National Hydrography Dataset (NHD), high resolution", "U.S. Geological Survey",
      "https://www.usgs.gov/national-hydrography/national-hydrography-dataset",
      "The national map of streams, rivers, lakes, springs and their names (from GNIS), at 1:24,000 or finer.",
      "Creek names; which creeks NHD maps as year-round or part of the year; where the routing follows mapped "
      "channels and lake outlets; the size floor (named and year-round creeks are drawn smaller); lake outlines, "
      "names, inlets and outlets; springs; mapped waterfalls.",
      "all", PUBLIC_USGS, USGS_TERMS, "U.S. Geological Survey, National Hydrography Dataset",
      hosts=("prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography",), also=("flow", "lakes", "falls")),
    S("nhdplus", "streams", "NHDPlus Version 2", "U.S. Environmental Protection Agency and U.S. Geological Survey",
      "https://www.epa.gov/waterdata/nhdplus-national-hydrography-dataset-plus",
      "The national stream network at 1:100,000 with drainage areas, routing and modelled mean monthly flows (EROM).",
      "The drainage that rivers bring in from beyond a map's edge, lake outlets, which arm a river's name follows, "
      "and outside California the summer flow estimate (EROM's mean flow, scaled by this area's gauges).",
      "all", "Public domain (USGS and EPA data); USGS asks to be credited.", USGS_TERMS,
      hosts=("api.water.usgs.gov",), also=("flow",)),
    S("wbd", "streams", "Watershed Boundary Dataset (WBD)",
      "U.S. Geological Survey and USDA Natural Resources Conservation Service",
      "https://www.usgs.gov/national-hydrography/watershed-boundary-dataset",
      "The national map of hydrologic units, the land that drains to each part of the stream network, nested from "
      "large regions down to small watersheds.",
      "Which of NHD's downloads each map reads: NHD comes in 4-digit hydrologic units, and a map reads those whose "
      "outlines meet its boxes.",
      "all", PUBLIC_USGS, USGS_TERMS, "U.S. Geological Survey, Watershed Boundary Dataset",
      hosts=("hydro.nationalmap.gov/arcgis/rest/services/wbd",)),
    S("nlcd_impervious", "streams", "NLCD 2021 impervious cover, 30 m",
      "U.S. Geological Survey, served by the Multi-Resolution Land Characteristics Consortium (MRLC)",
      "https://www.mrlc.gov/",
      "The National Land Cover Database's share of each 30 m cell covered by roofs, roads and pavement, for 2021.",
      "Creeks a city has put in sewers: an unnamed line NHD doesn't map, through ground 40 % or more paved over, "
      "with hardly any open waterway along it and no trout water near, isn't drawn. Drawn all the same: the outlet "
      "NHD maps from a lake or pond of 2.5 acres or more, and a gap under 1,640 ft (500 m) with the creek drawn "
      "above and below.",
      "all", "Public domain (USGS data); MRLC's service states no fees and no access constraints. USGS asks to be "
      "credited.", USGS_TERMS, "U.S. Geological Survey, National Land Cover Database (NLCD) 2021",
      hosts=("www.mrlc.gov/geoserver/mrlc_download",)),
    S("tiger", "streams", "TIGER/Line state outlines (2024)", "U.S. Census Bureau",
      "https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html",
      "The Census Bureau's boundaries of the states.",
      "Where a map stops at a state line: central Vermont at New York, in Lake Champlain; southeastern Pennsylvania "
      "at New Jersey, in the Delaware.", ["cfg:clip_state"],
      "No licence stated; the Census Bureau asks to be cited as the source.",
      "https://www.census.gov/about/policies/citation.html", "U.S. Census Bureau, TIGER/Line Shapefiles, 2024",
      hosts=("www2.census.gov",)),
    S("tigerweb", "lakes", "TIGERweb counties and towns", "U.S. Census Bureau", "https://tigerweb.geo.census.gov/",
      "The Census Bureau's map service of counties and towns.",
      "The county of each piece of private land on the land-ownership layer, whose popup links to that county's parcel "
      "viewer; and New York's lake stocking lists, which name a town, not a place: a record goes to the lake of its "
      "name in that town.",
      "all", "No licence stated; the Census Bureau asks to be cited as the source.",
      "https://www.census.gov/about/policies/citation.html", "U.S. Census Bureau, TIGERweb",
      hosts=("tigerweb.geo.census.gov",), also=("land",)),

    # ---- summer flow ----
    S("tnc_flows", "flow", "California Natural Flows Database", "The Nature Conservancy",
      "https://rivers.codefornature.org/",
      "Modelled natural (unimpaired) monthly flow for every stream reach in California, 1950 to last month.",
      "The summer flow classes and the flow figures in LA's popups (July to October of recent years).",
      "src:tnc_flows",
      "Open Database License (ODbL): free to use with credit; a database made from it and shared publicly is to be "
      "offered under the ODbL too.", ODBL,
      "Zimmerman, J.K.H., D.M. Carlisle, J.T. May, K.R. Klausmeyer, T.E. Grantham, L.R. Brown and J.K. Howard. "
      "California Unimpaired Flows Database v2.1.2, 2023. The Nature Conservancy, San Francisco, CA. "
      "https://rivers.codefornature.org/",
      hosts=("flow-api.codefornature.org",), accessed=("la/_shared/flow/natural_flows.csv",), odbl=True),
    S("usgs_water", "flow", "Stream gauges (USGS Water Data APIs)", "U.S. Geological Survey",
      "https://waterdata.usgs.gov/",
      "Daily and current streamflow, gauge height and water temperature at USGS gauges, with the daily statistics "
      "for each date.",
      "Checks and scales the summer flow (outside California a year's gauge records scale NHDPlus's mean flows), "
      "marks creeks whose own gauge runs dry, and the gauges layer: today's reading against the usual for the date. "
      "A tap on a gauge asks USGS from your own browser for its latest flow, gauge height and water temperature "
      "(provisional data, subject to revision), for the popup, the trout calendar's \"now\" and My Waters, the "
      "gauges you follow (kept on your device only).",
      "all", "Public domain for the most part (USGS); USGS asks to be credited.", USGS_TERMS,
      "U.S. Geological Survey, Water Data for the Nation",
      hosts=("api.waterdata.usgs.gov", "waterdata.usgs.gov")),
    S("cdec", "flow", "California Data Exchange Center (CDEC)", "California Department of Water Resources",
      "https://cdec.water.ca.gov/",
      "California's real-time and historical river, reservoir and weather stations.",
      "Two Piru Creek gauges in the gauges layer: above Pyramid Lake, and the dam's release to lower Piru Creek.",
      "src:cdec", "No terms on CDEC's pages, which link the Department of Water Resources' Conditions of Use.",
      "https://water.ca.gov/Conditions-of-Use", hosts=("cdec.water.ca.gov",)),
    S("sentinel2", "flow", "Copernicus Sentinel-2 imagery (Level-2A, from Earth Search on AWS)",
      "European Union, Copernicus programme (ESA); the copy on AWS by Element 84",
      "https://registry.opendata.aws/sentinel-2-l2a-cogs/",
      f"Satellite images at 10 m; the maps read their late-summer greenness (NDVI) in {_years(GREEN_YEARS)}.",
      "How green each channel stays in late summer: a bare channel the flow model rates as flowing is marked "
      "near-certainly dry (LA and Jackson, where summer drought browns the slopes).",
      "src:late_summer_green",
      "Free, full and open use under EU law: it may be reproduced, shared, adapted and combined, with the notice "
      "below.", "https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice",
      f"Contains modified Copernicus Sentinel data {_span(GREEN_YEARS)}", hosts=("earth-search.aws.element84.com",)),

    # ---- water temperature, shade, heat ----
    S("prism", "temp", "PRISM climate normals, 1991–2020 (August mean air temperature, 800 m)",
      "PRISM Group, Oregon State University", "https://prism.oregonstate.edu/",
      "Long-term average air temperature on an 800 m grid.",
      "The summer water-temperature estimate (fitted to measured creeks with elevation), and the heat limit that "
      "marks down desert creeks hotter than any trout creek here.",
      "all", "Free to reproduce and distribute; PRISM keeps ownership and asks for the citation below.",
      "https://prism.oregonstate.edu/terms/", "PRISM Group, Oregon State University, https://prism.oregonstate.edu",
      hosts=("prism.oregonstate.edu",), accessed=("_national/prism_tmean_aug_us.zip",)),
    S("wqp", "temp", "Water Quality Portal",
      "National Water Quality Monitoring Council, with USGS and the U.S. Environmental Protection Agency",
      "https://www.waterqualitydata.us/",
      "Water measurements from USGS, EPA and many state, tribal and local agencies.",
      "The measured July–August water temperatures of stream sites that the water-temperature estimate is fitted "
      "to and checked against.",
      "all", "No licence stated on the portal's pages; it asks for the citation below.",
      "https://www.waterqualitydata.us/portal_userguide/",
      "Water Quality Portal. Washington (DC): National Water Quality Monitoring Council, United States Geological "
      "Survey (USGS), Environmental Protection Agency (EPA); 2021. https://doi.org/10.5066/P9QRKUVJ",
      hosts=("www.waterqualitydata.us",)),
    S("tcc", "temp", "Tree canopy cover (NLCD TCC), latest year, 30 m", "USDA Forest Service",
      "https://data.fs.usda.gov/geodata/rastergateway/treecanopycover/",
      "The share of each 30 m cell under tree canopy, mapped from satellite imagery.",
      "Shade on each creek, with the terrain's own shade, in the fish score; the latest year, so recent fires show.",
      "all", GOV_NO_TERMS, USFS_TERMS, hosts=("imagery.geoplatform.gov",)),

    # ---- trout ----
    S("cdfw", "trout", "California Department of Fish and Wildlife (BIOS)",
      "California Department of Fish and Wildlife", "https://wildlife.ca.gov/Data/BIOS",
      "Designated Heritage and Wild Trout Waters, the Heritage and Wild Trout Program's surveys, and trout planting "
      "(stocking) locations.",
      "Trout waters on the map, the surveys (trout found or not) and the last year's stocking in the popups and the "
      "fish score; the public boat launches of its fishing guide (California's boating facility survey) as official fishing access sites and boat ramps (the \"Fishing access & boat ramps\" layer, where routes may start).",
      "src:cdfw_trout", "CC BY 4.0: free to use with credit; BIOS's citation satisfies it.", CC_BY,
      "California Department of Fish and Wildlife, Biogeographic Information and Observation System (BIOS): "
      "Designated Heritage and Wild Trout Waters [ds1356], Planting Location [ds2897], Heritage and Wild Trout "
      "Program data. https://wildlife.ca.gov/Data/BIOS",
      hosts=("services2.arcgis.com/Uq9r85Potqm3MfRV", "wildlife.ca.gov"), also=("trails",)),
    S("ct_deep", "trout", "Connecticut DEEP fisheries data",
      "Connecticut Department of Energy and Environmental Protection",
      "https://portal.ct.gov/deep/fishing",
      "Fish community samples (wild and stocked trout told apart), stocked streams and lakes, fisheries management "
      "areas (Wild Trout and Trout Management Areas), boat launches, and lake depth contours (1959–2002 surveys).",
      "Trout waters and records, the stocked trout lakes, lake access and lake depths; its boat launches as official fishing access sites and boat ramps (the \"Fishing access & boat ramps\" layer, where routes may start).",
      "src:ct_trout",
      "CC0 (no rights reserved) for the management areas, boat launches and depth contours; no licence stated on "
      "the fish samples and stocking layers.", "https://creativecommons.org/publicdomain/zero/1.0/", "CT DEEP",
      hosts=("services1.arcgis.com/FjPcSmEFuDYlIdKC", "portal.ct.gov", "www.ct.gov"), also=("lakes", "trails")),
    S("vt_anr", "trout", "Vermont Fish & Wildlife and Agency of Natural Resources",
      "Vermont Agency of Natural Resources", "https://vtfishandwildlife.com/",
      "Brook trout waters (catchments with wild brook trout), the 2021 stocking list, fishing access areas, "
      "special-regulation lakes, and lake soundings (bathymetry, compiled 2020).",
      "Trout waters and stocking records, lake access and rules, and lake depth contours" + _acc("vtfw", "; its fishing "
      "access areas as official fishing access sites and boat ramps (the \"Fishing access & boat ramps\" layer, where "
      "routes may start)") + ".",
      ["src:vt_trout"] + ([] if "vtfw" in _ACC_OUT else ["adk_high_peaks", "adk_southeast"]),
      _acc("vtfw", "Fishing access areas: Creative Commons Attribution-ShareAlike 4.0 (Vermont Open Geodata Portal): free "
           "to use with credit, and the access points drawn from them are shared under the same licence. ") +
      "No licence stated on the other layers.", None if "vtfw" in _ACC_OUT else "https://creativecommons.org/licenses/by-sa/4.0/",
      "Vermont Agency of Natural Resources, Fish & Wildlife Department",
      hosts=("anrmaps.vermont.gov", "vtfishandwildlife.com"), also=("lakes", "trails")),
    S("va_dwr", "trout", "Virginia Department of Wildlife Resources", "Virginia Department of Wildlife Resources",
      "https://dwr.virginia.gov/",
      "The cold-water stream survey (wild trout streams, classes I–IV), stocked trout reaches and lakes, public "
      "fishing lakes, and the Lake Robertson depth map.",
      "Trout waters and stocking records, lake access and boat rules, Lake Robertson's depth" + _acc("vadwr", "; its "
      "boating access locations as official fishing access sites and boat ramps (the \"Fishing access & boat ramps\" "
      "layer, where routes may start)") + ".",
      "src:va_trout",
      "DWR's GIS data disclaimer: its data \"are available by permission of the Virginia Department of Wildlife "
      "Resources\" and are to be cited as below; no licence stated.", "https://dwr.virginia.gov/gis/gis-data-disclaimer/",
      "Trout Stocked Streams. 2017. Virginia Department of Game and Inland Fisheries." + _acc("vadwr", " Boating Access "
      "Locations. 2026. Virginia Department of Wildlife Resources."),
      hosts=("services.dwr.virginia.gov", "dwr.virginia.gov"), also=("lakes", "trails")),
    S("ga_dnr", "trout", "Georgia DNR Wildlife Resources trout data", "Georgia Department of Natural Resources",
      "https://georgiawildlife.com/fishing/trout",
      "Designated trout streams, recently stocked streams and this year's standardized trout sampling, and the "
      "Wildlife Resources Division's water access points (boat ramps, bank fishing, canoe access).",
      "Trout waters and trout records; the water access points as official fishing access sites and boat ramps (the \"Fishing access & boat ramps\" layer, where routes may start).", "src:ga_trout",
      NONE_STATED, "Georgia Department of Natural Resources, Wildlife Resources Division",
      hosts=("services6.arcgis.com/9QlSLDqa0P1cHLhu", "georgiawildlife.com", "gadnrwrd.maps.arcgis.com"), also=("trails",)),
    S("wgfd", "trout", "Wyoming Game and Fish fishing guides", "Wyoming Game and Fish Department",
      "https://wgfd.wyo.gov/fishing-boating",
      "The fishing guide's streams (ribbon classes and game fish) and lakes (game fish, class, depths), and the "
      "native cutthroat waters of the Cutt-Slam.",
      "Trout waters, wild brook trout water, and the fish, depths and access of Jackson's lakes; the fishing guide's "
      "boat ramps, the Public Access Areas and the float-fishing river access points as "
      "official fishing access sites and boat ramps (the \"Fishing access & boat ramps\" layer, where routes may start).",
      "src:wy_trout", "No licence stated; WGFD's geospatial data page gives a disclaimer only.",
      "https://wgfd.wyo.gov/geospatial-data", "Wyoming Game and Fish Department",
      hosts=("services6.arcgis.com/cWzdqIyxbijuhPLw", "wgfd.wyo.gov"), also=("lakes", "trails")),
    S("streamnet", "trout", "StreamNet fish distribution",
      "Pacific States Marine Fisheries Commission (StreamNet); data from Idaho Department of Fish and Game",
      "https://www.streamnet.org/",
      "Fish distribution by stream from the western states' agencies.",
      "Idaho Fish and Game's Yellowstone cutthroat trout streams on the Idaho side of the Jackson map.",
      "src:id_trout", "No licence on the map service; StreamNet's data use agreements cover its data downloads.",
      "https://www.streamnet.org/resources/exchange-tools/data-agreements/",
      "StreamNet, Pacific States Marine Fisheries Commission; data from Idaho Department of Fish and Game",
      hosts=("gis.psmfc.org",)),
    S("pfbc", "trout", "Pennsylvania Fish and Boat Commission", "Pennsylvania Fish and Boat Commission",
      "https://www.pa.gov/en/agencies/fishandboat.html",
      "Class A wild trout streams, streams with natural trout reproduction, trout special-regulation areas, "
      "stocked trout sections and lakes, lake access points, lake regulations and boating rules, and its lake "
      "survey reports.",
      "Trout waters and stocking records, the stocked trout lakes, lake access, rules and some lake depths and fish.",
      "src:pa_trout",
      "No licence stated on PFBC's map services. Its fishing and boating access areas (PASDA): free to use with credit "
      "to PFBC; a changed copy is to say how it was changed (the map keeps each site's name, water, kind, parking and "
      "page) and not suggest PFBC approved it.", "https://www.pasda.psu.edu/uci/DataSummary.aspx?dataset=984",
      "Pennsylvania Fish and Boat Commission (access areas reduced to the fields the map shows; not reviewed by PFBC)",
      hosts=("fbweb.pa.gov", "conservationexplorer.dcnr.pa.gov", "www.pa.gov", "www.pasda.psu.edu"), also=("lakes", "trails")),
    S("de_dnrec", "trout", "Delaware fishing access (FirstMap)",
      "Delaware Department of Natural Resources and Environmental Control",
      "https://firstmap.delaware.gov/",
      "Delaware's designated trout streams in New Castle County and their fly-fishing-only sections, and its fishing "
      "access sites (boat ramps, piers, canoe launches).",
      "Trout waters on the Delaware side of the southeastern Pennsylvania map; the fishing access sites as "
      "official fishing access sites and boat ramps (the \"Fishing access & boat ramps\" layer, where routes may start).", "src:de_trout",
      "No licence stated; the fishing access item gives an as-is disclaimer only.", None,
      "Delaware Department of Natural Resources and Environmental Control",
      hosts=("enterprise.firstmap.delaware.gov", "dnrec.delaware.gov"), also=("trails",)),
    S("ncwrc", "trout", "North Carolina Wildlife Resources Commission", "North Carolina Wildlife Resources Commission",
      "https://www.ncwildlife.gov/fishing/where-fish/public-mountain-trout-waters",
      "Public Mountain Trout Waters (streams and impoundments, by class), boating access areas and public fishing "
      "areas.",
      "Trout waters and their classes, trout lakes NHD lacks, and lake access; the boating access and public fishing "
      "areas as official fishing access sites and boat ramps (the \"Fishing access & boat ramps\" layer, where routes may start).",
      ["src:nc_trout", "n_georgia"],
      "Boating and fishing areas: free and unrestricted use. Products from the trout waters should cite NCWRC as "
      "below.", None,
      "The source of the North Carolina Wildlife Resources Commission Public Mountain Trout Waters data is North "
      "Carolina Wildlife Resources Commission.",
      hosts=("services1.arcgis.com/YfqBAUM5nWR3yhGP", "www.ncwildlife.gov"), also=("lakes", "trails")),
    S("twra", "trout", "Tennessee Wildlife Resources Agency", "Tennessee Wildlife Resources Agency",
      "https://www.tn.gov/twra.html",
      "Trout stocking sites, wadeable-stream fish samples (1996–2022), brook trout genetics (2016), access sites "
      "and the Calderwood reciprocal fishing area.",
      "Trout records and lake access on the Tennessee side of the Smokies; its boat launches and fishing sites as "
      "official fishing access sites and boat ramps (the \"Fishing access & boat ramps\" layer, where routes may start).", "src:tn_trout",
      "Called \"a public resource of general information\" in TWRA's disclaimer; no licence stated.",
      hosts=("services3.arcgis.com/PWXNAH2YKmZY7lBq", "www.tn.gov"), also=("lakes", "trails")),
    S("grsm", "trout", "Great Smoky Mountains National Park GIS", "National Park Service",
      "https://www.nps.gov/grsm/",
      "The park's trout distribution by stream segment, its waterfalls and its roads.",
      "Trout records and wild brook trout water, the park's waterfalls, and the park roads closures are drawn along.",
      "src:grsm_trout",
      NPS_PUBLIC,
      NPS_TERMS, "National Park Service, Great Smoky Mountains National Park",
      hosts=("services1.arcgis.com/fBc8EJBxQRMcHlei",), also=("falls", "closures")),
    S("ebci", "trout", "Cherokee fishing zones", "Eastern Band of Cherokee Indians", "https://fishcherokee.com/",
      "The tribe's fishing zones: the Raven Fork trophy section and the stocked Enterprise Waters.",
      "Trout waters and the tribal permit each needs.", "src:ebci_trout", NONE_STATED,
      hosts=("services.arcgis.com/IT5YbezrAr6F9SXt",)),
    S("nysdec", "trout", "New York State DEC trout and lands layers",
      "New York State Department of Environmental Conservation", "https://dec.ny.gov/",
      "Trout stream reaches (wild, stocked), waters classed for trout (T) or trout spawning (TS), public fishing "
      "rights along trout streams, and DEC lands.",
      "Trout waters and records, fishing access, and the Forest Preserve units that close trails to bikes.",
      ["src:ny_trout", "src:nys_forest_preserve"],
      "DEC asks to be credited in products made from its data; its layers allow no secondary distribution of the "
      "data without its permission.", None, "New York State Department of Environmental Conservation",
      hosts=("services6.arcgis.com/DZHaqZm9cxOD4CWM",), also=("land",)),
    S("nydata", "trout", "data.ny.gov (Open NY)", "New York State; datasets by the Department of Environmental Conservation",
      "https://data.ny.gov/",
      "DEC's fish stocking lists since 2011, its recommended fishing lakes and ponds, points of interest on DEC "
      "lands, its boat launch list and the Public Fishing Rights parking areas.",
      "Lake stocking records, the lake fishing list and launches; the boat launches, fishing access sites, piers and "
      "fishing rights parking as official fishing access sites and boat ramps (the \"Fishing access & boat ramps\" layer, where routes may start).", ["adk_*"],
      "Open NY Terms of Use.", "https://data.ny.gov/dataset/OPEN-NY-Terms-Of-Use/77gx-ii52",
      hosts=("data.ny.gov", "dec.ny.gov"), also=("lakes", "trails")),
    S("tu_ebtjv", "trout", "Brook trout portfolio (wild brook trout patches)",
      "Trout Unlimited and the Eastern Brook Trout Joint Venture", "https://easternbrooktrout.org/",
      "The latest assessment of wild brook trout patches across the eastern range, Connecticut to Georgia.",
      "Wild brook trout water: trout labels, and the fish score's brook trout sizing.", "src:tu_brook_trout",
      "No licence stated on the map service.", None, "Trout Unlimited, Eastern Brook Trout Joint Venture",
      hosts=("services1.arcgis.com/754BERmVIq3RqSf8",)),
    S("inat", "trout", "iNaturalist", "iNaturalist and its observers", "https://www.inaturalist.org/",
      "Wildlife sightings shared by the public, confirmed by other observers.",
      "Research-grade sightings of rainbow and brown trout (brook and cutthroat trout too in some areas) with an "
      "exact location, as trout records.", "all", "iNaturalist's terms of use apply.",
      "https://www.inaturalist.org/pages/terms", hosts=("api.inaturalist.org",)),

    # ---- lakes ----
    S("lidar", "lakes", "3DEP 1-meter lidar elevation", "U.S. Geological Survey",
      "https://www.usgs.gov/3d-elevation-program",
      "Lidar elevation models at 1 m, each from a dated survey.",
      "Lake outlines and water levels: lidar flattens a lake's surface, so its level cells are the shoreline on the "
      "survey date, and the date is shown.", "all", PUBLIC_USGS, USGS_TERMS,
      "U.S. Geological Survey, 3D Elevation Program",
      hosts=("tnmaccess.nationalmap.gov", "index.nationalmap.gov")),
    S("nla", "lakes", "National Lakes Assessment (2007, 2012, 2017, 2022)", "U.S. Environmental Protection Agency",
      "https://www.epa.gov/national-aquatic-resource-surveys/nla",
      "A national survey of lakes, with a sonar depth at each lake's index site.",
      "Measured lake depths (a natural lake's deepest spot; a lower bound for a reservoir).", "all",
      "EPA geospatial data are public domain by default; EPA asks for the citation below.",
      "https://www.epa.gov/web-policies-and-procedures/epa-disclaimers",
      "U.S. Environmental Protection Agency. National Aquatic Resource Surveys. National Lakes Assessment 2007, "
      "2012, 2017 and 2022 (data and metadata files). "
      "https://www.epa.gov/national-aquatic-resource-surveys/data-national-aquatic-resource-surveys",
      hosts=("www.epa.gov",), accessed=("_national/nla/*",)),
    S("usgs_lakes", "lakes", "USGS lake surveys", "U.S. Geological Survey", "https://www.sciencebase.gov/",
      "The multibeam survey of Little Rock Reservoir (2022, doi:10.5066/P9BQW35E) and the sonar survey of Chambers "
      "Lake (2014).", "Depth contours and depths of those two lakes.", ["la", "se_pa"], PUBLIC_USGS, USGS_TERMS,
      "U.S. Geological Survey", hosts=("www.sciencebase.gov", "pubs.usgs.gov")),
    S("noaa_enc", "lakes", "NOAA electronic navigational charts 14781–14784",
      "NOAA Office of Coast Survey", "https://charts.noaa.gov/ENCs/ENCs.shtml",
      "The Lake Champlain charts, with about 12,000 soundings from the lake surveys of 1870–1939.",
      "Lake Champlain's depth contours, below low lake level (the charts' datum); not for navigation.",
      ["central_vt", "adk_high_peaks", "adk_southeast"],
      "May be used and redistributed without restriction, with NOAA's user agreement shown and NOAA named, so users "
      "know where the charts come from; copies are not official charts.",
      "https://charts.noaa.gov/ENCs/Agreement.shtml", "NOAA Office of Coast Survey, ENC charts 14781–14784",
      hosts=("charts.noaa.gov",)),
    S("dcnr", "lakes", "Pennsylvania DCNR state park lake data",
      "Pennsylvania Department of Conservation and Natural Resources", "https://www.dcnr.pa.gov/",
      "State park boat launches, and the PA Geological Survey's depth maps of state park lakes (Marsh Creek, "
      "Hopewell, Scotts Run).", "Lake access and depth contours.", ["se_pa"], NONE_STATED,
      hosts=("www.gis.dcnr.pa.gov", "maps.dcnr.pa.gov")),
    S("tva", "lakes", "TVA recreation sites", "Tennessee Valley Authority", "https://www.tva.com/",
      "The Tennessee Valley Authority's boat ramps and recreation areas.",
      "Boat ramps on the Smokies' and north Georgia's TVA reservoirs: lake access, and official fishing access sites and boat ramps (the \"Fishing access & boat ramps\" layer, where routes may start).",
      ["smokies", "n_georgia"], NONE_STATED, hosts=("services.arcgis.com/w8auYAijfGK1Mydj", "www.tva.com"), also=("trails",)),
    S("lake_reports", "lakes", "Lake depths and fish surveys from reports",
      "National Park Service, Bureau of Reclamation, Virginia DWR, PA DCNR and PFBC, and published studies",
      "https://irma.nps.gov/DataStore/",
      "Figures read from reports no web service carries: Grand Teton's alpine lake surveys (NPS), sonar surveys of "
      "Jenny and Jackson Lakes (Larsen et al. 2016; McGlue et al. 2023), Reclamation's survey of Lake Arrowhead, "
      "Virginia DWR's Lake Robertson map, DCNR's depth maps and PFBC's lake surveys.",
      "Lake depths and gill-net or trap-net fish records; each lake's popup names its report and links it.",
      ["jackson", "la", "lexington_va", "se_pa"],
      "Figures read from each report and credited to it in the popup.",
      hosts=("irma.nps.gov", "par.nsf.gov", "data.usbr.gov", "dwr.virginia.gov")),
    S("gbif", "lakes", "GBIF occurrence records", "Global Biodiversity Information Facility (GBIF.org)",
      "https://www.gbif.org/",
      "Species records from museums, agencies, surveys and iNaturalist, gathered into one index.",
      "Dated trout, salmon and char records at lakes; each popup names the record's dataset.", "all",
      "GBIF's data user agreement and each dataset's own licence apply.", "https://www.gbif.org/terms/data-user",
      "GBIF.org occurrence records (family Salmonidae); datasets as named in each popup",
      hosts=("api.gbif.org",)),

    # ---- falls ----
    S("gnis", "falls", "Geographic Names Information System (GNIS)", "U.S. Geological Survey",
      "https://www.usgs.gov/tools/geographic-names-information-system-gnis",
      "The official names of US places and features, with positions; the current file and the 2021 archive.",
      "Named falls and rapids (also names since dropped from the current file); NHD's creek and lake names come "
      "from it too.", "all", PUBLIC_USGS, USGS_TERMS, "U.S. Geological Survey, Geographic Names Information System",
      hosts=("prd-tnm.s3.amazonaws.com/StagedProducts", "edits.nationalmap.gov"), also=("streams",)),
    S("wikidata", "falls", "Wikidata", "Wikimedia Foundation and Wikidata's editors", "https://www.wikidata.org/",
      "The free knowledge base behind Wikipedia.",
      "Waterfalls, cascades, rapids, swimming holes and plunge pools with coordinates, and their Wikipedia "
      "articles.", "all", "CC0: its data are free of rights.", "https://www.wikidata.org/wiki/Wikidata:Licensing",
      hosts=("query.wikidata.org", "www.wikidata.org")),
    S("cdfw_pad", "falls", "California Fish Passage Assessment Database",
      "California Department of Fish and Wildlife, with the Pacific States Marine Fisheries Commission",
      "https://wildlife.ca.gov/Data/BIOS",
      "An inventory of fish passage assessments: barriers, natural and built.",
      "Natural barriers (falls, cascades, chutes) as known falls, with their notes.", "src:cdfw_pad",
      "No licence stated on the layer.", None, "California Department of Fish and Wildlife, Passage Assessment "
      "Database [ds69]", hosts=("services2.arcgis.com/Uq9r85Potqm3MfRV",)),
    S("overture", "falls", "Overture Maps places", "Overture Maps Foundation", "https://overturemaps.org/",
      "Open map data from Meta, Microsoft, Foursquare and others.",
      "By a strict rule only: a waterfall listing named falls, cascade or waterfall on a mapped creek, or a named "
      "swimming hole, where no other source has it.", "all",
      "Per provider: CDLA-Permissive-2.0 (most places), Apache-2.0 (Foursquare), CC0 (AllThePlaces).",
      "https://docs.overturemaps.org/attribution/",
      "Overture Maps Foundation, overturemaps.org; includes Foursquare data © 2024 Foursquare Labs, Inc. "
      "(Apache-2.0), transformed to the Overture schema",
      hosts=("overturemaps.org", "docs.overturemaps.org", "cdla.dev", "www.apache.org")),

    # ---- trails, roads, parking ----
    S("osm", "trails", "OpenStreetMap", "OpenStreetMap contributors (OpenStreetMap Foundation)",
      "https://www.openstreetmap.org/",
      "The free, editable map of the world, made by volunteers.",
      "Trails and fire roads, the long trail (Pacific Crest, Appalachian, Long Trail, Horse-Shoe, "
      "Northville–Placid), roads, parking and road conditions, the road network for drive times, gated roads, "
      "stream names NHD lacks, lakes NHD misses, and waterfalls, rapids, creek pools and swimming holes.",
      "all",
      "Open Database License (ODbL): free to use with credit; a database made from it and shared publicly is to be "
      "offered under the ODbL too.", "https://www.openstreetmap.org/copyright", "© OpenStreetMap contributors",
      hosts=("overpass-api.de", "overpass.openstreetmap.fr", "www.openstreetmap.org"),
      also=("streams", "lakes", "falls", "closures"), odbl=True),
    S("usgs_trails", "trails", "National Digital Trails", "U.S. Geological Survey (The National Map)",
      "https://www.usgs.gov/national-digital-trails",
      "Official trails of the Forest Service, Park Service, state parks and counties in one layer.",
      "Official trail names, numbers, managers and allowed uses on OpenStreetMap's trails, and named official "
      "trails OpenStreetMap lacks (dotted: \"agency records only\").", "all", PUBLIC_USGS, USGS_TERMS,
      "U.S. Geological Survey, National Digital Trails", hosts=("partnerships.nationalmap.gov",)),
    S("usfs", "trails", "Forest Service roads, trails and recreation sites", "USDA Forest Service",
      "https://data.fs.usda.gov/geodata/edw/datasets.php",
      "National Forest System roads (open and closed to the public), Motor Vehicle Use Maps, system trails, "
      "trailheads and recreation sites, wilderness areas and land ownership.",
      "Gated fire roads open to walking, road classes and open dates, which trails allow bikes, trailheads, fishing "
      "and boating sites, no bikes in wilderness, and private land inside the forests.", "all", GOV_NO_TERMS, USFS_TERMS,
      "USDA Forest Service", hosts=("apps.fs.usda.gov", "www.fs.usda.gov"), also=("closures", "land")),
    S("csp", "trails", "California State Parks recreational routes", "California State Parks",
      "https://www.parks.ca.gov/?page_id=29682",
      "State Parks' trail routes with their allowed uses, and the Santa Monica Mountains trail inventory State Parks "
      "hosts.", "Which LA trails allow mountain bikes.", "src:la_trail_layers",
      "© California State Parks, all rights reserved: for free personal or public-sector use, credited to California "
      "State Parks, not to be sold or altered; commercial use needs its approval.",
      "https://www.parks.ca.gov/?page_id=29682", "California State Parks",
      note="Named in the LA map's credits line too.", hosts=("services2.arcgis.com/AhxrK3F6WM8ECvDi",)),
    S("nps_poi", "trails", "National Park Service points of interest", "National Park Service",
      "https://www.nps.gov/subjects/digital/nps-data-api.htm",
      "The parks' mapped points of interest, among them boat launches, canoe and kayak access and water access.",
      "The boat launches and water access of the Chattahoochee River National Recreation Area and Grand Teton as "
      "official fishing access sites and boat ramps (the \"Fishing access & boat ramps\" layer, where routes may start).", ["jackson", "n_georgia"], NPS_PUBLIC, NPS_TERMS,
      "National Park Service", hosts=("mapservices.nps.gov", "www.nps.gov")),
    S("idfg", "trails", "Idaho Fish and Game fishing and boating access sites", "Idaho Department of Fish and Game",
      "https://data-idfggis.opendata.arcgis.com/",
      "IDFG's public fishing and boating access sites, with ramps and docks.",
      "The access sites on the Idaho side of the Jackson map (Teton Valley, the Palisades) as "
      "official fishing access sites and boat ramps (the \"Fishing access & boat ramps\" layer, where routes may start).", ["jackson"],
      "No licence stated; a disclaimer leaves it to users to judge the data's fitness and releases IDFG from liability.",
      None, "Idaho Department of Fish and Game, IFWIS", hosts=("gisportal-idfg.idaho.gov", "idfg.idaho.gov")),
    S("scdnr", "trails", "South Carolina public water access", "South Carolina Department of Natural Resources",
      "https://data-scdnr.opendata.arcgis.com/",
      "SCDNR's public water access sites: boat ramps, paddle launches, piers and bank fishing.",
      "The access sites on the South Carolina side of the north Georgia map (the Chattooga, Tugaloo and Hartwell) as "
      "official fishing access sites and boat ramps (the \"Fishing access & boat ramps\" layer, where routes may start).", ["n_georgia"],
      "No licence stated; published \"to promote outdoor recreation\" with an as-is disclaimer.", None,
      "South Carolina Department of Natural Resources", hosts=("services.arcgis.com/acgZYxoN5Oj8pDLa", "www.dnr.sc.gov")),
    S("ma_ofba", "trails", "Massachusetts fishing and boating access sites (MassGIS)",
      "Massachusetts Office of Fishing and Boating Access; MassGIS",
      "https://www.mass.gov/orgs/office-of-fishing-and-boating-access",
      "The state's public fishing and boating access sites.",
      "The access sites on the Massachusetts side of the northeastern Connecticut map as "
      "official fishing access sites and boat ramps (the \"Fishing access & boat ramps\" layer, where routes may start).",
      [] if "maofba" in _ACC_OUT else ["ne_ct"],
      "No licence stated on the item; MassGIS describes its data as public records.", None,
      "MassGIS (Bureau of Geographic Information), Commonwealth of Massachusetts; Office of Fishing and Boating Access",
      hosts=("services1.arcgis.com/hGdibHYSPO59RG1h", "www.mass.gov")),
    S("rigis", "trails", "Rhode Island fishing and boating access (RIGIS)",
      "Rhode Island Department of Environmental Management; RIGIS", "https://www.rigis.org/",
      "Freshwater and saltwater fishing access, small-craft launches and trailer ramps.",
      "The freshwater sites on the Rhode Island side of the northeastern Connecticut map as "
      "official fishing access sites and boat ramps (the \"Fishing access & boat ramps\" layer, where routes may start).", ["ne_ct"],
      "Provided as is; RIGIS asks that both RIGIS and the producer be acknowledged.", None,
      "RIGIS and the Rhode Island Department of Environmental Management",
      hosts=("services2.arcgis.com/S8zZg9pg23JUEexQ", "dem.ri.gov", "www.rigis.org")),

    # ---- closures and approach times ----
    S("caltrans", "closures", "Caltrans Lane Closure System", "California Department of Transportation",
      "https://cwwp2.dot.ca.gov/", "Current and planned closures on California's state highways.",
      "Closures on LA's mountain highways, routed along the road between their ends.", "src:ca_closures",
      "Public domain under Caltrans's Conditions of Use; free of charge.", "https://dot.ca.gov/conditions-of-use",
      hosts=("cwwp2.dot.ca.gov",)),
    S("ca_counties", "closures", "County road closures (Los Angeles, San Bernardino, Riverside, Ventura)",
      "LA County Public Works, San Bernardino County Public Works, Riverside County TLMA, Ventura County Public Works",
      "https://dpw.lacounty.gov/", "Each county's current road closures.", "Closed county roads in the LA mountains.",
      "src:ca_closures", "No licence stated on the feeds.",
      hosts=("dpw.gis.lacounty.gov", "services.arcgis.com/ZZ0KZXZVmgB1v555", "gis.countyofriverside.us",
             "services5.arcgis.com/LU8yNTyyh8FrdvWy")),
    S("eaton", "closures", "Eaton Fire impacted trails and roads", "County of Los Angeles",
      "https://egis-lacounty.hub.arcgis.com/",
      "The county's layer of trails and roads closed after the 2025 Eaton Fire, and its closure areas.",
      "Closed trails and roads, and the fire closure areas layer.", "src:la_trail_layers",
      "LA County's Enterprise GIS Terms of Use apply.", "https://egis-lacounty.hub.arcgis.com/pages/terms-of-use",
      hosts=("services.arcgis.com/RmCCgQtiZLDCtblq",)),
    S("wy_id_roads", "closures", "Teton County road closures and Idaho 511",
      "Teton County (Wyoming) Emergency Management; Idaho Transportation Department",
      "https://511.idaho.gov/", "Teton County's emergency road closures, and Idaho 511's work-zone feed.",
      "Closed roads around Jackson and on the Idaho side (Teton Valley, Palisades).", ["src:teton_county", "src:id_511"],
      "No terms stated on either feed's pages.",
      hosts=("services9.arcgis.com/6ukHJ1QHS9lvQoRO", "511.idaho.gov")),
    S("gdot", "closures", "Georgia 511 events", "Georgia Department of Transportation (published with GEMA/HS)",
      "https://511ga.org/", "Road incidents and closures across Georgia, refreshed every 15 minutes.",
      "Closed roads in the North Georgia mountains.", "src:gdot_511", "No licence stated on the layer.",
      hosts=("services1.arcgis.com/2iUE8l8JKrP2tygQ",)),
    S("ne_compass", "closures", "New England Compass work zones", "Vermont Agency of Transportation (New England Compass)",
      "https://www.newenglandcompass.com/", "Work zones and road closures, seasonal ones included (Lincoln Gap, "
      "Smugglers Notch).", "Closed roads in central Vermont.", "src:ne_compass", "No terms found on its pages.",
      hosts=("api.dx.ne-compass.com",)),
    S("va511", "closures", "Virginia 511", "Virginia Department of Transportation", "https://511.vdot.virginia.gov/",
      "Road incidents and closures across Virginia.", "Closed roads around Lexington.", "src:vdot_511",
      "No terms found on its pages.", hosts=("data.511-atis-ttrip-prod.iteriscloud.com",)),
    S("ncdot_tdot", "closures", "North Carolina and Tennessee road events",
      "North Carolina Department of Transportation (DriveNC); Tennessee Department of Transportation (SmartWay)",
      "https://drivenc.gov/", "Each state's road incidents and closures.", "Closed roads around the Smokies.",
      ["src:ncdot_tims", "src:tdot_smartway"],
      "NCDOT: a disclaimer only, no licence; TDOT: no terms found on its pages.",
      hosts=("services.arcgis.com/NuWFvHYDMVmmxMeM", "spatial.tdot.tn.gov")),
    S("nps_roads", "closures", "National Park road status",
      "National Park Service: Grand Teton, Great Smoky Mountains, Blue Ridge Parkway", "https://www.nps.gov/",
      "The parks' road status layers, alerts and seasonal road pages, and the Parkway's mileposts.",
      "Closed park roads (Teton Park Road, the Smokies' seasonal roads, Parkway sections by milepost).",
      ["src:grte_roads", "src:grsm_roads", "src:blri_roads"],
      NPS_PUBLIC,
      NPS_TERMS, "National Park Service", hosts=("www.nps.gov", "services1.arcgis.com/fBc8EJBxQRMcHlei")),

    # ---- fires ----
    S("calfire", "fires", "California historic fire perimeters", "CAL FIRE Fire and Resource Assessment Program",
      "https://www.fire.ca.gov/",
      "Perimeters of California's fires, published once a year, with the Forest Service, BLM, NPS and USFWS.",
      "Fire perimeters since 2016 on LA's map and in the fish score.", "src:cal_fire",
      "No licence stated on the layer (a disclaimer).", None,
      "CAL FIRE Fire and Resource Assessment Program, with USDA Forest Service Region 5, BLM, NPS and USFWS",
      hosts=("services1.arcgis.com/jUJYIo9tSA7EHvfZ",)),
    S("nifc", "fires", "Interagency fire perimeters (history and this year, WFIGS)",
      "National Interagency Fire Center", "https://data-nifc.opendata.arcgis.com/",
      "Every agency's fire perimeters in one layer, and this year's perimeters as fires burn.",
      "Fire perimeters since 2016 outside California, and this year's everywhere.", "all",
      "No licence stated on the layers (a disclaimer only).", None,
      "National Interagency Fire Center", hosts=("services3.arcgis.com/T4QMspbfLg3qTGWY",)),
    S("baer", "fires", "Burned Area Emergency Response (BAER) soil burn severity", "USDA Forest Service",
      "https://burnseverity.cr.usgs.gov/baer/", "Soil burn severity maps made right after large fires.",
      "Each reach's burn severity in its latest fire, and the outline of a fire missing from the perimeter layers.",
      "all", GOV_NO_TERMS, USFS_TERMS, "USDA Forest Service, BAER", hosts=("apps.fs.usda.gov",)),
    S("usgs_dfh", "fires", "Post-fire debris-flow hazard assessments", "U.S. Geological Survey",
      "https://www.usgs.gov/programs/landslide-hazards/science/scientific-background",
      "Modelled likelihood and size of debris flows below recent burns.",
      "The debris-flow hazard below recent fires in the popups.", "all", PUBLIC_USGS, USGS_TERMS,
      "U.S. Geological Survey", hosts=("services.arcgis.com/v01gqwM5QqNysAAi",)),

    # ---- land ----
    S("padus", "land", "Protected Areas Database of the United States (PAD-US) 4.1",
      "U.S. Geological Survey Gap Analysis Project", "https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-overview",
      "Public lands, tribal land, land trusts' and other non-profits' land and conservation easements, with their "
      "owners, managers, designations and public access. Its easements come mostly from the National Conservation "
      "Easement Database (conservationeasement.us), which holds no landowner information and is kept in PAD-US since "
      "2025.",
      "The land-ownership layer (public, conservation or open, tribal and private land, with each holding's owner and "
      "manager); land with restricted or no public access (outside California); and the land and access around each "
      "lake.",
      "all", PUBLIC_USGS, USGS_TERMS, "U.S. Geological Survey (USGS) Gap Analysis Project (GAP), Protected Areas "
      "Database of the United States (PAD-US) 4.1, https://doi.org/10.5066/P96WBCHS",
      note="The land-ownership layer shows the names PAD-US gives, private owners' and easements' included.",
      hosts=("services.arcgis.com/v01gqwM5QqNysAAi",), also=("lakes",)),
    S("land_contacts", "land", "Land managers' and land trusts' own web pages", "Each agency, tribe and non-profit named",
      "", "The website and main office phone each organization publishes on its own pages, read there by hand "
      "(scripts/land_contacts.csv, with the day each was read).",
      "Whom to ask about a piece of public, tribal or conservation land, in the land-ownership layer's popups.",
      "all", "Each organization's own public contact details, linked to its own pages; nothing is copied from them "
      "but a name, a web address and a phone number.", None, None, hosts=()),
    S("parcel_viewers", "land", "County and state parcel viewers (links only)", "Each county's assessor or GIS office, "
      "or its state", "", "The official online maps where a parcel's owner can be looked up "
      "(scripts/county_viewers.csv).",
      "The popups for private land link to the official parcel viewer of its county, at the spot where the viewer "
      "allows it: the owner's full record is there. The maps read nothing from these viewers.",
      "all", "Links only. Each viewer has its own terms; some restrict copying their data, which the maps don't do.",
      None, None, hosts=()),
    S("cpad", "land", "California Protected Areas Database (CPAD)",
      "CPAD (www.calands.org), served by the California Natural Resources Agency",
      "https://www.calands.org/", "California's parks and open space, with their public access.",
      "Land with restricted or no public access on LA's map.", "src:cpad",
      "No licence stated on the service, which credits CPAD as below.", None,
      "California Protected Areas Database (CPAD), www.calands.org", hosts=("gis.cnra.ca.gov",)),
    S("fws_ch", "land", "Critical habitat for threatened and endangered species", "U.S. Fish and Wildlife Service",
      "https://ecos.fws.gov/ecp/report/critical-habitat",
      "Designated critical habitat (not closure boundaries).",
      "Critical habitat of stream species (fish, mussels, stream amphibians) on the map and in the popups.", "all",
      "Use constraints: none (the layer); its files are not the legal source for the boundaries.",
      "https://www.fws.gov/disclaimer", "U.S. Fish and Wildlife Service",
      hosts=("services.arcgis.com/QVENGdaPbd4LUkLV",)),
    S("nmfs_ch", "land", "Southern steelhead critical habitat", "NOAA Fisheries",
      "https://www.fisheries.noaa.gov/",
      "Designated critical habitat of southern California steelhead.",
      "Steelhead critical habitat on LA's map.", ["la"],
      "Public information that may be copied; NOAA asks for \"Courtesy: National Oceanic and Atmospheric "
      "Administration\".", "https://www.fisheries.noaa.gov/website-policies-and-disclaimers",
      "Courtesy: National Oceanic and Atmospheric Administration", hosts=("services2.arcgis.com/C8EMgrsFcRFL6LrL",)),

    # ---- cell coverage ----
    S("fcc_bdc", "cell", "National Broadband Map: mobile broadband availability (Broadband Data Collection)",
      "Federal Communications Commission (FCC)", "https://broadbandmap.fcc.gov/",
      "Where each facilities-based mobile carrier reports 4G LTE and 5G-NR service, by state, twice a year, as the "
      "FCC's own hexagons (H3 resolution 9: 0.1 km2, about 1,100 ft across), a hexagon counted where its centre lies "
      "in the carrier's coverage. The carriers model it under the FCC's rules: 4G LTE at 5/1 Mbps and 5G-NR at 7/1 "
      "Mbps, each with a 90 % chance at the cell's edge and the cell half loaded, for a phone outdoors. A model, not a "
      "measurement.",
      "The Cell coverage layer: where each carrier, or any, reports 4G LTE or 5G outdoors, and each carrier's signal "
      "at a tapped spot. Read through the FCC's Public Data API, with an FCC account's API token.",
      "all", "The FCC's API Terms of Service: its data may be used to search, display and analyze, as is; content "
      "changed may not be presented as the FCC's own, so the layer says it is derived from FCC data (the hexagons "
      "outlined together, cut at the map's edge).",
      "https://www.fcc.gov/reports-research/developers/api-terms-service",
      "This product uses the FCC Data API but is not endorsed or certified by the FCC.",
      note="Networks most phones can't use are left out of the layer: Southern Linc, Southern Company's network for "
           "utilities and businesses (the FCC's data doesn't mark them, so they are named in 11e_coverage.py).",
      hosts=("bdc.fcc.gov/api/public/map", "broadbandmap.fcc.gov"), accessed=("_national/fcc_bdc/*.json.gz",)),

    # ---- base maps ----
    S("esri", "base", "Esri basemaps: World Light Gray (base and labels), World Hillshade, World Imagery", "Esri",
      "https://www.esri.com/",
      "Esri's online map layers.",
      "The light gray map the maps open on, the place and road labels, the 2D terrain shading and the satellite "
      "view.", "all", "Licensed under Esri's Master License Agreement, as each layer's own page says.",
      "https://www.esri.com/en-us/legal/terms/full-master-agreement",
      "Light gray and labels: Esri, HERE, Garmin, © OpenStreetMap contributors, and the GIS User Community. "
      "Imagery: Esri, Vantor, Earthstar Geographics, and the GIS User Community. Hillshade: Esri, Vantor, Airbus DS, "
      "USGS, NGA, NASA, CGIAR, N Robinson, NCEAS, NLS, OS, NMA, Geodatastyrelsen, Rijkswaterstaat, GSA, Geoland, "
      "FEMA, Intermap, and the GIS user community.", hosts=("server.arcgisonline.com",)),
    S("usgs_topo", "base", "USGS Topo base map", "U.S. Geological Survey (The National Map)",
      "https://www.usgs.gov/programs/national-geospatial-program/national-map",
      "The National Map's topographic base map.",
      "The \"USGS Topo\" base map choice, and the base map a phone keeps for use with no connection.", "all", PUBLIC_USGS,
      USGS_TERMS, "USGS The National Map", hosts=("basemap.nationalmap.gov",)),
    S("opentopomap", "base", "OpenTopoMap", "OpenTopoMap", "https://opentopomap.org/about",
      "A topographic map drawn from OpenStreetMap and SRTM elevation.", "The \"OpenTopoMap\" base map choice (2D).",
      "all", "CC BY-SA 3.0, with the credit below.", "https://creativecommons.org/licenses/by-sa/3.0/",
      "Map data: © OpenStreetMap contributors, SRTM | Map display: © OpenTopoMap (CC-BY-SA)",
      hosts=("*.tile.opentopomap.org", "opentopomap.org")),
    S("terrain_tiles", "base", "Terrain Tiles on AWS", "Mapzen / Tilezen, hosted by the AWS Open Data Program",
      "https://registry.opendata.aws/terrain-tiles/",
      "Elevation tiles of the world, built from the USGS 3DEP, SRTM and GMTED2010 and NOAA's ETOPO1.",
      "The 3D maps' terrain and their terrain shading (a phone keeps them at a low zoom for use with no connection).",
      "all",
      "Each source's own terms (the USGS data are public domain); the tiles ask for the credit below.",
      "https://github.com/tilezen/joerd/blob/master/docs/attribution.md",
      "United States 3DEP (formerly NED) and global GMTED2010 and SRTM terrain data courtesy of the U.S. Geological "
      "Survey; global ETOPO1 terrain data U.S. National Oceanic and Atmospheric Administration",
      hosts=("s3.amazonaws.com/elevation-tiles-prod",)),
    S("fonts", "base", "Noto Sans map fonts (Protomaps basemap assets)", "Protomaps",
      "https://github.com/protomaps/basemaps-assets", "Font glyphs for vector map labels.",
      "The lettering of the 3D maps' labels.", "all", "SIL Open Font License.",
      "https://github.com/protomaps/basemaps-assets", hosts=("protomaps.github.io",)),

    # ---- software ----
    S("leaflet", "software", "Leaflet, and folium which writes the 2D maps",
      "Vladimir Agafonkin and contributors; folium's contributors", "https://leafletjs.com/",
      "The JavaScript map library of the 2D maps, the map of all areas and the one-file map; folium is the Python "
      "library that builds the 2D pages with it.", "Draws the 2D maps.", "all",
      "Leaflet: BSD 2-Clause. folium: MIT.", "https://github.com/Leaflet/Leaflet/blob/main/LICENSE",
      hosts=("cdn.jsdelivr.net/npm/leaflet@*", "cdn.jsdelivr.net/gh/python-visualization/folium/*")),
    S("folium_libs", "software", "jQuery, Bootstrap, Font Awesome and Leaflet plugins",
      "OpenJS Foundation, the Bootstrap authors, Fonticons and the plugins' authors",
      "https://python-visualization.github.io/folium/",
      "The libraries folium's 2D pages load beside Leaflet: jQuery, Bootstrap 5 and Bootstrap 3's glyphicons, Font "
      "Awesome Free, and the Leaflet.awesome-markers, Leaflet.fullscreen and leaflet-measure plugins.",
      "The 2D maps' layer panel and buttons, the markers' icons, the full-screen button and the measuring tool.", "all",
      "MIT, except Bootstrap 3's glyphicons stylesheet (Apache 2.0) and Font Awesome Free (icons CC BY 4.0, fonts SIL "
      "OFL 1.1, code MIT).", "https://fontawesome.com/license/free",
      hosts=("code.jquery.com", "cdn.jsdelivr.net/npm/bootstrap@*", "netdna.bootstrapcdn.com",
             "cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@*", "cdnjs.cloudflare.com/ajax/libs/leaflet.awesome-markers/*",
             "cdn.jsdelivr.net/npm/leaflet.fullscreen@*", "cdn.jsdelivr.net/gh/ljagis/leaflet-measure@*")),
    S("maplibre", "software", "MapLibre GL JS", "MapLibre contributors", "https://maplibre.org/",
      "The JavaScript library of the 3D maps.", "Draws the 3D maps and their terrain.", "all", "BSD 3-Clause.",
      "https://github.com/maplibre/maplibre-gl-js/blob/main/LICENSE.txt", hosts=("unpkg.com/maplibre-gl@*",)),
    S("plotly_pako", "software", "plotly.js and pako", "Plotly, Inc.; Vitaly Puzrin and Andrei Tuputcyn",
      "https://plotly.com/javascript/",
      "plotly.js draws the creek profiles' charts; pako unpacks the one-file map's data.",
      "The creek profiles and the one-file map.", "all", "Both MIT.",
      "https://github.com/plotly/plotly.js/blob/master/LICENSE",
      hosts=("cdn.jsdelivr.net/npm/plotly.js-dist-min@*", "cdn.jsdelivr.net/npm/pako@*")),
]


def _parcel_layers():
    """One entry per official parcel layer 11d_parcels.py reads for owners' names (scripts/parcel_sources.csv)."""
    import csv
    path = os.path.join(HERE, "parcel_sources.csv")
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(ln for ln in f if not ln.startswith("#")))
    where = lambda u: re.sub(r"^https?://", "", u).split("/rest/")[0] if u else ""       # host and service folder
    return [S("parcels_" + r["key"], "land", f"{r['name']} (owners' names)", r["publisher"], r["terms"] or r["url"],
              "Parcel outlines with their owners' names, as the publisher gives them" +
              (f", as of {r['as_of']}" if r["as_of"] else "") + ".",
              "The owners' names of the private parcels beside the map's streams and lakes, in the land-ownership "
              "layer, where each popup names this source and its date. Never a mailing address, phone or e-mail.",
              tuple(m for m in r["maps"].split(";") if m), r["licence"][:1].upper() + r["licence"][1:] + ".",
              r["terms"] or None, f"{r['publisher']}, {r['name']}",
              hosts=tuple(h for h in (where(r["url"]), where(r["table"])) if h))
            for r in rows]


SOURCES += _parcel_layers()

# The waterfall guides of data/known_falls_curated*.csv, by the name their `source` column gives (several joined by
# " · "). card: a source with its own entry above, not repeated in the guides' list.
GUIDES = {
    "OpenStreetMap": dict(card="osm"), "USGS GNIS": dict(card="gnis"), "USGS GNIS (locale)": dict(card="gnis"),
    "Overture Maps": dict(card="overture"), "Great Smoky Mountains NP": dict(card="grsm"),
    "World Waterfall Database": dict(url="https://www.worldwaterfalldatabase.com/",
                                     terms="Used with its owners' consent."),
    "nnywaterfalls.com (David J. Schryver)": dict(url="https://nnywaterfalls.com/",
                                                  terms="Used with its owner's consent."),
    "gawaterfalls.com (Mark Ozboyd)": dict(url="https://www.gawaterfalls.com/",
                                           terms="No licence stated for its list; each fall links its page."),
    "New England Waterfalls": dict(url="https://www.newenglandwaterfalls.com/", by="Greg Parsons",
                                   terms="Its site's notice covers its photographs (not used here); none for its "
                                         "text."),
    "SGM waterfall list (Chester et al. 1999)": dict(url="https://www.tchester.org/sgm/lists/waterfalls.html",
                                                     by="Tom Chester, Jane Strong and Paul Ayers",
                                                     terms="Free to reproduce with credit to the list."),
    "Vermont waterfall inventory (1985)": dict(by="Vermont Agency of Natural Resources, 1985–88 survey",
                                               terms=NONE_STATED),
    "Vermont River Conservancy": dict(url="https://vermontriverconservancy.org/", terms=NONE_STATED),
    "RiverBrain": dict(url="https://riverbrain.com/", terms=NONE_STATED),
    "ncwaterfalls.com": dict(url="https://ncwaterfalls.com/", terms=NONE_STATED),
    "Waterfall Hero": dict(url="https://waterfallhero.blogspot.com/", terms=NONE_STATED),
    # these four: their sites' terms restrict reuse or couldn't be read; kept, credited and linked ("Keep them", the
    # user, 2026-11-25)
    "Trail Finder": dict(url="https://www.trailfinder.info/", by="Upper Valley Trails Alliance",
                         terms_url="https://www.trailfinder.info/terms"),
    "The Outbound": dict(url="https://theoutbound.com/", terms_url="https://theoutbound.com/terms"),
    "komoot": dict(url="https://www.komoot.com/", terms_url="https://www.komoot.com/terms-of-service"),
    "freearenas.com": dict(url="https://freearenas.com/"),
    "Caltech Adventure Hikes guide": dict(by="Caltech Library"),
    "W&L Outing Club": dict(by="Washington and Lee University"),
    "Richmond Land Trust": dict(by="the gorge preserve's owner, named with Apple Maps"),
    "NPS Chattahoochee River NRA map": dict(url="https://www.nps.gov/chat/", by="National Park Service",
                                            terms=NPS_PUBLIC),
    "Blue Ridge Parkway": dict(url="https://www.nps.gov/blri/", by="National Park Service",
                               terms=NPS_PUBLIC),
    "USFS Cherokee NF": dict(url="https://www.fs.usda.gov/cherokee", by="USDA Forest Service", terms=GOV_NO_TERMS),
    "Google Maps": dict(url="https://www.google.com/maps", terms="Single places looked up by hand; each such point "
                        "names Google Maps in its popup."),
    "Apple Maps": dict(url="https://maps.apple.com/", terms="Single places looked up by hand; each such point names "
                       "Apple Maps in its popup."),
}

# Web addresses in scripts/ that are no data source: links in popups and credits, the site itself, placeholders
LINKS = {
    "alexanderswann.github.io": "the site itself", "github.com": "the site's repository (publish_site.sh)",
    "www.google.com": "Google Maps links in popups", "*.wikipedia.org": "Wikipedia links in falls popups",
    "creativecommons.org": "licence links in the credits", "www.w3.org": "XML namespaces", "www.topografix.com": "the GPX namespace",
    "example.invalid": "a placeholder (06_map.py)", "127.0.0.1": "a closed port for offline tests (netfetch.py)",
}


# ---- the check ----
_URL = re.compile(r"""(?:https?|ftp)://[^\s"'`<>()\\]+""")


def _addr(url):
    """'host/path' of a URL as written in the code: no scheme or port, lower case (addresses() has made each {template}
    a *)."""
    host, _, path = url.split("://", 1)[1].partition("/")
    return (host.split(":")[0] + "/" + path).rstrip("/").lower()


def _covers(pattern, addr):
    p = pattern.lower().rstrip("/")
    return fnmatch.fnmatchcase(addr, p) or fnmatch.fnmatchcase(addr, p + "/*")


def addresses(folder=HERE):
    """[(address, file, line)] for every web address written in the scripts and page files of `folder` (not this
    file, which names them all)."""
    out = []
    for p in sorted(glob.glob(os.path.join(folder, "*"))):
        if not p.endswith((".py", ".js", ".html", ".sh", ".css")) or os.path.basename(p) == "credits.py":
            continue
        with open(p, encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                line = re.sub(r"\$?\{[^{}]*\}", "*", line)        # {z}, ${key}, an f-string's {wp.group(1)}
                out += [(_addr(m.group(0)), os.path.basename(p), i) for m in _URL.finditer(line)]
    return out


def unlisted(folder=HERE):
    """[(address, 'file:line')] of the web addresses no source and no LINKS entry covers, the first place each is
    written."""
    pats = [h for s in SOURCES for h in s["hosts"]] + list(LINKS)
    seen = {}
    for a, f, i in addresses(folder):
        if a not in seen and not any(_covers(p, a) for p in pats):
            seen[a] = f"{f}:{i}"
    return sorted(seen.items())


# ---- the page ----
def _visible():
    return [k for k, v in AREAS.items() if not v.get("hidden")]


def areas_of(s):
    """The visible areas a source covers, in config.py's order."""
    want = ["all"] if s["maps"] == "all" else ([s["maps"]] if isinstance(s["maps"], str) else list(s["maps"]))
    keys = []
    for w in want:
        if w == "all":
            keys += list(AREAS)
        elif w.startswith("src:"):
            keys += [k for k, v in AREAS.items() if w[4:] in v.get("sources", ())]
        elif w.startswith("cfg:"):
            keys += [k for k, v in AREAS.items() if v.get(w[4:])]
        else:
            keys += [k for k in AREAS if fnmatch.fnmatchcase(k, w)]
    vis = _visible()
    return [k for k in AREAS if k in keys and k in vis]


def guides(visible_only=True):
    """[(name, points)] of the curated lists' sources, most points first: on the maps shown, or on every map."""
    rows = []
    for p in sorted(glob.glob(f"{ROOT}/data/known_falls_curated*.csv")):
        t = pd.read_csv(p, usecols=["area", "source"])
        rows.append(t[t.area.isin(_visible() if visible_only else list(AREAS))])
    if not rows:
        return []
    src = pd.concat(rows).source.dropna().str.split(" · ").explode().str.strip()
    return list(src[src != ""].value_counts().items())


def _accessed(s):
    paths = [p for g in s["accessed"] for p in glob.glob(f"{RAW}/{g}")]
    return dt.date.fromtimestamp(max(os.path.getmtime(p) for p in paths)) if paths else None


def _text(t):
    """Escaped text with its web addresses as links."""
    out, last = [], 0
    for m in re.finditer(r"https?://[^\s<>\"]+[^\s<>\".,;:)]", t or ""):
        out += [html.escape(t[last:m.start()]), f'<a href="{html.escape(m.group(0))}">{html.escape(m.group(0))}</a>']
        last = m.end()
    return "".join(out) + html.escape((t or "")[last:])


def _day(d):
    return f"{d:%b} {d.day}, {d.year}"


def _maps(keys):
    if keys == _visible():
        return "All maps"
    return " · ".join(f'<a href="{k}/stream_map.html">{html.escape(AREAS[k]["label"])}</a>' for k in keys)


def _short_maps(keys):
    if keys == _visible():
        return "All maps"
    return " · ".join(AREAS[k]["label"] for k in keys) if len(keys) <= 2 else f"{len(keys)} maps"


def _entry(key, name, sub, rows):
    """One source: its name, publisher and maps always shown; the rest on a tap (a <details>)."""
    dl = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows)
    return (f'<details class="src" id="{key}"><summary><span class="nm">{html.escape(name)}</span>'
            f'<span class="sm">{html.escape(sub)}</span></summary><dl>{dl}</dl></details>')


def _card(s, keys):
    host = re.sub(r"^https?://(www\.)?", "", s["url"]).split("/")[0]
    rows = ([("Web", f'<a href="{html.escape(s["url"])}">{html.escape(host)}</a>')] if s["url"] else []) + [
        ("What it is", _text(s["what"])), ("On the maps", _text(s["use"]))]     # (no single address: each its own)
    if s["group"] != "software":
        rows.append(("Maps", _maps(keys)))
    terms = _text(s["terms"]) + (f' <a href="{html.escape(s["terms_url"])}">Terms</a>' if s["terms_url"] else "")
    rows.append(("Licence", terms))
    credit = s["credit"]
    when = _accessed(s)
    if credit or when:
        rows.append(("Credit", _text(credit or "") + (f" (downloaded {_day(when)})" if when else "")))
    if s["note"]:
        rows.append(("Note", _text(s["note"])))
    if s["odbl"]:
        rows.append(("Note", 'What the maps make from it is offered under the ODbL too: '
                             '<a href="#odbl">Data shared under the ODbL</a>.'))
    sub = s["by"] if s["group"] == "software" else f'{s["by"]} · {_short_maps(keys)}'
    return _entry(s["key"], s["name"], sub, rows)


def _guides_card(found):
    items = []
    for name, n in found:
        g = GUIDES.get(name)
        if g is None:
            items.append(f"<li>{html.escape(name)}: {n} point{'s' * (n != 1)}</li>")
            continue
        if g.get("card"):
            continue
        by = f" ({html.escape(g['by'])})" if g.get("by") else ""
        terms = " ".join(t for t in (_text(g.get("terms", "")), f'<a href="{html.escape(g["terms_url"])}">Its terms</a>'
                                     if g.get("terms_url") else "") if t)
        label = (f'<a href="{html.escape(g["url"])}">{html.escape(name)}</a>' if g.get("url") else html.escape(name))
        items.append(f'<li>{label}{by}: {n} point{"s" * (n != 1)}.{" " + terms if terms else ""}</li>')
    if not items:
        return ""
    return (f'<details class="src" id="guides"><summary><span class="nm">Waterfall and swimming-hole guides</span>'
            f'<span class="sm">{len(items)} guidebooks, inventories and guide sites, each credited and linked in its '
            f'points\' popups</span></summary><ul class="guides">{"".join(items)}</ul></details>')


CSS = """
:root { color-scheme: light dark; --bg: #f5f4f1; --card: #fff; --ink: #1d1d1f; --muted: #5d5c58; --line: #e2e0db;
        --accent: #0b5cad; }
@media (prefers-color-scheme: dark) { :root { --bg: #121211; --card: #1c1c1b; --ink: #f0efec; --muted: #aaa9a3;
        --line: #2f2f2c; --accent: #79b0ff; } }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.45 -apple-system, system-ui, sans-serif; }
main { max-width: 760px; margin: 0 auto; padding: 12px 14px 40px; }
a { color: var(--accent); }
.top { display: flex; justify-content: space-between; align-items: center; font-size: 14px; }
#all { font: inherit; font-size: 13px; color: var(--accent); background: var(--card); border: 1px solid var(--line);
       border-radius: 999px; padding: 3px 10px; }
h1 { font-size: 22px; line-height: 1.2; margin: 10px 0 6px; }
.lede { color: var(--muted); margin: 0 0 10px; }
nav { display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0 2px; }
nav a { background: var(--card); border: 1px solid var(--line); border-radius: 999px; padding: 4px 10px;
        font-size: 13px; text-decoration: none; color: var(--ink); }
h2 { font-size: 18px; margin: 24px 0 2px; scroll-margin-top: 8px; }
.gi { color: var(--muted); font-size: 14px; margin: 0 0 6px; }
.src { background: var(--card); border: 1px solid var(--line); border-radius: 12px; margin: 6px 0; scroll-margin-top: 8px; }
.src summary { list-style: none; cursor: pointer; padding: 9px 30px 9px 12px; position: relative; }
.src summary::-webkit-details-marker { display: none; }
.src summary::after { content: "›"; position: absolute; right: 12px; top: 8px; font-size: 20px; color: var(--muted);
                      transition: transform .15s; }
.src[open] summary::after { transform: rotate(90deg); }
.nm { display: block; font-weight: 600; line-height: 1.3; }
.sm { display: block; color: var(--muted); font-size: 13px; margin-top: 1px; }
.src dl, .src .guides { margin: 0; padding: 0 12px 10px; }
dl { display: grid; grid-template-columns: 6.6em 1fr; gap: 4px 10px; font-size: 14px; }
dt { color: var(--muted); font-size: 12.5px; padding-top: 1px; }
dd { margin: 0; overflow-wrap: anywhere; }
@media (max-width: 480px) {      /* a phone: each row one paragraph, its label leading */
  dl { display: block; } dt { display: inline; font-size: 13px; } dt::after { content: ": "; }
  dd { display: inline; } dd::after { content: ""; display: block; margin-bottom: 5px; } }
.guides { padding-left: 30px !important; font-size: 14px; }
.guides li { margin: 4px 0; overflow-wrap: anywhere; }
.also { color: var(--muted); font-size: 13.5px; margin: 6px 0 0; }
.notice { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 10px 12px;
          font-size: 14px; margin: 6px 0; overflow-wrap: anywhere; }
footer { color: var(--muted); font-size: 13px; margin-top: 28px; }
"""

# "Open all" / "Close all", and a link to an entry (#osm, the "also used here" links) opens it
JS = """
const ds = [...document.querySelectorAll("details.src")], all = document.getElementById("all");
all.onclick = () => { const o = ds.some(d => !d.open); ds.forEach(d => d.open = o); all.textContent = o ? "Close all" : "Open all"; };
const go = () => { const t = location.hash && document.getElementById(decodeURIComponent(location.hash.slice(1)));
  if (t && t.tagName === "DETAILS") { t.open = true; t.scrollIntoView(); } };
addEventListener("hashchange", go); go();
"""


def _odbl():
    """The page's ODbL notice (the user's "Add the ODbL notice", 2026-11-25): the data the maps make from a source under
    the ODbL (OpenStreetMap; LA's flows from TNC's database) are offered under the ODbL too, as its share-alike asks. They
    are in the data file each map loads, map3d_data.js beside the map. "" when no map shown uses such a source."""
    used = {s["key"]: s for s in SOURCES if s["odbl"] and areas_of(s)}
    if not used:
        return ""
    made = []
    if "osm" in used:
        made.append("the trails, roads and parking on these maps, and the other features they take from OpenStreetMap "
                    "(the long trails, gated roads, some lakes, falls, swimming holes and creek names), are made from "
                    "OpenStreetMap")
    if "tnc_flows" in used:
        maps = " and ".join(AREAS[k]["label"] for k in areas_of(used["tnc_flows"]))
        made.append(f"the summer flow figures on the {html.escape(maps)} map are made from The Nature Conservancy's "
                    "California Natural Flows Database")
    for k, s in used.items():
        if k not in ("osm", "tnc_flows"):
            made.append(f"the data the maps make from {html.escape(s['name'])} ({html.escape(s['by'])})")
    first = _visible()[0]
    text = "; ".join(made)
    return ('<h2 id="odbl">Data shared under the ODbL</h2><p class="notice">' + text[0].upper() + text[1:]
            + f'. Those sources are under the <a href="{ODBL}">Open Database License (ODbL) 1.0</a>, so these maps offer '
            "the data they made from them under the ODbL too: free to copy, share and adapt under that licence, with "
            "credit to their sources. The data are in the file each map loads, map3d_data.js in the map's folder (for "
            f'example <a href="{first}/map3d_data.js">{first}/map3d_data.js</a>).</p>')


def page():
    groups, toc = [], []
    for g, title, intro in GROUPS:
        body = [_card(s, k) for s, k in ((s, areas_of(s)) for s in SOURCES if s["group"] == g) if k]
        if g == "falls":
            body.append(_guides_card(guides()))
        also = [s for s in SOURCES if g in s["also"] and areas_of(s)]
        if also:
            body.append('<p class="also">Also used here: ' + ", ".join(
                f'<a href="#{s["key"]}">{html.escape(s["name"])}</a>' for s in also) + "</p>")
        if not any(body):
            continue
        toc.append(f'<a href="#{g}">{html.escape(title)}</a>')
        groups.append(f'<h2 id="{g}">{html.escape(title)}</h2><p class="gi">{html.escape(intro)}</p>' + "".join(body))
    odbl = _odbl()
    if odbl:
        toc.append('<a href="#odbl">Data shared under the ODbL</a>')
        groups.append(odbl)
    n = len(_visible())
    n = "one two three four five six seven eight nine ten eleven twelve".split()[n - 1] if 0 < n <= 12 else n
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Stream maps: where the data comes from</title>
<meta name="description" content="Every source the stream maps use: what it is, what the maps use it for, who publishes it, its licence and the credit it asks for.">
<style>{CSS}</style></head>
<body><main>
<div class="top"><a href="index.html">← All maps</a><button id="all" type="button">Open all</button></div>
<h1>Where the data comes from</h1>
<p class="lede">The {n} stream maps are built from public data, a few agencies' own layers and some guidebooks. Here is
every source, grouped by what you see on the map. Tap a source for what it is, what the maps use it for, who publishes
it, its licence or terms, the credit it asks for and the maps it covers. Each map's credits line links here.</p>
<nav>{"".join(toc)}</nav>
{"".join(groups)}
<footer>Updated {_day(dt.date.today())}. Licences and terms as each publisher's own pages stated them on
{_day(TERMS_READ)}; where they state none, the entry says so.</footer>
</main><script>{JS}</script></body></html>
"""


def write(path):
    """Writes the page; prints what it holds and a NOTE for any download address or guide with no entry."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(page())
    shown = [s for s in SOURCES if areas_of(s)]
    print(f"{path}: {len(shown)} of {len(SOURCES)} sources on {len(_visible())} maps "
          f"({len(SOURCES) - len(shown)} only on hidden maps)")
    for a, where in unlisted():
        print(f"NOTE: no credits entry (credits.py) for {a} ({where})")
    for name, n in guides(visible_only=False):
        if name not in GUIDES:
            print(f"NOTE: the waterfall guide {name!r} ({n} points) has no entry in credits.py's GUIDES")
