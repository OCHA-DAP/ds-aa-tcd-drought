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

# ERA5 hourly reanalysis processing

```python jupyter={"outputs_hidden": false}
%load_ext jupyter_black
%load_ext autoreload
%autoreload 2
```

```python
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.colors as colors
import ochanticipy
import pandas as pd
import xarray as xr
from tqdm.notebook import tqdm

from src.datasources import codab, era5
from src import utils, constants
```

```python jupyter={"outputs_hidden": false}
# codab.download_codab()
```

```python jupyter={"outputs_hidden": false}
adm2 = codab.load_codab()
```

```python jupyter={"outputs_hidden": false}
adm2_aoi = adm2[adm2["ADM1_PCODE"].isin(constants.NEW_ADM1_AOI_PCODES)]
adm2_aoi.plot()
```

```python
adm2_aoi["ADM2_PCODE"].nunique()
```

```python
# era5.download_era5_monthly()
```

```python
# era5.process_combine_era5_hourly()
```

```python
# era5.process_era5_hourly_to_daily()
```

```python
# era5.calculate_daily_rasterstats()
```

```python
era5.calculate_dry_spells()
```

```python
df = era5.load_dry_spells()
df_aoi_old = df[df["ADM2_PCODE"].isin(constants.ADM2_AOI_PCODES)]
df_aoi_new = df[df["ADM2_PCODE"].isin(constants.NEW_ADM2_AOI_PCODES)]
```

```python
df_aoi_new["ADM2_PCODE"].nunique()
```

```python
df_prio = (
    df_aoi_new.sort_values("year", ascending=False)
    .groupby("ADM2_PCODE")["count"]
    .agg(["first", "mean"])
    .reset_index()
    .rename(columns={"first": "2023_season", "mean": "historical_average"})
)
filename = "tcd_aoi_adm2_mean_dryspells.csv"
df_prio.to_csv(era5.ERA5_PROC_DIR / filename, index=False)
```

```python
all_years = df_aoi_new["year"].unique()
adm0_rp = df_aoi_new.groupby("year")["count"].sum().to_frame()
adm0_rp = adm0_rp.reindex(all_years, fill_value=0)
adm0_rp["rank"] = adm0_rp["count"].rank(method="min")
adm0_rp["rp"] = len(all_years) / (len(adm0_rp) - adm0_rp["rank"] + 1)
adm0_rp
```

```python
fig, ax = plt.subplots()
adm0_rp.sort_values("rp").plot(x="rp", y="count", ax=ax)
# add annotation for 2023
rp_2023, count_2023 = adm0_rp.loc[2023][["rp", "count"]]
ax.plot(rp_2023, count_2023, "r.")
annotation = (
    f"2023:\nRP = {rp_2023:.1f} years\n"
    f"Count = {int(count_2023)} dry spells"
)
ax.annotate(
    annotation,
    (rp_2023, count_2023),
    color="red",
    textcoords="offset points",
    xytext=(3, -3),
    va="top",
)
# add annotation for worst years
rp_worst_prev = 0
for worst_n in range(5):
    rp_worst, count_worst, year_worst = (
        adm0_rp.reset_index()
        .sort_values("rp", ascending=False)
        .iloc[worst_n][["rp", "count", "year"]]
    )
    if year_worst == 2023:
        continue
    if rp_worst == rp_worst_prev:
        va = "top"
    else:
        va = "bottom"
    ax.plot(rp_worst, count_worst, ".", color="grey")
    ax.annotate(
        int(year_worst),
        (rp_worst, count_worst),
        color="grey",
        va=va,
        ha="center",
    )
    rp_worst_prev = rp_worst
ax.set_xlabel("Return period (years)")
ax.set_ylabel("Total count of ADM2-level dry spells")
ax.set_title(
    "Return period of ADM2-level dry spells in Chad AOI since 1981"
    "\n(< 2 mm for at least 14 days during JAS)"
)
ax.legend().set_visible(False)
```

```python
dfs = []
for adm2_pcode, group in df_aoi_new.groupby("ADM2_PCODE"):
    dff = group.groupby("year")["count"].sum().to_frame()
    dff = dff.reindex(all_years, fill_value=0)
    dff["ADM2_PCODE"] = adm2_pcode
    dff["rank"] = dff["count"].rank(method="min")
    dff["rp"] = len(dff) / (len(dff) - dff["rank"] + 1)
    dfs.append(dff.reset_index())
    display(dff)

adm2_rp = pd.concat(dfs, ignore_index=True)
```

```python
adm2_rp["count"].value_counts()
```

```python
adm2_rp[adm2_rp["year"] == 2023]["count"].sum()
```

```python
year = 2023

dff = adm2_rp[adm2_rp["year"] == year]
adm2_plot = adm2.merge(dff, on="ADM2_PCODE")

fig, ax = plt.subplots(figsize=(15, 5))
bin_edges = [3, 5, 10, 20]
cmap = mpl.colormaps.get_cmap("YlOrRd")

adm2_plot.plot(
    column="rp",
    cmap=cmap,
    legend=True,
    ax=ax,
    norm=colors.BoundaryNorm(bin_edges, cmap.N, extend="both"),
    linewidth=0.2,
    edgecolor="black",
)
ax.axis("off")
ax.set_title(
    f"Période de retour de séquences sèches par département pour {year}"
)
adm2_plot.apply(
    lambda x: ax.annotate(
        text=x["ADM2_FR"],
        xy=x.geometry.centroid.coords[0],
        ha="center",
        va="center",
        fontsize=8,
    ),
    axis=1,
)
plt.show()
```

```python
year = 2023

dff = adm2_rp[adm2_rp["year"] == year]
adm2_plot = adm2.merge(dff, on="ADM2_PCODE")

fig, ax = plt.subplots(figsize=(15, 5))
cmap = mpl.colormaps.get_cmap("YlOrRd")

total_count = adm2_rp[adm2_rp["year"] == year]["count"].sum()

adm2_plot.plot(
    column="count",
    cmap=cmap,
    legend=True,
    ax=ax,
    # norm=colors.BoundaryNorm(bin_edges, cmap.N, extend="both"),
    linewidth=0.2,
    edgecolor="black",
    categorical=True,
)
ax.axis("off")
ax.set_title(
    f"Compte de séquences sèches par département pour {year}\n(total = {total_count})"
)
adm2_plot.apply(
    lambda x: ax.annotate(
        text=x["ADM2_FR"],
        xy=x.geometry.centroid.coords[0],
        ha="center",
        va="center",
        fontsize=8,
    ),
    axis=1,
)

plt.show()
```

```python

```
