---
jupyter:
  jupytext:
    formats: ipynb,md
    text_representation:
      extension: .md
      format_name: markdown
      format_version: '1.3'
      jupytext_version: 1.16.1
  kernelspec:
    display_name: ds-aa-tcd-drought
    language: python
    name: ds-aa-tcd-drought
---

# IPC / CH evolution by département

Evolution of Cadre Harmonisé (CH) food insecurity over time, at the lowest
admin level available for Chad (ADM2 / département), for the whole country and
for the AA framework area.

- Data layer: `src/datasources/ipc.py` (HDX → blob, IPC API cross-check).
- Report builder: `analysis/ipc_ch_evolution/generate_report.py`
  → writes `docs/ipc_ch_evolution/index.html`.

```python
%load_ext jupyter_black
%load_ext autoreload
%autoreload 2
```

```python
from src.datasources import ipc, codab
from analysis.ipc_ch_evolution import generate_report
```

## Refresh data (optional)

Pull the latest consolidated CH file from HDX, mirror raw to blob, and write the
processed Chad ADM2 time series back to blob. This also folds in any
OCHA-shared workbooks not yet on HDX (see `ipc.OCHA_CH_WORKBOOKS`, e.g. the
May 2026 analysis under `raw/ipc/ocha/`). Only needed when a new CH round is
published or shared.

```python
# ipc.refresh()          # HDX + OCHA workbooks
# ipc.process_ch()       # reprocess from the already-mirrored raw files
```

## Load processed time series

```python
ts = ipc.load_adm2_timeseries()
ts.head()
```

```python
print(f"{ts['ADM2_PCODE'].nunique()} départements, "
      f"{ts['valid_date'].nunique()} periods "
      f"({ts['valid_date'].min():%b %Y} → {ts['valid_date'].max():%b %Y})")
```

## National vs framework-AOI aggregates (latest projection)

```python
natl = ipc.aggregate(ts)
aoi = ipc.aggregate(ts[ts["is_aoi"]])
print(f"Country : {natl['phase35'].iloc[-1]/1e6:.2f} M "
      f"({natl['frac_phase35'].iloc[-1]*100:.1f}%)")
print(f"AOI     : {aoi['phase35'].iloc[-1]/1e6:.2f} M "
      f"({aoi['frac_phase35'].iloc[-1]*100:.1f}%)")
print(f"AOI share of national phase-3+ burden: "
      f"{aoi['phase35'].iloc[-1]/natl['phase35'].iloc[-1]*100:.0f}%")
```

## Cross-check the latest round against the IPC API

HDX is the historical backbone (2014→present); the IPC API only reaches back to
Nov 2020, so it is used here purely to validate the most recent projection.

```python
ipc.crosscheck_latest_with_api(ts)
```

## Most recent analysis — CH May 2026

The May 2026 CH analysis (current Mar–May 2026 + projected Jun–Aug 2026) is
newer than anything on the IPC API / HDX. The official CH workbook shared by
OCHA Chad is mirrored to `raw/ipc/ocha/` and folded into the time series, so it
appears directly in every figure. Its headline national figures — verified
against the workbook (3.18 M / 17.5 %; six provinces hold 1.45 M ≈ 46 %) — are
also kept in `ipc.LATEST_REPORTED` for the report callout.

```python
ipc.LATEST_REPORTED
```

## Build the report

Regenerates all figures and the self-contained HTML page under `docs/`.

```python
ts = ipc.load_adm2_timeseries()
adm2_geo = codab.load_codab_from_blob(admin_level=2)
adm1_geo = codab.load_codab_from_blob(admin_level=1)
generate_report.make_figures(ts, adm2_geo, adm1_geo)
summary = generate_report.compute_summary(ts)
generate_report.build_html(ts, summary)
```
