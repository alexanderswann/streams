"""Diagram of the fish score (scripts/scoring.py score()): equation header, weight bar, one response curve per term."""
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.colors import LinearSegmentedColormap

OUT = sys.argv[1]
SURF, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"
C = dict(size="#2a78d6", thermal="#eb6834", grad="#1baf7a", remote="#eda100")
MULT = "#3d3c39"
plt.rcParams.update({"font.family": ["Helvetica Neue", "DejaVu Sans"], "font.size": 10, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.8,
                     "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF})


def band(x, lo, hi, soft):
    return np.clip(1 - np.clip(np.maximum(lo - x, x - hi), 0, None) / soft, 0, 1)


fig = plt.figure(figsize=(17, 11.6), dpi=160)
gs = fig.add_gridspec(4, 6, height_ratios=[0.78, 0.3, 1, 1.15], hspace=0.5, wspace=0.42,
                      left=0.045, right=0.985, top=0.965, bottom=0.05)

# ---------------- header: the equation ----------------
hx = fig.add_subplot(gs[0, :]); hx.axis("off"); hx.set_xlim(0, 100); hx.set_ylim(0, 30)
hx.text(0, 29, "How the fish score is computed", fontsize=22, weight="bold", color=INK, va="top")
hx.text(0, 21.3, "Each stream reach scores 0–100.  A weighted habitat sum (0–1) is multiplied by four factors, "
        "then capped at 100.   Source: scripts/scoring.py  score()", fontsize=11.5, color=INK2, va="top")


def box(x, y, w, h, label, sub, col, fill=True):
    hx.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.9", lw=1.6,
                                ec=col, fc=col + ("22" if fill else "00")))
    hx.text(x + w / 2, y + h * 0.63, label, ha="center", va="center", fontsize=15, weight="bold", color=INK)
    hx.text(x + w / 2, y + h * 0.27, sub, ha="center", va="center", fontsize=9.5, color=INK2)


y0, h = 2.2, 12
hx.text(0, y0 + h / 2, "100 ×", fontsize=19, va="center", color=INK, weight="bold")
box(6.3, y0, 7.6, h, "W", "water", MULT, fill=False)
hx.text(14.6, y0 + h / 2, "×", fontsize=19, va="center", color=INK)
hx.text(16.3, y0 + h / 2, "(", fontsize=46, va="center", color=MUTED)
xs = 18.3
for i, (k, wt, lab, sub) in enumerate([("size", "0.30", "S", "creek size"), ("thermal", "0.30", "T", "thermal"),
                                       ("grad", "0.15", "G", "gradient"), ("remote", "0.25", "R", "remoteness")]):
    x = xs + i * 11.6
    hx.text(x + 0.3, y0 + h / 2, wt, fontsize=13, va="center", color=INK2)
    box(x + 3.4, y0, 6.6, h, lab, sub, C[k])
    if i < 3:
        hx.text(x + 10.55, y0 + h / 2, "+", fontsize=19, va="center", color=INK)
hx.text(64.6, y0 + h / 2, ")", fontsize=46, va="center", color=MUTED)
for i, (lab, sub) in enumerate([("B", "burn"), ("F", "trout evidence"), ("H", "heat gate")]):
    x = 67.2 + i * 11
    hx.text(x, y0 + h / 2, "×", fontsize=19, va="center", color=INK)
    box(x + 2, y0, 8.2, h, lab, sub, MULT, fill=False)
hx.text(100, y0 - 2.2, "outlined = multipliers (scale the whole score)   ·   filled = habitat terms (weights sum to 1)",
        ha="right", fontsize=9.5, color=MUTED)

# ---------------- weight bar ----------------
wx = fig.add_subplot(gs[1, :])
segs = [("Size  30", 30, C["size"], 1), ("Thermal: water temp  15", 15, C["thermal"], 1),
        ("shade  10.5", 10.5, C["thermal"], 0.72), ("north  4.5", 4.5, C["thermal"], 0.45),
        ("Gradient  15", 15, C["grad"], 1), ("Remoteness  25", 25, C["remote"], 1)]
left = 0
for lab, v, col, a in segs:
    wx.barh(0, v - 0.35, left=left + 0.175, height=0.62, color=col, alpha=a, lw=0)
    wx.text(left + v / 2, -0.62, lab, ha="center", va="top", fontsize=9.5, color=INK)
    left += v
wx.set_xlim(0, 100); wx.set_ylim(-1.3, 0.55); wx.axis("off")
wx.set_title("Habitat points out of 100, before the multipliers (a perfect reach with W = B = F = H = 1 scores 100)",
             loc="left", fontsize=11.5, color=INK, weight="bold")


