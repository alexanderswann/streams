#!/usr/bin/env python3
"""Is the lake term of the Adirondack water-temperature fits supported by the measured sites, and where?

watertemp.py (2026-11-21) adds  coefficient x lake share  to a reach's estimated July-August water temperature, the
lake share being the part of the reach's drainage that arrives through a lake or pond upstream (fading out on rivers
of 19-193 sq mi). It is in the fits of adk_high_peaks, adk_southwest and (through the group fit) adk_northwest.

This script asks four things, read-only, from one build's files:
  1. At the measured sites (the pipeline's own table, water_temp_sites.csv): how much warmer are lake-fed sites, by
     how far below the pond the site is and by the pond's size? Distance and pond are found by walking up the main
     stem from the site's reach to the first lake of the lakes layer.
  2. Which reaches does the term mark down by 10+ fish-score points, how many miles, how many with a trout record,
     and how far below what size of pond do they lie? (The score is recomputed with the term taken out; each reach's
     miles are split along it by distance below the pond.)
  3. The same on the drawn map (DRAWN, optional: a folder with <area>/map3d_data.js of that build): the default
     stream layer cut into 25 m pieces, each put on its reach. "10+ points" is a knife-edge (the term's most common
     markdown is 9-12 points), so the miles are also given for other thresholds.
  4. Does a lake term that is stronger at the outlet than below it fit the measured sites better than the flat one?
Inputs (a snapshot folder SNAP with, per area: <box>/streams_scored.gpkg, lakes.gpkg, water_temp_fit.json,
water_temp_sites.csv; and TABLES_DIR with <area>/stream_reaches_ranked.csv of the same build).
    SNAP=<folder> TABLES_DIR=<folder> [DRAWN=<folder>] AUDIT_TABLES=<out> python audit/scripts/lake_term_test.py
Tables: lake_term_sites.csv, lake_term_sites_summary.csv, lake_term_distance_fit.csv, lake_term_reaches.csv,
lake_term_reaches_summary.csv, lake_term_drawn_summary.csv
"""
import sys, os, json, glob
import numpy as np, pandas as pd, geopandas as gpd, shapely
from scipy.spatial import cKDTree
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from fish_score_audit import terms

SNAP = os.environ["SNAP"]
TDIR = os.environ["TABLES_DIR"]
DRAWN = os.environ.get("DRAWN")
ADK = ["adk_high_peaks", "adk_northwest", "adk_southwest", "adk_southeast"]
LAKE_FULL_KM2, LAKE_NONE_KM2 = 50.0, 500.0
DIST_BINS = [-1, 200, 1000, 3000, 1e9]
DIST_LAB = ["within 650 ft of the pond", "650 ft - 0.6 mi below", "0.6 - 1.9 mi below", "over 1.9 mi below"]
SIZE_BINS = [0, 5, 25, 100, 1e9]
SIZE_LAB = ["pond under 5 acres", "5-25 acres", "25-100 acres", "lake over 100 acres"]
F = lambda c: c * 9 / 5 + 32
NO_LAKE = "no lake found up the main stem"


def split_by_distance(up, length):
    """Metres of a stretch that starts `up` metres below the lake and is `length` long, in each distance bin."""
    e = [0.0] + DIST_BINS[1:]
    return [max(0.0, min(up + length, hi) - max(up, lo)) for lo, hi in zip(e[:-1], e[1:])]


def lake_share(edge, full):
    full = np.asarray(full, float)
    with np.errstate(invalid="ignore", divide="ignore"):
        share = np.clip(1 - np.asarray(edge, float) / full, 0, 1)
        fade = np.clip((np.log10(LAKE_NONE_KM2) - np.log10(np.clip(full, 1e-3, None)))
                       / (np.log10(LAKE_NONE_KM2) - np.log10(LAKE_FULL_KM2)), 0, 1)
    return share * fade


