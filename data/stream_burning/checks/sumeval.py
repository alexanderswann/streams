"""One table over the areas of an evaluation (evaluate.sh): sumeval.py <eval dir>"""
import sys, re, os, glob
E = sys.argv[1]
ORDER = ["la", "jackson", "n_georgia", "central_vt", "ne_ct", "lexington_va", "se_pa", "smokies", "adk_high_peaks", "adk_northwest", "adk_southwest", "adk_southeast"]
rows, tot = [], {}
def num(s): return float(s.replace(",", ""))
for a in ORDER:
    p = f"{E}/{a}.txt"
    if not os.path.exists(p):
        continue
    t = open(p).read()
    parts = re.split(r"######## ", t)
    A, B, C = parts[1], parts[2], parts[3]
    def grab(txt):
        st = re.search(r"reaches\s+(\d+) \| flagged in-lake\s+(\d+) \(\s*([\d.]+) km\), outside every drawn lake\s+([\d.]+) km:\s+(\d+) reaches with 100\+ m outside \(\s*([\d.]+) km\),\s+(\d+) untouched.*?not flagged:\s+([\d.]+) km inside counted lakes \((\d+) reaches with 100\+ m\),\s+([\d.]+) km inside any drawn lake", txt)
        fl = re.search(r"known falls (\d+): found pass 1 (\d+), both passes (\d+)", txt)
        dr = re.search(r"drops: pass 1 (\d+) .*?big-creek pass (\d+)", txt)
        lo = re.search(r"under half of NHDPlus: (\d+)", txt)
        fd = re.search(r"sudden flow drops.*?: (\d+)", txt)
        dead = sum(int(x) for x in re.findall(r"^\s*\w+\s+\d+\s+[\d.]+\s+\d+\s+(\d+)\s+[\d.]+\s+[\d.]+\s*$", txt, re.M))
        return dict(reaches=int(st.group(1)), flagged=int(st.group(2)), creek_as_lake=num(st.group(4)), n100=int(st.group(5)), untouched=int(st.group(7)),
                    lake_as_creek=num(st.group(10)), falls=int(fl.group(3)), falls_n=int(fl.group(1)), drops=int(dr.group(1)), big=int(dr.group(2)),
                    outlets=int(lo.group(1)), flowdrops=int(fd.group(1)), dead=dead)
    a_, b_ = grab(A), grab(B)
    km = re.findall(r"'km60': np\.float64\(([\d.]+)\)", C)
    mv = re.search(r"fish score up 10\+: (\d+), down 10\+: (\d+)", C)
    nm = re.search(r"name changed: (\d+)", C)
    rows.append((a, a_, b_, float(km[0]), float(km[1]), int(mv.group(1)), int(mv.group(2)), int(nm.group(1)), t.count("Traceback")))
hdr = f"{'area':15s} {'reaches':>15s} {'creek as lake km':>17s} {'lake as creek km':>17s} {'fish 60+ km':>17s} {'up/down':>9s} {'falls found':>14s} {'drops p1':>11s} {'big-creek':>10s} {'outlets':>8s} {'flow drops':>10s} {'dead ends':>9s} tb"
print(hdr)
S = [0] * 16
for a, x, y, k0, k1, up, dn, nm, tb in rows:
    print(f"{a:15s} {x['reaches']:6d} → {y['reaches']:6d} {x['creek_as_lake']:7.1f} → {y['creek_as_lake']:6.1f} {x['lake_as_creek']:7.1f} → {y['lake_as_creek']:6.1f} {k0:7.1f} → {k1:7.1f} {up:4d}/{dn:<4d} "
          f"{x['falls']:4d} → {y['falls']:4d}/{x['falls_n']:<4d} {x['drops']:4d} → {y['drops']:4d} {x['big']:4d} → {y['big']:3d} {x['outlets']:3d} → {y['outlets']:2d} {x['flowdrops']:3d} → {y['flowdrops']:2d} {x['dead']:3d} → {y['dead']:2d}  {tb}")
    for i, v in enumerate((x['reaches'], y['reaches'], x['creek_as_lake'], y['creek_as_lake'], x['lake_as_creek'], y['lake_as_creek'], k0, k1, up, dn, x['falls'], y['falls'], x['outlets'], y['outlets'], x['drops'] + x['big'], y['drops'] + y['big'])):
        S[i] += v
print(f"{'all listed':15s} {S[0]:6.0f} → {S[1]:6.0f} {S[2]:7.1f} → {S[3]:6.1f} {S[4]:7.1f} → {S[5]:6.1f} {S[6]:7.1f} → {S[7]:7.1f} {S[8]:4.0f}/{S[9]:<4.0f} {S[10]:4.0f} → {S[11]:4.0f}       drops {S[14]:.0f} → {S[15]:.0f}   outlets {S[12]:.0f} → {S[13]:.0f}")
