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

# IPC from HDX

Using [IPC data from HDX](https://data.humdata.org/dataset/cadre-harmonise)

```python
%load_ext jupyter_black
%load_ext autoreload
%autoreload 2
```

```python
import plotly.express as px
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

from src.datasources import ipc, codab
from src import constants
```

```python
ipc.process_tcd_hdx_ipc()
```

```python
df = ipc.load_tcd_hdx_ipc()
df = df[
    (df["adm2_pcod2"].notnull())
    & (df["adm3_pcod2"].isnull())
    & (df["adm1_pcod2"].isin(constants.ADM1_AOI_PCODES))
]
cols = [
    "adm0_name",
    "adm0_pcod2",
    "adm0_pcod3",
    "adm1_name",
    "adm1_pcod2",
    "adm2_name",
    "adm2_pcod2",
    "exercise_code",
    "exercise_label",
    "exercise_year",
    "chtype",
    "reference_code",
    "reference_label",
    "reference_year",
    "population",
    "phase_class",
    "phase1",
    "phase2",
    "phase3",
    "phase4",
    "phase5",
    "phase35",
]
df = df[cols]
df = df.sort_values("reference_year")
for x in [1, 2, 3, 4, 5, "35"]:
    df[f"frac_phase{x}"] = df[f"phase{x}"] / df["population"]
```

```python
df.columns
```

```python
df
```

```python
# find analysis to match fw sorting
cols = [
    "adm1_name",
    "adm2_name",
    "frac_phase35",
    "phase35",
    "exercise_label",
    "reference_label",
    "reference_year",
]
df[df["phase35"] > 80000][cols]
```

```python
# reproducing FW current analysis
current_exercise_label = "Jan-May"
current_reference_year = 2022
current_reference_label = "Jun-Aug"
df_agg = df[
    (df["exercise_label"] == current_exercise_label)
    & (df["reference_label"] == current_reference_label)
    & (df["reference_year"] == current_reference_year)
].set_index(["adm1_name", "adm2_name"])
df_agg["weighted_3_4"] = df_agg["frac_phase3"] + df_agg["frac_phase4"] * 10
df_agg["norm_weighted_3_4"] = (
    df_agg["weighted_3_4"] / df_agg["weighted_3_4"].max()
)
df_agg = df_agg.sort_values("norm_weighted_3_4", ascending=False)
cols = ["norm_weighted_3_4", "frac_phase35", "phase35"]
fw_current = (
    df_agg.copy()[cols]
    .reset_index()
    .rename(columns={x: f"fw_current_{x}" for x in cols})
)
fw_current
```

```python
# updated current
current_exercise_label = "Sep-Dec"
current_reference_year = 2024
current_reference_label = "Jun-Aug"
df_agg = df[
    (df["exercise_label"] == current_exercise_label)
    & (df["reference_label"] == current_reference_label)
    & (df["reference_year"] == current_reference_year)
].set_index(["adm1_name", "adm2_name"])
df_agg["weighted_3_4"] = df_agg["frac_phase3"] + df_agg["frac_phase4"] * 10
df_agg["norm_weighted_3_4"] = (
    df_agg["weighted_3_4"] / df_agg["weighted_3_4"].max()
)
df_agg = df_agg.sort_values("norm_weighted_3_4", ascending=False)
cols = ["norm_weighted_3_4", "frac_phase35", "phase35"]
updated_current = (
    df_agg.copy()[cols]
    .reset_index()
    .rename(columns={x: f"update_current_{x}" for x in cols})
)
updated_current
```

```python
# reproducting FW historical analysis (more or less)
min_year = 2018
max_year = 2022
exercise_label = "Sep-Dec"
reference_label = "Jun-Aug"

dff = df[
    (df["reference_year"] >= min_year)
    & (df["reference_year"] <= max_year)
    & (df["exercise_label"] == exercise_label)
    & (df["reference_label"] == reference_label)
].copy()
df_agg = dff.groupby(["adm1_name", "adm2_name"]).mean(numeric_only=True)
df_agg["weighted_3_4"] = df_agg["frac_phase3"] + df_agg["frac_phase4"] * 10
df_agg["norm_weighted_3_4"] = (
    df_agg["weighted_3_4"] / df_agg["weighted_3_4"].max()
)
df_agg = df_agg.sort_values("norm_weighted_3_4", ascending=False)
cols = ["norm_weighted_3_4", "frac_phase35", "phase35"]
fw_historical = (
    df_agg.copy()[cols]
    .reset_index()
    .rename(columns={x: f"fw_hist_{x}" for x in cols})
)
fw_historical
```

```python
# reproducting FW historical analysis (including all years)
min_year = 0
max_year = 2022
exercise_label = "Sep-Dec"
reference_label = "Jun-Aug"

dff = df[
    (df["reference_year"] >= min_year)
    & (df["reference_year"] <= max_year)
    & (df["exercise_label"] == exercise_label)
    & (df["reference_label"] == reference_label)
].copy()
df_agg = dff.groupby(["adm1_name", "adm2_name"]).mean(numeric_only=True)
df_agg["weighted_3_4"] = df_agg["frac_phase3"] + df_agg["frac_phase4"] * 10
df_agg["norm_weighted_3_4"] = (
    df_agg["weighted_3_4"] / df_agg["weighted_3_4"].max()
)
df_agg = df_agg.sort_values("norm_weighted_3_4", ascending=False)
cols = ["norm_weighted_3_4", "frac_phase35", "phase35"]
fw_historical_allyears = (
    df_agg.copy()[cols]
    .reset_index()
    .rename(columns={x: f"fw_hist_allyears_{x}" for x in cols})
)
fw_historical_allyears
```

```python
# updating historical analysis
min_year = 2018
max_year = 3000
exercise_label = "Sep-Dec"
reference_label = "Jun-Aug"

dff = df[
    (df["reference_year"] >= min_year)
    & (df["reference_year"] <= max_year)
    & (df["exercise_label"] == exercise_label)
    & (df["reference_label"] == reference_label)
].copy()
df_agg = dff.groupby(["adm1_name", "adm2_name"]).mean(numeric_only=True)
df_agg["weighted_3_4"] = df_agg["frac_phase3"] + df_agg["frac_phase4"] * 10
df_agg["norm_weighted_3_4"] = (
    df_agg["weighted_3_4"] / df_agg["weighted_3_4"].max()
)
df_agg = df_agg.sort_values("norm_weighted_3_4", ascending=False)
cols = ["norm_weighted_3_4", "frac_phase35", "phase35"]
updated_historical = (
    df_agg.copy()[cols]
    .reset_index()
    .rename(columns={x: f"update_hist_{x}" for x in cols})
)
updated_historical
```

```python
updated_historical
```

```python
# combining all

adm_name_cols = ["adm1_name", "adm2_name"]
combined_results = updated_historical.merge(fw_historical, on=adm_name_cols)
combined_results = combined_results.merge(updated_current, on=adm_name_cols)
combined_results = combined_results.merge(fw_current, on=adm_name_cols)
combined_results = combined_results.sort_values(
    "fw_hist_norm_weighted_3_4", ascending=False
)
combined_results = combined_results.set_index(adm_name_cols)
metrics = [
    "hist_norm_weighted_3_4",
    "hist_frac_phase35",
    "current_frac_phase35",
    "current_phase35",
]
updates = ["fw", "update"]
cols = []
for metric in metrics:
    combined_results[f"diff_{metric}"] = (
        combined_results[f"update_{metric}"] - combined_results[f"fw_{metric}"]
    )
    cols.extend([f"fw_{metric}", f"diff_{metric}", f"update_{metric}"])
combined_results[cols]
filename = "tcd_ipc_fw_update.csv"
combined_results[cols].reset_index().to_csv(
    ipc.IPC_PROC_DIR / filename, index=False
)
```

```python
combined_results[[col for col in combined_results.columns if "update_" in col]]
```

```python
min_year = 0
max_year = 3000
exercise_labels = ["Jan-May", "Sep-Dec", "Sep-Dec"]
reference_labels = ["Jun-Aug", "Sep-Dec", "Jun-Aug"]

val_col = "frac_phase35"
adm1s = ["Lac", "Kanem", "Barh-El-Gazel", "Batha", "Wadi Fira"]

for reference_label, exercise_label in zip(reference_labels, exercise_labels):
    dff = df[
        (df["reference_year"] >= min_year)
        & (df["reference_year"] <= max_year)
        & (df["exercise_label"] == exercise_label)
        & (df["reference_label"] == reference_label)
    ].copy()

    fw_year = 2021 if reference_label == "Sep-Dec" else 2022

    fig, axs = plt.subplots(1, 5, sharey=True, figsize=(25, 6))

    for j, adm1 in enumerate(adm1s):
        dfff = dff[dff["adm1_name"] == adm1]
        dfff = dfff.pivot_table(
            index="reference_year",
            columns="adm2_name",
            values=val_col,
            aggfunc="last",
        )
        dfff.plot(ax=axs[j])
        axs[j].axvline(x=fw_year, color="grey", linestyle="--")
        axs[j].set_title(adm1)
        axs[j].set_xlabel("Reference year")
        axs[j].set_ylabel("Frac. at phase 3+")
        axs[j].legend(title="Department", loc="lower left")

    fig.suptitle(
        f"Chad IPC phase by province and department
        (exercise {exercise_label}, projected for {reference_label})",
        fontsize=16,
    )
    plt.tight_layout()
    plt.show()
```
