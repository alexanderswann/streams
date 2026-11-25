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
at (lon, lat of the sounding or the lake, to match it; or easting, northing with crs, the EPSG code they are in), reservoir_index (True: an EPA
index site on a reservoir, a lower bound, not the maximum).
"""

# GBIF's species names for the trout family, as the maps say them. GBIF follows the 2023 AFS list, which splits
# cutthroat trout: the inland ones (Yellowstone, Snake River fine-spotted, Bonneville, Colorado River, Rio Grande) are
# Oncorhynchus virginalis, Rocky Mountain cutthroat trout.
SALMONIDS = {
    "Oncorhynchus clarkii": "cutthroat trout", "Oncorhynchus virginalis": "cutthroat trout",
    "Oncorhynchus clarkii bouvieri": "Yellowstone cutthroat trout", "Oncorhynchus clarkii behnkei": "Snake River cutthroat trout",
    "Oncorhynchus clarkii utah": "Bonneville cutthroat trout", "Oncorhynchus lewisi": "westslope cutthroat trout",
    "Oncorhynchus henshawi": "Lahontan cutthroat trout", "Oncorhynchus mykiss": "rainbow trout",
    "Oncorhynchus aguabonita": "golden trout", "Oncorhynchus nerka": "kokanee salmon", "Oncorhynchus kisutch": "coho salmon",
    "Oncorhynchus tshawytscha": "Chinook salmon", "Salmo trutta": "brown trout", "Salmo salar": "Atlantic salmon",
    "Salvelinus fontinalis": "brook trout", "Salvelinus namaycush": "lake trout", "Salvelinus confluentus": "bull trout",
    "Salvelinus alpinus": "Arctic char", "Thymallus arcticus": "Arctic grayling", "Prosopium williamsoni": "mountain whitefish",
    "Prosopium cylindraceum": "round whitefish", "Coregonus clupeaformis": "lake whitefish", "Coregonus artedi": "cisco"}

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
          src="Wyoming Game & Fish / NPS alpine lake survey", at=(e, n_), crs=26912, ref=SG2005)
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
# Measured depths from reports elsewhere (each read in its source, 2026-11-20). "note" goes with the depth in the popup.
DEPTHS["la"] = [
    dict(lake="Lake Arrowhead", max_m=46.2, mean_m=18.6, rank=1, date="2008-09",
         method="echo sounder with RTK GPS on lines 100 ft apart; area-capacity table at 1 ft steps",
         src="Bureau of Reclamation 2009 (sonar survey; depth below full pool)", at=(-117.1858, 34.2593),
         note="bottom at 4,955 ft, full pool 5,106.7 ft (lake datum); mean = 46,855 acre-feet over 767 acres",
         ref="Bureau of Reclamation 2009, Lake Arrowhead 2008 bathymetric survey report: area-capacity table from 4,955.0 ft "
             "(0 acres) to full pool 5,106.7 ft (767 acres, 46,855 acre-feet), Arrowhead Lake Association datum (11.2 ft "
             "below NAVD88); https://data.usbr.gov/rise/content-rise-public/rise/catalog-item/binary/"
             "Lake%20Arrowhead_Bathymetric%20Survey%20Report%202009_508.pdf"),
]
DEPTHS["lexington_va"] = [
    dict(lake="Lake Robertson", max_m=13.7, mean_m=None, rank=3, date="undated", method="depth contours at 5 ft",
         src="Virginia DWR lake map (5 ft contours)", at=(-79.6084, 37.8044),
         note="deepest contour 45 ft: the bottom is a little deeper",
         ref="Virginia DWR, Lake A. Willis Robertson, Rockbridge County, 31 acres, 5 ft contour intervals; "
             "https://dwr.virginia.gov/wp-content/uploads/Lake_A_Willis_Robertson.pdf"),
]

# SE Pennsylvania (each read in its source, 2026-11-20). DCNR / PA Geological Survey water-depth maps of state park lakes:
# the deepest point each plate gives, below normal pool (the depth bands themselves are drawn by lake_bathymetry.py)
OFMI_MC = ("Behr & Moore 2015, Water depth of Marsh Creek Lake, Marsh Creek State Park, DCNR Open-File Miscellaneous "
           "Investigation OFMI 15-18.0 (data collected January 2005 by USGS and PA Geological Survey; 5 ft contours; normal "
           "pool 359.5 ft); https://maps.dcnr.pa.gov/publications/Default.aspx?id=842")
OFMI_FC = ("Behr 2017, Water depth of Hopewell and Scotts Run lakes, French Creek State Park, DCNR OFMI 17-02.0 (data "
           "collected April 18, 2017 by PA Geological Survey and Bureau of State Parks; 2 ft contours; normal pool 505 ft "
           "(Hopewell), 592 ft (Scotts Run)); https://maps.dcnr.pa.gov/publications/Default.aspx?id=963")
DEPTHS["se_pa"] = [
    dict(lake="Marsh Creek Reservoir", max_m=round(78.5 * 0.3048, 1), mean_m=None, rank=1, date="2005-01",
         method="depth survey (instrument not named), 5 ft contours", src="DCNR / PA Geological Survey depth map OFMI 15-18.0",
         at=(-75.72439, 40.07016), note="deepest point on the survey's map, below normal pool (359.5 ft)", ref=OFMI_MC),
    dict(lake="Hopewell Lake", max_m=round(20 * 0.3048, 1), mean_m=None, rank=1, date="2017-04-18",
         method="depth survey (instrument not named), 2 ft contours", src="DCNR / PA Geological Survey depth map OFMI 17-02.0",
         at=(-75.78302, 40.20198), note="deepest point on the survey's map, below normal pool (505 ft)", ref=OFMI_FC),
    dict(lake="Scotts Run Lake", max_m=round(22 * 0.3048, 1), mean_m=None, rank=1, date="2017-04-18",
         method="depth survey (instrument not named), 2 ft contours", src="DCNR / PA Geological Survey depth map OFMI 17-02.0",
         at=(-75.79952, 40.21092), note="deepest point on the survey's map, below normal pool (592 ft)", ref=OFMI_FC),
    # the agency's own figure, method not given: below EPA's sonar (rank 2), shown beside it
    dict(lake="Struble Lake", max_m=round(19 * 0.3048, 1), mean_m=None, rank=4, date="2020", method="not stated",
         src="PFBC biologist report ('approximately 19 feet')", at=(-75.86524, 40.11227),
         ref="PFBC 2020 trap net survey of Struble Lake; https://www.pa.gov/content/dam/copapwp-pagov/en/fishandboat/"
             "documents/fishing/where-to-fish/biologist-reports/6x03-22-strublelake.pdf"),
]

SURVEYS = {"jackson": [
    dict(lake=n, date=d, fish=f, at=(e, n_), crs=26912, src="Wyoming Game & Fish / NPS gill nets", ref=SG2005)
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
    # PFBC's 2021 trap-net survey of Scotts Run Lake (Table 1 of the report; all trout of hatchery origin: PFBC stocks it
    # spring and fall). gear: what the popup calls the survey (Gill-net where not given)
    "se_pa": [dict(lake="Scotts Run Lake", date="2021", gear="Trap-net", at=(-75.79952, 40.21092), src="PFBC trap nets",
                   fish="stocked trout: rainbow (17), brown (12) and brook (11), 8-16 in; with bluegill, pumpkinseed, "
                        "chain pickerel, largemouth bass, yellow perch and bullheads",
                   ref="PFBC 2021 trap net and night boat electrofishing survey of Scotts Run Lake; https://www.pa.gov/"
                       "content/dam/copapwp-pagov/en/fishandboat/documents/fishing/where-to-fish/biologist-reports/"
                       "6x2021scottsrunlake-trapnet.pdf")],
}


def inside(table, keep):
    """Every record of DEPTHS or SURVEYS that keep(record) accepts, in the order they are typed in here. The lists are
    grouped by the map they were typed in for, but any area takes the records whose point lies in it (05d_lakes.py)."""
    return [d for group in table.values() for d in group if keep(d)]
