#!/usr/bin/env python3
"""The fish score, taken apart on the reach tables (stream_reaches_ranked.csv).

    fish = 100 x water x (0.30 size + 0.30 thermal + 0.15 gradient + 0.25 remoteness) x burn x trout x heat x channel
(scripts/scoring.py:322). For every area: does the table reproduce its own score; how the scores are spread and where
they pile up at 100; what each term contributes; how many reaches each rule that LOWERS a score touches; and the two
checks against trout records: reaches with trout on record that score low, reaches halved by a no-trout sample.
    TABLES_DIR=<folder with <area>/stream_reaches_ranked.csv, tried before output/> python audit/scripts/fish_score_audit.py
Tables: audit/tables/fish_score_summary.csv, fish_score_terms.csv, fish_score_penalties.csv, trout_low_scores.csv
"""
import sys, os
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from common import *

SNAP = os.environ.get("TABLES_DIR", "")
THIS_YEAR = 2026


def table(area):
    for base in ([SNAP] if SNAP else []) + [f"{ROOT}/output"]:
        p = f"{base}/{area}/stream_reaches_ranked.csv"
        if os.path.exists(p):
            return p
    return None


def band(x, lo, hi, soft):
    return np.clip(1 - np.clip(np.maximum(lo - x, x - hi), 0, None) / soft, 0, 1)


def terms(s):
    big = s.area_full_km2.fillna(s.area_km2)
    size = np.clip(np.log10(big.clip(lower=1e-6)) / np.log10(50), 0, 1)
    grad = band(s.gradient_pct, 1, 8, 10)
    ridden = s.bike_med_min.fillna(0)
    remote = np.clip((s.approach_med_min.fillna(0) + ridden) / 120, 0, 1)
    base = 0.30 * size + 0.30 * s.thermal + 0.15 * grad + 0.25 * remote
    mult = s.burn_factor * s.trout_factor * s.heat_factor * s.channel_factor
    again = np.clip(100 * s.water_term * base * mult, 0, 100)
    return pd.DataFrame(dict(size=size, grad=grad, remote=remote, base=base, mult=mult, again=again))


