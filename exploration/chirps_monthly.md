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

# CHIRPS monthly

```python
%load_ext jupyter_black
%load_ext autoreload
%autoreload 2
```

```python
from ochanticipy import create_custom_country_config, CodAB, ChirpsMonthly
```

```python
country_config = create_custom_country_config("../aaa.yaml")
```

```python
geobb = GeoBoundingBox.from_shape(aoi)
chirps = ChirpsMonthly(
    country_config=country_config, geo_bounding_box=geobb
)
chirps.download()
chirps.process()
```

```python

```
