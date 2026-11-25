"""
Thin client for the Cornwall Insight Data API (v1, spec 0.3.0).

Auth: API key in the `apikey` header. Keys are managed by your API Admin in CATALYST.
"""
from __future__ import annotations

import requests
import pandas as pd

BASE_URL = "https://api.cornwall-insight.com/external/v1"

# ---- Allowed values (from the API reference, spec 0.3.0) -------------------------
ARCHETYPES = ["Domestic", "Small non-domestic", "Large non-domestic"]
FUEL_TYPES = ["Electricity", "Gas"]
ELECTRICITY_REGIONS = [
    "Average across all regions", "East Midlands", "Eastern", "London", "Midlands",
    "N Wales & Mersey", "North East", "North West", "Northern Scotland", "South East",
    "South Wales", "South Western", "Southern", "Southern Scotland", "Yorkshire",
]
GAS_REGIONS = [
    "Average across all regions", "East Midlands", "Eastern", "London", "North West",
    "Northern", "Scotland", "South East", "South West", "Southern", "Wales North",
    "Wales South", "West Midlands", "Yorkshire",
]
CM_CONSUMPTION = ["All", "Peak"]
CFD_SCENARIOS = [
    "Central", "High Generation", "Low Generation", "High Power Price", "Low Power Price",
    "High Generation & High Power Price", "High Generation & Low Power Price",
    "Low Generation & High Power Price", "Low Generation & Low Power Price",
]
RIIOED3 = ["Central", "Low", "High"]
RIIOET3 = ["Baseline", "Medium", "High"]
FIT_CFD_SCENARIOS = ["Central", "High", "Low"]
TNUOS_SCENARIOS = ["Central", "Low", "Low IC"]
TNUOS_ZONES = [
    "Cotswold", "South Lancashire, Yorkshire and Humber", "Somerset and Wessex",
    "South Wales & Gloucester", "South Lincolnshire and North Norfolk", "South West Scotland",
    "Essex and Kent", "East Aberdeenshire", "Central London", "North Midlands and North Wales",
    "Oxfordshire, Surrey and Sussex", "Anglesey and Snowdon", "Mid Wales and The Midlands",
    "North Lancashire and The Lakes", "North Scotland", "Skye and Lochalsh",
    "Stirlingshire and Fife", "North East England", "The Trossachs", "Central Grampian",
    "Lothian and Borders", "Eastern Grampian and Tayside", "West Devon and Cornwall",
    "Solway and Cheviot", "Western Highlands", "Pembrokeshire", "Argyll",
]


class CornwallAPIError(RuntimeError):
    def __init__(self, status: int, code: str | None, message: str, url: str):
        self.status, self.code, self.url = status, code, url
        super().__init__(f"HTTP {status} {code or ''}: {message}")


class CornwallClient:
    def __init__(self, api_key: str, base_url: str = BASE_URL, timeout: int = 60):
        if not api_key:
            raise ValueError("An API key is required")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"accept": "application/json", "apikey": api_key})

    # params is a list of (name, value) tuples so a name can repeat (TNUoS zone_names)
    def get(self, path: str, params: list[tuple[str, str]] | None = None) -> tuple[pd.DataFrame, str]:
        r = self.session.get(f"{self.base_url}{path}", params=params or [], timeout=self.timeout)
        if r.status_code != 200:
            code, msg = None, r.text[:500]
            try:
                body = r.json()
                code, msg = body.get("code"), body.get("message", msg)
            except ValueError:
                pass
            raise CornwallAPIError(r.status_code, code, msg, r.url)
        data = r.json()
        if isinstance(data, dict):                    # spec declares some responses as a single object
            data = data.get("data", data)
            if isinstance(data, dict):
                data = [data]
        return pd.DataFrame(data), r.url

    # ---- Endpoints ----------------------------------------------------------------
    def overall_charges(self, archetypes, fuel_types, electricity_regions=None, gas_regions=None,
                        cm_consumption="All", cfd_scenario="Central", riioed3="Central",
                        riioet3="Baseline", from_date=None, to_date=None, include_nulls=False):
        p = [("archetypes", ",".join(archetypes)), ("fuel_types", ",".join(fuel_types)),
             ("cm_consumption", cm_consumption), ("cfd_scenario", cfd_scenario),
             ("riioed3", riioed3), ("riioet3", riioet3),
             ("include_nulls", str(include_nulls).lower())]
        if electricity_regions:
            p.append(("electricity_regions", ",".join(electricity_regions)))
        if gas_regions:
            p.append(("gas_regions", ",".join(gas_regions)))
        if from_date:
            p.append(("from_date", str(from_date)))
        if to_date:
            p.append(("to_date", str(to_date)))
        return self.get("/tpc/overall_charges", p)

    def non_locational_charges(self, type_="non-domestic", cm_consumption="All", cfd_scenario="Central"):
        return self.get("/tpc/non_locational_charges",
                        [("type", type_), ("cm_consumption", cm_consumption), ("cfd_scenario", cfd_scenario)])

    def fit_cfd_charges(self, from_date=None, scenarios=None):
        p = []
        if from_date:
            p.append(("from_date", str(from_date)))
        if scenarios:
            p.append(("scenarios", ",".join(scenarios)))
        return self.get("/tpc/fit_cfd_charges", p)

    def tnuos_forecast(self, scenarios=None, zone_names=None):
        p = []
        if scenarios:
            p.append(("scenarios", ",".join(scenarios)))
        for z in zone_names or []:                    # repeated param: names contain commas
            p.append(("zone_names", z))
        return self.get("/tnuos/forecast", p)
