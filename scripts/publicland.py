"""Which PAD-US holdings recorded as restricted (Pub_Access RA) are open on foot (2026-11-24; B10's R13).

PAD-US's "restricted" means a permit, a registration or highly variable hours. It also covers a good deal of public
land that is open on foot, where the rules are on use, not on entry: a licence or a pass (Georgia's wildlife
management areas), seasons and zones (Vermont's Dead Creek), a lake the state holds (Lower Saranac, Raquette). These
are told apart by PAD-US's own fields, not by unit names:
  - the manager: the Forest Service, the Park Service and the Bureau of Land Management, whose land is open on foot;
  - the designation type: wilderness and wilderness study areas whoever manages them, and the states' parks,
    recreation areas, forests (resource management areas), wilderness and conservation areas (wildlife management
    areas, game lands, public lakes).
Everything else recorded restricted stays so: easements (private land under a conservation easement, and the state's
working forests, where the public may use only some of the land), refuges and hatcheries, private, local and
university preserves, watershed land. 11_context.py reads it for the reaches and drops."""
OPEN_MANAGERS = ("Forest Service", "National Park Service", "Bureau of Land Management")
OPEN_TYPES = ("Wilderness Area", "Wilderness Study Area", "State Park", "State Recreation Area",
              "State Resource Management Area", "State Wilderness", "State Conservation Area")


def open_on_foot(pad):
    """Boolean Series: the holdings of `pad` (PAD-US rows with Pub_Access, MngNm_Desc and DesTp_Desc) recorded as
    restricted that are open on foot."""
    return pad.Pub_Access.eq("RA") & (pad.MngNm_Desc.isin(OPEN_MANAGERS) | pad.DesTp_Desc.isin(OPEN_TYPES))
