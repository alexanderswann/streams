"""One table over the areas measured with measure_area.sh: the live build (A) against the scratch build (B), from the
check and comparison files. python summarize.py <root B> <live checks dir> [area ...]"""
import sys, os, re, json
import pandas as pd

R, L = sys.argv[1], sys.argv[2]
areas = sys.argv[3:] or ["la", "jackson", "n_georgia", "central_vt", "ne_ct", "lexington_va", "se_pa", "smokies",
                         "adk_high_peaks", "adk_northwest", "adk_southwest", "adk_southeast"]


def grab(text, pat, cast=float, group=1):
    m = re.search(pat, text)
    return cast(m.group(group)) if m else None


def checks(path):
    if not os.path.exists(path):
        return {}
    t = open(path).read()
    out = dict(
        hr_miss=grab(t, r"D8 misses (\d+)", int),
        v2_half=grab(t, r"under half of V2 at the line's lower end: (\d+)", int),
        short=grab(t, r'"outside_lakes": (\d+)', int),
        lake_out=grab(t, r"below them under half of NHDPlus: (\d+)", int),
        flow_drops=grab(t, r"both flowing\): (\d+)", int),
        falls=grab(t, r"all:\s+pass 1: \d+ / \d+ \| pass 1 \+ big-creek pass: (\d+) / \d+", int),
        falls_of=grab(t, r"all:\s+pass 1: \d+ / \d+ \| pass 1 \+ big-creek pass: \d+ / (\d+)", int))
    dead = re.findall(r"^\s*\S+\s+\d+\s+[-\d.]+\s+\d+\s+(\d+)\s+[\d.]+\s+[\d.]+$", t, re.M)
    out["dead_edge"] = sum(int(d) for d in dead) if dead else None
    mins = re.findall(r"^\s*\S+\s+\d+\s+([-\d.]+)\s+\d+\s+\d+\s+[\d.]+\s+[\d.]+$", t, re.M)
    out["min_area"] = min(float(m) for m in mins) if mins else None
    return out


def landing(path):
    """Reaches outside lakes in both builds whose full drainage changed 20 %+ and 5+ km2: where a lake's water now lands
    on another reach (a fix where a side creek had carried it, a regression where the river loses it)."""
    if not os.path.exists(path):
        return {}
    m = pd.read_csv(path, low_memory=False)
    t = m[((m.ratio >= 1.2) | (m.ratio <= 1 / 1.2)) & ((m.af_b - m.af_a).abs() > 5)
          & (m.water_class_b != "reservoir") & (m.water_class_a != "reservoir")]
    return dict(outside_lakes_drainage_changed=f"{int((t.af_b > t.af_a).sum())} gained / {int((t.af_b < t.af_a).sum())} lost")


rows = []
for a in areas:
    A, B = checks(f"{L}/checks_{a}.txt"), checks(f"{R}/data/checks_{a}.txt")
    cmp_ = f"{R}/data/compare_{a}.txt"
    c = open(cmp_).read() if os.path.exists(cmp_) else ""
    dA = grab(c, r"fish scores  A: (\{.*\})", str)
    dB = grab(c, r"             B: (\{.*\})", str)
    js = lambda s: json.loads(re.sub(r"np\.float64\(([-\d.]+)\)", r"\1", s.replace("'", '"'))) if s else {}
    dA, dB = js(dA), js(dB)
    st = re.findall(r"straight runs of 300\+ m: outside lakes \d+ runs, ([\d.]+) km .*?; in lakes \d+ runs, ([\d.]+) km", c)
    fl = re.findall(r"known falls (\d+): found pass 1 \d+, both passes (\d+)", c)
    moves = re.search(r"fish score up 10\+: (\d+), down 10\+: (\d+)", c)
    rows.append(dict(
        area=a,
        reaches=f"{dA.get('n', '?')} → {dB.get('n', '?')}",
        fish60_km=f"{dA.get('km60', '?')} → {dB.get('km60', '?')}",
        moves_10=f"{moves.group(1)} up / {moves.group(2)} down" if moves else "?",
        moved_20m_km=grab(c, r"moved 20\+ m ([\d.]+)"),
        straight_lakes_km=f"{st[0][1]} → {st[1][1]}" if len(st) == 2 else "?",
        straight_out_km=f"{st[0][0]} → {st[1][0]}" if len(st) == 2 else "?",
        **{k: f"{A.get(k)} → {B.get(k)}" for k in ("hr_miss", "v2_half", "short", "lake_out", "flow_drops", "dead_edge")},
        falls=f"{A.get('falls')} → {B.get('falls')} of {B.get('falls_of')}",
        known_falls=f"{fl[0][1]} → {fl[1][1]} of {fl[0][0]}" if len(fl) == 2 else "?",
        **landing(f"{R}/data/compare_{a}.csv")))
t = pd.DataFrame(rows).set_index("area")
pd.set_option("display.width", 250)
print(t.T.to_string())
