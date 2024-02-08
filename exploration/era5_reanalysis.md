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
codab.download_codab()
```

```python jupyter={"outputs_hidden": false}
adm2 = codab.load_codab()
```

```python jupyter={"outputs_hidden": false}
adm2.plot()
```

```python
adm2[adm2["ADM2_PCODE"] == "TD0703"]
```

```python
adm2_aoi = adm2[adm2["ADM1_PCODE"].isin(constants.ADM1_AOI_PCODES)]
adm2_aoi_pcodes = adm2_aoi["ADM2_PCODE"].unique()
```

```python
adm2_aoi_pcodes
```

```python
# era5.download_era5_monthly()
```

```python
era5.process_combine_era5_hourly()
```

```python
era5.process_era5_hourly_to_daily()
```

```python
era5.calculate_daily_rasterstats()
```

```python
df = era5.load_era5_daily_rasterstats()
```

```python
df_season = df[df["date"].dt.month.isin([7, 8, 9])]
```

```python
df_season_aoi = df_season[df_season["ADM2_PCODE"].isin(adm2_aoi_pcodes)]
df_season_aoi
```

```python
df_zero = df_season_aoi[df_season_aoi["mean"] == 0]
df_zero["ADM2_PCODE"].value_counts()
```

```python
df_season_aoi["mean"].hist(bins=100)
```

```python
df_season_aoi["mean"].quantile(0.7)
```

```python

```

```python
dry_mean_thresh = 2e-3
test_adm2 = "TD0703"

dfs = []
for adm2_code, adm2_group in tqdm(df_season_aoi.groupby("ADM2_PCODE")):
    for year, group in adm2_group.groupby(adm2_group["date"].dt.year):
        running_count = 0
        consecutive = []
        for _, row in group.iterrows():
            if row["mean"] <= dry_mean_thresh:
                running_count += 1
            else:
                running_count = 0
            consecutive.append(running_count)
        group["consecutive"] = consecutive
        consec_count = (
            group["consecutive"].value_counts().to_frame().reset_index()
        )
        consec_count["year"] = year
        consec_count["ADM2_PCODE"] = adm2_code
        consec_count["mean_lte_thresh"] = dry_mean_thresh
        dfs.append(consec_count)

dry_spells = pd.concat(dfs, ignore_index=True)
```

```python
dry_spells
```

```python
all_years = dry_spells["year"].unique()
all_years
```

```python
dry_len_thresh = 14
long_dry_spells = dry_spells[dry_spells["consecutive"] == dry_len_thresh]
```

```python
long_dry_spells.groupby("year")["count"].sum().plot()
```

```python
adm0_rp = long_dry_spells.groupby("year")["count"].sum().to_frame()
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
    f"2023:\nRP = {rp_2023} years\n" f"Count = {int(count_2023)} dry spells"
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
for worst_n in range(5):
    rp_worst, count_worst, year_worst = (
        adm0_rp.reset_index()
        .sort_values("rp", ascending=False)
        .iloc[worst_n][["rp", "count", "year"]]
    )
    if year_worst == 2023:
        continue
    ax.plot(rp_worst, count_worst, ".", color="grey")
    ax.annotate(
        int(year_worst),
        (rp_worst, count_worst),
        color="grey",
        va="bottom",
        ha="center",
    )
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
for adm2_pcode, group in long_dry_spells.groupby("ADM2_PCODE"):
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
ax.set_title(f"Return period of ADM2 dry spell count for {year}")
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
    norm=colors.BoundaryNorm(bin_edges, cmap.N, extend="both"),
    linewidth=0.2,
    edgecolor="black",
    categorical=True,
)
ax.axis("off")
ax.set_title(
    f"Count of dry spells by ADM2 for {year}\n(total = {total_count})"
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
