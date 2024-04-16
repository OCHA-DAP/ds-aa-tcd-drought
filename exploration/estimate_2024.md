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
    display_name: ds-cmr-flooding-support
    language: python
    name: ds-cmr-flooding-support
---

# Estimate for 2024

```python
%load_ext jupyter_black
%load_ext autoreload
%autoreload 2
```

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from src.datasources import ecmwf, impact, floodscan, codab
```

```python
adm2 = codab.load_codab(admin_level=2)
```

```python
filename = "cmr_adm2_impact_exposed.csv"
impact_exposure = pd.read_csv(impact.IMPACT_PROC_DIR / filename)
x, y = impact_exposure[["total_exposed", "Total personne affecté"]].values.T
slope, intercept = np.polyfit(x, y, 1)


def exposed_to_impact(exposed):
    return max(int(slope * exposed + intercept), 0)
```

```python
fs = floodscan.load_adm_flood_exposures(admin_level=2)
```

```python
fs[fs["ADM2_PCODE"] == "CM004002"].plot(x="year", y="total_exposed")
```

```python
np.percentile(fs[fs["ADM2_PCODE"] == "CM004002"]["total_exposed"], 0)
```

```python
filename = "cmr_ecmwf_m3l456_ranks.csv"
ec = pd.read_csv(ecmwf.ECMWF_PROC_DIR / filename)
```

```python
percentile = ec.set_index("year").loc[2024]["percentile"] * 100
```

```python
high_percentile, low_percentile = percentile + 20, percentile - 20
```

```python
print(high_percentile, low_percentile)
```

```python
fs_2024 = fs.groupby("ADM2_PCODE").first()

for per, per_label in zip(
    [low_percentile, percentile, high_percentile], ["low", "mid", "high"]
):
    fs_2024[f"{per_label}_exp"] = (
        fs.groupby("ADM2_PCODE")["total_exposed"]
        .apply(lambda x: np.percentile(x, per))
        .astype(int)
    )
    fs_2024[f"{per_label}_imp"] = fs_2024[f"{per_label}_exp"].apply(
        exposed_to_impact
    )

fs_2024 = fs_2024.drop(columns=["total_exposed", "year"]).reset_index()
```

```python
fs_2024[fs_2024["low_exp"] > 0]
```

```python
fs_2024_plot = adm2.merge(fs_2024, on="ADM2_PCODE")
```

```python
fs_2024_plot
```

```python
fig, ax = plt.subplots(figsize=(8, 8))

fs_2024_plot[fs_2024_plot["mid_imp"] > 0].plot(
    column="mid_imp", cmap="Reds", legend=True, ax=ax
)
adm2.boundary.plot(ax=ax, linewidth=0.5, color="k")
ax.set_title(
    "Prévision moyenne de personnes\nimpactées par inondations en 2024,\n"
    "basée sur prévisions ECMWF de mars pour juin-juillet-août"
)

ax.axis("off")
```

```python
fs_2024_plot[fs_2024_plot["low_imp"] > 0].plot(
    column="low_imp", cmap="Purples", legend=True
)
```

```python
cols = [
    # "ADM1_PCODE",
    "ADM1_FR",
    # "ADM2_PCODE",
    "ADM2_FR",
    # "total_pop",
    "low_imp",
    "high_imp",
    # "geometry",
]
low_label = "Est. impact bas"
high_label = "Est. impact haut"
fs_2024_plot.sort_values("high_imp", ascending=False)[cols].iloc[:].rename(
    columns={
        "low_imp": low_label,
        "high_imp": high_label,
        "ADM1_FR": "Région",
        "ADM2_FR": "Département",
    }
).style.background_gradient(cmap="Reds").format(
    "{:,.0f}", subset=[low_label, high_label]
)
```

```python

```
