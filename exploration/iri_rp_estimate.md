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

# IRI RP estimate

Estimating RP of IRI forecast using spatial quantile and Pearson distribution

```python
%load_ext jupyter_black
%load_ext autoreload
%autoreload 2
```

```python
import xarray as xr
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import beta
from copulas.multivariate import GaussianMultivariate
from copulas.univariate import BetaUnivariate

import scipy.stats as stats

from src.datasources import iri, codab
from src.constants import *
```

```python
adm2 = codab.load_codab()
adm2_aoi = adm2[adm2["ADM1_PCODE"].isin(ADM1_AOI_PCODES)]
adm2_aoi.plot()
```

```python
def upsample_dataarray(
    da: xr.DataArray, resolution: float = 0.1
) -> xr.DataArray:
    new_lat = np.arange(da.Y.min() - 1, da.Y.max() + 1, resolution)
    new_lon = np.arange(da.X.min() - 1, da.X.max() + 1, resolution)
    return da.interp(
        Y=new_lat,
        X=new_lon,
        method="nearest",
        kwargs={"fill_value": "extrapolate"},
    )
```

```python
ds = iri.load_raw_iri()
```

```python
da = ds.isel(C=0)["prob"]
da = da.rio.write_crs(4326)
da_clip_low = da.rio.clip(adm2_aoi.geometry, all_touched=True)
da_up = upsample_dataarray(da_clip_low)
da_up = da_up.rio.write_crs(4326)
da_clip = da_up.rio.clip(adm2_aoi.geometry)
```

```python
da_q = da_clip.quantile(0.8, dim=["X", "Y"]) / 100
```

```python
valid_month = 7
dfs = []
for L in [1, 2, 3, 4]:
    month = valid_month - L
    da_L = da_q.sel(L=L, F=da_q["F.month"] == month)
    df_in = da_L.to_dataframe()["prob"].reset_index()
    df_in["F"] = pd.to_datetime(df_in["F"].astype(str))
    df_in["L"] = L
    dfs.append(df_in)
```

```python
df = pd.concat(dfs)
```

```python
df
```

```python
def calculate_return_period_beta(level, a, b):
    cdf_value = stats.beta.cdf(level, a, b, loc=0, scale=1)
    p_exceedance = 1 - cdf_value
    return_period = 1 / p_exceedance
    return return_period
```

```python
def calculate_mean_error(x):
    data = x

    sample_mean = np.mean(data)

    # Step 2: Calculate the sample standard error (SE)
    sample_std = np.std(data, ddof=1)  # ddof=1 for sample standard deviation
    sample_size = len(data)
    standard_error = sample_std / np.sqrt(sample_size)

    # Step 3: Define the confidence level (e.g., 95%)
    confidence_level = 0.95
    alpha = 1 - confidence_level

    # Step 4: Calculate the critical t value for a 95% confidence interval
    t_critical = stats.t.ppf(1 - alpha / 2, df=sample_size - 1)

    # Step 5: Calculate the margin of error
    margin_of_error = t_critical * standard_error

    # Step 6: Calculate the confidence interval
    ci_lower = sample_mean - margin_of_error
    ci_upper = sample_mean + margin_of_error
    return margin_of_error
```

```python
def fit_beta(x, mean_calc):
    if mean_calc == "stationary":
        a, b, loc, scale = stats.beta.fit(x, floc=0, fscale=1)
        mean_error = calculate_mean_error(x)
        return a, b, mean_error
    elif mean_calc == "drift":
        index = range(len(x))
        coefficients = np.polyfit(index, x, 1)
        slope, intercept = coefficients
        known_mean = slope * (index[-1] + 1) + intercept
        print(known_mean)
    elif mean_calc == "known":
        known_mean = 1 / 3
    estimated_variance = np.var(x)
    eta = (known_mean * (1 - known_mean) / estimated_variance) - 1
    a = known_mean * eta
    b = (1 - known_mean) * eta
    loc, scale = 0, 1
    return a, b, 0
```

```python
dicts = []
for mean_calc in ["stationary", "drift", "known"]:
    for L, group in df.groupby("L"):
        a, b, mean_error = fit_beta(group["prob"], mean_calc=mean_calc)
        mean = a / (a + b)
        rp = calculate_return_period_beta(0.6, a, b)
        dicts.append(
            {
                "L": L,
                "a": a,
                "b": b,
                "mean": mean,
                "mean_error": mean_error,
                "max_mean": mean + mean_error,
                "rp": rp,
                "mean_calc": mean_calc,
            }
        )
```

```python
df_distributions = pd.DataFrame(dicts)
df_distributions["freq"] = 1 / df_distributions["rp"]
df_distributions
```

```python
for mean_calc in ["stationary", "drift", "known"]:
    print(mean_calc)
    for window in [1, 2]:
        print(window)
        print("anti-correlation:")
        display(
            1
            / df_distributions[
                (df_distributions["L"].isin([window * 2 - 1, window * 2]))
                & (df_distributions["mean_calc"] == mean_calc)
            ]["freq"].sum()
        )
        print("perfect correlation:")
        display(
            1
            / df_distributions[
                (df_distributions["L"].isin([window * 2 - 1, window * 2]))
                & (df_distributions["mean_calc"] == mean_calc)
            ]["freq"].max()
        )
    print()
```

```python
df_year = df.copy()
df_year["year"] = df_year["F"].dt.year
```

```python
df_year.pivot(index="year", columns="L", values="prob").corr()
```

```python
df_year.pivot(index="year", columns="L", values="prob").plot()
```

## Multi-variate

```python
data = np.array(df_year.pivot(index="year", columns="L", values="prob"))
```

```python
data
```

```python
beta_fits = []
for i in range(data.shape[1]):
    alpha, beta_param, _, _ = beta.fit(data[:, i], floc=0, fscale=1)
    beta_fits.append((alpha, beta_param))

# # Step 2: Calculate the empirical correlation matrix
correlation_matrix = np.corrcoef(data.T)

# # Step 3: Use a Gaussian Copula to model dependency
# # Transform data into uniform margins (for copula fitting)
uniform_data = np.zeros_like(data)
for i in range(data.shape[1]):
    alpha, beta_param = beta_fits[i]
    uniform_data[:, i] = beta.cdf(
        data[:, i], alpha, beta_param, loc=0, scale=1
    )
# covariance_matrix = np.cov(uniform_data, rowvar=False)

# # Fit a Gaussian Copula to the uniform data
copula = GaussianMultivariate()
copula.fit(uniform_data)

# # Step 4: Generate random samples from the copula
num_samples = 1000  # Number of samples to generate
samples_from_copula = np.array(copula.sample(num_samples))

# # Ensure samples_from_copula is 2D and matches the shape of generated_samples
generated_samples = np.zeros_like(samples_from_copula)

# # Transform the samples back to Beta-distributed values
for i in range(data.shape[1]):
    alpha, beta_param = beta_fits[i]
    generated_samples[:, i] = beta.ppf(
        samples_from_copula[:, i], alpha, beta_param, loc=0, scale=1
    )
```

```python
data
```

```python
covariance_matrix = np.cov(data, rowvar=False)
covariance_matrix
```

```python
df_generated = pd.DataFrame(generated_samples)
```

```python
df_generated[df_generated.isnull().any(axis=1)]
```

```python
df_generated_triggers = df_generated > 0.425
```

```python
df_generated_triggers["any"] = df_generated_triggers.any(axis=1)
```

```python
1 / df_generated_triggers["any"].mean()
```

```python

```
