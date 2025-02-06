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

# Switch ECMWF

```python
%load_ext jupyter_black
%load_ext autoreload
%autoreload 2
```

```python
import calendar

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import statsmodels.api as sm
from matplotlib.ticker import LogLocator, FuncFormatter
from dask.diagnostics import ProgressBar

from src.datasources import seas5, codab, iri
from src.utils.raster import upsample_dataarray
from src.constants import *
from src.utils import blob_utils
from src.utils.rp_calc import calculate_groups_rp
```

## SEAS5

### Loading and processing

```python
df_seas5 = seas5.load_seas5_stats()
```

```python
df_seas5
```

```python
df_seas5.groupby("issued_month")["q"].mean().plot()
```

Note major leadtime bias! This is something we had seen before.

```python
df_seas5["window"] = df_seas5["issued_month"].apply(
    lambda x: 1 if x <= 4 else 2
)
```

```python
df_seas5 = calculate_groups_rp(df_seas5, by=["issued_month"])
```

```python
df_seas5
```

### Compare individual/combined RP

```python
total_years = df_seas5["year"].nunique()
dicts = []
for rp_individual in df_seas5["q_rp"].unique():
    dff = df_seas5[df_seas5["q_rp"] >= rp_individual]
    n_years = dff["year"].nunique()
    rp_combined = (total_years + 1) / n_years
    dicts.append({"rp_individual": rp_individual, "rp_combined": rp_combined})

df_rps = pd.DataFrame(dicts).sort_values("rp_individual")
```

```python
fig, ax = plt.subplots(dpi=200)

df_rps.plot(x="rp_individual", y="rp_combined", ax=ax, legend=False)

ax.set_xlim(left=1)
ax.set_ylim(bottom=1)

ax.set_xlabel("Période de retour de chaque prévision individuellement (ans)")
ax.set_ylabel("Période de retour combinée des prévisions (ans)")
ax.set_title("Comparaison du période de retour individuelle et combinée")

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
```

```python
min_year = 2000

df_seas5_recent = df_seas5[df_seas5["year"] >= min_year]
```

```python
df_seas5_recent = calculate_groups_rp(df_seas5_recent, by=["issued_month"])
```

```python
total_years_recent = df_seas5_recent["year"].nunique()
dicts = []
for rp_individual in df_seas5_recent["q_rp"].unique():
    dff = df_seas5_recent[df_seas5_recent["q_rp"] >= rp_individual]
    n_years = dff["year"].nunique()
    rp_combined = (total_years_recent + 1) / n_years
    dicts.append({"rp_individual": rp_individual, "rp_combined": rp_combined})

df_rps_recent = pd.DataFrame(dicts).sort_values("rp_individual")
```

```python
df_rps_recent
```

Looks like we need > 8.67 and < 13 for a 3 year combined RP.

```python
fig, ax = plt.subplots(dpi=200)

df_rps_recent.plot(x="rp_individual", y="rp_combined", ax=ax, legend=False)

ax.set_xlim(left=1)
ax.set_ylim(bottom=1)

ax.set_xlabel("Période de retour de chaque prévision individuellement (ans)")
ax.set_ylabel("Période de retour combinée des prévisions (ans)")
ax.set_title("Comparaison du période de retour individuelle et combinée")

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
```

```python
rp_individual_seas5 = 9

df_seas5_triggers_recent = df_seas5_recent[
    df_seas5_recent["q_rp"] >= rp_individual_seas5
]
```

```python
rp_combined_seas5 = (total_years_recent + 1) / df_seas5_triggers_recent[
    "year"
].nunique()
```

```python
rp_combined_seas5
```

Looks like 9 will do it.

### Check trend

```python
df_seas5_recent.pivot(index="year", columns="issued_month", values="q").plot()
```

```python
for issued_month, group in df_seas5_recent.groupby("issued_month"):
    X = sm.add_constant(group.index)
    model = sm.OLS(group["q"], X).fit()
    print(f"issued month {issued_month}")
    print(model.summary())
```

Very minor trend on month 5, but otherwise fine. Will leave this for now
and not truncate further to preserve historical record.

### Calculate thresholds

```python
dicts = []
for issued_month, group in df_seas5_recent.groupby("issued_month"):
    group_sorted = group.copy().sort_values("q_rp")
    rp_val = np.interp(
        rp_individual_seas5, group_sorted["q_rp"], group_sorted["q"]
    )
    dicts.append({"issued_month": issued_month, "thresh": rp_val})

df_threshs = pd.DataFrame(dicts)
```

```python
df_threshs
```

### Plot historical activations

