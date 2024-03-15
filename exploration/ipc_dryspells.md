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

# IPC - dry spells

```python
%load_ext jupyter_black
%load_ext autoreload
%autoreload 2
```

```python
import os
from pathlib import Path

import plotly.express as px
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

from src.datasources import ipc, codab, era5
from src import constants
```

## Load data

### CODAB

```python
adm2 = codab.load_codab()
adm2_aoi = adm2[adm2["ADM2_PCODE"].isin(constants.NEW_ADM2_AOI_PCODES)]
```

```python
adm2_aoi.plot()
```

### Dry spells

```python
dry_spells = era5.load_dry_spells()
df_dry = dry_spells[
    (dry_spells["year"].isin(years))
    & (dry_spells["ADM2_PCODE"].isin(constants.NEW_ADM2_AOI_PCODES))
]
```

### IPC/CH

```python
df = ipc.load_tcd_hdx_ipc()
df = df[
    (df["adm2_pcod2"].notnull())
    & (df["adm3_pcod2"].isnull())
    # & (df["adm1_pcod2"].isin(constants.ADM1_AOI_PCODES))
]
cols = [
    "adm0_name",
    "adm0_pcod2",
    "adm0_pcod3",
    "adm1_name",
    "adm1_pcod2",
    "adm2_name",
    "adm2_pcod2",
    "exercise_code",
    "exercise_label",
    "exercise_year",
    "chtype",
    "reference_code",
    "reference_label",
    "reference_year",
    "population",
    "phase_class",
    "phase1",
    "phase2",
    "phase3",
    "phase4",
    "phase5",
    "phase35",
]
df = df[cols]
df = df.sort_values("reference_year")
for x in [1, 2, 3, 4, 5, "35"]:
    df[f"frac_phase{x}"] = df[f"phase{x}"] / df["population"]

df = df[df["adm2_pcod2"].isin(constants.NEW_ADM2_AOI_PCODES)]
df = df.rename(columns={f"adm{x}_pcod2": f"ADM{x}_PCODE" for x in range(3)})
df
```

```python
exercise_label = "Sep-Dec"
reference_label = "Jun-Aug"
df_ipc = df[
    (df["exercise_label"] == exercise_label)
    & (df["reference_label"] == reference_label)
]
years = df_ipc["exercise_year"].unique()
```

### ERA5 monthly

```python
filename = "tcd_era5_monthly_jas_adm2_mean.csv"
df_monthly = pd.read_csv(era5.ERA5_PROC_DIR / filename)
```

```python
df_monthly
```

### Biomasse

```python
PROC_BIO_DIR = (
    Path(os.getenv("AA_DATA_DIR"))
    / "public"
    / "processed"
    / "tcd"
    / "biomasse"
)
filename = "tcd_adm2_yeardekad_biomasse.csv"
df_bio_all = pd.read_csv(PROC_BIO_DIR / filename)
season_dekads = range(19, 28)
df_bio = (
    df_bio_all[
        df_bio_all["dekad"].isin(season_dekads)
        & df_bio_all["year"].isin(years)
    ]
    .groupby(["ADM2_PCODE", "year"])["value"]
    .mean()
    .reset_index()
    .rename(columns={"value": "biomasse"})
)

df_bio
```

## Calc correlations

