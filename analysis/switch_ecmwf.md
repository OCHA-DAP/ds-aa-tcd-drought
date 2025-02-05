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
from matplotlib.ticker import LogLocator, FuncFormatter
from dask.diagnostics import ProgressBar

from src.datasources import seas5, codab
from src.utils.raster import upsample_dataarray
from src.constants import *
from src.utils import blob_utils
from src.utils.rp_calc import calculate_groups_rp
```

```python
df_seas5 = seas5.load_seas5_stats()
```

```python
df_seas5
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
df_seas5
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
fig, ax = plt.subplots(dpi=200)

ymin, ymax = 0.9, 39
trig_color = "rebeccapurple"

for issued_month, group in df_seas5_recent.groupby("issued_month"):
    group.plot(
        x="year",
        y="q_rp",
        marker=".",
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

ax.set_title("Prévisions et activations historiques de SEAS5")
ax.set_xlabel("Année")
ax.set_ylabel("Période de retour de prévision (ans)")

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
```

```python
np.arange(2, 10) * 1,
```
