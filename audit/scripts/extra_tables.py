#!/usr/bin/env python3
"""The smaller tables the report cites, each from the reach tables and the drawn maps of one build:

  table_vs_drawn.csv          miles and fish-60+ miles in the reach table against what the map draws
  trout_found_shown_dry.csv   reaches with trout found since 2016 that the flow class shows mostly dry or seasonal
  perennial_shown_drier.csv   NHD-perennial reaches shown below year-round; "unmapped" reaches; burn without a severity
  trout_records_off_map.csv   trout-found records (not lake records) farther than 500 ft from any drawn line
  fish_score_vs_surveys.csv   does the score, with the trout factor taken out, separate reaches where trout were found
                              from reaches whose latest sample found none (AUC; 0.5 = chance)
  lakes_missing_summary.csv   NHD lakes at each area's own smallest size that the lakes layer lacks
    SITE_DIR=<maps> TABLES_DIR=<reach tables> AUDIT_TABLES=<out> python audit/scripts/extra_tables.py
"""
import sys, os, re
import numpy as np, pandas as pd, geopandas as gpd, shapely
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from popups import reaches
from fish_score_audit import table, terms
from streams_vs_nhd import d8_area_near
from falls_lakes_checks import lakes

YEAR0 = 2016


def auc(pos, neg):
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    pos, neg = pos[~np.isnan(pos)], neg[~np.isnan(neg)]
    if len(pos) < 10 or len(neg) < 10:
        return np.nan
    r = pd.Series(np.concatenate([pos, neg])).rank().to_numpy()
    return (r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def main(areas):
    TV, DRY, PER, OFF, SV, LK = [], [], [], [], [], []
    src = open(f"{SCR}/05d_lakes.py").read()
    mins = {k: float(v) for k, v in re.findall(r'"(\w+)":\s*([\d.]+)', re.search(r"BUILT\s*=\s*\{(.*?)\}", src, re.S).group(1))}
    for a in areas:
        p = table(a)
        if p is None:
            continue
        t = pd.read_csv(p, low_memory=False)
        r = reaches(a)
        d, lk_layer = r[r.layer == "streams"], r[r.layer == "streams_lake"]
        L = t.len_m / MI
        lake = t.water_class.astype(str).eq("reservoir")
        km2 = t.area_full_km2.fillna(t.area_km2)
        found = (t.trout_found >= YEAR0) & (t.trout_absent.isna() | (t.trout_found >= t.trout_absent))
        absent = (t.trout_absent >= YEAR0) & ~found
        ev = t.trout_water.notna() | found
        # ---- table against map
        TV.append(dict(area=a, table_reaches=len(t), drawn_features=len(d), lake_layer_features=len(lk_layer), table_mi=L.sum(),
                       drawn_mi=d.len_m.sum() / MI, lake_layer_mi=lk_layer.len_m.sum() / MI, table_60_mi=L[t.fish_score >= 60].sum(),
                       drawn_60_mi=d.len_m[d.fish >= 60].sum() / MI))
        # ---- trout found, shown dry
        dry = found & ~lake & t.water_class.isin(["mostly dry", "seasonal"])
        DRY.append(dict(area=a, trout_found_reaches=int((found & ~lake).sum()), shown_mostly_dry=int((found & ~lake & t.water_class.eq("mostly dry")).sum()),
                        shown_seasonal=int((found & ~lake & t.water_class.eq("seasonal")).sum()), miles=round(L[dry].sum(), 1)))
        # ---- NHD perennial shown drier; unmapped; burn with no severity
        per = t.flow.eq("perennial") & ~lake
        below = per & t.water_class.isin(["usually flows", "seasonal", "mostly dry"])
        PER.append(dict(area=a, nhd_perennial=int(per.sum()), below_year_round=int(below.sum()), miles=round(L[below].sum(), 1),
                        with_trout_evidence=int((below & ev).sum()), mostly_dry=int((per & t.water_class.eq("mostly dry")).sum()),
                        median_sq_mi=round(km2[below].median() / 2.58999, 2) if below.any() else None,
                        unmapped=int((t.flow.eq("unmapped") & ~lake).sum()), unmapped_8sqmi_plus=int((t.flow.eq("unmapped") & ~lake & (km2 >= 20)).sum()),
                        burned=int((t.burn_factor < 1).sum()), burned_no_severity=int(((t.burn_factor < 1) & t.burn_sev.isna()).sum())))
        # ---- score against survey results
        tt = terms(t)
        base = 100 * t.water_term * tt.base * t.burn_factor * t.heat_factor * t.channel_factor
        evt = t.trout_ev.astype(str)
        wild = found & evt.str.contains(r"wild|Rainbow Trout|rainbow trout \(|brook trout \(|cutthroat", case=False) & ~evt.str.contains("stocked with trout", case=False)
        P, N, W = found & ~lake, absent & ~lake, wild & ~lake
        SV.append(dict(area=a, found=int(P.sum()), wild_found=int(W.sum()), no_trout=int(N.sum()), auc_score=auc(base[P], base[N]),
                       auc_score_wild=auc(base[W], base[N]), auc_size=auc(tt["size"][P], tt["size"][N]), auc_water=auc(t.water_term[P], t.water_term[N]),
                       auc_thermal=auc(t.thermal[P], t.thermal[N]), auc_remote=auc(tt.remote[P], tt.remote[N]),
                       median_sq_mi_found=round(km2[P].median() / 2.58999, 1) if P.any() else None,
                       median_sq_mi_none=round(km2[N].median() / 2.58999, 1) if N.any() else None))
        # ---- trout-found records on undrawn water
        pe = f"{ROOT}/output/{a}/context/trout_evidence.gpkg"
        if os.path.exists(pe):
            tw = gpd.read_file(pe).to_crs(epsg(a))
            pts = tw[tw.geom_type == "Point"].reset_index(drop=True)
            pts = pts[shapely.contains(area_box_union(a), pts.geometry.values)].reset_index(drop=True)
            dd, _ = nearest_dist(pts.geometry.x.values, pts.geometry.y.values, r.geometry.values, 3000)
            Lk = gpd.read_file(f"{ROOT}/data/derived/{a}/_shared/lakes.gpkg").to_crs(epsg(a))
            lt = shapely.STRtree(Lk.geometry.values)
            inlake = np.array([len(lt.query(g, predicate="dwithin", distance=40.0)) > 0 for g in pts.geometry.values])
            fnd = pts.trout.fillna(False).astype(bool).to_numpy() if "trout" in pts else np.ones(len(pts), bool)
            isl = pts.lake.fillna(False).astype(bool).to_numpy() if "lake" in pts else np.zeros(len(pts), bool)
            off = (dd > 150) & ~inlake & ~isl & fnd
            d8 = d8_area_near(a, pts.geometry.x.values[off], pts.geometry.y.values[off])
            OFF.append(dict(area=a, trout_found_records=int(fnd.sum()), on_undrawn_water=int(off.sum()), under_the_floor=int((d8 < 1).sum()),
                            kinds=str(pts.kind[off].value_counts().head(3).to_dict()) if "kind" in pts else ""))
        # ---- lakes against NHD at the area's own smallest size
        Ll, Nn, _ = lakes(a)
        if Ll is not None:
            tree = shapely.STRtree(Ll.geometry.values)
            big = Nn[Nn.ha >= mins.get(a, 1.0)].reset_index(drop=True)
            hit = np.array([len(tree.query(g_, predicate="intersects")) > 0 for g_ in big.geometry.values])
            LK.append(dict(area=a, smallest_acres=round(mins.get(a, 1.0) * 2.47105, 1), layer_lakes=len(Ll), nhd_lakes=len(big),
                           missing=int((~hit).sum()), missing_acres=round(big.ha[~hit].sum() * 2.47105), with_depth=int(Ll.depth_max_m.notna().sum())))
        print(a, "done", flush=True)
    for name, rows in (("table_vs_drawn", TV), ("trout_found_shown_dry", DRY), ("perennial_shown_drier", PER), ("trout_records_off_map", OFF),
                       ("fish_score_vs_surveys", SV), ("lakes_missing_summary", LK)):
        df = pd.DataFrame(rows)
        df.round(3).to_csv(f"{TABLES}/{name}.csv", index=False)
        print(f"\n{name}:\n{df.round(2).to_string(index=False)}")


if __name__ == "__main__":
    main(sys.argv[1:] or NAMES)
