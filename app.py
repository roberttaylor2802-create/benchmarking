"""
Cornwall Insight API Explorer
Run:  streamlit run app.py
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date

import altair as alt
import pandas as pd
import requests
import streamlit as st

import cornwall_api as ci
import demo_data

st.set_page_config(page_title="Cornwall API Explorer", page_icon="⚡", layout="wide")

# Fixed categorical order (validated palette, light surface). Never cycled.
PALETTE = ["#257de0", "#f47230", "#00b894", "#f2a600", "#ee7fac", "#008a17", "#6a4ce2", "#ec4647"]
MAX_SERIES = len(PALETTE)


# ----------------------------------------------------------------------------------
# Connection
# ----------------------------------------------------------------------------------
def _secret_key() -> str:
    try:
        return st.secrets.get("CORNWALL_API_KEY", "")
    except Exception:          # no secrets.toml
        return ""


with st.sidebar:
    st.header("Connection")
    preset = _secret_key() or os.environ.get("CORNWALL_API_KEY", "")
    if preset:
        st.success("API key loaded from secrets / environment")
        api_key = preset
    else:
        api_key = st.text_input("API key", type="password",
                                help="Better: put it in .streamlit/secrets.toml or the CORNWALL_API_KEY env var")
    demo = st.toggle("Use sample data (no API call)", value=not api_key,
                     help="Synthetic data shaped like the API - for trying the app, NOT Cornwall figures")
    if demo:
        st.warning("Showing SAMPLE data, not Cornwall figures.")
    base_url = st.text_input("Base URL", ci.BASE_URL)
    if st.button("Clear cached results"):
        st.cache_data.clear()
        st.session_state.clear()
        st.rerun()

key_fp = hashlib.sha256(api_key.encode()).hexdigest()[:12] if api_key else "none"


@st.cache_data(ttl=3600, show_spinner="Calling Cornwall API…")
def fetch(endpoint: str, params_json: str, is_demo: bool, url: str, key_fp: str, _key: str):
    params = json.loads(params_json)
    src = demo_data if is_demo else ci.CornwallClient(_key, base_url=url)
    return getattr(src, endpoint)(**params)


def run(endpoint: str, state_key: str, **params):
    """Call an endpoint, store the result in session_state, show friendly errors."""
    if not demo and not api_key:
        st.error("Enter an API key in the sidebar, or switch on sample data.")
        return
    try:
        df, url = fetch(endpoint, json.dumps(params, default=str, sort_keys=True), demo, base_url, key_fp, api_key)
    except ci.CornwallAPIError as e:
        hint = {401: "Key rejected - check it with your API Admin in CATALYST and that it has this endpoint enabled.",
                400: "A parameter value isn't valid for the current publication.",
                403: "Key isn't permitted for this endpoint."}.get(e.status, "")
        st.error(f"{e}\n\n{hint}")
        return
    except requests.RequestException as e:
        st.error(f"Network error reaching the API: {e}")
        return
    st.session_state[state_key] = df
    st.session_state.setdefault("log", []).insert(0, {"time": pd.Timestamp.now().strftime("%H:%M:%S"),
                                                     "endpoint": endpoint, "rows": len(df), "url": url})


def download(df: pd.DataFrame, name: str):
    st.download_button("Download CSV", df.to_csv(index=False).encode(), f"{name}_{date.today():%Y%m%d}.csv",
                       "text/csv", key=f"dl_{name}")


def facet_lines(df, x, y, facet, series, y_title, x_type="O", columns=3):
    """Small multiples: one panel per `facet`, colour by `series` (max 8)."""
    labels = list(dict.fromkeys(df[series]))
    if len(labels) > MAX_SERIES:
        st.info(f"Chart shows the first {MAX_SERIES} of {len(labels)} series - narrow the filters to see others. "
                "The table below has everything.")
        labels = labels[:MAX_SERIES]
        df = df[df[series].isin(labels)]
    base = alt.Chart(df).encode(
        x=alt.X(f"{x}:{x_type}", title=None, axis=alt.Axis(labelAngle=0, grid=False)),
        y=alt.Y(f"{y}:Q", title=y_title, axis=alt.Axis(gridOpacity=0.4)),
        color=alt.Color(f"{series}:N", scale=alt.Scale(domain=labels, range=PALETTE[:len(labels)]),
                        legend=alt.Legend(orient="top", title=None, labelLimit=400)),
        tooltip=[alt.Tooltip(f"{facet}:N"), alt.Tooltip(f"{series}:N"), alt.Tooltip(f"{x}:{x_type}"),
                 alt.Tooltip(f"{y}:Q", format=",.4f")],
    )
    layer = base.mark_line(strokeWidth=2) + base.mark_point(size=60, filled=True)
    chart = (layer.properties(width=230, height=150)
             .facet(facet=alt.Facet(f"{facet}:N", title=None, header=alt.Header(labelFontWeight="bold")),
                    columns=columns)
             .resolve_scale(y="independent"))
    st.altair_chart(chart, width="content")


# ----------------------------------------------------------------------------------
# Loss mapping used by the workbook ('Cornwall Loss Adjusted' column A)
# ----------------------------------------------------------------------------------
def default_loss_point(component: str) -> str:
    c = component.lower()
    if any(k in c for k in ["bsuos", "balancing", "contracts for difference", "cfd", "rab", "capacity market"]):
        return "NBP"
    if "aahedc" in c or "hdca" in c:
        return "GSP"
    if any(k in c for k in ["renewables obligation", "(ro)", "feed-in", "fit", "eii"]):
        return "MSP"
    return "None"


def fy_index(fy: str, base: str) -> int:
    return int(str(fy)[:4]) - int(base[:4])


# ----------------------------------------------------------------------------------
st.title("Cornwall Insight API Explorer")
st.caption("Third Party Charges and TNUoS forecasts from the Cornwall Insight Data API (v1)")

tabs = st.tabs(["TPC overall charges", "Curve inputs (workbook view)", "Non-locational TPC",
                "FiT & CfD (quarterly)", "TNUoS", "Request log"])

# ---- 1. Overall charges ------------------------------------------------------------
with tabs[0]:
    with st.form("oc"):
        c1, c2, c3 = st.columns(3)
        arch = c1.multiselect("Archetypes", ci.ARCHETYPES, ["Large non-domestic"])
        fuels = c1.multiselect("Fuel", ci.FUEL_TYPES, ["Electricity"])
        eregs = c2.multiselect("Electricity regions", ci.ELECTRICITY_REGIONS, ["Average across all regions"])
        gregs = c2.multiselect("Gas regions", ci.GAS_REGIONS, ["Average across all regions"])
        cm = c3.selectbox("Capacity Market consumption", ci.CM_CONSUMPTION)
        cfd = c3.selectbox("CfD scenario", ci.CFD_SCENARIOS)
        c4, c5, c6, c7 = st.columns(4)
        ed3 = c4.selectbox("RIIO-ED3", ci.RIIOED3)
        et3 = c5.selectbox("RIIO-ET3", ci.RIIOET3)
        fy_from = c6.number_input("From year (start of FY)", 2020, 2050, 2026)
        fy_to = c7.number_input("To year (start of FY)", 2020, 2060, 2035)
        go = st.form_submit_button("Fetch", type="primary")
    if go:
        run("overall_charges", "oc_df", archetypes=arch, fuel_types=fuels, electricity_regions=eregs,
            gas_regions=gregs, cm_consumption=cm, cfd_scenario=cfd, riioed3=ed3, riioet3=et3,
            from_date=int(fy_from), to_date=int(fy_to))
    df = st.session_state.get("oc_df")
    if df is not None and not df.empty:
        st.caption("Values are **real p/kWh in 2026-27 prices** (per the API reference).")
        df = df.copy()
        df["series"] = df["archetype"] + " · " + df["fuel"] + " · " + df["region"]
        comps = list(dict.fromkeys(df["component"]))
        show = st.multiselect("Components", comps, comps, key="oc_comps")
        facet_lines(df[df["component"].isin(show)], "forecast_year", "value", "component", "series", "p/kWh (real)")
        st.subheader("Table")
        pv = df.pivot_table(index=["series", "component"], columns="forecast_year", values="value", aggfunc="first")
        tot = pv.groupby(level="series").sum()
        tot.index = pd.MultiIndex.from_tuples([(s, "Total") for s in tot.index], names=pv.index.names)
        st.dataframe(pd.concat([pv, tot]).sort_index().style.format("{:.4f}"), width="stretch")
        download(df.drop(columns="series"), "tpc_overall_charges")
    elif df is not None:
        st.info("No rows returned for that selection.")

# ---- 2. Workbook view ----------------------------------------------------------------
with tabs[1]:
    st.markdown("Rebuilds the **Large non-domestic → Cornwall Loss Adjusted** step of the Curve Generator "
                "workbook and the post-forecast uplifts (Inputs B11:B13).")
    with st.form("wb"):
        c1, c2, c3, c4 = st.columns(4)
        lf_msp = c1.number_input("MSP loss", value=0.0, step=0.005, format="%.3f")
        lf_gsp = c2.number_input("GSP loss", value=0.07, step=0.005, format="%.3f")
        lf_nbp = c3.number_input("NBP loss", value=0.085, step=0.005, format="%.3f")
        bsc = c4.number_input("Elexon BSC cost added to EII (p/kWh)", value=0.0, format="%.4f")
        c5, c6, c7 = st.columns(3)
        infl = c5.number_input("Inflation for nominal conversion (% p.a.)", value=2.0, step=0.1,
                               help="ASSUMPTION - replace with your house CPI/RPI path. API values are real 2026-27 prices.")
        cfd_s = c6.selectbox("CfD scenario", ci.CFD_SCENARIOS, key="wb_cfd")
        cm_s = c7.selectbox("CM consumption", ci.CM_CONSUMPTION, key="wb_cm")
        go = st.form_submit_button("Fetch & build", type="primary")
    if go:
        run("overall_charges", "wb_df", archetypes=["Large non-domestic"], fuel_types=["Electricity"],
            electricity_regions=["Average across all regions"], gas_regions=None, cm_consumption=cm_s,
            cfd_scenario=cfd_s, riioed3="Central", riioet3="Baseline", from_date=None, to_date=None)
        st.session_state["wb_params"] = dict(MSP=lf_msp, GSP=lf_gsp, NBP=lf_nbp, bsc=bsc, infl=infl)
    df = st.session_state.get("wb_df")
    prm = st.session_state.get("wb_params")
    if df is not None and not df.empty and prm:
        real = df.pivot_table(index="component", columns="forecast_year", values="value", aggfunc="first")
        real = real[sorted(real.columns)]
        base = "2026-27"
        factors = pd.Series({fy: (1 + prm["infl"] / 100) ** fy_index(fy, base) for fy in real.columns})
        nominal = real * factors

        st.markdown("**Loss point per component** - edit if the API's names don't match")
        mapping = st.data_editor(
            pd.DataFrame({"component": real.index, "loss_point": [default_loss_point(c) for c in real.index]}),
            column_config={"loss_point": st.column_config.SelectboxColumn(options=["None", "MSP", "GSP", "NBP"])},
            hide_index=True, key="wb_map", width="stretch")
        lf = {"None": 0.0, "MSP": prm["MSP"], "GSP": prm["GSP"], "NBP": prm["NBP"]}
        adj = nominal.copy()
        for _, r in mapping.iterrows():
            adj.loc[r.component] = nominal.loc[r.component] * (1 - lf[r.loss_point])
        eii = [c for c in adj.index if "eii" in c.lower()]
        for c in eii:
            adj.loc[c] = adj.loc[c] + prm["bsc"]

        st.markdown("**Nominal p/kWh** (money of the day)")
        st.dataframe(nominal.style.format("{:.4f}"), width="stretch")
        st.markdown("**Loss adjusted, nominal p/kWh**")
        st.dataframe(adj.style.format("{:.4f}"), width="stretch")

        def avg_growth(row):
            vals = row.dropna().values
            return float(pd.Series(vals[1:] / vals[:-1] - 1).mean()) if len(vals) > 1 else float("nan")

        st.markdown("**Post-forecast uplift** (average year-on-year growth; BSUoS & EII default to 10% if negative)")
        ups = []
        for label, keys, floor in [("RAB", ["rab"], False), ("BSUoS", ["bsuos", "balancing"], True),
                                   ("EII Support Levy", ["eii"], True)]:
            match = [c for c in adj.index if any(k in c.lower() for k in keys)]
            if match:
                g = avg_growth(adj.loc[match[0]])
                ups.append({"Charge": label, "Component": match[0],
                            "Uplift": 0.10 if floor and g < 0 else g})
        if ups:
            cols = st.columns(len(ups))
            for col, u in zip(cols, ups):
                col.metric(u["Charge"], f"{u['Uplift']:.2%}", help=u["Component"])
        out = adj.reset_index().melt(id_vars="component", var_name="forecast_year", value_name="p_per_kwh_nominal_loss_adj")
        download(out, "cornwall_loss_adjusted")

# ---- 3. Non-locational ---------------------------------------------------------------
with tabs[2]:
    with st.form("nl"):
        c1, c2, c3 = st.columns(3)
        typ = c1.selectbox("Type", ["non-domestic", "domestic"])
        cm = c2.selectbox("Capacity Market consumption", ci.CM_CONSUMPTION, key="nl_cm")
        cfd = c3.selectbox("CfD scenario", ci.CFD_SCENARIOS, key="nl_cfd")
        go = st.form_submit_button("Fetch", type="primary")
    if go:
        run("non_locational_charges", "nl_df", type_=typ, cm_consumption=cm, cfd_scenario=cfd)
    df = st.session_state.get("nl_df")
    if df is not None and not df.empty:
        st.caption("National-average electricity components. EII Support Levy at its default RIIO case.")
        facet_lines(df, "forecast_year", "value", "component", "fuel", "value")
        st.dataframe(df.pivot_table(index="component", columns="forecast_year", values="value").style.format("{:.4f}"),
                     width="stretch")
        download(df, "tpc_non_locational")

# ---- 4. FiT & CfD quarterly ----------------------------------------------------------
with tabs[3]:
    with st.form("fc"):
        c1, c2 = st.columns(2)
        fd = c1.date_input("Quarters starting on or after", date(2026, 4, 1))
        scen = c2.multiselect("Scenarios", ci.FIT_CFD_SCENARIOS, ["Central"])
        go = st.form_submit_button("Fetch", type="primary")
    if go:
        run("fit_cfd_charges", "fc_df", from_date=fd.isoformat(), scenarios=scen)
    df = st.session_state.get("fc_df")
    if df is not None and not df.empty:
        df = df.copy()
        df["quarter_start"] = pd.to_datetime(df["datefrom"]).dt.date.astype(str)
        measures = [c for c in ["fit_value", "cfd_value", "cfd_ocl", "cfd_reservefund"] if c in df.columns]
        long = df.melt(id_vars=["quarter_start", "scenario"], value_vars=measures, var_name="measure")
        st.caption("Units aren't stated in the API reference yet - confirm with Cornwall before using.")
        facet_lines(long, "quarter_start", "value", "measure", "scenario", "value", columns=2)
        st.dataframe(df.drop(columns="quarter_start"), width="stretch", hide_index=True)
        download(df.drop(columns="quarter_start"), "fit_cfd_quarterly")

# ---- 5. TNUoS ------------------------------------------------------------------------
with tabs[4]:
    with st.form("tn"):
        c1, c2 = st.columns([1, 2])
        scen = c1.multiselect("Scenarios", ci.TNUOS_SCENARIOS, ["Central"])
        zones = c2.multiselect("Zones (leave empty for all)", ci.TNUOS_ZONES, [])
        go = st.form_submit_button("Fetch", type="primary")
    if go:
        run("tnuos_forecast", "tn_df", scenarios=scen, zone_names=zones)
    df = st.session_state.get("tn_df")
    if df is not None and not df.empty:
        metrics = [c for c in ["peak_security", "year_round_shared", "year_round_not_shared", "residual"] if c in df.columns]
        long = df.melt(id_vars=["scenario", "zone_name", "forecast_year"], value_vars=metrics, var_name="metric")
        sc = st.selectbox("Scenario to chart", sorted(df["scenario"].unique()))
        facet_lines(long[long["scenario"] == sc], "forecast_year", "value", "metric", "zone_name", "value", columns=2)
        st.dataframe(df, width="stretch", hide_index=True)
        download(df, "tnuos_forecast")

# ---- 6. Log --------------------------------------------------------------------------
with tabs[5]:
    log = st.session_state.get("log", [])
    if log:
        st.dataframe(pd.DataFrame(log), width="stretch", hide_index=True)
    else:
        st.info("No requests yet.")
