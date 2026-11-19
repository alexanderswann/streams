"""Study areas + shared settings.

An AREA (env var AREA, default "la") is one map: its own UTM zone, home point, ranges and data sources. Each area is
split into range boxes (env var REGION, default the area's first range) that meet edge to edge. Per-area data lives
in data/raw/<area>/<range>, data/derived/<area>/<range> and output/<area>/; files shared by an area's ranges in
data/raw/<area>/_shared; national downloads reused by every area (NHD HU4 GeoPackages, PRISM) in data/raw/_national.
"""
import os

RES = 10                      # m, USGS 3DEP 1/3 arc-second
TILE = 1500                   # px per download tile (large requests 500 on the server)

# Per area: crs = NAD83 / UTM zone (EPSG code); home = drive-time origin; ranges = {key: dict(label, hu4, bbox)} with
# bbox in that zone's metres and hu4 the NHD 4-digit hydrologic units that cover the box. Boxes of one area must not
# overlap, or streams get drawn twice.
AREAS = {
    "la": dict(
        label="LA mountains", crs=26911,
        # ZIP 90404 (Santa Monica), approximate ZCTA centroid
        home=dict(label="90404 Santa Monica", lon=-118.4735, lat=34.0275),
        ranges={
            "san_gabriel": dict(label="San Gabriel Mountains", hu4=("1807", "1809"),
                                # Tujunga/La Cañada east to Lytle Creek; foothills north to Little Rock / Big Rock
                                bbox=(365000, 3778000, 450000, 3820000)),
            "santa_monica": dict(label="Santa Monica Mountains", hu4=("1807",),
                                 # Point Mugu east to Sepulveda Pass; coast north to the Simi Hills
                                 bbox=(320000, 3764000, 366000, 3782000)),
            "san_bernardino": dict(label="San Bernardino Mountains", hu4=("1807", "1809", "1810"),
                                   # Lytle Creek / Cajon Pass east to Whitewater; foothills north to Deep Creek /
                                   # Holcomb. The west edge meets the San Gabriel box, so Lytle Creek's canyon has no gap
                                   bbox=(450000, 3768000, 532000, 3803000)),
            # Los Padres front ranges, in three boxes that meet edge to edge (and the San Gabriels at x=365000)
            "sespe": dict(label="Sespe, Topatopa & Mt. Pinos", hu4=("1807", "1806", "1803"),
                          # Matilija / Ojai east to the Sespe gorge; Fillmore north to Mt. Pinos, Lockwood, Frazier Park
                          bbox=(275000, 3806000, 326000, 3867000)),
            "piru": dict(label="Piru Creek & Castaic", hu4=("1807", "1809", "1803"),
                         # Lake Piru and Castaic north to Pyramid Lake, Gorman and the Grapevine
                         bbox=(326000, 3807000, 365000, 3859000)),
            "sierra_pelona": dict(label="Sierra Pelona", hu4=("1807", "1809"),
                                  # Bouquet and San Francisquito canyons, Lake Hughes; north of the San Gabriel box
                                  bbox=(365000, 3820000, 383000, 3851000)),
            "san_jacinto": dict(label="San Jacinto Mountains", hu4=("1807", "1810"),
                                # Idyllwild, Fuller Ridge and Snow Creek east to the Palm Springs canyons
                                bbox=(511000, 3717000, 547000, 3757000)),
            "santa_ana_mtns": dict(label="Santa Ana Mountains", hu4=("1807",),
                                   # Black Star / Silverado south to Trabuco, Ortega and Tenaja; kept 4 km off the coast
                                   bbox=(435000, 3707000, 471000, 3752000)),
        }),

    # ---- New areas: DRAFT boxes from lon/lat extents, to be checked against HUC-10 divides before the first run.
    # Home points: the user's ZIPs, at the town centre (rural ZIPs span whole valleys).
    "jackson": dict(
        label="Jackson Hole & Hoback", crs=26912,
        home=dict(label="83001 Jackson (town square; the ZIP spans the valley)", lon=-110.7624, lat=43.4799),
        ranges={
            "teton_snake": dict(label="Tetons & Snake River", hu4=("1704",),
                                # Teton east slope, Jackson Hole, Teton Pass / north Snake River Range
                                bbox=(495000, 4800000, 528000, 4856000)),
            "gros_ventre": dict(label="Gros Ventre", hu4=("1704",),
                                # Gros Ventre River and range, Slide Lake, Flat Creek headwaters
                                bbox=(528000, 4800000, 558000, 4856000)),
            "hoback": dict(label="Hoback & Snake River Canyon", hu4=("1704", "1404"),
                           # Hoback River (Granite, Cliff, Shoal creeks), Hoback Range, Snake River Canyon to Alpine
                           bbox=(495000, 4766000, 558000, 4800000)),
        }),
    "n_georgia": dict(
        label="North Georgia mountains", crs=26917,   # the west boxes reach ~1 degree past zone 17; error < 0.2%
        home=dict(label="30305 Atlanta (Buckhead)", lon=-84.3850, lat=33.8317),
        ranges={
            "cohutta": dict(label="Cohutta, Conasauga & Jacks", hu4=("0315", "0601"),
                            bbox=(137000, 3815000, 193000, 3880000)),
            "blue_ridge": dict(label="Toccoa, Blue Ridge & Chattahoochee headwaters", hu4=("0313", "0601", "0315"),
                               bbox=(193000, 3815000, 252000, 3880000)),
            "rabun": dict(label="Rabun, Chattooga & Tallulah", hu4=("0306", "0601", "0313"),
                          bbox=(252000, 3815000, 309000, 3880000)),
            "hooch_tailwater": dict(label="Chattahoochee tailwater (Buford Dam to Atlanta)", hu4=("0313",),
                                    bbox=(177000, 3744000, 219000, 3790000)),
        }),
    "central_vt": dict(
        label="Central Vermont", crs=26918,
        home=dict(label="05753 Middlebury", lon=-73.1673, lat=44.0153),
        ranges={
            "stowe_lamoille": dict(label="Stowe & upper Lamoille", hu4=("0415",), bbox=(640000, 4913000, 705000, 4937000)),
            "mad_winooski": dict(label="Mad River, Winooski & New Haven River", hu4=("0415",), bbox=(640000, 4880000, 705000, 4913000)),
            "white_river": dict(label="Middlebury River, Breadloaf & White River", hu4=("0108", "0415"),
                                bbox=(640000, 4845000, 705000, 4880000)),
        }),
    "ne_ct": dict(
        label="Northeastern Connecticut", crs=26918,   # straddles the 18N / 19N line at 72 W
        home=dict(label="06281 Woodstock", lon=-71.9740, lat=41.9480),
        ranges={
            "natchaug": dict(label="Natchaug, Fenton & Willimantic", hu4=("0110", "0108"),
                             bbox=(719000, 4603000, 745000, 4661000)),
            "quinebaug": dict(label="Quinebaug, Five Mile & Moosup", hu4=("0110", "0109"),
                              bbox=(745000, 4603000, 772000, 4661000)),
        }),
    "lexington_va": dict(
        label="Lexington, Virginia", crs=26917,
        home=dict(label="24450 Lexington", lon=-79.4428, lat=37.7840),
        ranges={
            "maury_goshen": dict(label="Maury River, Goshen Pass & Buffalo Creek", hu4=("0208",),
                                 bbox=(609000, 4156000, 641000, 4214000)),
            "blue_ridge_va": dict(label="Blue Ridge: St. Mary's, Irish Creek & South River", hu4=("0208", "0207"),
                                  bbox=(641000, 4156000, 673000, 4214000)),
        }),
}

