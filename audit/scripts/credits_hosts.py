#!/usr/bin/env python3
"""Every source the maps read has an entry on the credits page (scripts/credits.py, 2026-11-24).

Lists each web address written in scripts/ (the downloads, which all go through netfetch.py, and the pages' map tiles)
with the credits entry that covers it, and each waterfall guide of data/known_falls_curated*.csv with its entry; fails
(exit 1) when an address or a guide has none. Read-only, no network, about a second. The map step says the same in its
log (13_overview.py: "NOTE: no credits entry ...").
    .venv/bin/python audit/scripts/credits_hosts.py [scripts folder]     (default: this checkout's scripts/)
To fix a failure, add the source to credits.py's SOURCES (or its address to a source's hosts, or to LINKS when it is
only a link), or the guide to GUIDES.
"""
import os, sys

SCR = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
sys.path.insert(0, SCR)
import credits   # noqa: E402  (scripts/ first on the path)

pats = [(h, s["key"]) for s in credits.SOURCES for h in s["hosts"]] + [(h, "link: " + w) for h, w in credits.LINKS.items()]
rows, bad = {}, []
for a, f, i in credits.addresses(SCR):
    if a in rows:
        continue
    who = next((k for h, k in pats if credits._covers(h, a)), None)
    rows[a] = (who, f"{f}:{i}")
    if who is None:
        bad.append(a)
w = max(len(a) for a in rows)
for a, (who, where) in sorted(rows.items(), key=lambda x: (x[1][0] is not None, x[0])):
    print(f"{a:<{w}}  {who or 'NO ENTRY'}  ({where})")
missing = [(g, n) for g, n in credits.guides(visible_only=False) if g not in credits.GUIDES]
for g, n in missing:
    print(f"guide {g!r} ({n} points): NO ENTRY in GUIDES")
print(f"{len(rows)} web addresses in {SCR}, {len(credits.SOURCES)} sources; "
      f"{len(bad)} addresses and {len(missing)} guides with no credits entry")
sys.exit(1 if bad or missing else 0)
