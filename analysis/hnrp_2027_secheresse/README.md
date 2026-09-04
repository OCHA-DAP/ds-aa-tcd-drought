# HNRP 2027 — indice de risque sécheresse par département

Builds the per-département (COD ADM2, 70 units) drought-risk indicators and
composite index requested for the Chad HNRP 2027 shock-analysis workbook,
writes them into a copy of that workbook, and generates the write-up page at
<https://ocha-dap.github.io/ds-aa-tcd-drought/hnrp_2027_secheresse/>.

Pillars (2024–2026): Cadre Harmonisé phase 3+ share (HDX + OCHA Tchad May-2026
workbook, via `src/datasources/ipc.py`), FAO ASIS agricultural stress index and
FEWS NET RFE rainfall (FAO GAUL-2015 units, area-weighted onto COD ADM2), and
GeoSahel biomass (DMP, `WA_BIO_ADM2_v4`). Scores are linear 0–1 between fixed
thresholds; index = weighted mean (CH 0.4, ASI / biomasse / pluie 0.2 each);
Saharan provinces get hazard scores of 0. Full method on the page.

## Run order

```bash
W=work
A=analysis/hnrp_2027_secheresse
$A/fetch_data.sh $W                        # FAO ASIS, GeoSahel, GAUL
PYTHONPATH=. .venv/bin/python $A/prepare_blob_inputs.py $W   # CH, CODAB, crosswalk
cp "<workbook>.xlsx" $W/hnrp.xlsx          # the HNRP workbook
.venv/bin/python - <<'PY'                  # sheet name / p-code list for the join
import pandas as pd
l = pd.read_excel("work/hnrp.xlsx", "Listes departements inclus", header=4)
l = l.iloc[:, 0:5]
l.columns = ["ADM1_FR", "ADM1_PCODE", "ADM2_FR", "ADM2_PCODE", "Portee"]
l.dropna(subset=["ADM2_PCODE"]).to_csv("work/sheet_adm2.csv", index=False)
PY
.venv/bin/python $A/build_indicators.py $W  # -> work/indicators.csv
.venv/bin/python $A/build_timeseries.py $W  # -> work/indicators_by_year.csv (explorer)
.venv/bin/python $A/inject_xlsx.py $W/hnrp.xlsx $W/hnrp_v2.xlsx $W/indicators.csv
.venv/bin/python $A/gen_page.py $W docs/hnrp_2027_secheresse
```

`inject_xlsx.py` edits the workbook XML directly rather than round-tripping
through openpyxl, which would drop the slicers, pivot caches and the Power Pivot
data model the workbook carries. The new sheet's scores, index, rank, category
and binary indicator are live formulas reading the weights and thresholds in
row 3; the Recap sheet gets four INDEX/MATCH columns (AI–AL).

The page is bilingual (FR/EN toggle), colours the map by category, and carries an
explorer (single year 1999–2026 or a consolidated range, worst-year or mean, any
subset of the four indicators) and a per-département time-series chart, all
computed in the browser from `indicateurs_par_annee_adm2.csv` embedded in the page.
