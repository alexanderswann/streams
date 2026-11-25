"""The two downloads buried.py reads for one range, fetched before 05_score.py (run_mid.sh), which leaves out the reaches
a city has buried (buried.py):
  - NLCD 2021 impervious cover, 30 m (MRLC's WCS): data/raw/<area>/<range>/nlcd_impervious.tif, kept as served
    (EPSG:5070) until the range's box outgrows it;
  - OpenStreetMap's waterway lines with their tunnel, culvert, covered and location tags (Overpass):
    osm_waterways_tags.gpkg, kept a week, and fetched again when the range's box changes (.extent.json).
Each goes through netfetch.py: one that can't be fetched keeps the copy already there, with a dated NOTE; with none
the step fails, and run_mid.sh runs it once more, then stops the area (the stamp marks the run failed, so the publish
gate refuses the area until it has run). 05_score.py fetches them itself where this step hasn't run. Run with
AREA=<area> REGION=<range>."""
import buried

p = buried.impervious_tif()
w = buried.waterways()
print(f"{buried.REGION}: NLCD impervious cover {p.rsplit('/', 1)[-1]}; OpenStreetMap waterways {len(w)} lines, "
      f"{int(w['open'].astype(bool).sum()) if len(w) else 0} open")