AREA = os.environ.get("AREA", "la")
if AREA not in AREAS:
    raise SystemExit(f"AREA={AREA!r} is not one of {', '.join(AREAS)}")
A = AREAS[AREA]
AREA_LABEL = A["label"]
EPSG = A["crs"]
CRS = f"EPSG:{EPSG}"
HOME = A["home"]
REGIONS = A["ranges"]

REGION = os.environ.get("REGION", next(iter(REGIONS)))
if REGION not in REGIONS:
    raise SystemExit(f"REGION={REGION!r} is not a range of AREA={AREA} ({', '.join(REGIONS)})")
LABEL = REGIONS[REGION]["label"]
HU4 = REGIONS[REGION]["hu4"]
XMIN, YMIN, XMAX, YMAX = REGIONS[REGION]["bbox"]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NATIONAL = f"{ROOT}/data/raw/_national"         # NHD HU4 downloads, PRISM: reused by every area
RAW_ROOT = f"{ROOT}/data/raw/{AREA}"
DERIVED_ROOT = f"{ROOT}/data/derived/{AREA}"
SHARED = f"{RAW_ROOT}/_shared"                  # shared by this area's ranges (trails, roads, flow, wilderness, ...)
SHARED_DERIVED = f"{DERIVED_ROOT}/_shared"
MAP_OUT = f"{ROOT}/output/{AREA}"               # combined map + exports


def raw_dir(r):
    return f"{RAW_ROOT}/{r}"


def derived_dir(r):
    return f"{DERIVED_ROOT}/{r}"


def out_dir(r):
    return f"{MAP_OUT}/{r}"


RAW, DERIVED, OUT = raw_dir(REGION), derived_dir(REGION), out_dir(REGION)
for d in (NATIONAL, SHARED, SHARED_DERIVED, RAW, DERIVED, OUT):
    os.makedirs(d, exist_ok=True)
