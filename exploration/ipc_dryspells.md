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
import plotly.express as px
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

from src.datasources import ipc, codab, era5
from src import constants
```

```python
test = era5.load_dry_spells()
```

```python
test["ADM2_PCODE"].nunique()
```

```python
adm2 = codab.load_codab()
adm2_aoi = adm2[adm2["ADM2_PCODE"].isin(constants.NEW_ADM2_AOI_PCODES)]
```

```python
adm2_aoi.plot()
```

```python
dry_spells = era5.load_dry_spells()
```

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

```python
df_ipc["ADM2_PCODE"].nunique()
```

```python
years
```

```python
dry_spells["ADM2_PCODE"].nunique()
```

```python
df_dry = dry_spells[
    (dry_spells["year"].isin(years))
    & (dry_spells["ADM2_PCODE"].isin(constants.NEW_ADM2_AOI_PCODES))
]
df_dry["ADM2_PCODE"].nunique()
```

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
    print(df_adm2)
    corr = df_adm2["count"].corr(df_adm2["frac_phase35"])
    dicts.append({"ADM2_PCODE": adm2_pcode, "corr": corr})
```

```python
df_corr = pd.DataFrame(dicts)
```

```python
# df_corr = df_corr.fillna(0.0)
```

```python
corr_plot
```

```python
years
```

```python
corr_plot = adm2_aoi.merge(df_corr, on="ADM2_PCODE")

fig, ax = plt.subplots(figsize=(12, 6))
corr_plot[~corr_plot["corr"].isna()].plot(
    column="corr", legend=True, ax=ax, cmap="PuOr", vmin=-0.7, vmax=0.7
)
corr_plot[corr_plot["corr"].isna()].plot(ax=ax, hatch="///", facecolor="white")
adm2_aoi.boundary.plot(linewidth=0.5, color="k", ax=ax)
ax.axis("off")
ax.set_title(
    "Corrélation entre compte de séquences sèches et "
    "frac. de population phase CH 3+ (depuis 2015)"
)
```

```python

```
