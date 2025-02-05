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

# Switch ECMWF

```python
%load_ext jupyter_black
%load_ext autoreload
%autoreload 2
```

```python
from dask.diagnostics import ProgressBar

from src.datasources import seas5, codab
from src.utils.raster import upsample_dataarray
from src.constants import *
from src.utils import blob_utils
```

```python
test = seas5.open_seas5_rasters()
```

```python
test
```

```python
da_seas5 = test
```

```python
adm1.plot()
```

```python
adm1 = codab.load_codab_from_blob(admin_level=1, aoi_only=True)
# da_seas5 = open_seas5_rasters()
da_seas5_tri = da_seas5.mean(dim="lt")
```

```python
da_seas5_up = upsample_dataarray(da_seas5_tri)
```

```python
da_seas5_clip = da_seas5_up.rio.clip(adm1.geometry)
```

```python
da_seas5_q = da_seas5_clip.quantile(q=ORIGINAL_Q, dim=["x", "y"])
```

```python
with ProgressBar():
    da_seas5_q_computed = da_seas5_q.compute()
```

```python
df_seas5 = da_seas5_q_computed.to_dataframe("q")["q"].reset_index()
```

```python
blob_utils.upload_parquet_to_blob(df_seas5, blob_name)
```

```python
df_seas5 = seas5.load
```
