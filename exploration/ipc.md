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

# IPC from IPC API

```python
%load_ext jupyter_black
%load_ext autoreload
%autoreload 2
```

```python
import unicodedata
import re
import datetime

import matplotlib.pyplot as plt

from src.datasources import ipc, codab
from src import constants
```

```python
adm2 = codab.load_codab()
adm2_aoi = adm2[adm2["ADM1_PCODE"].isin(constants.ADM1_AOI_PCODES)]
```

```python
# ipc.download_subnational_ipc_analyses()
```

```python
df = ipc.load_subnational_ipc_analyses()
```

```python
for x in ["top", "group", "area"]:
    print([col for col in df.columns if col.startswith(x)])
```

```python
df["top_current_period_dates"].unique()
```

```python
def ipc_current_daterange_to_date(date_range: str):
    # Step 1: Extract the start month and year
    start_month_year = date_range.split("-")[0].strip()

    # Step 2: Construct new date string with day set to '1'
    new_date_str = f"{start_month_year} 1"

    # Optionally, convert to datetime object for further manipulation
    new_date = datetime.datetime.strptime(new_date_str, "%b %Y %d")
    return new_date
```

```python
df["top_current_startdate"] = df["top_current_period_dates"].apply(
    ipc_current_daterange_to_date
)
```

```python
df["top_current_startdate"].unique()
```

```python
len(df["area_id"].unique())
```

```python
df[df["group_name"] == "Wadi Fira"].groupby("area_name").first()
```

```python
df["area_name"].unique()
```

```python
def normalize_text(s):
    s = (
        unicodedata.normalize("NFD", s)
        .encode("ascii", "ignore")
        .decode("utf-8")
    )  # Remove accents
    s = s.lower()  # Convert to lowercase
    s = re.sub(r"[\s\-]", "", s)  # Remove spaces and dashes
    return s
```

```python
for x in adm2_aoi["ADM2_FR"].apply(normalize_text).sort_values().unique():
    if x not in df["area_name"].apply(normalize_text).sort_values().unique():
        print(x)
```

```python
adm2_aoi["norm_name"] = (
    adm2_aoi["ADM2_FR"]
    .apply(normalize_text)
    .replace({"fitri": "fittri", "kobe": "iriba"})
)
df["norm_name"] = df["area_name"].apply(normalize_text)
```

```python
adm2_aoi_ipc = adm2_aoi.merge(
    df.groupby("norm_name").first()["area_name"].reset_index(), on="norm_name"
)
```

```python
adm2_aoi_ipc
```

```python
col = "area_p3plus_percentage"

df_aoi = df[df["area_name"].isin(adm2_aoi_ipc["area_name"])]

max_val = df_aoi[col].max()
min_val = df_aoi[col].min()

for startdate, group in df_aoi.groupby("top_current_startdate"):
    print(startdate)
    period_name = group.iloc[0]["top_current_period_dates"]
    adm2_plot = adm2_aoi_ipc.merge(group[[col, "area_name"]], on="area_name")
    fig, ax = plt.subplots(figsize=(20, 5))
    adm2_plot.plot(
        ax=ax,
        column=col,
        vmin=min_val,
        vmax=max_val,
        legend=True,
    )
    ax.set_title(f"IPC for current period {period_name}")
    ax.axis("off")
    adm2_plot.apply(
        lambda x: ax.annotate(
            text=x["ADM2_FR"],
            xy=x.geometry.centroid.coords[0],
            ha="center",
            va="center",
            fontsize=8,
            color="white",
        ),
        axis=1,
    )
    cbar_ax = fig.axes[1]
    cbar_ax.set_title("Frac. of population\nphase 3+")
```

```python
col = "area_p3plus_percentage"

df_aoi = df[df["area_name"].isin(adm2_aoi_ipc["area_name"])]

max_val = df_aoi[col].max()
min_val = df_aoi[col].min()

fig, ax = plt.subplots(
    len(df_aoi.groupby("top_current_startdate")), 1, figsize=(25, 5 * 7)
)
axes_flat = ax.flatten()

ax_i = 0
for startdate, group in df_aoi.groupby("top_current_startdate"):
    print(startdate)
    period_name = group.iloc[0]["top_current_period_dates"]
    adm2_plot = adm2_aoi_ipc.merge(group[[col, "area_name"]], on="area_name")
    adm2_plot.plot(
        ax=axes_flat[ax_i],
        column=col,
        vmin=min_val,
        vmax=max_val,
    )
    axes_flat[ax_i].axis("off")
    ax_i += 1

plt.tight_layout(pad=0, w_pad=0, h_pad=0)  # Adjust pad, w_pad, h_pad as needed

# Additional customization to reduce spacing between subplots
plt.subplots_adjust(wspace=0, hspace=-0.15)  # Adjust spacing between subplots
```

```python
col = "area_p3plus"

df_aoi = df[df["area_name"].isin(adm2_aoi_ipc["area_name"])]

max_val = df_aoi[col].max()
min_val = df_aoi[col].min()

for startdate, group in df_aoi.groupby("top_current_startdate"):
    print(startdate)
    period_name = group.iloc[0]["top_current_period_dates"]
    adm2_plot = adm2_aoi_ipc.merge(group[[col, "area_name"]], on="area_name")
    fig, ax = plt.subplots(figsize=(20, 5))
    adm2_plot.plot(
        ax=ax,
        column=col,
        vmin=min_val,
        vmax=max_val,
        legend=True,
    )
    ax.set_title(f"IPC for current period {period_name}")
    ax.axis("off")
    adm2_plot.apply(
        lambda x: ax.annotate(
            text=x["ADM2_FR"],
            xy=x.geometry.centroid.coords[0],
            ha="center",
            va="center",
            fontsize=8,
            color="white",
        ),
        axis=1,
    )
    cbar_ax = fig.axes[1]
    cbar_ax.set_title("Total population\nphase 3+", fontsize=10)
```

```python
col = "area_p3plus"

df_aoi = df[df["area_name"].isin(adm2_aoi_ipc["area_name"])]

max_val = df_aoi[col].max()
min_val = df_aoi[col].min()

fig, ax = plt.subplots(
    len(df_aoi.groupby("top_current_startdate")), 1, figsize=(25, 5 * 7)
)
axes_flat = ax.flatten()

ax_i = 0
for startdate, group in df_aoi.groupby("top_current_startdate"):
    print(startdate)
    period_name = group.iloc[0]["top_current_period_dates"]
    adm2_plot = adm2_aoi_ipc.merge(group[[col, "area_name"]], on="area_name")
    adm2_plot.plot(
        ax=axes_flat[ax_i],
        column=col,
        vmin=min_val,
        vmax=max_val,
    )
    axes_flat[ax_i].axis("off")
    ax_i += 1

plt.tight_layout(pad=0, w_pad=0, h_pad=0)  # Adjust pad, w_pad, h_pad as needed

# Additional customization to reduce spacing between subplots
plt.subplots_adjust(wspace=0, hspace=-0.15)  # Adjust spacing between subplots
```

```python
fig, ax = plt.subplots(figsize=(20, 5))
adm2_plot.plot(ax=ax, facecolor="white", linewidth=0.5, edgecolor="black")
ax.axis("off")
adm2_plot.apply(
    lambda x: ax.annotate(
        text=x["ADM2_FR"],
        xy=x.geometry.centroid.coords[0],
        ha="center",
        va="center",
        fontsize=8,
        color="black",
    ),
    axis=1,
)
plt.show()
```
