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

# SEAS5 rank
<!-- markdownlint-disable MD013 -->

Doing the same thing as in `ecmwf_switch` but with rank

```python
%load_ext jupyter_black
%load_ext autoreload
%autoreload 2
```

```python
import calendar

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import statsmodels.api as sm
from dask.diagnostics import ProgressBar
from scipy.stats import skewnorm, beta, f_oneway, kruskal
from matplotlib.ticker import LogLocator, FuncFormatter

from src.datasources import seas5, iri, codab
from src.utils.raster import upsample_dataarray
from src.utils.rp_calc import calculate_groups_rp
from src.utils import blob_utils
from src.constants import *
```

## Load and process rasters

```python
adm1 = codab.load_codab_from_blob(admin_level=1, aoi_only=True)
```

```python
da_seas5 = seas5.open_seas5_rasters()
```

```python
da_seas5_tri = da_seas5.mean(dim="lt")
da_seas5_up = upsample_dataarray(da_seas5_tri)
da_seas5_clip = da_seas5_up.rio.clip(adm1.geometry)
```

```python
da_seas5_clip
```

```python
# have to rechunk with all years as one to allow rank calculation
da_seas5_clip_yearchunk = da_seas5_clip.chunk({"year": -1})
```

```python
da_seas5_rank = da_seas5_clip_yearchunk.rank(dim="year", pct=True)
```

```python
with ProgressBar():
    da_seas5_rank_computed = da_seas5_rank.compute()
```

```python
da_seas5_rank_computed
```

Look at ranks for random pixel to check distribution looks plausible

```python
da_seas5_rank_computed.isel(x=50, y=30, issued_month=0)
```

Plot a couple years to make sure they look sensible

```python
da_seas5_rank_computed.sel(year=1999, issued_month=6).plot()
```

```python
da_seas5_rank_computed.sel(year=2002, issued_month=6).plot()
```

It does seem weird that the value is 1 almost everywhere in 1999. So, just to be absolutely sure we're calculating the spatial quantile in the right direction, calculate it for both `ORIGINAL_Q` and `1 - ORIGINAL_Q`. The inverse one (`1 - ORIGINAL_Q`) should always be higher than (or equal to) the normal one, since it's the highest quantile (0.8 instead of 0.2).

```python
da_seas5_rank_q = da_seas5_rank.quantile(q=ORIGINAL_Q, dim=["x", "y"])
```

```python
with ProgressBar():
    da_seas5_rank_q_computed = da_seas5_rank_q.compute()
```

```python
da_seas5_rank_q_test = da_seas5_rank.quantile(q=1 - ORIGINAL_Q, dim=["x", "y"])
```

```python
with ProgressBar():
    da_seas5_rank_q_test_computed = da_seas5_rank_q_test.compute()
```

From the plot below, looks like we're good.

```python
fig, ax = plt.subplots()
da_seas5_rank_q_computed.isel(issued_month=0).plot(ax=ax)
da_seas5_rank_q_test_computed.isel(issued_month=0).plot(ax=ax, color="red")
```

```python
df_seas5_rank_q = da_seas5_rank_q_computed.to_dataframe("q")["q"].reset_index()
```

```python
blob_name = f"{blob_utils.PROJECT_PREFIX}/processed/seas5/seas5_rank_q{ORIGINAL_Q*100:.0f}.parquet"  # noqa
blob_utils.upload_parquet_to_blob(df_seas5_rank_q, blob_name)
```

## Calculate threshs

```python
df_seas5 = seas5.load_seas5_stats(variable="rank")
```

```python
df_seas5
```

```python
# just check the histogram to see that it's sensible
for issued_month, group in df_seas5.groupby("issued_month"):
    group["q"].hist(alpha=0.3)
```

```python
df_seas5.groupby("issued_month")["q"].mean().plot()
```

```python
df_seas5["window"] = df_seas5["issued_month"].apply(
    lambda x: 1 if x <= 4 else 2
)
```

Have a quick look at combined RPs. Not that important since ultimately we'll be picking something that fits with the observational as well.

```python
df_seas5 = calculate_groups_rp(df_seas5, by=["issued_month"])
```

