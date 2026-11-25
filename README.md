# Cornwall Insight API Explorer (Streamlit)

## Run it
```
cd cornwall_explorer
pip install -r requirements.txt
streamlit run app.py
```
It opens in your browser at http://localhost:8501.

## API key
Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and paste your key,
or set the `CORNWALL_API_KEY` environment variable, or type it into the sidebar.
Don't commit or share `secrets.toml`.

Switch on "Use sample data" to try the app without a key. Sample figures are synthetic, not Cornwall's.

## Tabs
- **TPC overall charges**: `/tpc/overall_charges`. All filters and sensitivities, small-multiple charts, table with totals, CSV.
- **Curve inputs (workbook view)**: Large non-domestic, Electricity, GB average. Converts real 2026-27 prices to nominal
  using your inflation assumption, applies MSP/GSP/NBP losses as in "Cornwall Loss Adjusted", and calculates the
  RAB/BSUoS/EII post-forecast uplifts (Inputs B11:B13).
- **Non-locational TPC**: `/tpc/non_locational_charges`.
- **FiT & CfD (quarterly)**: `/tpc/fit_cfd_charges`.
- **TNUoS**: `/tnuos/forecast`.
- **Request log**: every call made this session.

Results are cached for an hour. Use "Clear cached results" after a new Cornwall publication.
