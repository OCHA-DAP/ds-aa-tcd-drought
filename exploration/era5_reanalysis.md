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
import pandas as pd
import xarray as xr

from src.datasources import codab, era5
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
era5.download_era5_monthly()
```

```python
era5_land = xr.load_dataset(era5.ERA5_RAW_DIR / "era5-land-test.grib")
era5_land2 = xr.load_dataset(era5.ERA5_RAW_DIR / "era5-land-test2.grib")
era5_land3 = xr.load_dataset(era5.ERA5_RAW_DIR / "era5-land-test3.grib")
```

```python
era5_land3.isel(time=0)
```

```python
era5_land
```

```python
era5_land2
```

```python
era5_land.isel(step=-1)
```

```python
daily_2023 = era5.load_era5_hourly(2023)
daily_2022 = era5.load_era5_hourly(2022)
```

```python
daily_2023
```

```python
daily_2022.sel(time="2022-12-31T18")
```

```python
hourly_combined = xr.open_dataset(
    era5.ERA5_PROC_DIR / "ecmwf-reanalysis-hourly-precipitation-combined.nc"
)["tp"]
```

```python
hourly_combined.isel(time=0, step=1).valid_time.values
```

```python
hourly_combined["valid_time_m1"] = hourly_combined["valid_time"] - 1
```

```python
hourly_combined.isel(time=0, step=1).valid_time_m1.values
```

```python
daily = (
    hourly_combined.groupby("valid_time_m1.date").sum().isel(date=slice(1, -1))
)
```

```python
daily["date"] = pd.to_datetime(daily["date"])
daily
```

```python
daily = hourly_combined.groupby("time.date").sum().sum(dim="step")
daily["date"] = pd.to_datetime(daily["date"])
daily
```