# ---------------- habitat curves ----------------
def panel(ax, title, sub, col):
    ax.set_title(title, loc="left", fontsize=11.5, weight="bold", color=INK, pad=20)
    ax.text(0, 1.03, sub, transform=ax.transAxes, fontsize=8.6, color=INK2, va="bottom")
    ax.grid(True, color=GRID, lw=0.6); ax.set_axisbelow(True)
    ax.tick_params(length=0, labelsize=8.5)


def curve(ax, x, y, col, **kw):
    ax.plot(x, y, color=col, lw=2.2, solid_capstyle="round", **kw)


# The score works in km2 and °C (scoring.py); the panels show square miles and °F (units.py), like the maps
SQMI, F = 0.386102, (lambda c: c * 9 / 5 + 32)
ax = fig.add_subplot(gs[2, 0])
a = np.logspace(-0.5, 2.5, 300)                      # km2
curve(ax, a * SQMI, np.clip(np.log10(a) / np.log10(50), 0, 1), C["size"])
ax.set_xscale("log"); ax.set_xticks([0.1, 0.39, 2, 19.3, 100]); ax.set_xticklabels(["0.1", "0.39", "2", "19", "100"])
ax.set_xlabel("drainage area (sq mi, log)"); ax.set_ylim(-0.03, 1.05)
panel(ax, "S  size", "0.39 sq mi → 0,  19+ sq mi → 1", C["size"])

ax = fig.add_subplot(gs[2, 1])
e = np.linspace(10, 28, 400)                         # °C
curve(ax, F(e), np.clip((25 - e) / 5, 0, 1), C["thermal"])
ax.axvspan(F(10), F(20), color=C["thermal"], alpha=0.07, lw=0)
ax.set_xlabel("estimated summer water temperature (°F)"); ax.set_ylim(-0.03, 1.05)
panel(ax, "T · water temperature  (×0.5)", "full ≤ 68 °F, none ≥ 77 °F; tailwaters always 1", C["thermal"])

ax = fig.add_subplot(gs[2, 2])
sh = np.linspace(0, 80, 200)
curve(ax, sh, np.clip(sh / 45, 0, 1), C["thermal"])
ax.set_xlabel("combined summer shade (%)"); ax.set_ylim(-0.03, 1.05)
panel(ax, "T · shade  (×0.35)", "1−(1−terrain)(1−0.8·canopy); 45%+ full", C["thermal"])

ax = fig.add_subplot(gs[2, 3])
n = np.linspace(-0.3, 0.3, 200)
curve(ax, n, np.clip((n + 0.15) / 0.3, 0, 1), C["thermal"])
ax.set_xticks([-0.3, -0.15, 0, 0.15, 0.3]); ax.set_xticklabels(["-0.3\nS-facing", "-0.15", "0", "0.15", "0.3\nN-facing"])
ax.set_xlabel("mountainside northness"); ax.set_ylim(-0.03, 1.05)
panel(ax, "T · northness  (×0.15)", "south-facing → 0,  north-facing → 1", C["thermal"])

ax = fig.add_subplot(gs[2, 4])
g = np.linspace(0, 25, 300)
curve(ax, g, band(g, 1, 8, 10), C["grad"])
ax.axvspan(1, 8, color=C["grad"], alpha=0.08, lw=0)
ax.set_xlabel("gradient (%)"); ax.set_ylim(-0.03, 1.05)
panel(ax, "G  gradient", "full 1–8%, zero by 18%", C["grad"])

ax = fig.add_subplot(gs[2, 5])
m = np.linspace(0, 180, 300)
curve(ax, m, np.clip(m / 120, 0, 1), C["remote"])
curve(ax, m, np.clip(2 * m / 120, 0, 1), C["remote"], ls=(0, (4, 2.5)))
ax.text(100, 0.62, "all walked", fontsize=8.8, color=INK, ha="left")
ax.text(64, 0.9, "all ridden", fontsize=8.8, color=INK, ha="left")
ax.set_xlabel("approach time (min)"); ax.set_ylim(-0.03, 1.08); ax.set_xticks([0, 60, 120, 180])
panel(ax, "R  remoteness", "120+ min → 1; ridden minutes count ×2", C["remote"])

