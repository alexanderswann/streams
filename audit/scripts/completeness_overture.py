#!/usr/bin/env python3
"""Overture Maps places (Meta, Microsoft, BrightQuery and Foursquare points of interest, under CDLA-Permissive-2.0 and
Apache-2.0: both allow use on the site with credit) that could be waterfalls, swimming holes or named water, for
completeness.py: audit/reference/<area>/overture_places.csv. Needs duckdb (not in the project's .venv: run it with a
Python that has it) and the boxes completeness_fetch.py writes (audit/reference/area_bbox.json). Network only.

Kept: places Overture files as waterfall, beach, river, lake or hot spring, and any place whose name says falls,
cascade, swimming hole, swim area, blue hole, punch bowl, potholes, gorge or plunge (Overture's categories are loose:
Notchbrook Swimming Hole in Stowe is filed as pool cleaning). completeness.py decides what counts as which.
    <python with duckdb> audit/scripts/completeness_overture.py [area ...]
"""
import sys, os, json, time, urllib.request
import duckdb

ROOT = "/Users/mac/Fishing"
REF = f"{ROOT}/audit/reference"
CATS = ("waterfall", "beach", "river", "lake", "hot_springs", "swimming_hole")
NAME_RE = r"\bfalls?\b|waterfall|cascade|swimming hole|swim(ming)? area|swimmin|swim hole|blue hole|punch ?bowl|pothole|gorge|plunge"


def latest_release():
    with urllib.request.urlopen(urllib.request.Request("https://stac.overturemaps.org/catalog.json",
                                                       headers={"User-Agent": "stream-analysis/0.1"}), timeout=60) as r:
        return json.load(r)["latest"]


def main(areas):
    bb = json.load(open(f"{REF}/area_bbox.json"))
    rel = latest_release()
    con = duckdb.connect()
    con.sql("INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2'; SET enable_progress_bar=false;")
    src = f"s3://overturemaps-us-west-2/release/{rel}/theme=places/type=place/*"
    for a in areas or list(bb):
        w, s, e, n = bb[a]
        t0 = time.time()
        os.makedirs(f"{REF}/{a}", exist_ok=True)
        out = f"{REF}/{a}/overture_places.csv"
        try:
            con.sql(f"""COPY (
              SELECT id, names.primary AS name, taxonomy.primary AS cat, basic_category AS basic, confidence,
                     operating_status AS status, round((bbox.xmin + bbox.xmax) / 2, 6) AS lon, round((bbox.ymin + bbox.ymax) / 2, 6) AS lat,
                     array_to_string(list_distinct(list_transform(sources, lambda x: x.dataset)), ';') AS datasets,
                     array_to_string(list_distinct(list_transform(sources, lambda x: x.license)), ';') AS licence,
                     '{rel}' AS release
              FROM read_parquet('{src}', hive_partitioning=1)
              WHERE bbox.xmin BETWEEN {w} AND {e} AND bbox.ymin BETWEEN {s} AND {n}
                AND (taxonomy.primary IN {CATS} OR regexp_matches(lower(names.primary), '{NAME_RE}'))
            ) TO '{out}.tmp' (FORMAT CSV, HEADER)""")
            os.replace(out + ".tmp", out)
            n_ = con.sql(f"SELECT count(*) FROM read_csv('{out}')").fetchall()[0][0]
            print(f"{a}: {n_} places ({time.time() - t0:.0f} s, release {rel})", flush=True)
        except Exception as ex:   # noqa: BLE001  (keep any old copy; go on)
            print(f"{a}: FAILED ({str(ex)[:150]}); old copy kept", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
