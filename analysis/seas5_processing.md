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

# Processing SEAS5 rasters

```python
%load_ext jupyter_black
%load_ext autoreload
%autoreload 2
```

```python
from src.datasources import seas5, codab
```

```python
codab.download_codab()
```

```python
adm = codab.load_codab_from_blob(admin_level=1, aoi_only=True)
```

```python
adm.plot()
```

```python
da = seas5.open_seas5_rasters()
```

```python
da
```

```python

```
