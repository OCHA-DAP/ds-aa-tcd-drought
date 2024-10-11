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

# Biomasse

```python
%load_ext jupyter_black
%load_ext autoreload
%autoreload 2
```

```python
import os
from pathlib import Path

import pandas as pd
import re

from src.datasources import biomasse as bm
from src.datasources import codab
from src.constants import *
```

```python
adm = codab.load_codab()
adm = adm[adm["ADM2_PCODE"].isin(ADM2_AOI_PCODES)]
```

```python
adm.plot()
```

```python
adm["area"] = adm.to_crs(3857).geometry.area / 1000 / 1000
total_area = adm["area"].sum()
```

```python
total_area
```

```python
bm.download_dmp()
```

```python
filename = "WA_DMP_ADM2_ef_v0.csv"
bm_all = pd.read_csv(bm._RAW_PATH / filename)
```

```python
bm_tcd = bm_all[bm_all["admin0Pcod"] == "TD"]

pattern = r"^DMP_\d{4}\d{2}$"

# Select columns that match the pattern plus 'admin2Pcod'
filtered_cols = ["admin2Pcod"] + [
    col for col in bm_tcd.columns if re.match(pattern, col)
]

# Filter the DataFrame to keep only the matched columns
bm_tcd_filtered = bm_tcd[filtered_cols]
```

```python
bm_tcd_mean = bm_tcd[
    ["admin2Pcod"] + [x for x in bm_tcd.columns if "DMP_MEA" in x]
]
```

```python
df_long_mean = bm_tcd_mean.melt(
    id_vars=["admin2Pcod"], var_name="mean_dekad", value_name="value"
)
```

```python
df_long_mean
```

```python
df_long_mean["dekad"] = df_long_mean["mean_dekad"].str[-2:].astype(int)
```

```python
df_final_mean = df_long_mean.drop("mean_dekad", axis=1)

df_final_mean = df_final_mean[["admin2Pcod", "dekad", "value"]]
df_final_mean = df_final_mean.rename(
    columns={"admin2Pcod": "ADM2_PCODE", "value": "mean"}
)
```

```python
df_final_mean
```

```python
fill_value = -9998.8
df_long = bm_tcd_filtered.melt(
    id_vars=["admin2Pcod"], var_name="year_dekad", value_name="value"
)
df_long = df_long[df_long["value"] != fill_value]

# Step 2: Parse the "year" and "dekad"
df_long["year"] = (
    df_long["year_dekad"].str.extract(r"DMP_(\d{4})\d{2}").astype(int)
)
df_long["dekad"] = (
    df_long["year_dekad"].str.extract(r"DMP_\d{4}(\d{2})").astype(int)
)

# Step 3: Drop the original 'year_dekad' column and reorganize the DataFrame
df_final = df_long.drop("year_dekad", axis=1)

# Rearrange columns if needed
df_final = df_final[["admin2Pcod", "year", "dekad", "value"]]
df_final = df_final.rename(columns={"admin2Pcod": "ADM2_PCODE"})
```

```python
df_final[df_final["ADM2_PCODE"] == "TD0101"]["value"].plot()
```

```python
PROC_BIO_DIR = (
    Path(os.getenv("AA_DATA_DIR"))
    / "public"
    / "processed"
    / "tcd"
    / "biomasse"
)
filename = "tcd_adm2_yeardekad_biomasse.csv"
df_final.to_csv(PROC_BIO_DIR / filename, index=False)
```

```python
df_final
```

```python
df_merged = df_final.merge(df_final_mean).merge(adm[["ADM2_PCODE", "area"]])
```

```python
df_merged["anom"] = df_merged["value"] / df_merged["mean"]
```

```python
df_merged["value_area"] = df_merged["value"] * 1
# df_merged["mean_area"] = df_merged["mean"] * df_merged["area"]
```

```python
df_aoi = df_merged[df_merged["ADM2_PCODE"].isin(ADM2_AOI_PCODES)]
```

```python
df_aoi
```

```python
df_dekad = df_aoi.groupby(["year", "dekad"])["value_area"].sum().reset_index()
```

```python
df_dekad
```

```python
df_dekad["mean_area"] = df_dekad.groupby("dekad")["value_area"].transform(
    "mean"
)
```

```python
df_dekad["anom"] = df_dekad["value_area"] / df_dekad["mean_area"]
```

```python
df_dekad
```

```python
df_dekad[(df_dekad["year"] == 2023) & (df_dekad["dekad"] == 24)]
```

```python
df_merged[df_merged["value"] > 0]["value"].hist()
```
