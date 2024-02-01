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

# Monthly precipitation

```python
%load_ext jupyter_black
%load_ext autoreload
%autoreload 2
```

```python
import matplotlib.pyplot as plt
import pandas as pd

from src.datasources import era5, codab
from src import constants, utils
```

```python
da = era5.load_era5_monthly()
da = da.groupby("valid_time.date").first()
da["date"] = pd.to_datetime(da["date"])
da = da.rio.write_crs(4326)
```

```python
adm2 = codab.load_codab()
adm2_aoi = adm2[adm2["ADM1_PCODE"].isin(constants.ADM1_AOI_PCODES)]
```

```python
adm2_aoi.plot()
```

```python
da_up = utils.upsample_dataarray(da)
da_aoi = da_up.rio.clip(adm2_aoi.geometry, all_touched=True)
```

```python
fig, ax = plt.subplots(figsize=(20, 5))
da_aoi.isel(date=5).plot(ax=ax)
adm2_aoi.boundary.plot(ax=ax)
```

```python
for month in [7, 8, 9]:
    fig, ax = plt.subplots(figsize=(20, 5))
    da_aoi.sel(date=f"2022-{month:02d}-01").plot(ax=ax)
    adm2_aoi.boundary.plot(ax=ax)
```

```python
df = da_aoi.mean(dim=["latitude", "longitude"]).to_dataframe().reset_index()
df = df.drop(columns=["number", "step", "surface", "spatial_ref"])
```

```python
df_season = df[df["date"].dt.month.isin([7, 8, 9])]
```

```python
df_season_year = (
    df_season.groupby(df_season["date"].dt.year)["tp"]
    .mean()
    .reset_index()
    .rename(columns={"date": "year"})
)
```

```python
df_season_year
df_season_year["rank"] = df_season_year["tp"].rank()
df_season_year["rp"] = len(df_season_year) / df_season_year["rank"]
df_season_year["tp_mm"] = df_season_year["tp"] * 1000
df_season_year = df_season_year.set_index("year")
```

```python
fig, ax = plt.subplots()
df_season_year.sort_values("rp").plot(x="rp", y="tp_mm", ax=ax)
# add annotation for 2023
rp_2023, val_2023 = df_season_year.loc[2023][["rp", "tp_mm"]]
ax.plot(rp_2023, val_2023, "r.")
annotation = f"2023:\nRP = {rp_2023} years\n" f"Value = {val_2023:.1f} mm"
ax.annotate(
    annotation,
    (rp_2023, val_2023),
    color="red",
    textcoords="offset points",
    xytext=(3, 3),
    va="bottom",
)
# add annotation for worst years
for worst_n in range(5):
    rp_worst, val_worst, year_worst = (
        df_season_year.reset_index()
        .sort_values("rp", ascending=False)
        .iloc[worst_n][["rp", "tp_mm", "year"]]
    )
    if year_worst == 2023:
        continue
    ax.plot(rp_worst, val_worst, ".", color="grey")
    ax.annotate(
        int(year_worst),
        (rp_worst, val_worst),
        color="grey",
        va="top",
        ha="right",
    )
ax.set_xlabel("Return period (years)")
ax.set_ylabel("Average daily precipitation (mm)")
ax.set_title(
    "Return period of Chad AOI precipitation since 1981,"
    "\nduring Jul-Aug-Sep"
)
ax.legend().set_visible(False)
```

```python

```
