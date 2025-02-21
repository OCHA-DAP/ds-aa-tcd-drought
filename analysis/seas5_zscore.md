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

# SEAS5 Z-score
<!-- markdownlint-enable MD013 -->

Doing the same thing as in `ecmwf_switch` but with Z-score

```python
%load_ext jupyter_black
%load_ext autoreload
%autoreload 2
```

```python
import calendar

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import statsmodels.api as sm
from dask.diagnostics import ProgressBar
from scipy.stats import skewnorm
from matplotlib.ticker import LogLocator, FuncFormatter

from src.datasources import seas5, iri, codab
from src.utils.raster import upsample_dataarray
from src.utils.rp_calc import calculate_groups_rp
from src.utils import blob_utils
from src.constants import *
```

```python
adm1 = codab.load_codab_from_blob(admin_level=1, aoi_only=True)
```

```python
da_seas5 = seas5.open_seas5_rasters()
```

```python
da_seas5.isel(lt=0, issued_month=0, year=0).plot()
```

```python
da_seas5.isel(lt=-1, issued_month=0, year=0).plot()
```

```python
da_seas5.isel(lt=0, issued_month=-1, year=0).plot()
```

```python
da_seas5.isel(lt=-1, issued_month=-1, year=0).plot()
```

```python
da_seas5_tri = da_seas5.mean(dim="lt")
da_seas5_up = upsample_dataarray(da_seas5_tri)
da_seas5_clip = da_seas5_up.rio.clip(adm1.geometry)
```

```python
da_seas5_clip
```

```python
fig, ax = plt.subplots(figsize=(8, 4))
da_seas5_clip.isel(year=-1, issued_month=0).plot(ax=ax, cmap="RdBu")
adm1.boundary.plot(ax=ax, color="k")
ax.axis("off")
```

```python
da_seas5_mean = da_seas5_clip.mean(dim="year")
```

```python
with ProgressBar():
    da_seas5_mean.isel(issued_month=0).plot()
```

```python
da_seas5_std = da_seas5_clip.std(dim="year")
```

```python
with ProgressBar():
    da_seas5_std.isel(issued_month=0).plot()
```

```python
da_seas5_zscore = (da_seas5_clip - da_seas5_mean) / da_seas5_std
```

```python
with ProgressBar():
    da_seas5_zscore_computed = da_seas5_zscore.compute()
```

```python
fig, ax = plt.subplots(figsize=(8, 4))
da_seas5_zscore_computed.isel(year=-1, issued_month=1).plot(ax=ax, cmap="RdBu")
adm1.boundary.plot(ax=ax, color="k")
ax.axis("off")
```

```python
da_seas5_zscore_computed.std(dim=["x", "y"]).mean(dim="year").plot()
```

```python
da_seas5_zscore_computed.mean(dim=["x", "y", "year"]).plot()
```

```python
q = ORIGINAL_Q
da_seas5_zscore_q = da_seas5_zscore.quantile(q=q, dim=["x", "y"])
```

```python
q
```

```python
with ProgressBar():
    da_seas5_zscore_q_computed = da_seas5_zscore_q.compute()
```

```python
da_seas5_zscore_q_computed.isel(issued_month=0).plot()
```

```python
df_seas5_zscore_q = da_seas5_zscore_q_computed.to_dataframe("q")[
    "q"
].reset_index()
```

```python
df_seas5_zscore_q["q"].hist()
```

```python
df_seas5_zscore_q.nunique()
```

```python
df_seas5_zscore_q["q"].quantile(1 / 3)
```

```python
f"{q*100:.0f}"
```

```python
blob_name = f"{blob_utils.PROJECT_PREFIX}/processed/seas5/seas5_zscore_q{q*100:.0f}.parquet"
blob_utils.upload_parquet_to_blob(df_seas5_zscore_q, blob_name)
```

```python
df_seas5 = seas5.load_seas5_stats(variable="zscore")
```

```python
df_seas5
```

```python
# just check the histogram to see that it's sensible
for issued_month, group in df_seas5.groupby("issued_month"):
    group["q"].hist(alpha=0.3)
```

```python
df_seas5.groupby("issued_month")["q"].mean().plot()
```

```python
df_seas5["window"] = df_seas5["issued_month"].apply(
    lambda x: 1 if x <= 4 else 2
)
```

```python
df_seas5 = calculate_groups_rp(df_seas5, by=["issued_month"])
```

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
min_year = 1999

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
rp_individual_seas5 = 10

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

```python
2024 - 1999 + 1
```

```python
27 / 9
```
