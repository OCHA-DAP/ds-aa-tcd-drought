# HNRP 2027 — indice de risque sécheresse par département

Builds the per-département (COD ADM2, 70 units) drought-risk indicators and
composite index requested for the Chad HNRP 2027 shock-analysis workbook,
writes them into a copy of that workbook, and generates the write-up page at
<https://ocha-dap.github.io/ds-aa-tcd-drought/hnrp_2027_secheresse/>.

Three pillars over 2024–2025 (the two most recent complete seasons),
worst of the two:

- **Cadre Harmonisé** phase 3+ share (HDX + the OCHA Chad May-2026 workbook,
  via `src/datasources/ipc.py`), max over the analyses of 2024 and 2025.
- **FAO ASIS ASI**, mean of the dekads 1 June – 21 August, **detrended**
  (additive, 1999–2024 fit, re-centred on the period mean, clipped 0–100).
  Published on 28 GAUL-2015 units, area-weighted onto COD ADM2.
- **GeoSahel biomass** (DMP, `WA_BIO_ADM2_v4`), dekads 10–23 cumulative,
  **detrended** as a ratio to the 1999–2024 trend line, as the AA framework does.

Scores are linear 0–1 between fixed thresholds; index = weighted mean
(CH 0.4, ASI 0.3, biomass 0.3); Saharan provinces get hazard scores of 0.
Estimated rainfall (FEWS NET RFE) was evaluated and dropped as redundant with
the two vegetation signals. Full method on the page.

## Run order

<!-- markdownlint-disable MD013 -->
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
.venv/bin/python $A/build_indicators.py $W  # -> indicators.csv + indicators_by_year.csv
.venv/bin/python $A/inject_xlsx.py $W/hnrp.xlsx $W/hnrp_v2.xlsx $W/indicators.csv
.venv/bin/python $A/gen_page.py $W docs/hnrp_2027_secheresse
```
<!-- markdownlint-enable MD013 -->

`inject_xlsx.py` edits the workbook XML directly rather than round-tripping
through openpyxl, which would drop the slicers, pivot caches and the Power Pivot
data model the workbook carries. The new sheet's scores, index, rank, category
and binary indicator are live formulas reading the weights and thresholds in
row 3; the Recap sheet gets four INDEX/MATCH columns (AI–AL).

The page is bilingual (FR/EN toggle), colours the map by category, and carries an
explorer (single year 1999–2026 or a consolidated range, worst-year or mean, any
subset of the three indicators) and a per-département time-series chart, all
computed in the browser from the per-year table embedded in the page. Raw and
detrended ASI/biomass are both shipped, in the sheet and in the explorer.

The index window is `WINDOW` in `build_indicators.py` and the `$C$3:$K$3` parameter
row in the generated sheet. It excludes 2026 because that season is incomplete
(ASI and biomass stop at dekad 23; the June–August CH is a projection). Note the
consequence: 2024 and 2025 were good pastoral years in the Sahel, so the current
index is driven mostly by the CH and does not show the 2026 drought. The page
explorer recomputes with 2026 included in one click.
