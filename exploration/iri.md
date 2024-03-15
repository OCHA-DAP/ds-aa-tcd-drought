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

# IRI

```python
%load_ext jupyter_black
%load_ext autoreload
%autoreload 2
```

```python
import xarray as xr
import matplotlib.pyplot as plt
import numpy as np

from src.datasources import iri, codab
from src import constants
```

```python
# note: this requires Python 3.9, for some reason
iri.download_iri()
```

```python
adm2 = codab.load_codab()
adm2_aoi = adm2[adm2["ADM1_PCODE"].isin(constants.ADM1_AOI_PCODES)]
adm2_aoi.plot()
```

```python
ds = iri.load_raw_iri()
```

```python
ds
```

```python
F_max = float(ds.F.max().values)
```

```python
month = int(F_max % 12) + 1
year = int(F_max // 12) + 1960
date_str = f"{year}-{month:02}-16"
date_str
```

```python
ds.isel(F=-1, L=-1, C=0)["prob"].plot()
```

```python
da = ds.isel(F=-1, L=-1, C=0)["prob"]
da = da.rio.write_crs(4326)
```

```python
L = int(da.L)
```

```python
L
```

```python
da_aoi = da.rio.clip(adm2_aoi.geometry, all_touched=True)
```

```python
def upsample_dataarray(
    da: xr.DataArray, resolution: float = 0.1
) -> xr.DataArray:
    new_lat = np.arange(da.Y.min(), da.Y.max(), resolution)
    new_lon = np.arange(da.X.min(), da.X.max(), resolution)
    return da.interp(Y=new_lat, X=new_lon, method="nearest")
```

```python
da_aoi_up = upsample_dataarray(da_aoi, resolution=0.01)
da_aoi_up_aoi = da_aoi_up.rio.clip(adm2_aoi.geometry, all_touched=False)
```

```python
fig, ax = plt.subplots(figsize=(12, 6))
da_aoi_up_aoi.plot(ax=ax)
adm2_aoi.boundary.plot(ax=ax, linewidth=0.5, color="white")
ax.axis("off")
ax.set_title(
    f"IRI seasonal forecast, probability of lower tercile,
    published {date_str}, leadtime months: {L}"
)
```

```python
da_aoi_up_aoi.quantile(0.8)
```
