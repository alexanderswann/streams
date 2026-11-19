"""Study areas + shared settings, UTM 11N. Pick the region with the REGION env var (default san_gabriel)."""
import os

CRS = "EPSG:26911"          # NAD83 / UTM zone 11N (meters)
RES = 10                      # m, USGS 3DEP 1/3 arc-second
TILE = 1500                   # px per download tile (large requests 500 on the server)

# bbox in UTM 11N metres; hu4 = NHD 4-digit hydrologic units that cover the box
REGIONS = {
    "san_gabriel": dict(label="San Gabriel Mountains", hu4=("1807", "1809"),
                        # Tujunga/La Cañada east to Lytle Creek; foothills north to Little Rock / Big Rock
                        bbox=(365000, 3778000, 450000, 3820000)),
    "santa_monica": dict(label="Santa Monica Mountains", hu4=("1807",),
                         # Point Mugu east to Sepulveda Pass; coast north to the Simi Hills
                         bbox=(320000, 3764000, 366000, 3782000)),
    "san_bernardino": dict(label="San Bernardino Mountains", hu4=("1807", "1809", "1810"),
                           # Lytle Creek / Cajon Pass east to Whitewater; foothills north to Deep Creek / Holcomb.
                           # The west edge meets the San Gabriel box, so Lytle Creek's canyon has no gap
                           bbox=(450000, 3768000, 532000, 3803000)),
    # Los Padres front ranges, in three boxes that meet edge to edge (and the San Gabriels at x=365000)
    "sespe": dict(label="Sespe, Topatopa & Mt. Pinos", hu4=("1807", "1806", "1803"),
                  # Matilija / Ojai east to the Sespe gorge; Fillmore north to Mt. Pinos, Lockwood and Frazier Park
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
}
REGION = os.environ.get("REGION", "san_gabriel")
LABEL = REGIONS[REGION]["label"]
HU4 = REGIONS[REGION]["hu4"]
XMIN, YMIN, XMAX, YMAX = REGIONS[REGION]["bbox"]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = f"{ROOT}/data/raw/{REGION}"
DERIVED = f"{ROOT}/data/derived/{REGION}"
OUT = f"{ROOT}/output/{REGION}"
SHARED = f"{ROOT}/data/raw/_shared"   # NHD HU4 downloads, reused across regions
MAP_OUT = f"{ROOT}/output"            # combined map + exports
for d in (RAW, DERIVED, OUT, SHARED):
    os.makedirs(d, exist_ok=True)

# Trip origin for drive times: ZIP 90404 (Santa Monica), approximate ZCTA centroid
HOME = dict(label="90404 Santa Monica", lon=-118.4735, lat=34.0275)
