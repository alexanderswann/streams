"""Measured lake depths and lake fish surveys that no web service carries, typed in from their sources (each checked
against the document on 2026-11-19). 05d_lakes.py matches them to its lakes and keeps, for each lake, the best
measurement: a published sonar survey first, then EPA's sonar sounding at the deepest spot it found, then a
fisheries survey's transducer depth, then the fisheries agency's listed depth. The others are kept as notes, and a
disagreement of more than 20% (and 2 m) is shown. Modelled depths (GLOBathy, HydroLAKES) are never used.

EPA National Lakes Assessment soundings are read from the EPA files by lakesources.py, for every area.

No lake in the Jackson boxes has published bathymetry (a depth grid, contours or soundings) that can be downloaded:
surveys exist for Jenny Lake (NPS bathymetry raster; Larsen et al. 2016, 2019), Jackson Lake (CHIRP, 2018 and 2021;
McGlue et al. 2023; Johnson 2024) and Palisades Reservoir (multibeam, June 2022; Reclamation ENV-2023-008), but only as
figures or on request (checked 2026-11-19).

Each depth record: lake (name as in lakes.gpkg / GNIS), max_m, mean_m (or None), rank (1 published sonar survey,
2 EPA sonar, 3 fisheries transducer survey), date, method, src (short, for the map), ref (full citation / link),
at (lon, lat or UTM 12N easting, northing of the sounding or the lake, to match it), reservoir_index (True: an EPA
index site on a reservoir, a lower bound, not the maximum).
"""

SG2005 = ("Stephens & Gipson 2005, Inventory of fish in alpine lakes in Grand Teton National Park (Wyoming Game & "
          "Fish for the NPS Greater Yellowstone Network), Appendix A; https://irma.nps.gov/DataStore/DownloadFile/151582")
NLA = "EPA National Lakes Assessment, sonar depth at the index site (for a natural lake, the deepest spot the crew found)"

DEPTHS = {"jackson": [
    dict(lake="Jenny Lake", max_m=73, mean_m=43, rank=1, date="2013", method="NPS bathymetry raster and CHIRP sonar profiles",
         src="Larsen et al. 2016 (sonar survey)", at=(-110.725, 43.757),
         ref="Larsen et al. 2016, Quaternary Science Reviews 138:62-75 ('a maximum depth of ~73 m, and an average depth of ~43 m'); "
             "https://www.nps.gov/grte/learn/historyculture/upload/Larsen-et-al-2016-Deglaciation-and-postglacial-environmental-changes-in-the-Teton-Mountain-Range-recorded-at-Jenny-Lake-Grand-Teton-National-Park-WY_QSR-reduced.pdf"),
    dict(lake="Jackson Lake", max_m=143, mean_m=None, rank=1, date="2018", method="CHIRP sub-bottom sonar, lake-wide",
         src="McGlue et al. 2023 (sonar survey; the depth varies with the reservoir level)", at=(-110.65, 43.90),
         ref="McGlue et al. 2023, Earth Science, Systems and Society, doi:10.3389/esss.2023.10066 ('~190 ms TWTT (~143 m) "
             "during our survey'); https://par.nsf.gov/servlets/purl/10395463"),
] + [dict(lake=n, max_m=round(ft * 0.3048, 1), mean_m=None, rank=3, date=d, method="portable transducer, deepest point found",
          src="Wyoming Game & Fish / NPS alpine lake survey", at=(e, n_), ref=SG2005)
     for n, ft, d, e, n_ in [
         ("Amphitheater Lake", 30, "2002-08-07", 517660, 4841660), ("Arrowhead Pool", 4, "2002-09-10", 519465, 4846745),
         ("Cirque Lake", 196, "2003-08-15", 513230, 4852760), ("Coyote Lake", 15, "2002-09-18", 510500, 4831610),
         ("Delta Lake", 26, "2002-08-08", 518400, 4842000), ("Forget-me-not Lakes", 6, "2003-08-29", 510550, 4832850),
         ("Grizzly Bear Lake", 31, "2003-09-10", 515280, 4849850), ("Hechtman Lake", 81, "2002-09-06", 516450, 4876750),
         ("Holly Lake", 22, "2002-08-20", 516280, 4848680), ("Icefloe Lake", 111, "2003-08-08", 514300, 4841350),
         ("Indian Lake", 47, "2002-09-17", 509040, 4830850), ("Kit Lake", 14, "2003-08-08", 513400, 4840000),
         ("Lake of the Crags", 63, "2002-09-11", 518500, 4846750), ("Lake Solitude", 37, "2002-08-19", 512550, 4848600),
         ("Lake Taminah", 58, "2003-08-07", 515700, 4839200), ("Laurel Lake", 12, "2002-09-04", 520840, 4847450),
         ("Marion Lake", 26, "2003-09-04", 505750, 4829850), ("Mica Lake", 63, "2002-09-15", 512600, 4847650),
         ("Mink Lake", 32, "2003-10-02", 512550, 4850650), ("Pass Lake", 2, "2003-09-05", 507450, 4832100),
         ("Ramshead Lake", 19, "2002-09-11", 519050, 4846880), ("Snowdrift Lake", 174, "2002-08-29", 514000, 4839350),
         ("Surprise Lake", 18, "2002-08-07", 518000, 4841550), ("Timberline Lake", 68, "2003-08-19", 514250, 4836900)]],
}

