"""Label paths: smoothed copies of a winding line (the PCT, named trails) for text that bends along it on the maps.

One set per zoom band, so lettering follows the line without kinking at that scale. Each path is the line
resampled every 100 m and smoothed twice with a moving average wide enough (~20 px or more on screen) to iron out
switchbacks, trimmed rather than padded at the ends (no hooks), and run west to east so the text reads upright.
Centres go where the smoothed path is at least the label's length + 28 px on screen and the real line stays
within 5 px of it over the stretch the text covers (the maps put the text 7-8 px off the path), spaced so labels
repeat sensibly. Vertices are thinned to ~18 px apart: Leaflet rounds vertices to whole pixels, so closer ones would
snap each segment to coarse angles and the letters would jump between them.

A band is (zoom band, smoothing window in 100 m samples, raw half-length m, spacing m, [m/px at each zoom it
serves, lowest zoom first]). Returns [{"z", "c": [lat, lon], "a": angle, "p": [[lon, lat], ...]}].
"""
import numpy as np, shapely, shapely.ops
from pyproj import Transformer

TO_WGS = Transformer.from_crs(26911, 4326, always_xy=True)
# m/px at 34 degrees north for zooms 11..16
MPP = {11: 65, 12: 32, 13: 16, 14: 8, 15: 4, 16: 2}


def smooth(seg, win, step=100):
    n = int(seg.length // step) + 1
    xy = np.array([seg.interpolate(t).coords[0] for t in np.linspace(0, seg.length, n)])
    k = np.ones(win) / win
    for _ in range(2):
        if len(xy) < win:
            return None
        xy = np.column_stack([np.convolve(xy[:, 0], k, "valid"), np.convolve(xy[:, 1], k, "valid")])
    return xy


def label_paths(ln, bands, text_px, max_gap_px=5, step=100):
    """ln: LineString in EPSG:26911."""
    out = []
    for zb, win, half_p, spacing, mpps in bands:
        mpp0 = mpps[0]
        if ln.length < 2 * half_p:
            continue
        paths, gap = {}, {}
        for d in np.arange(half_p, ln.length - half_p, spacing / 6):
            xy = smooth(shapely.ops.substring(ln, d - half_p, d + half_p), win, step)
            if xy is None or len(xy) < 2:
                continue
            sm = shapely.LineString(xy)
            if sm.length / mpp0 < text_px + 28:
                continue
            paths[d] = xy
            gap[d] = max(max(sm.distance(ln.interpolate(t)) for t in np.arange(d - text_px / 2 * m, d + text_px / 2 * m, step))
                         / m for m in mpps)
        picked = []
        for d in sorted(gap, key=gap.get):
            if gap[d] <= max_gap_px and all(abs(d - q) >= spacing for q in picked):
                picked.append(d)
        keep = max(1, round(18 * mpp0 / step))
        for d in sorted(picked):
            xy = paths[d]
            xy = np.vstack([xy[::keep], xy[-1:]]) if (len(xy) - 1) % keep else xy[::keep]
            if xy[-1, 0] < xy[0, 0]:
                xy = xy[::-1]
            ang = -np.degrees(np.arctan2(xy[-1, 1] - xy[0, 1], xy[-1, 0] - xy[0, 0]))
            lon, lat = TO_WGS.transform(xy[:, 0], xy[:, 1])
            c = TO_WGS.transform(*ln.interpolate(d).coords[0])
            out.append({"z": zb, "c": [round(c[1], 5), round(c[0], 5)], "a": round(float(ang), 1),
                        "p": [[round(x, 5), round(y, 5)] for x, y in zip(lon, lat)]})
    return out
