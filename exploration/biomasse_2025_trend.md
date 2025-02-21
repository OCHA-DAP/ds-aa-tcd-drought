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

# Biomasse trend check

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
```

```python
df_bm = bm.load_aggregated_biomasse_data(iso3="tcd", admin_level="ADM2")
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
df_bm["biomasse_anomaly"].quantile()
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
fig, ax = plt.subplots()

df_bm.plot(
    x="biomasse_anomaly",
    y="biomasse_linearfit_anomaly",
    marker=".",
    linewidth=0,
    ax=ax,
    legend=False,
)
ax.axhline(new_thresh)
ax.axvline(80)
```

```python

```
