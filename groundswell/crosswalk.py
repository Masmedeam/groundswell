"""Map a (state, county) — and by extension a ZIP's county — to one of our metros.

Each WARN state maps to exactly one demo metro, so state + county membership is
enough to roll up notices without an external ZIP->CBSA crosswalk. (HUD ZIP->CBSA
is a future precision upgrade.)
"""
from .config import METROS


def norm_county(c):
    if not c:
        return ""
    return (
        str(c).lower().replace(" county", "").replace(" parish", "").replace(" borough", "").strip()
    )


_STATE_METROS = {}
_METRO_COUNTIES = {}
for _m in METROS:
    _STATE_METROS.setdefault(_m["warn_state"], []).append(_m["metro_id"])
    _METRO_COUNTIES[_m["metro_id"]] = {norm_county(c) for c in _m.get("counties", [])}


def to_metro(state, county):
    """Return metro_id for a (state, county) pair, or None if outside our metros."""
    nc = norm_county(county)
    for mid in _STATE_METROS.get(state, []):
        if nc and nc in _METRO_COUNTIES[mid]:
            return mid
    return None


def metro_for_region_name(region_name):
    """Match a Zillow metro-level RegionName (e.g. 'Austin, TX') to a metro_id."""
    for m in METROS:
        if region_name == m["zori_region"]:
            return m["metro_id"]
    return None
