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

# ETH support

```python
%load_ext jupyter_black
%load_ext autoreload
%autoreload 2
```

```python
import os
from pathlib import Path

import geopandas as gpd
import xarray as xr
import rioxarray as rxr
```

```python
AA_DATA_DIR = Path(os.getenv("AA_DATA_DIR"))
IRI_GLB_RAW_DIR = AA_DATA_DIR / "private" / "processed" / "glb" / "iri"
CODAB_DIR = AA_DATA_DIR / "public" / "raw" / "eth" / "cod_ab"
```

```python
filename = "eth_adm.shp.zip"
codab = gpd.read_file(f"zip://{CODAB_DIR / filename}")
```

```python
codab.plot()
```

```python
filename = "glb_iri_forecast_seasonal_precipitation_tercile_prob_Np90Sm90Ep180Wm180.nc"
iri_all = xr.open_dataset(IRI_GLB_RAW_DIR / filename)
```

```python
forecast_date = "2020-11-16"
leadtime = 4
iri_nov = iri_all["prob"].sel(L=leadtime, F=forecast_date)
```

```python
iri_nov.isel(C=0).plot()
```

```python
iri_nov = iri_nov.squeeze(drop=True)
iri_nov = iri_nov.rio.write_crs(4326)
```

```python
iri_nov
```

```python
iri_nov_eth = iri_nov.rio.clip(codab.geometry, all_touched=True)
```

```python
iri_nov_eth.isel(C=0).plot()
```

```python
filename = f"glb_iri_forecast_seasonal_precipitation_tercile_prob_{forecast_date}_L{leadtime}.tif"
iri_nov.rio.to_raster(IRI_GLB_RAW_DIR / filename, driver="COG")

filename = f"eth_iri_forecast_seasonal_precipitation_tercile_prob_{forecast_date}_L{leadtime}.tif"
iri_nov_eth.rio.to_raster(IRI_GLB_RAW_DIR / filename, driver="COG")
```

```python
test = rxr.open_rasterio(IRI_GLB_RAW_DIR / filename)
```

```python
test
```

```python
test.isel(band=0).plot(vmin=40, vmax=70, figsize=(20, 10))
```

```python

```
