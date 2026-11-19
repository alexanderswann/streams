"""D8 flow-path helpers shared by the step detectors: downstream/upstream pointers and distance walks."""
import numpy as np
from config import RES

CODES = {1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1), 64: (-1, 0), 128: (-1, 1)}


def pointers(fdir, area, min_area):
    """Flat-index downstream pointer, step length to it, and main-stem upstream pointer (largest donor)."""
    H, W = fdir.shape
    N = H * W
    r, c = np.indices((H, W))
    down = np.arange(N)
    step = np.zeros(N)
    for code, (dr, dc) in CODES.items():
        m = (fdir == code).ravel()
        rr, cc = r.ravel()[m] + dr, c.ravel()[m] + dc
        ok = (rr >= 0) & (rr < H) & (cc >= 0) & (cc < W)
        idx = np.flatnonzero(m)[ok]
        down[idx] = rr[ok] * W + cc[ok]
        step[idx] = RES * np.hypot(dr, dc)
    chan = np.flatnonzero(area >= min_area)
    up = np.arange(N)
    srt = chan[np.argsort(area[chan])]  # ascending, so the largest donor writes last
    recv = down[srt]
    keep = recv != srt
    up[recv[keep]] = srt[keep]
    return down, step, up


def walk(start, dist, ptr, length):
    """Follow ptr from each start until >= dist m travelled. Returns (end index, distance); inf if stuck."""
    cur, d = start.copy(), np.zeros(len(start))
    for _ in range(int(dist / RES) + 2):
        go = d < dist
        if not go.any():
            break
        nxt = ptr[cur[go]]
        moved = nxt != cur[go]
        d[go] += np.where(moved, length(cur[go], nxt), np.inf)
        cur[go] = np.where(moved, nxt, cur[go])
    return cur, d


def group_runs(flag, down):
    """Union contiguous flagged cells along the flow path; returns list of member-index arrays."""
    sc = np.flatnonzero(flag)
    lab = {i: i for i in sc}
    def find(i):
        while lab[i] != i:
            lab[i] = lab[lab[i]]
            i = lab[i]
        return i
    for i in sc:
        j = down[i]
        if j != i and flag[j]:
            lab[find(i)] = find(j)
    groups = {}
    for i in sc:
        groups.setdefault(find(i), []).append(i)
    return [np.array(g) for g in groups.values()]


def run_length(top, base, down, step):
    j, run = top, 0.0
    for _ in range(10000):
        if j == base or down[j] == j:
            break
        run += step[j]
        j = down[j]
    return run