# Gill-net surveys of the same report (Appendix B; fish found: Yellowstone cutthroat trout in three lakes; Arrowhead
# Pool was too shallow to net, 4 ft; Timberline Lake's net wasn't set for ice, its minnow trap caught nothing).
SURVEYS = {"jackson": [
    dict(lake=n, date=d, fish=f, at=(e, n_), src="Wyoming Game & Fish / NPS gill nets", ref=SG2005)
    for n, d, f, e, n_ in [
        ("Amphitheater Lake", "2002-08-07", None, 517660, 4841660), ("Cirque Lake", "2003-08-15", None, 513230, 4852760),
        ("Coyote Lake", "2002-09-18", None, 510500, 4831610), ("Delta Lake", "2002-08-08", None, 518400, 4842000),
        ("Forget-me-not Lakes", "2003-08-29", None, 510550, 4832850),
        ("Grizzly Bear Lake", "2003-09-10", "Yellowstone cutthroat trout (58 netted, 4.5-18 in)", 515280, 4849850),
        ("Hechtman Lake", "2002-09-06", None, 516450, 4876750),
        ("Holly Lake", "2002-08-20", "Yellowstone cutthroat trout (8 netted, 10.8-16 in)", 516280, 4848680),
        ("Icefloe Lake", "2003-08-08", None, 514300, 4841350), ("Indian Lake", "2002-09-17", None, 509040, 4830850),
        ("Kit Lake", "2003-08-08", None, 513400, 4840000), ("Lake of the Crags", "2002-09-11", None, 518500, 4846750),
        ("Lake Solitude", "2002-08-19", "Yellowstone cutthroat trout (49 netted, 4-14.5 in)", 512550, 4848600),
        ("Lake Taminah", "2003-08-07", None, 515700, 4839200), ("Laurel Lake", "2002-09-04", None, 520840, 4847450),
        ("Marion Lake", "2003-09-04", None, 505750, 4829850), ("Mica Lake", "2002-09-15", None, 512600, 4847650),
        ("Mink Lake", "2003-10-02", None, 512550, 4850650), ("Pass Lake", "2003-09-05", None, 507450, 4832100),
        ("Ramshead Lake", "2002-09-11", None, 519050, 4846880), ("Snowdrift Lake", "2002-08-29", None, 514000, 4839350),
        ("Surprise Lake", "2002-08-07", None, 518000, 4841550)]],
}