```python
total_years = df_seas5["year"].nunique()
dicts = []
for rp_individual in df_seas5["q_rp"].unique():
    dff = df_seas5[df_seas5["q_rp"] >= rp_individual]
    n_years = dff["year"].nunique()
    rp_combined = (total_years + 1) / n_years
    dicts.append({"rp_individual": rp_individual, "rp_combined": rp_combined})

df_rps = pd.DataFrame(dicts).sort_values("rp_individual")
```

```python
fig, ax = plt.subplots(dpi=200)

df_rps.plot(x="rp_individual", y="rp_combined", ax=ax, legend=False)

ax.set_xlim(left=1)
ax.set_ylim(bottom=1)

ax.set_xlabel("Période de retour de chaque prévision individuellement (ans)")
ax.set_ylabel("Période de retour combinée des prévisions (ans)")
ax.set_title("Comparaison du période de retour individuelle et combinée")

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
```

```python
min_year = 1999

df_seas5_recent = df_seas5[df_seas5["year"] >= min_year]
```

```python
df_seas5_recent = calculate_groups_rp(df_seas5_recent, by=["issued_month"])
```

```python
total_years_recent = df_seas5_recent["year"].nunique()
dicts = []
for rp_individual in df_seas5_recent["q_rp"].unique():
    dff = df_seas5_recent[df_seas5_recent["q_rp"] >= rp_individual]
    n_years = dff["year"].nunique()
    rp_combined = (total_years_recent + 1) / n_years
    dicts.append({"rp_individual": rp_individual, "rp_combined": rp_combined})

df_rps_recent = pd.DataFrame(dicts).sort_values("rp_individual")
```

```python
df_rps_recent
```

```python
fig, ax = plt.subplots(dpi=200)

df_rps_recent.plot(x="rp_individual", y="rp_combined", ax=ax, legend=False)

ax.set_xlim(left=1)
ax.set_ylim(bottom=1)

ax.set_xlabel("Période de retour de chaque prévision individuellement (ans)")
ax.set_ylabel("Période de retour combinée des prévisions (ans)")
ax.set_title("Comparaison du période de retour individuelle et combinée")

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
```

```python
rp_individual_seas5 = 27

df_seas5_triggers_recent = df_seas5_recent[
    df_seas5_recent["q_rp"] >= rp_individual_seas5
]
```

```python
rp_combined_seas5 = (total_years_recent + 1) / df_seas5_triggers_recent[
    "year"
].nunique()
```

```python
rp_combined_seas5
```

```python
df_seas5_recent.pivot(index="year", columns="issued_month", values="q").plot()
```

```python
df_seas5_recent
```

Save quantile values to blob to read them in `combined_rp_2025.ipynb`

```python
blob_name = f"{blob_utils.PROJECT_PREFIX}/processed/seas5_recent_2025.parquet"
blob_utils.upload_parquet_to_blob(df_seas5_recent, blob_name)
```

```python
for issued_month, group in df_seas5_recent.groupby("issued_month"):
    X = sm.add_constant(group.index)
    model = sm.OLS(group["q"], X).fit()
    print(f"issued month {issued_month}")
    print(model.summary())
```

```python
dicts = []
for issued_month, group in df_seas5_recent.groupby("issued_month"):
    group_sorted = group.copy().sort_values("q_rp")
    rp_val = np.interp(
        rp_individual_seas5, group_sorted["q_rp"], group_sorted["q"]
    )
    dicts.append({"issued_month": issued_month, "thresh": rp_val})

df_threshs = pd.DataFrame(dicts)
```

```python
df_threshs
```

```python
df_seas5_recent
```

## Plotting

### RP-based threshold plot

Calculate thresholds individually for each month, with a fixed individual RP.