# ---------------- multipliers ----------------
ax = fig.add_subplot(gs[3, 0:2])
fy = np.linspace(0, 1, 100)
curve(ax, fy, 0.05 + 0.95 * fy, MULT)
ax.set_xlabel("share of summers since 2011 with ≥ 0.1 cfs, Jul–Oct (TNC flow model)"); ax.set_ylim(-0.03, 1.08)
fb = [("NHD perennial", 1.0), ("NHD intermittent", 0.35), ("reservoir / other", 0.3),
      ("NHD unmapped", 0.15), ("NHD ephemeral", 0.05)]
for lab, v in fb:
    ax.plot(1.06, v, "o", ms=7, color=SURF, mec=MULT, mew=1.6, clip_on=False)
    ax.text(1.09, v + {0.35: 0.025, 0.3: -0.025}.get(v, 0), f"{lab}  {v:g}", fontsize=8.5, color=INK2, va="center", transform=ax.transData, clip_on=False)
ax.text(1.06, 0.66, "○ NHD flow class,\nused where the flow\nmodel has no data", va="center", fontsize=8.5, color=MUTED, ha="left")
ax.set_xlim(0, 1)
panel(ax, "W  water", "0.05 + 0.95 × flow share  (below a gauged diversion: the gauge's record)",
      MULT)
pos = ax.get_position(); ax.set_position([pos.x0, pos.y0, pos.width * 0.66, pos.height])

ax = fig.add_subplot(gs[3, 2:4])
sevs = [("high", 1.0), ("moderate", 0.75), ("low", 0.4), ("very low", 0.15)]
yrs = [("≤ 2 yr", 0.4), ("3–5 yr", 0.7), ("6–9 yr", 0.9), ("10+ / none", 1.0)]
grid = np.array([[1 - (1 - b) * s for _, b in yrs] for _, s in sevs])
cmap = LinearSegmentedColormap.from_list("seq", ["#3d3c39", "#f4f3f0"])
ax.imshow(grid, cmap=cmap, vmin=0.35, vmax=1.05, aspect="auto")
for i in range(4):
    for j in range(4):
        ax.text(j, i, f"{grid[i, j]:.2f}", ha="center", va="center", fontsize=10,
                color=SURF if grid[i, j] < 0.7 else INK, weight="bold")
ax.set_xticks(range(4)); ax.set_xticklabels([y for y, _ in yrs])
ax.set_yticks(range(4)); ax.set_yticklabels([s for s, _ in sevs])
ax.set_xlabel("years since fire (fires since 2016)"); ax.set_ylabel("burn severity / debris hazard")
for sp in ax.spines.values(): sp.set_visible(False)
ax.tick_params(length=0, labelsize=8.8)
ax.set_title("B  burn", loc="left", fontsize=11.5, weight="bold", color=INK, pad=20)
ax.text(0, 1.03, "1 − (1 − age factor) × severity;  max of BAER severity and USGS debris-flow hazard",
        transform=ax.transAxes, fontsize=8.6, color=INK2, va="bottom")
pos = ax.get_position(); ax.set_position([pos.x0 + 0.02, pos.y0, pos.width * 0.8, pos.height])

ax = fig.add_subplot(gs[3, 4])
labs = ["latest survey\nfound none", "no evidence", "trout found /\nwild trout water"]
vals = [0.5, 1.0, 1.2]
ax.bar(range(3), vals, width=0.55, color=MULT, lw=0)
for i, v in enumerate(vals):
    ax.text(i, v + 0.04, f"×{v:g}", ha="center", fontsize=10, weight="bold", color=INK)
ax.set_xticks(range(3)); ax.set_xticklabels(labs, fontsize=8.2); ax.set_ylim(0, 1.4)
ax.axhline(1, color=MUTED, lw=0.8, ls=":")
panel(ax, "F  trout evidence", "last 10 years; score still capped at 100", MULT)

ax = fig.add_subplot(gs[3, 5])
t = np.linspace(26, 32, 300)                         # °C
curve(ax, F(t), np.clip(1 - (t - 29) / 1.5 * 0.8, 0.2, 1), MULT)
ax.axvline(F(26.7), color=MUTED, lw=0.8, ls=":")
ax.text(F(26.85), 0.32, "warmest creek\nwith a trout\nrecord, 80.1 °F", fontsize=7.8, color=INK2)
ax.text(F(26.85), 0.64, "off where trout\nare known, or\nbelow a dam", fontsize=7.8, color=INK2, ha="left", va="center")
ax.set_xlabel("August mean air temp (°F, PRISM)"); ax.set_ylim(-0.03, 1.08)
panel(ax, "H  heat gate", "1 up to 84 °F, down to 0.2 at 87 °F+", MULT)

fig.savefig(OUT)
print("saved", OUT)
