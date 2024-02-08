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

# Download ERA5 hourly reanalysis

Notebook only for downloading hourly reanalysis.
Takes several hours to download all years.

```python
%load_ext jupyter_black
%load_ext autoreload
%autoreload 2
```

```python
from src.datasources import era5
```

```python
years = range(1981, 2024)
```

```python
era5.download_era5_hourly(years)
```

```python

```