```python
dicts = []
for adm2_pcode in df_ipc["ADM2_PCODE"].unique():
    df_dry_adm2 = (
        df_dry[df_dry["ADM2_PCODE"] == adm2_pcode][["count", "year"]]
        # .set_index("year")
        # .reindex(years)
        # .fillna(0)
        # .reset_index()
    )

    df_ipc_adm2 = df_ipc[df_ipc["ADM2_PCODE"] == adm2_pcode][
        ["exercise_year", "frac_phase35"]
    ]
    df_monthly_adm2 = df_monthly[df_monthly["ADM2_PCODE"] == adm2_pcode]
    df_adm2 = (
        df_ipc_adm2.merge(
            df_dry_adm2[["count", "year"]],
            left_on="exercise_year",
            right_on="year",
            how="left",
        )
        .drop(columns="year")
        .fillna(0)
    )
    df_adm2["count"] = df_adm2["count"].astype(int)

    df_adm2 = df_adm2.merge(
        df_monthly_adm2[["tp", "year"]],
        left_on="exercise_year",
        right_on="year",
    ).drop(columns=["year"])

    df_bio_adm2 = df_bio[df_bio["ADM2_PCODE"] == adm2_pcode]
    df_adm2 = df_adm2.merge(
        df_bio_adm2,
        left_on="exercise_year",
        right_on="year",
    ).drop(columns=["year"])

    print(df_adm2)
    dry_corr = df_adm2["count"].corr(df_adm2["frac_phase35"])
    monthly_corr = df_adm2["tp"].corr(df_adm2["frac_phase35"])
    bio_corr = df_adm2["biomasse"].corr(df_adm2["frac_phase35"])
    dicts.append(
        {
            "ADM2_PCODE": adm2_pcode,
            "dry_corr": dry_corr,
            "monthly_corr": monthly_corr,
            "bio_corr": bio_corr,
        }
    )
```

```python
df_corr = pd.DataFrame(dicts)
```

```python
df_corr.mean(numeric_only=True)
```

```python
filename = "tcd_adm2_ch_correlations.csv"
df_corr.rename(
    columns={
        "dry_corr": "dryspell_corr",
        "monthly_corr": "totalprecip_corr",
        "bio_corr": "biomasse_corr",
    }
).merge(adm2_aoi[["ADM2_PCODE", "ADM2_FR"]]).to_csv(
    ipc.IPC_PROC_DIR / filename, index=False
)
```

## Plots

```python
corr_plot = adm2_aoi.merge(df_corr, on="ADM2_PCODE")
```

```python
fig, ax = plt.subplots(figsize=(12, 6))
corr_plot[~corr_plot["dry_corr"].isna()].plot(
    column="dry_corr", legend=True, ax=ax, cmap="PuOr", vmax=1, vmin=-1
)
corr_plot[corr_plot["dry_corr"].isna()].plot(
    ax=ax, hatch="//", facecolor="white", edgecolor="grey"
)
adm2_aoi.boundary.plot(linewidth=0.5, color="k", ax=ax)
adm2_aoi.apply(
    lambda x: ax.annotate(
        text=x["ADM2_FR"],
        xy=x.geometry.centroid.coords[0],
        ha="center",
        va="center",
        fontsize=8,
    ),
    axis=1,
)
ax.axis("off")
ax.set_title(
    "Corrélation entre compte de séquences sèches et "
    "frac. de population phase CH 3+ (depuis 2015)"
)
```

```python
fig, ax = plt.subplots(figsize=(12, 6))
corr_plot.plot(
    column="monthly_corr",
    legend=True,
    ax=ax,
    cmap="PuOr_r",
    vmax=1,
    vmin=-1,
)

adm2_aoi.boundary.plot(linewidth=0.5, color="k", ax=ax)
adm2_aoi.apply(
    lambda x: ax.annotate(
        text=x["ADM2_FR"],
        xy=x.geometry.centroid.coords[0],
        ha="center",
        va="center",
        fontsize=8,
    ),
    axis=1,
)
ax.axis("off")
ax.set_title(
    "Corrélation entre précipitation totale JAS et "
    "frac. de population phase CH 3+ (depuis 2015)"
)
```

```python
fig, ax = plt.subplots(figsize=(12, 6))
corr_plot.plot(
    column="bio_corr", legend=True, ax=ax, cmap="PuOr_r", vmax=1, vmin=-1
)

adm2_aoi.boundary.plot(linewidth=0.5, color="k", ax=ax)
adm2_aoi.apply(
    lambda x: ax.annotate(
        text=x["ADM2_FR"],
        xy=x.geometry.centroid.coords[0],
        ha="center",
        va="center",
        fontsize=8,
    ),
    axis=1,
)
ax.axis("off")
ax.set_title(
    "Corrélation entre biomasse moyenne JAS et "
    "frac. de population phase CH 3+ (depuis 2015)"
)
```

```python

```
