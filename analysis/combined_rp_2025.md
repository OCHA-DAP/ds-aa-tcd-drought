---
jupyter:
  jupytext:
    formats: ipynb,md
    text_representation:
      extension: .md
      format_name: markdown
      format_version: '1.3'
      jupytext_version: 1.16.3
  kernelspec:
    display_name: Python 3 (ipykernel)
    language: python
    name: python3
---

# Combined RP - 2025
<!-- markdownlint-disable MD013 -->

Combining SEAS5 and Biomasse triggers to assess combined RP

```python
%load_ext jupyter_black
%load_ext autoreload
%autoreload 2
```

```python
import pandas as pd
import matplotlib.pyplot as plt
import statsmodels.api as sm
import seaborn as sns
import numpy as np
import ocha_stratus as stratus

from src.datasources import biomasse as bm
from src.datasources import seas5
from src.constants import *
from src.utils.rp_calc import calculate_one_group_rp
```

## Load and merge data

```python
blob_name = f"{PROJECT_PREFIX}/processed/biomasse_d24_2025.parquet"
df_bm = stratus.load_parquet_from_blob(blob_name)
```

```python
df_bm
```

```python
variable = "rank"
df_seas5 = seas5.load_seas5_stats(variable=variable)
```

```python
df_seas5
```

```python
df_seas5_yearly = df_seas5.pivot(
    index="year", columns="issued_month", values="q"
).reset_index()
```

```python
df_combined = df_seas5_yearly.merge(
    df_bm[["year", "biomasse_linearfit_anomaly"]]
)
```

## Compare combinations

### Iterate over combinations

In the cell below we iterate over all the possible trigger combinations.

```python
dicts = []
# set to True for different thresholds per issued month
# set to False for fixed threshold (this is what is in the framework)
rp_based = False

if rp_based:
    fcast_values = range(1, len(df_combined) + 1)
else:
    fcast_values = np.arange(0, 1, 0.01)

# being lazy and just setting rank_fcast to either the rank cutoff or absolute
# cutoff, depending on whether we are doing rp_based
for rank_fcast in fcast_values:
    if rp_based:
        # filter by rank
        rp_fcast_ind = (len(df_combined) + 1) / (rank_fcast)
        dff_1 = df_combined[
            (df_combined[3].rank(ascending=False) <= rank_fcast)
            | (df_combined[4].rank(ascending=False) <= rank_fcast)
        ]
        dff_2 = df_combined[
            (df_combined[5].rank() <= rank_fcast)
            | (df_combined[6].rank() <= rank_fcast)
        ]
        dff_fcast = df_combined[
            (df_combined[3].rank() <= rank_fcast)
            | (df_combined[4].rank() <= rank_fcast)
            | (df_combined[5].rank() <= rank_fcast)
            | (df_combined[6].rank() <= rank_fcast)
        ]
    else:
        # filter by absolute value
        rp_fcast_ind = rank_fcast
        dff_1 = df_combined[
            (df_combined[3] <= rank_fcast) | (df_combined[4] <= rank_fcast)
        ]
        dff_2 = df_combined[
            (df_combined[5] <= rank_fcast) | (df_combined[6] <= rank_fcast)
        ]
        dff_fcast = df_combined[
            (df_combined[3] <= rank_fcast)
            | (df_combined[4] <= rank_fcast)
            | (df_combined[5] <= rank_fcast)
            | (df_combined[6] <= rank_fcast)
        ]
    try:
        rp_1 = (len(df_combined) + 1) / len(dff_1)
    except ZeroDivisionError:
        rp_1 = np.inf
    try:
        rp_2 = (len(df_combined) + 1) / len(dff_2)
    except ZeroDivisionError:
        rp_2 = np.inf

    try:
        rp_fcast = (len(df_combined) + 1) / len(dff_fcast)
    except ZeroDivisionError:
        rp_fcast = np.inf
    for rank_obsv in range(1, len(df_combined) + 1):
        rp_obsv = (len(df_combined) + 1) / (rank_obsv)
        if rp_based:
            dff_any = df_combined[
                (df_combined[3].rank() <= rank_fcast)
                | (df_combined[4].rank() <= rank_fcast)
                | (df_combined[5].rank() <= rank_fcast)
                | (df_combined[6].rank() <= rank_fcast)
                | (
                    df_combined["biomasse_linearfit_anomaly"].rank()
                    <= rank_obsv
                )
            ]
        else:
            dff_any = df_combined[
                (df_combined[3] <= rank_fcast)
                | (df_combined[4] <= rank_fcast)
                | (df_combined[5] <= rank_fcast)
                | (df_combined[6] <= rank_fcast)
                | (
                    df_combined["biomasse_linearfit_anomaly"].rank()
                    <= rank_obsv
                )
            ]
        rp_any = (len(df_combined) + 1) / len(dff_any)
        dicts.append(
            {
                "rp_fcast_ind": rp_fcast_ind,
                "rp_fcast": rp_fcast,
                "rp_obsv": rp_obsv,
                "rp_1": rp_1,
                "rp_2": rp_2,
                "rp_any": rp_any,
                "fcast_val": rank_fcast,
            }
        )
```

```python
df_rps = pd.DataFrame(dicts)
```

```python
df_rps
```