```python
fig, ax = plt.subplots(dpi=200, figsize=(7, 7))

ymin, ymax = 0.9, 39
trig_color = "crimson"

shapes = {3: "+", 4: "x", 5: "s", 6: "D"}

for issued_month, group in df_seas5_recent.groupby("issued_month"):
    group.plot(
        x="year",
        y="q_rp",
        marker=shapes.get(issued_month),
        markerfacecolor="none",
        markeredgecolor="black",
        markersize=5,
        linewidth=0,
        ax=ax,
        label=FRENCH_MONTHS.get(calendar.month_abbr[issued_month]),
    )

for year, group in df_seas5_recent.groupby("year"):
    max_val = group["q_rp"].max()
    trigger_bool = max_val >= rp_individual_seas5
    color = trig_color if trigger_bool else "grey"
    fontweight = "bold" if trigger_bool else "normal"
    ax.plot(
        [year, year],
        [ymin, max_val],
        color="grey",
        linewidth=0.1,
        zorder=-1,
    )
    ax.annotate(
        f"{year}  ",
        (year - 0.1, max_val),
        ha="center",
        rotation=-90,
        va="bottom",
        fontsize=8,
        color=color,
        fontweight=fontweight,
    )

ax.axhline(rp_individual_seas5, color=trig_color, zorder=-2)
ax.axhspan(
    ymin=rp_individual_seas5,
    ymax=ymax,
    facecolor=trig_color,
    alpha=0.1,
    zorder=-2,
)

# ax.set_ylim(bottom=0)
ax.set_yscale("log")
ax.yaxis.set_major_locator(
    LogLocator(base=10.0, subs=np.arange(2, 10) * 1, numticks=10)
)
ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0f}"))
ax.set_ylim(top=ymax, bottom=ymin)

ax.set_xticks([])

plt.xticks(rotation=-90)

ax.legend(
    loc="upper left",
    bbox_to_anchor=(1, 1),
    borderaxespad=1.0,
    title="Mois de\npublication",
)

ax.set_title(
    "Prévisions et activations historiques de SEAS5\n"
    f"(période de retour combinée = {rp_combined_seas5:.1f} ans)"
)
ax.set_xlabel("Année")
ax.set_ylabel("Période de retour de prévision (ans)")

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
```

### Fixed threshold plot

Set a fixed threshold for the different months. This seems reasonable as:

- We can't really say whether the spatial quantile values we're plotting have a different distribution from issue month to issue month, so it doesn't really make sense to fix the threshold independently for each one.
- Having the same threshold for each month is just easier to remember and easier to explain.

Here the `thresh` is hard-coded as this is the number that's going in the framework document. It's taken from the combiend RP analysis in `combined_rp_2025.ipynb` (being the option that was determined to be most appropriate after working group discussions).

```python
fig, ax = plt.subplots(dpi=200, figsize=(7, 7))

thresh = 0.15

ymin, ymax = 0.9, 39
trig_color = "crimson"

shapes = {3: "+", 4: "x", 5: "s", 6: "D"}

for issued_month, group in df_seas5_recent.groupby("issued_month"):
    group.plot(
        x="year",
        y="q",
        marker=shapes.get(issued_month),
        markerfacecolor="none",
        markeredgecolor="black",
        markersize=5,
        linewidth=0,
        ax=ax,
        label=FRENCH_MONTHS.get(calendar.month_abbr[issued_month]),
    )

for year, group in df_seas5_recent.groupby("year"):
    min_val = group["q"].min()
    trigger_bool = min_val <= thresh
    color = trig_color if trigger_bool else "grey"
    fontweight = "bold" if trigger_bool else "normal"
    ax.plot(
        [year, year],
        [1, min_val],
        color="grey",
        linewidth=0.1,
        zorder=-1,
    )
    ax.annotate(
        f"  {year}  ",
        (year - 0.1, min_val),
        ha="center",
        rotation=-90,
        va="top",
        fontsize=8,
        color=color,
        fontweight=fontweight,
    )

ax.axhline(thresh, color=trig_color, zorder=-2)
ax.axhspan(
    ymin=0,
    ymax=thresh,
    facecolor=trig_color,
    alpha=0.1,
    zorder=-2,
)

ax.annotate(
    f"  Seuil = {thresh}".replace(".", ","),
    (df_seas5_recent["year"].max() + 1, thresh),
    color=trig_color,
    va="center",
)

ax.set_xticks([])
ax.set_ylim(0, 1)

plt.xticks(rotation=-90)

ax.legend(
    loc="upper left",
    bbox_to_anchor=(1, 1),
    borderaxespad=1.0,
    title="Mois de\npublication",
)

ax.set_title(
    "Prévisions et activations historiques de SEAS5\n"
    f"(période de retour combinée = {rp_combined_seas5:.1f} ans)".replace(
        ".", ","
    )
)
ax.set_xlabel("Année")
ax.set_ylabel(
    "Centile historique des précipitations JAS,\n"
    "20e centile sur la zone d'intérêt"
)

# ax.spines["top"].set_visible(False)
# ax.spines["right"].set_visible(False)
```

