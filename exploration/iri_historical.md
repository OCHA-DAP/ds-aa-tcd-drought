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

# IRI historical

```python
%load_ext jupyter_black
%load_ext autoreload
%autoreload 2
```

```python
import os
from pathlib import Path

import xarray as xr
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from src.datasources import iri, codab
from src import constants
```

```python
DATA_DIR = Path(os.getenv("AA_DATA_DIR"))
SAH_IRI_PATH = (
    DATA_DIR
    / "private"
    / "processed"
    / "sah"
    / "iri"
    / "sah_iri_forecast_seasonal_precipitation_tercile_prob_Np24Sp7Ep24Wm6.nc"
)
```

```python
def upsample_dataarray(
    da: xr.DataArray, resolution: float = 0.1
) -> xr.DataArray:
    new_lat = np.arange(da.latitude.min(), da.latitude.max(), resolution)
    new_lon = np.arange(da.longitude.min(), da.longitude.max(), resolution)
    return da.interp(latitude=new_lat, longitude=new_lon, method="nearest")
```

```python
adm = codab.load_codab()
adm = adm[adm["ADM1_PCODE"].isin(constants.ADM1_AOI_PCODES)]
```

```python
adm.plot()
```

```python
iri = xr.load_dataset(SAH_IRI_PATH)
iri = iri.rename({"X": "longitude", "Y": "latitude"})
iri = iri.rio.write_crs(4326)
iri_up = upsample_dataarray(iri, resolution=0.05)
iri_up_clip = iri_up.rio.clip(adm.geometry)
```

```python
fig, ax = plt.subplots()
iri_up_clip.isel(F=0, L=0, C=0)["prob"].plot(ax=ax)
adm.boundary.plot(ax=ax)
```

```python
df = iri_up_clip.to_dataframe()["prob"].dropna().reset_index()
df["F"] = pd.to_datetime(df["F"].apply(lambda x: x.strftime("%Y-%m-%d")))
```

```python
df["year"] = df["F"].dt.year
df["f_month"] = df["F"].dt.month
df["C"] = df["C"].replace({0: "lower", 1: "average", 2: "higher"})
df = df.pivot(
    columns="C",
    values="prob",
    index=["L", "year", "f_month", "latitude", "longitude"],
).reset_index()
df
```

```python
area_frac = 0.2
act_thresh = 42.5

dicts = []

for year in df["year"].unique():
    df_year = df[df["year"] == year]
    # March forecast for JAS
    dff = df_year[(df_year["f_month"] == 3) & (df_year["L"] == 4)]
    march_lower = dff.quantile(1 - area_frac)["lower"]
    # April forecast for JAS
    dff = df_year[(df_year["f_month"] == 4) & (df_year["L"] == 3)]
    april_lower = dff.quantile(1 - area_frac)["lower"]
    # May forecast for JAS
    dff = df_year[(df_year["f_month"] == 5) & (df_year["L"] == 2)]
    may_lower = dff.quantile(1 - area_frac)["lower"]
    # June forecast for JAS
    dff = df_year[(df_year["f_month"] == 6) & (df_year["L"] == 1)]
    june_lower = dff.quantile(1 - area_frac)["lower"]

    dicts.append(
        {
            "year": year,
            "march": march_lower,
            "april": april_lower,
            "may": may_lower,
            "june": june_lower,
        }
    )

results = pd.DataFrame(dicts)
for x in ["march", "april", "may", "june"]:
    results[f"{x}_act"] = results[x] >= act_thresh

results["window1"] = results["march_act"] | results["april_act"]
results["window2"] = results["may_act"] | results["june_act"]
```

```python
results
```
