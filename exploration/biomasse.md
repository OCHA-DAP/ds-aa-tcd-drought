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
bm_tcd_filtered.iloc[0]
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