class Net:
    """One area's reaches with what is needed to walk upstream to the first lake."""
    def __init__(self, a):
        parts = []
        for p in sorted(glob.glob(f"{SNAP}/{a}/*/streams_scored.gpkg")):
            parts.append(gpd.read_file(p, columns=["sid"]).to_crs(epsg(a)))
        s = pd.concat(parts, ignore_index=True)
        t = pd.read_csv(f"{TDIR}/{a}/stream_reaches_ranked.csv", low_memory=False)
        s = s.merge(t, on="sid", how="inner").reset_index(drop=True)
        self.a, self.s = a, gpd.GeoDataFrame(s, geometry="geometry", crs=epsg(a))
        g = self.s.geometry.values
        self.start = np.array([p.coords[0][:2] for p in g])
        self.end = np.array([p.coords[-1][:2] for p in g])
        self.len = shapely.length(g)
        self.full = self.s.area_full_km2.fillna(self.s.area_km2).to_numpy(float)
        self.share = np.nan_to_num(lake_share(self.s.area_edge_km2.fillna(self.s.area_km2), self.full))
        self.inlake = self.s.water_class.astype(str).eq("reservoir").to_numpy()
        self.end_tree = cKDTree(self.end)
        L = gpd.read_file(f"{SNAP}/{a}/lakes.gpkg").to_crs(epsg(a))
        self.lakes, self.lake_tree = L, shapely.STRtree(L.geometry.values)
        self.tree = shapely.STRtree(g)
        # lines are stored running downstream if the reach that starts where another ends drains more
        j = self.end_tree.query(self.start, distance_upper_bound=1.0)[1]
        ok = j < len(s)
        self.downstream_share = float((self.full[ok] >= self.full[j[ok]] - 1e-6).mean())

    def lake_near(self, xy, tol=45.0):
        k = self.lake_tree.query(shapely.Point(xy), predicate="dwithin", distance=tol)
        if not len(k):
            return None
        i = k[np.argmax(self.lakes.ha.to_numpy()[k])]
        return i

    def walk(self, i, d0=0.0, limit=25000.0):
        """From reach i (d0 = metres already walked up to its upstream end): the first lake up the main stem.
        -> (metres below the lake, lake row or None)."""
        d, seen = d0, set()
        for _ in range(400):
            if i in seen:
                break
            seen.add(i)
            if self.inlake[i]:                                    # the reach itself is lake water
                k = self.lake_near(self.start[i], 80) or self.lake_near(self.end[i], 80)
                return d, k
            k = self.lake_near(self.start[i])
            if k is not None:
                return d, k
            up = [j for j in self.end_tree.query_ball_point(self.start[i], 20.0) if j != i]
            if not up or d > limit:
                return np.nan, None
            i = max(up, key=lambda j: self.full[j])
            d += self.len[i]
        return np.nan, None


def distance_fit(S3):
    """Does a lake term with distance in it fit the measured sites better? The sites with lake water and a lake found
    upstream; what is fitted is the warmth left over once the fit's other terms are taken off (they are held), per
    unit of lake share: one value (as now) against two (within 650 ft of the pond, and beyond). Leave-one-out."""
    d = S3[(S3.lake_term > 0) & S3.ft_below_lake.notna()]
    y, x, near = d.excess_f.to_numpy(), d.lake_term.to_numpy(), (d.ft_below_lake * FT <= DIST_BINS[1]).to_numpy()
    fed = x >= 0.5

    def flat(k):
        c = (x[k] * y[k]).sum() / (x[k] ** 2).sum()
        return lambda X, N: c * X, {"per unit of lake share, F": c}

    def two(k):
        co = np.linalg.lstsq(np.c_[x[k] * near[k], x[k] * ~near[k]], y[k], rcond=None)[0]
        return lambda X, N: X * np.where(N, co[0], co[1]), {"within 650 ft, F": co[0], "beyond, F": co[1]}
    out, every = [], np.arange(len(d))
    for name, f in (("one value (as now)", flat), ("two values", two)):
        m, par = f(every)
        loo = np.array([y[i] - f(every != i)[0](x[i:i + 1], near[i:i + 1])[0] for i in every])
        out.append(dict(lake_term=name, sites=len(d), lake_fed_sites=int(fed.sum()), **{k: round(float(v), 1) for k, v in par.items()},
                        fit_error_f=np.sqrt(((y - m(x, near)) ** 2).mean()), leave_one_out_f=np.sqrt((loo ** 2).mean()),
                        leave_one_out_lake_fed_f=np.sqrt((loo[fed] ** 2).mean())))
    O = pd.DataFrame(out).round(2)
    O.to_csv(f"{TABLES}/lake_term_distance_fit.csv", index=False)
    print("\na lake term with distance in it, against the flat one:\n", O.to_string(index=False))