Just double-checking the historical activations per window.

```python
thresh = 0.1
dff = df_seas5_recent[df_seas5_recent["q"] <= thresh]
dff.groupby(["window"])["year"].nunique()
```

### Issued-month-wise plot

From here, we can see the values grouped by issued month instead of year. We can see that it's plausible the values from the issued months come from the same distribution.

```python
fig, ax = plt.subplots(figsize=(6, 8))

df_seas5_recent.plot(x="issued_month", y="q", ax=ax, linewidth=0, legend=False)

for mo, group in df_seas5_recent.groupby("issued_month"):
    for year, row in group.set_index("year").iterrows():
        ax.annotate(
            f"{year}: {row['q']:.2f}",
            (row["issued_month"], row["q"]),
            ha="center",
            va="center",
            fontsize=8,
        )

ax.set_xticks([3, 4, 5, 6])
ax.set_xlim(2, 7)
```

## RP modeling

This section can be ignored. If anything it just shows that fitting a distribution to the values doesn't really make sense. Also, the values from the various issue months are not necessarily from different distributions.

```python
def fit_beta_rp(issued_month, rp_fit):
    # Fit the Beta distribution to the 'issued_3' column in df_pivot_recent
    # Given data is strictly between 0 and 1, so we set floc=0 and fscale=1
    params = beta.fit(
        df_pivot_recent[f"issued_{issued_month}"].clip(0 + 1e-10, 1 - 1e-10),
        floc=0,
        fscale=1,
    )

    # Generate a range of values for plotting the PDF (from 0 to 1)
    x = np.linspace(0, 1, 1000)
    pdf_values = beta.pdf(x, *params)

    # Create the histogram of the 'issued_3' column
    plt.figure(figsize=(8, 6))
    plt.hist(
        df_pivot_recent[f"issued_{issued_month}"],
        bins=30,
        density=True,
        alpha=0.6,
        color="g",
        label="Data Histogram",
    )

    # Plot the PDF of the fitted Beta distribution
    plt.plot(x, pdf_values, "r-", lw=2, label="Fitted Beta Distribution")

    # Add labels and legend
    plt.title("Goodness of Fit: Beta Distribution")
    plt.xlabel(f"issued_{issued_month}")
    plt.ylabel("Density")
    plt.legend()

    # Show the plot
    plt.show()

    # Calculate the threshold for the return period using the Beta distribution
    thresh = beta.ppf(1 / rp_fit, *params)
    print(f"thresh for {rp_fit}-yr RP: {thresh}")
    n_trig_years = len(
        df_pivot_recent[df_pivot_recent[f"issued_{issued_month}"] <= thresh]
    )
    print(f"n years triggered with this thresh: {n_trig_years}")
    print(
        f"empirical RP with this thresh: {(len(df_pivot_recent)+1)/n_trig_years}"
    )
```

```python
fit_beta_rp(3, 3)
```

```python
fit_beta_rp(4, 3)
```

```python
params = beta.fit(
    df_seas5_recent["q"].clip(0 + 1e-10, 1 - 1e-10),
    floc=0,
    fscale=1,
)
x = np.linspace(0, 1, 1000)
pdf_values = beta.pdf(x, *params)
plt.figure(figsize=(8, 6))
plt.hist(
    df_seas5_recent["q"],
    bins=30,
    density=True,
    alpha=0.6,
    color="g",
    label="Data Histogram",
)

# Plot the PDF of the fitted Beta distribution
plt.plot(x, pdf_values, "r-", lw=2, label="Fitted Beta Distribution")
```

```python
params
```

```python
# Perform one-way ANOVA
f_stat, p_val = f_oneway(
    df_pivot_recent["issued_3"],
    df_pivot_recent["issued_4"],
    df_pivot_recent["issued_5"],
    df_pivot_recent["issued_6"],
)
print(f"F-statistic: {f_stat}, p-value: {p_val}")
```

```python
f_stat, p_val = kruskal(
    df_pivot_recent["issued_3"],
    df_pivot_recent["issued_4"],
    df_pivot_recent["issued_5"],
    df_pivot_recent["issued_6"],
)
print(f"F-statistic: {f_stat}, p-value: {p_val}")
```
