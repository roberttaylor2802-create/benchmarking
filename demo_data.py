"""
Synthetic SAMPLE data shaped like the API responses, so the app can be tried
without a key or network. These are NOT Cornwall Insight figures.
"""
import numpy as np
import pandas as pd

YEARS = ["2026-27", "2027-28", "2028-29", "2029-30", "2030-31"]

ELEC_COMPONENTS = {
    "Transmission": 0.70, "Distribution": 2.00, "System balancing (BSUoS)": 1.45,
    "EII Support Levy": 0.10, "AAHEDC (HDCA)": 0.05, "Renewables Obligation (RO)": 3.30,
    "Feed-in Tariffs (FiT)": 0.85, "Contracts for Difference (CfDs)": 0.35,
    "Nuclear Regulated Asset Base (RAB)": 0.45, "Capacity Market (CM)": 1.15,
    "Climate Change Levy (CCL)": 0.80,
}
GAS_COMPONENTS = {"Transmission": 0.02, "Distribution": 0.33, "Green Gas Levy (GGL)": 0.00001,
                  "Climate Change Levy (CCL)": 0.80}


def _growth(seed):
    return np.random.default_rng(seed).uniform(-0.03, 0.12)


def overall_charges(archetypes, fuel_types, electricity_regions=None, gas_regions=None,
                    cm_consumption="All", cfd_scenario="Central", riioed3="Central",
                    riioet3="Baseline", **_):
    rows = []
    arche_scale = {"Domestic": 1.15, "Small non-domestic": 1.05, "Large non-domestic": 1.0}
    for a in archetypes:
        for f in fuel_types:
            comps = ELEC_COMPONENTS if f == "Electricity" else GAS_COMPONENTS
            regions = (electricity_regions if f == "Electricity" else gas_regions) or ["Average across all regions"]
            for reg in regions:
                for i, (c, base) in enumerate(comps.items()):
                    g = _growth(i)
                    for k, y in enumerate(YEARS):
                        rows.append(dict(component=c, region=reg, fuel=f, archetype=a, forecast_year=y,
                                         value=round(base * arche_scale[a] * (1 + g) ** k, 6),
                                         cm_consumption=cm_consumption, cfd_scenario=cfd_scenario,
                                         riioed3=riioed3, riioet3=riioet3))
    return pd.DataFrame(rows), "demo://tpc/overall_charges"


def non_locational_charges(type_="non-domestic", cm_consumption="All", cfd_scenario="Central"):
    rows = []
    for i, c in enumerate(["Renewables Obligation (RO)", "Feed-in Tariffs (FiT)", "Contracts for Difference (CfDs)",
                           "Capacity Market (CM)", "EII Support Levy", "AAHEDC (HDCA)"]):
        base = ELEC_COMPONENTS[c]
        for k, y in enumerate(YEARS):
            rows.append(dict(component=c, fuel="Electricity", forecast_year=y,
                             value=round(base * (1 + _growth(i)) ** k, 6),
                             cm_consumption=cm_consumption, cfd_scenario=cfd_scenario))
    return pd.DataFrame(rows), "demo://tpc/non_locational_charges"


def fit_cfd_charges(from_date=None, scenarios=None):
    scen = scenarios or ["Central"]
    q = pd.date_range("2026-04-01", "2031-01-01", freq="QS-APR")
    mult = {"Central": 1.0, "High": 1.2, "Low": 0.8}
    rows = []
    for s in scen:
        for k, d in enumerate(q):
            if from_date and d < pd.Timestamp(from_date):
                continue
            cfd = 0.35 * mult[s] * (1 + 0.04 * np.sin(k))
            rows.append(dict(datefrom=d.strftime("%Y-%m-%dT00:00:00.000Z"), scenario=s,
                             cfd_ocl=round(cfd * 0.1, 5), cfd_reservefund=round(cfd * 0.05, 5),
                             cfd_value=round(cfd, 5), fit_value=round(0.85 * mult[s] * (1 + 0.01 * k), 5)))
    return pd.DataFrame(rows), "demo://tpc/fit_cfd_charges"


def tnuos_forecast(scenarios=None, zone_names=None):
    from cornwall_api import TNUOS_ZONES
    rows = []
    for s in scenarios or ["Central"]:
        for z in zone_names or TNUOS_ZONES[:5]:
            zi = TNUOS_ZONES.index(z) + 1
            for y in range(2026, 2031):
                rows.append(dict(run="DEMO", scenario=s, zone=zi, zone_name=z, forecast_year=y,
                                 peak_security=round(1 + 0.05 * zi, 3),
                                 year_round_shared=round(2 + 0.1 * zi + 0.2 * (y - 2026), 3),
                                 year_round_not_shared=0.01, residual=round(-1.5 + 0.05 * zi, 3)))
    return pd.DataFrame(rows), "demo://tnuos/forecast"