def main():
    S, R, D = [], [], []
    os.makedirs(TABLES, exist_ok=True)
    for a in ADK:
        net = Net(a)
        fit = json.load(open(f"{SNAP}/{a}/water_temp_fit.json"))
        coef = fit.get("coef", {})
        print(f"{a}: {len(net.s)} reaches; lines run downstream at {100 * net.downstream_share:.1f} % of joins; fit terms {fit.get('terms')}, "
              f"lake coefficient {coef.get('lake')}", flush=True)
        s = net.s
        evid = (s.trout_water.notna() | ((s.trout_found >= 2016) & (s.trout_absent.isna() | (s.trout_found >= s.trout_absent)))).to_numpy()
        # ---- 1. measured sites
        st = pd.read_csv(f"{SNAP}/{a}/water_temp_sites.csv")
        pts = gpd.GeoSeries(gpd.points_from_xy(st.lon, st.lat), crs=4326).to_crs(epsg(a))
        for q, p in zip(st.itertuples(), pts.values):
            if pd.isna(q.lake):
                continue
            k = net.tree.query(p, predicate="dwithin", distance=150.0)
            if not len(k):
                continue
            dist = shapely.distance(s.geometry.values[k], p)
            i = k[np.argmin(np.round(np.abs(net.share[k] - q.lake), 2) * 1000 + dist)]
            d0 = s.geometry.values[i].project(p)
            dm, lk = net.walk(i, d0)
            no_lake = fit["intercept"] + sum(c * (q.elev / 1000 if t == "elev_km" else np.log10(max(net.full[i], 0.5)) if t == "log_area" else q.air)
                                             for t, c in coef.items() if t != "lake")
            S.append(dict(area=a, site=q.name, readings=q.n, measured_f=F(q.w), lake_term=round(q.lake, 2), sq_mi=round(net.full[i] / 2.58999, 2),
                          trout_record=bool(evid[i]), ft_below_lake=None if np.isnan(dm) else round(dm / FT),
                          lake=None if lk is None else net.lakes.name.iat[lk], lake_acres=None if lk is None else round(net.lakes.ha.iat[lk] * 2.47105, 1),
                          est_without_lake_f=F(no_lake), est_with_lake_f=F(no_lake + coef.get("lake", 0) * min(q.lake, fit.get("ranges", {}).get("lake", [0, 1])[1])),
                          in_fit="lake" in coef, lat=q.lat, lon=q.lon, m_below=dm))
        # ---- 2. reaches the term marks down
        if "lake" not in coef:
            continue
        t = terms(s)
        creek = ~net.inlake
        lk_term = np.minimum(net.share, fit["ranges"]["lake"][1])
        wt = s.water_aug.to_numpy(float)
        wt0 = wt - coef["lake"] * lk_term
        cool = np.clip((25 - wt) / 5, 0, 1); cool0 = np.clip((25 - wt0) / 5, 0, 1)
        tail = s.tailwater.notna().to_numpy() if "tailwater" in s else np.zeros(len(s), bool)
        dth = np.where(tail, 0, 0.5 * (cool0 - cool))
        base0 = t.base.to_numpy() + 0.30 * dth
        sc = np.clip(100 * s.water_term * t.base * t["mult"], 0, 100).to_numpy()
        sc0 = np.clip(100 * s.water_term.to_numpy() * base0 * t["mult"].to_numpy(), 0, 100)
        down = np.where(creek, sc0 - sc, 0.0)
        up = np.full(len(s), np.nan); acres = np.full(len(s), np.nan)
        for i in np.where(down >= 10)[0]:
            dm, lk = net.walk(i, 0.0)
            up[i] = dm; acres[i] = np.nan if lk is None else net.lakes.ha.iat[lk] * 2.47105
            row = dict(area=a, sid=s.sid.iat[i], name=s.name.iat[i], miles=net.len[i] / MI, sq_mi=round(net.full[i] / 2.58999, 2),
                       fish=sc[i], fish_without_term=round(sc0[i]), est_f=round(F(wt[i]), 1), est_without_f=round(F(wt0[i]), 1),
                       lake_term=round(float(lk_term[i]), 2), trout_record=bool(evid[i]), record=str(s.trout_water.iat[i])[:60],
                       m_below_top=None if np.isnan(dm) else dm, lake=None if lk is None else net.lakes.name.iat[lk],
                       lake_acres=None if lk is None else round(acres[i], 1), lat=s.lat.iat[i], lon=s.lon.iat[i])
            parts = [0.0] * len(DIST_LAB) if np.isnan(dm) else split_by_distance(dm, net.len[i])
            row.update({f"mi {l}": m / MI for l, m in zip(DIST_LAB, parts)})
            R.append(row)
        some = creek & (lk_term > 0)
        print(f"   creek reaches with a lake term: {int(some.sum())} ({net.len[some].sum() / MI:.0f} mi); marked down 10+ points: "
              f"{int((down >= 10).sum())} ({net.len[down >= 10].sum() / MI:.0f} mi), "
              f"with a trout record {net.len[(down >= 10) & evid].sum() / MI:.0f} mi; 5-10 points: {net.len[(down >= 5) & (down < 10)].sum() / MI:.0f} mi", flush=True)
        # ---- 3. the same on the drawn map: 25 m pieces of the default layer, each on its reach
        if DRAWN:
            import popups
            d = popups.reaches(a, site_dir=DRAWN, layers=("streams",)).reset_index(drop=True)
            x, y, ln, idx = seg_midpoints(d.geometry.values, 25.0)
            pts = shapely.points(x, y)
            (pi, ti), _ = net.tree.query_nearest(pts, max_distance=10.0, return_distance=True, all_matches=False)
            keep = down[ti] >= 5
            pi, ti = pi[keep], ti[keep]
            g = s.geometry.values
            pos = np.array([g[r].project(q) if down[r] >= 10 else np.nan for r, q in zip(ti, pts[pi])])
            tr = pd.Series(d.trout.astype(str).to_numpy()[idx[pi]])
            D.append(pd.DataFrame(dict(area=a, mi=ln[pi] / MI, down=down[ti], m_below=up[ti] + pos, acres=acres[ti], fish=d.fish.to_numpy(float)[idx[pi]],
                                       fish_reach=sc[ti], est_f=d.water_f.to_numpy(float)[idx[pi]],
                                       record=np.where(tr.str.contains("NY class"), "New York trout water class",
                                                       np.where(tr.str.contains("patch"), "wild brook trout patch",
                                                                np.where(tr.isin(["nan", "None", ""]), "no trout record", "other trout record"))))))
            print(f"   drawn: {d.len_m.sum() / MI:.0f} mi in the default layer; on the reaches marked down 10+ points {D[-1].mi[D[-1].down >= 10].sum():.1f} mi", flush=True)

    S, R = pd.DataFrame(S), pd.DataFrame(R)
    S["below"] = pd.cut(S.m_below, DIST_BINS, labels=DIST_LAB).astype(object).fillna(NO_LAKE)
    S["pond"] = pd.cut(S.lake_acres.astype(float), SIZE_BINS, labels=SIZE_LAB).astype(object).fillna("-")
    S["excess_f"] = S.measured_f - S.est_without_lake_f              # how much warmer than a creek with no lake at that elevation
    S["miss_f"] = S.measured_f - S.est_with_lake_f                   # measured minus the map's estimate
    R["pond"] = pd.cut(R.lake_acres.astype(float), SIZE_BINS, labels=SIZE_LAB).astype(object).fillna("-")
    S.drop(columns="m_below").round(2).to_csv(f"{TABLES}/lake_term_sites.csv", index=False)
    R.round(3).to_csv(f"{TABLES}/lake_term_reaches.csv", index=False)

    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
    S3 = S[S.in_fit]                                                 # the maps whose fit has the term
    fed = S3[S3.lake_term >= 0.5]
    print(f"\nall four maps: measured sites on a reach {len(S)}, with a lake term of 0.5+ {int((S.lake_term >= 0.5).sum())}")
    print(f"the maps with the term: measured sites on a reach {len(S3)}; with a lake term of 0.5+: {len(fed)} ({int(fed.readings.sum())} readings); "
          f"0 < term < 0.5: {int(((S3.lake_term > 0) & (S3.lake_term < 0.5)).sum())}; none: {int((S3.lake_term == 0).sum())}")
    se = lambda v: v.std() / np.sqrt(len(v)) if len(v) > 1 else np.nan
    g = lambda d, by: d.groupby(by, sort=False).agg(
        sites=("measured_f", "size"), readings=("readings", "sum"), measured_f=("measured_f", "mean"),
        sites_73f_or_more=("measured_f", lambda v: int((v >= 73).sum())), sites_68f_or_less=("measured_f", lambda v: int((v <= 68).sum())),
        map_estimate_f=("est_with_lake_f", "mean"), warmer_than_no_lake_f=("excess_f", "mean"), warmer_se=("excess_f", se),
        measured_minus_map_f=("miss_f", "mean"), minus_map_se=("miss_f", se)).round(1)
    A_ = g(fed.assign(below=pd.Categorical(fed.below, DIST_LAB + [NO_LAKE])).sort_values("below"), "below")
    mid = fed[fed.below.isin(DIST_LAB[1:3])]
    A2 = g(mid.assign(below="650 ft - 1.9 mi below (the two rows together)"), "below")
    B_ = g(fed.assign(pond=pd.Categorical(fed.pond, SIZE_LAB + ["-"])).sort_values("pond"), "pond")
    C_ = g(fed.assign(tr=np.where(fed.trout_record, "trout record on the reach", "no trout record")), "tr")
    D_ = g(S3[S3.lake_term == 0].assign(tr=np.where(S3[S3.lake_term == 0].trout_record, "no lake, trout record", "no lake, no trout record")), "tr")
    E_ = g(mid.assign(n=np.where(mid.readings >= 3, "650 ft - 1.9 mi, sites with 3+ readings", "650 ft - 1.9 mi, sites with 1-2 readings")), "n")
    print("\nlake-fed sites (term 0.5+) by distance below the pond:\n", pd.concat([A_, A2]).to_string())
    print("\nby readings per site:\n", E_.to_string())
    print("\nlake-fed sites (term 0.5+) by pond size:\n", B_.to_string())
    print("\nlake-fed sites by trout record:\n", C_.to_string()); print(D_.to_string())
    print("\nlake-fed measured sites, distance x pond size:\n",
          pd.crosstab(pd.Categorical(fed.below, DIST_LAB + [NO_LAKE]), pd.Categorical(fed.pond, SIZE_LAB + ["-"]), dropna=False).to_string())
    pd.concat([A_.assign(split="distance below the pond"), A2.assign(split="distance below the pond"), E_.assign(split="readings per site"),
               B_.assign(split="pond size"), C_.assign(split="trout record"), D_.assign(split="no lake term")]).to_csv(f"{TABLES}/lake_term_sites_summary.csv")
    distance_fit(S3)
    if len(R):
        mi = lambda d: round(d.miles.sum(), 1)
        cols = [f"mi {l}" for l in DIST_LAB]
        print(f"\nREACH TABLES. Marked down 10+ points by the lake term: {len(R)} reaches, {mi(R)} mi; with a trout record {mi(R[R.trout_record])} mi "
              f"(NY trout class {mi(R[R.record.str.contains('NY class', na=False)])} mi); estimate {R.est_f.quantile(.1):.0f}-{R.est_f.quantile(.9):.0f} F "
              f"(without the term {R.est_without_f.quantile(.1):.0f}-{R.est_without_f.quantile(.9):.0f} F); median fish {R.fish.median():.0f} against {R.fish_without_term.median():.0f}; "
              f"lake term 5th percentile {R.lake_term.quantile(.05):.2f}, median {R.lake_term.median():.2f}; smallest pond {R.lake_acres.min():.1f} acres")
        y = R.groupby(pd.Categorical(R.pond, SIZE_LAB + ["-"]), observed=False)[cols].sum().T
        y.index = DIST_LAB
        y.loc[NO_LAKE] = [R.miles[R.m_below_top.isna() & (R.pond == c)].sum() for c in y.columns]
        y["all"] = y.sum(axis=1)
        print("\nmarked-down miles (reach tables), distance below the pond x pond size, each reach split along its length:\n", y.round(1).to_string())
        print("\nby area:\n", R.groupby("area").agg(reaches=("miles", "size"), miles=("miles", "sum"), with_trout_record_mi=("miles", lambda v: v[R.loc[v.index, "trout_record"]].sum())).round(1).to_string())
        y.round(1).to_csv(f"{TABLES}/lake_term_reaches_summary.csv")
    if D:
        D = pd.concat(D, ignore_index=True)
        m = D[D.down >= 10]
        out = []
        tot = m.mi.sum()
        print(f"\nDRAWN MAP. On reaches the term marks down 10+ points: {tot:.1f} mi {m.groupby('area').mi.sum().round(1).to_dict()}; the drawn score is the "
              f"reach's within 1 point on {100 * m.mi[(m.fish - m.fish_reach).abs() <= 1].sum() / tot:.1f} % of them; estimate {m.est_f.quantile(.1):.0f}-{m.est_f.quantile(.9):.0f} F; "
              f"median score {m.fish.median():.0f}, median markdown {m.down.median():.1f}; under 60 now and 60+ without the term: {m.mi[(m.fish < 60) & (m.fish + m.down >= 60)].sum():.1f} mi")
        for thr in (8, 9, 9.5, 10, 10.5, 11, 12):
            w = D[D.down >= thr]
            out.append(dict(split="markdown of at least", group=f"{thr} points", miles=w.mi.sum(), with_trout_record=w.mi[w.record != "no trout record"].sum(),
                            ny_class=w.mi[w.record == "New York trout water class"].sum(), wild_trout_patch=w.mi[w.record == "wild brook trout patch"].sum()))
        out.append(dict(split="markdown", group="5 to 10 points", miles=D.mi[(D.down >= 5) & (D.down < 10)].sum()))
        b = pd.cut(m.m_below, DIST_BINS, labels=DIST_LAB).astype(object).fillna(NO_LAKE)
        z = pd.cut(m.acres, SIZE_BINS, labels=SIZE_LAB).astype(object).fillna("-")
        for k, v in m.groupby(b).mi.sum().reindex(DIST_LAB + [NO_LAKE]).fillna(0).items():
            out.append(dict(split="10+ points, distance below the pond", group=k, miles=v))
        for k, v in m.groupby(z).mi.sum().reindex(SIZE_LAB + ["-"]).fillna(0).items():
            out.append(dict(split="10+ points, pond size", group=k, miles=v))
        for k, v in m.groupby("record").mi.sum().items():
            out.append(dict(split="10+ points, trout record", group=k, miles=v))
        for k, v in m.groupby("area").mi.sum().items():
            out.append(dict(split="10+ points, map", group=k, miles=v))
        O = pd.DataFrame(out).round(1)
        O.to_csv(f"{TABLES}/lake_term_drawn_summary.csv", index=False)
        print(O.to_string(index=False))
        print("\ndrawn miles marked down 10+ points, distance x pond size:\n", pd.crosstab(b, z, values=m.mi, aggfunc="sum").fillna(0).round(1).to_string())


if __name__ == "__main__":
    main()