```python
fig, ax = plt.subplots(dpi=200, figsize=(7, 7))

ymin, ymax = 0.9, 39
trig_color = "crimson"

shapes = {3: "+", 4: "x", 5: "s", 6: "D"}

for issued_month, group in df_seas5_recent.groupby("issued_month"):
    group.plot(
        x="year",
        y="q_rp",
        marker=shapes.get(issued_month),
        markerfacecolor="none",
        markeredgecolor="black",
        markersize=5,
        linewidth=0,
        ax=ax,
        label=FRENCH_MONTHS.get(calendar.month_abbr[issued_month]),
    )

for year, group in df_seas5_recent.groupby("year"):
    max_val = group["q_rp"].max()
    trigger_bool = max_val >= rp_individual_seas5
    color = trig_color if trigger_bool else "grey"
    fontweight = "bold" if trigger_bool else "normal"
    ax.plot(
        [year, year],
        [ymin, max_val],
        color="grey",
        linewidth=0.1,
        zorder=-1,
    )
    ax.annotate(
        f"{year}  ",
        (year - 0.1, max_val),
        ha="center",
        rotation=-90,
        va="bottom",
        fontsize=8,
        color=color,
        fontweight=fontweight,
    )

ax.axhline(rp_individual_seas5, color=trig_color, zorder=-2)
ax.axhspan(
    ymin=rp_individual_seas5,
    ymax=ymax,
    facecolor=trig_color,
    alpha=0.1,
    zorder=-2,
)

# ax.set_ylim(bottom=0)
ax.set_yscale("log")
ax.yaxis.set_major_locator(
    LogLocator(base=10.0, subs=np.arange(2, 10) * 1, numticks=10)
)
ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0f}"))
ax.set_ylim(top=ymax, bottom=ymin)

ax.set_xticks([])

plt.xticks(rotation=-90)

ax.legend(
    loc="upper left",
    bbox_to_anchor=(1, 1),
    borderaxespad=1.0,
    title="Mois de\npublication",
)

ax.set_title(
    "Prévisions et activations historiques de SEAS5\n"
    f"(période de retour combinée = {rp_combined_seas5:.1f} ans)"
)
ax.set_xlabel("Année")
ax.set_ylabel("Période de retour de prévision (ans)")

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
```

## IRI

### Load and process

```python
adm1 = codab.load_codab_from_blob(admin_level=1, aoi_only=True)
```

```python
ds_iri = iri.load_raw_iri()
```

```python
da_iri = ds_iri.isel(C=0)["prob"]
da_iri = da_iri.rio.write_crs(4326)
```

```python
da_iri_clip_low = da_iri.rio.clip(adm1.geometry, all_touched=True)
```

```python
da_iri_up = upsample_dataarray(da_iri_clip_low, x_var="X", y_var="Y")
```

```python
da_iri_clip = da_iri_up.rio.clip(adm1.geometry)
```

```python
da_iri_q = da_iri_clip.quantile(1 - ORIGINAL_Q, dim=["X", "Y"])
```

```python
da_iri_q
```

```python
df_iri = da_iri_q.to_dataframe("q")["q"].reset_index()
```

```python
df_iri["issued_date"] = pd.to_datetime(df_iri["F"].astype(str))
df_iri["issued_year"] = df_iri["issued_date"].dt.year
df_iri["issued_month"] = df_iri["issued_date"].dt.month
```

```python
df_iri_triggers = df_iri[
    ((df_iri["issued_month"] == 3) & (df_iri["L"] == 4))
    | ((df_iri["issued_month"] == 4) & (df_iri["L"] == 3))
    | ((df_iri["issued_month"] == 5) & (df_iri["L"] == 2))
    | ((df_iri["issued_month"] == 6) & (df_iri["L"] == 1))
][["issued_year", "issued_month", "q"]].rename(columns={"issued_year": "year"})
df_iri_triggers
```

```python
df_iri_triggers.pivot(index="year", columns="issued_month", values="q").plot()
```

## Comparison

```python
df_compare = df_seas5.merge(
    df_iri_triggers, on=["year", "issued_month"], suffixes=["_seas5", "_iri"]
)
```

```python
df_compare
```

### Plot issued months

```python
x_var = "q_iri"
y_var = "q_seas5"
x_color = "darkblue"
y_color = "green"
xmin, xmax = 10, 45
alpha = 0.1

for issued_month in df_compare["issued_month"].unique():
    fig, ax = plt.subplots(dpi=200, figsize=(5, 5))
    dff = df_compare[df_compare["issued_month"] == issued_month]
    rp_val = df_threshs.set_index("issued_month").loc[issued_month, "thresh"]

    for year, row in dff.set_index("year").iterrows():
        ax.annotate(
            year,
            (row[x_var], row[y_var]),
            va="center",
            ha="center",
            fontsize=8,
            fontweight="bold",
        )

    y_buffer = (dff[y_var].max() - dff[y_var].min()) * 0.1
    ymin, ymax = (
        min(dff[y_var].min(), rp_val) - y_buffer,
        dff[y_var].max() + y_buffer,
    )

    ax.axvline(ORIGINAL_IRI_THRESH, color=x_color)
    ax.axvspan(ORIGINAL_IRI_THRESH, xmax, facecolor=x_color, alpha=alpha)
    ax.annotate(
        " Seuil actuel du cadre",
        (ORIGINAL_IRI_THRESH, ymin),
        rotation=90,
        va="bottom",
        ha="right",
        fontsize=8,
        color=x_color,
    )

    ax.axhline(rp_val, color=y_color)
    ax.axhspan(ymin, rp_val, facecolor=y_color, alpha=alpha)
    ax.annotate(
        f" Seuil PR {rp_individual_seas5}-ans = {rp_val:.2f} mm",
        (xmin, rp_val),
        va="bottom",
        ha="left",
        fontsize=8,
        color=y_color,
    )

    ax.set_title(
        "Comparaison des prévisions de "
        f"{FRENCH_MONTHS.get(calendar.month_abbr[issued_month])} "
        f"pour JAS"
    )
    ax.set_ylabel(
        "Précipitations moyennes sur trimestre,\n"
        f"{ORIGINAL_Q*100:.0f}e centile sur zone d'intérêt (mm / jour) [SEAS5]"
    )
    ax.set_xlabel(
        f"Probabilité de précipitations inférieures à normale,\n"
        f"{(1-ORIGINAL_Q)*100:.0f}e centile sur zone d'intérêt (%) [IRI]"
    )

    ax.set_xlim((xmin, xmax))
    ax.set_ylim((ymin, ymax))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
```