def main(areas):
    S, T, P, LOW = [], [], [], []
    for a in areas:
        p = table(a)
        if p is None:
            continue
        s = pd.read_csv(p, low_memory=False)
        t = terms(s)
        L = s.len_m.to_numpy(float) / MI
        tot = L.sum()
        fs = s.fish_score.to_numpy(float)
        lake = s.water_class.astype(str).eq("reservoir").to_numpy()
        diff = np.abs(t.again.to_numpy() - fs)
        raw = 100 * s.water_term * t.base * t["mult"]                     # before the cap at 100
        pos = (s.trout_found >= THIS_YEAR - 10) & (s.trout_absent.isna() | (s.trout_found >= s.trout_absent))
        neg = (s.trout_absent >= THIS_YEAR - 10) & ~pos
        evid = pos | s.trout_water.notna()
        S.append(dict(area=a, table=(os.environ.get("SITE_NAME", "snapshot") if SNAP and p.startswith(SNAP) else "output/ as it stands"), reaches=len(s), miles=tot,
                      reproduced_within_2_pct=100 * (diff <= 2).mean(), median=np.median(fs),
                      mi_60_plus_pct=100 * L[fs >= 60].sum() / tot, mi_80_plus_pct=100 * L[fs >= 80].sum() / tot,
                      mi_at_100_pct=100 * L[fs >= 100].sum() / tot, capped_would_exceed_100_pct=100 * L[raw.to_numpy() > 100.5].sum() / tot,
                      trout_evidence_mi_pct=100 * L[evid.to_numpy()].sum() / tot,
                      evidence_scoring_60_plus_pct=100 * L[(evid.to_numpy()) & (fs >= 60)].sum() / max(L[evid.to_numpy()].sum(), 1e-9),
                      no_evidence_scoring_60_plus_pct=100 * L[(~evid.to_numpy()) & (fs >= 60)].sum() / max(L[~evid.to_numpy()].sum(), 1e-9)))
        # what each term is worth: its mean, its spread, and how much of the spread of the score it carries on its own
        stream = ~lake
        cols = dict(water=s.water_term, size=t["size"], thermal=s.thermal, gradient=t.grad, remoteness=t.remote,
                    burn=s.burn_factor, trout=s.trout_factor, heat=s.heat_factor, channel=s.channel_factor)
        for k, v in cols.items():
            v = v.to_numpy(float)[stream]
            T.append(dict(area=a, term=k, mean=np.nanmean(v), sd=np.nanstd(v), share_at_max_pct=100 * np.mean(v >= np.nanmax(v) - 1e-9),
                          corr_with_score=np.corrcoef(np.nan_to_num(v, nan=np.nanmean(v)), fs[stream])[0, 1] if np.nanstd(v) > 0 else np.nan))
        # every rule that lowers
        wr = s.water_rule.astype(str)
        pen = {"no-trout sample: x0.5": (s.trout_factor == 0.5), "heat gate < 1": (s.heat_factor < 1),
               "built channel by name: x0.2": (s.channel_factor < 1), "burn < 1": (s.burn_factor < 1),
               "bare channel -> seasonal at most": wr.eq("bare channel"), "gauge record (either way)": wr.eq("gauge"),
               "diversion gauge": s.water_by_gauge.astype(str).eq("True"), "reads as lake (water 0.3)": pd.Series(lake),
               "flow model: water under 0.5": (s.water_term < 0.5) & ~pd.Series(lake) & ~wr.isin(["bare channel", "gauge"]),
               "no flow estimate: NHD class used, under 1": s.water_class.astype(str).isin(["no data", "nan"]) & (s.water_term < 1)}
        for k, m in pen.items():
            m = m.to_numpy(bool)
            P.append(dict(area=a, rule=k, reaches=int(m.sum()), miles=round(L[m].sum(), 1), with_trout_evidence=int((m & evid.to_numpy()).sum()),
                          was_60_plus_without=int((m & (fs < 60) & ((fs / np.where(k.startswith("no-trout"), 0.5, 1)) >= 60)).sum()) if k.startswith("no-trout") else None))
        # trout on record, score under 40
        m = evid.to_numpy() & (fs < 40) & ~lake
        for q in s[m].sort_values("fish_score").itertuples():
            w = dict(water=q.water_term, size=t["size"].iat[q.Index], thermal=q.thermal, remote=t.remote.iat[q.Index], burn=q.burn_factor)
            LOW.append(dict(area=a, sid=q.sid, name=q.name, fish=q.fish_score, sq_mi=round((q.area_full_km2 if q.area_full_km2 == q.area_full_km2 else q.area_km2) / 2.58999, 2),
                            water_class=q.water_class, water_term=q.water_term, size=round(w["size"], 2), thermal=q.thermal, remote=round(w["remote"], 2),
                            burn=q.burn_factor, trout_factor=q.trout_factor, water_f=None if pd.isna(q.water_aug) else round(q.water_aug * 9 / 5 + 32),
                            record=str(q.trout_water if isinstance(q.trout_water, str) else q.trout_ev)[:90], lat=q.lat, lon=q.lon))
        print(a, "done", flush=True)
    pd.set_option("display.width", 260); pd.set_option("display.max_rows", 400); pd.set_option("display.max_colwidth", 60)
    S = pd.DataFrame(S); S.round(1).to_csv(f"{TABLES}/fish_score_summary.csv", index=False); print(S.round(1).to_string(index=False))
    T = pd.DataFrame(T); T.round(3).to_csv(f"{TABLES}/fish_score_terms.csv", index=False)
    print(T.pivot(index="term", columns="area", values="mean").round(2).to_string())
    print(T.pivot(index="term", columns="area", values="corr_with_score").round(2).to_string())
    P = pd.DataFrame(P); P.to_csv(f"{TABLES}/fish_score_penalties.csv", index=False)
    print(P.pivot(index="rule", columns="area", values="reaches").to_string())
    print(P.pivot(index="rule", columns="area", values="with_trout_evidence").to_string())
    LOW = pd.DataFrame(LOW); LOW.to_csv(f"{TABLES}/trout_low_scores.csv", index=False)
    print("trout on record, score under 40:", LOW.groupby("area").size().to_dict())


if __name__ == "__main__":
    main(sys.argv[1:] or NAMES)
