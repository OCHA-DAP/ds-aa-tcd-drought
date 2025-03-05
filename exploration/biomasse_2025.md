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

# Biomasse 2025
<!-- markdownlint-disable MD013 -->

Looking at Biomasse trend and setting thresholds

```python
%load_ext jupyter_black
%load_ext autoreload
%autoreload 2
```

```python
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import statsmodels.api as sm
import numpy as np

from src.datasources import biomasse as bm
from src.constants import *
from src.utils.rp_calc import calculate_one_group_rp
from src.utils import blob_utils
```

```python
NEW_ADM1_AOI_PCODES
```

## Process and load Biomasse

Commented out steps can be skipped since they have already been run.

```python
# bm.download_dmp(admin_level="ADM1")
```

```python
# dmp = bm.calculate_biomasse(admin_level="ADM1")
```

```python
# [x in dmp["admin1Pcod"].unique() for x in NEW_ADM1_AOI_PCODES]
```

```python
# bm.aggregate_biomasse(
#     admin_pcodes=NEW_ADM1_AOI_PCODES, iso3="tcd", admin_level="ADM1"
# )
```

```python
min_year = 1999
df_bm = bm.load_aggregated_biomasse_data(iso3="tcd", admin_level="ADM1")
df_bm = df_bm[df_bm["dekad"] == 24]
df_bm = df_bm[df_bm["year"] >= min_year]
```

```python
df_bm
```

```python
df_bm["biomasse"].mean()
```

## Check trend

```python
col = "biomasse"
X = sm.add_constant(df_bm.index)
model = sm.OLS(df_bm[col], X).fit()
display(model.summary())
df_bm[f"{col}_linearfit"] = model.fittedvalues
```

```python
df_bm
```

### Plot trend

```python
# Fit the OLS model
X = sm.add_constant(df_bm["year"])  # Add constant for the intercept
y = df_bm["biomasse"]

model = sm.OLS(y, X).fit()

# Get the predicted values and the confidence intervals
predictions = model.predict(X)

# Get the confidence intervals for the predictions
predictions_ci = model.get_prediction(X).conf_int(
    alpha=0.05
)  # 95% confidence interval

# Extract the lower and upper bounds of the confidence interval
lower_bound = predictions_ci[:, 0]  # Lower bound
upper_bound = predictions_ci[:, 1]  # Upper bound

# Plot
fig, ax = plt.subplots(dpi=200, figsize=(8, 5))

# Plot the biomasse data
df_bm.set_index("year")["biomasse"].plot(
    ax=ax, color="darkgreen", linestyle="-"
)

# Plot the linear fit
df_bm.set_index("year")["biomasse_linearfit"].plot(
    ax=ax, color="grey", linestyle="--", linewidth=1
)

# Plot the confidence interval as a shaded area
ax.fill_between(
    df_bm["year"],
    lower_bound,
    upper_bound,
    facecolor="grey",
    alpha=0.1,
    label="Intervalle de confiance 95%",
)

ax.legend(["Biomasse", "Ajustement linéaire", "Intervalle de confiance 95%"])

ax.set_xlim(df_bm["year"].min(), df_bm["year"].max())

ax.set_xlabel("Année")
ax.set_ylabel("Mesure de biomasse absolu")

formatter = FuncFormatter(lambda x, _: f"{int(x):,}")
ax.yaxis.set_major_formatter(formatter)

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

ax.set_title("Tendance de biomasse")
```

```python
df_bm["biomasse_linearfit_anomaly"] = (
    df_bm["biomasse"] / df_bm["biomasse_linearfit"] * 100
)
```

```python
df_bm.set_index("year")[
    ["biomasse_anomaly", "biomasse_linearfit_anomaly"]
].plot()
```

## Calculate RP

```python
for x in ["", "_linearfit"]:
    col = f"biomasse{x}_anomaly"
    df_bm = calculate_one_group_rp(df_bm, col)
```

```python
df_bm
```

```python
# save for loading in combined_rp_2025.ipynb
blob_name = f"{blob_utils.PROJECT_PREFIX}/processed/biomasse_d24_2025.parquet"
blob_utils.upload_parquet_to_blob(df_bm, blob_name)
```

```python
# check what RP would be now with old thresh
df_interp = df_bm.sort_values("biomasse_anomaly")
old_rp = np.interp(
    80, df_interp["biomasse_anomaly"], df_interp["biomasse_anomaly_rp"]
)
```

```python
old_rp
```

```python
# check linearfit thresh with the old RP
df_interp = df_bm.sort_values("biomasse_linearfit_anomaly", ascending=False)
new_thresh = np.interp(
    old_rp,
    df_interp["biomasse_linearfit_anomaly_rp"],
    df_interp["biomasse_linearfit_anomaly"],
)
```

```python
new_thresh
```

```python
# check actual values
# notably, to get a 5-yr empirical RP, we have to split between the
# 2017 and 2002 values, which are VERY close
# so, we really need to define the threshold with at least one decimal place
df_bm.sort_values("biomasse_linearfit_anomaly")
```

```python
df_bm.sort_values("biomasse_anomaly")
```

### Plot activations

With fixed RP (taken from combined RP analysis)

```python
fixed_rp = 5
raw_thresh = df_bm["biomasse_anomaly"].quantile(1 / fixed_rp)
trend_thresh = df_bm["biomasse_linearfit_anomaly"].quantile(1 / fixed_rp)
```

```python
raw_thresh, trend_thresh
```

```python
fig, ax = plt.subplots(dpi=200, figsize=(6, 6))

raw_color = "royalblue"
trend_color = "crimson"
both_color = "rebeccapurple"
none_color = "lightgrey"

alpha = 0.15

lims = (60, 140)

raw_thresh = df_bm["biomasse_anomaly"].quantile(1 / fixed_rp)
trend_thresh = df_bm["biomasse_linearfit_anomaly"].quantile(1 / fixed_rp)

ax.axhline(trend_thresh, color=trend_color)
ax.axhspan(ymin=lims[0], ymax=trend_thresh, facecolor=trend_color, alpha=alpha)

ax.axvline(raw_thresh, color=raw_color)
ax.axvspan(xmin=lims[0], xmax=raw_thresh, facecolor=raw_color, alpha=alpha)

for year, row in df_bm.set_index("year").iterrows():
    if (
        row["biomasse_anomaly"] < raw_thresh
        and row["biomasse_linearfit_anomaly"] < trend_thresh
    ):
        color = both_color
    elif row["biomasse_anomaly"] < raw_thresh:
        color = raw_color
    elif row["biomasse_linearfit_anomaly"] < trend_thresh:
        color = trend_color
    else:
        color = none_color
    ax.annotate(
        year,
        (row["biomasse_anomaly"], row["biomasse_linearfit_anomaly"]),
        fontsize=8,
        ha="center",
        va="center",
        color=color,
        fontweight="bold",
    )

ax.set_xlim(lims)
ax.set_ylim(lims)

ax.set_xlabel("Anomalie biomasse sans tendance (ancien) [%]")
ax.set_ylabel("Anomalie biomasse avec tendance (proposé) [%]")

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

ax.set_title(
    "Comparaison des seuils de biomasse avec et sans tendance\n"
    f"Période de retour = {fixed_rp} ans"
)
```

```python
trend_thresh
```
