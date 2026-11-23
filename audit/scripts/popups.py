"""Every value a stream popup states, parsed back out of the published map3d_data.js into one table per area.

    from popups import reaches
    df = reaches("la")            # GeoDataFrame in the area's UTM zone, one row per drawn stream feature
Columns (metric, as the pipeline keeps them; the maps show imperial):
  layer       'streams' (drawn by default) or 'streams_lake' (lines inside lakes, drawn when Lakes is off)
  name, drainage, fork, order, fish
  flow_class  year-round / usually flows / seasonal / mostly dry / reservoir, or None where the popup shows NHD's class
  flow_shown  the text the map shows ('summer: year-round', 'NHD perennial', ...)
  nhd_class   NHD's class as the popup quotes it (perennial, intermittent, ephemeral, unmapped, other)
  typ_cfs, drought_cfs, pct_flowing, flow_src ('TNC' / 'NHDPlus x gauges'), scaled (taken from the creek below)
  rule        why the class differs from the model's ('bare channel', 'gauge', 'tailwater', 'below <dam>', '')
  km2, elev_m, grad_pct
  drive_min, drive_mi, park, bike_min, bike_check, hike_min
  sun_h, shade_pct, canopy_pct, aspect, air_f, water_f, water_pm_f, water_basis, tailwater
  heat_factor (the heat gate's multiplier, 1 where none), trout (text), no_trout (a no-trout sample is the record),
  flags, burn, lat, lon, len_m
"""
import os, re, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from common import *

NUM = r"(-?\d[\d,]*(?:\.\d+)?)"


def _f(m, i=1):
    return float(m.group(i).replace(",", "")) if m else np.nan


def parse(p):
    out = {}
    fl = p.get("fl") or ""
    out["flow_shown"] = fl
    out["flow_class"] = fl[8:] if fl.startswith("summer: ") else None
    dq = p.get("dq") or ""
    m = re.search(r"NHD: (\w+)", dq)
    out["nhd_class"] = m.group(1) if m else (fl[4:] if fl.startswith("NHD ") else None)
    m = re.search(rf"low flow about {NUM} cfs in a typical July–October, {NUM} cfs in a drought year", dq)
    out["typ_cfs"], out["drought_cfs"] = _f(m, 1), _f(m, 2)
    m = re.search(rf"kept flowing {NUM}% of summers since (\d+)", dq)
    out["pct_flowing"] = _f(m, 1)
    out["flow_src"] = "TNC" if "TNC Natural Flows" in dq else ("NHDPlus x gauges" if "NHDPlus mean flow" in dq else None)
    out["scaled"] = "scaled from the creek below" in dq
    rule = ""
    if "no green along the channel" in dq:
        rule = "bare channel"
    elif "its releases keep it flowing" in dq:
        rule = "tailwater"
    elif re.search(r"gauge|USGS", dq):
        rule = "gauge"
    elif "releases set the flow" in dq:
        rule = "below dam"
    out["rule"] = rule
    acc = p.get("acc") or ""
    m = re.search(rf"Drive {NUM} min \({NUM} mi\)", acc)
    out["drive_min"], out["drive_mi"] = _f(m, 1), _f(m, 2)
    m = re.search(r"park at (.*?)(?: → |$)", acc)
    out["park"] = m.group(1) if m else None
    m = re.search(rf"bike {NUM} min", acc)
    out["bike_min"] = _f(m)
    out["bike_check"] = "double-check bike access" in acc
    m = re.search(rf"hike {NUM} min", acc)
    out["hike_min"] = _f(m)
    out["acc_text"] = acc
    sun = p.get("sun") or ""
    m = re.search(rf"{NUM} h direct sun mid-July \({NUM}% shaded by terrain\)", sun)
    out["sun_h"], out["shade_pct"] = _f(m, 1), _f(m, 2)
    m = re.search(rf"tree canopy {NUM}%", sun)
    out["canopy_pct"] = _f(m)
    m = re.search(r"slope faces ([\w/ ]+?)(?: · |$)", sun)
    out["aspect"] = m.group(1) if m else None
    m = re.search(rf"August air averages {NUM} °F", sun)
    out["air_f"] = _f(m)
    m = re.search(rf"summer water about {NUM} °F \(estimated from (.*?), ± {NUM} °F\)", sun)
    out["water_f"], out["water_pm_f"] = _f(m, 1), _f(m, 3)
    out["water_basis"] = m.group(2) if m else None
    out["tailwater"] = "tailwater below" in sun
    m = re.search(rf"fish score × {NUM}", p.get("ht") or "")
    out["heat_factor"] = _f(m) if m else 1.0
    tr = p.get("tr") or ""
    out["trout"] = tr
    out["no_trout"] = bool(tr) and "no trout" in tr.lower() and not re.search(
        r"wild|stocked|Heritage|Trout water|trout stream|patch|sighting|survey \d+: \w+ Trout|: (rainbow|brook|brown)", tr)
    out["flags"], out["burn"] = p.get("flags") or "", p.get("burn") or ""
    return out


def reaches(area, site_dir=None, layers=("streams", "streams_lake")):
    import geopandas as gpd
    parts = []
    for lay in layers:
        g = streams_gdf(area, lay, site_dir)
        if not len(g):
            continue
        extra = pd.DataFrame([parse(p) for p in g.drop(columns="geometry").to_dict("records")], index=g.index)
        g = g.rename(columns={"n": "name", "d": "drainage", "k": "fork", "o": "order", "fs": "fish", "a": "km2",
                              "el": "elev_m", "gr": "grad_pct", "y": "lat", "x": "lon"})
        g = pd.concat([g[["name", "drainage", "fork", "order", "fish", "km2", "elev_m", "grad_pct", "lat", "lon", "geometry"]], extra], axis=1)
        g.insert(0, "layer", lay)
        parts.append(g)
    df = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), geometry="geometry", crs=epsg(area))
    df["len_m"] = df.length
    df.insert(0, "area", area)
    return df


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    for a in sys.argv[1:] or NAMES:
        df = reaches(a)
        d = df[df.layer == "streams"]
        w = d.len_m
        print(f"{a:15s} n={len(d):6d} mi={w.sum()/MI:8.0f}  parsed: flow_class {d.flow_class.notna().mean():.3f} typ_cfs {d.typ_cfs.notna().mean():.3f} "
              f"drive {d.drive_min.notna().mean():.3f} hike {d.hike_min.notna().mean():.3f} sun {d.sun_h.notna().mean():.3f} "
              f"canopy {d.canopy_pct.notna().mean():.3f} water {d.water_f.notna().mean():.3f} air {d.air_f.notna().mean():.3f}")