```python
# filter to acceptable RPs
# this can be done various ways but ultimately the 4.5 was
# selected by CERF
df_rps_acceptable = df_rps[
    (df_rps["rp_any"] == 4.5)
    & (df_rps["rp_1"] != np.inf)
    & (df_rps["rp_2"] != np.inf)
]
```

```python
# plot the options
df_rps_acceptable.plot(x="rp_fcast_ind", y="rp_obsv", marker=".", linewidth=0)
```

```python
df_rps_acceptable
```

### Pick options for further plotting

```python
# picking options from table above by index
# these are selected based on having the lowest rps for
# various triggers- this could be done programatically
# but just being lazy here (and more flexible)

# for 3.9 yr overall:
# choices_index = [5, 27]
# for 4.5 yr overall:
# choices_index = [3, 26]
# for 4.3 overall from 2000 onwards:
# choices_index = [3, 25]
# for 4.5 with rank SEAS5:
# choices_index = [3, 27]
# for 4.5 with rank SEAS5 fixed thresh:
choices_index = [394, 471]

display(df_rps_acceptable.loc[choices_index])
```

### Plot comparison between selected options

```python
df_plot = (100 / df_rps_acceptable.loc[choices_index]).copy()

df_plot = df_plot[["rp_1", "rp_2", "rp_obsv", "rp_any"]].rename(
    columns={
        "rp_1": "1",
        "rp_2": "2",
        "rp_obsv": "3",
        "rp_any": "N'importe\nquelle",
    }
)
df_plot["name"] = [
    "Option 1 (favorise observationnel)",
    "Option 2 (favorise prévisions)",
]

df_melted = df_plot.melt(id_vars="name")

fig, ax = plt.subplots(dpi=200)

colors = ["dodgerblue", "darkblue", "mediumseagreen", "black"]
sns.barplot(
    data=df_melted, x="name", y="value", hue="variable", ax=ax, palette=colors
)

seas5_thresh_wording = "variable" if rp_based else "fixe"

ax.legend(title="Fenêtre", bbox_to_anchor=(1, 1), loc="upper left")
ax.set_xlabel("")
ax.set_ylabel("Probabilité de déclencher (%)")
ax.set_title(
    "Options de combinaisons de déclencheurs\n"
    f"Seuil SEAS5 {seas5_thresh_wording} à travers mois de publication"
)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
```

### Display yearly activations

Various options compared.

```python
def highlight_true(value):
    if isinstance(value, bool) and value is True or value == "Activation":
        return "background-color: crimson; color: white"
    elif (
        isinstance(value, bool)
        and value is False
        or value == "Pas d'activation"
    ):
        return "color: lightgrey"
    else:
        return ""
```

```python
def display_yearly_activations(rp_fcast, rp_obsv):
    df_disp = (
        df_combined.copy()
        .sort_values("year", ascending=False)
        .rename(columns={"year": "Année"})
        .set_index("Année")
    )
    df_disp["Fenêtre 1"] = (
        (len(df_disp) + 1) / df_disp[3].rank() >= rp_fcast
    ) | ((len(df_disp) + 1) / df_disp[4].rank() >= rp_fcast)
    df_disp["Fenêtre 2"] = (
        (len(df_disp) + 1) / df_disp[5].rank() >= rp_fcast
    ) | ((len(df_disp) + 1) / df_disp[6].rank() >= rp_fcast)
    df_disp["Fenêtre 3"] = (len(df_disp) + 1) / df_disp[
        "biomasse_linearfit_anomaly"
    ].rank() >= rp_obsv
    cols = [x for x in df_disp.columns if "Fenêtre" in str(x)]
    display(df_disp[cols].style.map(highlight_true))
```

```python
# for 4.5 yr overall:
# display_yearly_activations(13.5, 27)
# for 4.3 overall from 2000 onwards:
# display_yearly_activations(26, 6.5)
# for 4.5 with rank SEAS5:
display_yearly_activations(27, 6.75)
```

```python
# for 4.5 yr overall:
# display_yearly_activations(27, 6.75)
# for 4.5 with rank SEAS5:
display_yearly_activations(13.5, 13.5)
```

```python
def display_yearly_activations_fixed_seas5(seas5_thresh, rp_obsv):
    df_disp = (
        df_combined.copy()
        .sort_values("year", ascending=False)
        .rename(columns={"year": "Année"})
        .set_index("Année")
    )
    df_disp["Fenêtre 1"] = (df_disp[3] <= seas5_thresh) | (
        df_disp[4] <= seas5_thresh
    )
    df_disp["Fenêtre 2"] = (df_disp[5] <= seas5_thresh) | (
        df_disp[6] <= seas5_thresh
    )
    df_disp["Fenêtre 3"] = (len(df_disp) + 1) / df_disp[
        "biomasse_linearfit_anomaly"
    ].rank() >= rp_obsv
    cols = [x for x in df_disp.columns if "Fenêtre" in str(x)]
    display(
        df_disp[cols]
        .replace({True: "Activation", False: "Pas d'activation"})
        .style.map(highlight_true)
    )
```

```python
# here is the option we ultimately settled on
display_yearly_activations_fixed_seas5(0.15, 5.4)
```

```python
display_yearly_activations_fixed_seas5(0.18, 6.75)
```

```python

```
