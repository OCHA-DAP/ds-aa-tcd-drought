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

# Biomasse 2025

```python
%load_ext jupyter_black
%load_ext autoreload
%autoreload 2
```

```python
import matplotlib.pyplot as plt
import statsmodels.api as sm
import numpy as np

from src.datasources import biomasse as bm
from src.constants import *
from src.utils.rp_calc import calculate_one_group_rp
from src.utils import blob_utils
```

```python
NEW_ADM1_AOI_PCODES
```

```python
bm.download_dmp(admin_level="ADM1")
```

```python
dmp = bm.calculate_biomasse(admin_level="ADM1")
```

```python
[x in dmp["admin1Pcod"].unique() for x in NEW_ADM1_AOI_PCODES]
```

```python
bm.aggregate_biomasse(
    admin_pcodes=NEW_ADM1_AOI_PCODES, iso3="tcd", admin_level="ADM1"
)
```

```python
df_bm = bm.load_aggregated_biomasse_data(iso3="tcd", admin_level="ADM1")
df_bm = df_bm[df_bm["dekad"] == 24]
```

```python
df_bm
```

```python
df_bm["biomasse"].mean()
```

```python
col = "biomasse"
X = sm.add_constant(df_bm.index)
model = sm.OLS(df_bm[col], X).fit()
display(model.summary())
df_bm[f"{col}_linearfit"] = model.fittedvalues
```

```python
df_bm
```

```python
df_bm.set_index("year")[["biomasse", "biomasse_linearfit"]].plot()
```

```python
df_bm["biomasse_linearfit_anomaly"] = (
    df_bm["biomasse"] / df_bm["biomasse_linearfit"] * 100
)
```

```python
df_bm.set_index("year")[
    ["biomasse_anomaly", "biomasse_linearfit_anomaly"]
].plot()
```

```python
for x in ["", "_linearfit"]:
    col = f"biomasse{x}_anomaly"
    df_bm = calculate_one_group_rp(df_bm, col)
```

```python
df_bm
```

```python
df_interp = df_bm.sort_values("biomasse_anomaly")
old_rp = np.interp(
    80, df_interp["biomasse_anomaly"], df_interp["biomasse_anomaly_rp"]
)
```

```python
old_rp
```

```python
df_interp = df_bm.sort_values("biomasse_linearfit_anomaly", ascending=False)
new_thresh = np.interp(
    old_rp,
    df_interp["biomasse_linearfit_anomaly_rp"],
    df_interp["biomasse_linearfit_anomaly"],
)
```

```python
new_thresh
```

```python
df_bm.sort_values("biomasse_linearfit_anomaly")
```

```python
fixed_rp = 5
raw_thresh = df_bm["biomasse_anomaly"].quantile(1 / fixed_rp)
trend_thresh = df_bm["biomasse_linearfit_anomaly"].quantile(1 / fixed_rp)
```

```python
raw_thresh, trend_thresh
```

```python
fig, ax = plt.subplots(dpi=200, figsize=(8, 8))

raw_color = "royalblue"
trend_color = "crimson"
both_color = "rebeccapurple"
none_color = "lightgrey"

alpha = 0.15

lims = (60, 140)

raw_thresh = df_bm["biomasse_anomaly"].quantile(1 / fixed_rp)
trend_thresh = df_bm["biomasse_linearfit_anomaly"].quantile(1 / fixed_rp)

ax.axhline(trend_thresh, color=trend_color)
ax.axhspan(ymin=lims[0], ymax=trend_thresh, facecolor=trend_color, alpha=alpha)

ax.axvline(raw_thresh, color=raw_color)
ax.axvspan(xmin=lims[0], xmax=raw_thresh, facecolor=raw_color, alpha=alpha)

for year, row in df_bm.set_index("year").iterrows():
    if (
        row["biomasse_anomaly"] < raw_thresh
        and row["biomasse_linearfit_anomaly"] < trend_thresh
    ):
        color = both_color
    elif row["biomasse_anomaly"] < raw_thresh:
        color = raw_color
    elif row["biomasse_linearfit_anomaly"] < trend_thresh:
        color = trend_color
    else:
        color = none_color
    ax.annotate(
        year,
        (row["biomasse_anomaly"], row["biomasse_linearfit_anomaly"]),
        fontsize=8,
        ha="center",
        va="center",
        color=color,
        fontweight="bold",
    )

ax.set_xlim(lims)
ax.set_ylim(lims)

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
```

```python

```
