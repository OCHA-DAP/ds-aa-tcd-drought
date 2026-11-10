# flake8: noqa
"""Pull CHIRPS v3 monthly rainfall and MODIS (MOD13Q1) NDVI for a bounding box
around a set of points, for March-September of every year on record.

Inputs and outputs live outside the repo (the point list is not public):
    python 02_pull_climate.py <work_dir>
reads  <work_dir>/villages/located.csv   (row_id, lon, lat, ...)
writes <work_dir>/out/chirps.nc, <work_dir>/out/ndvi.nc

CHIRPS v3: 0.05 deg monthly COGs from CHC, windowed reads, no login.
NDVI: MOD13Q1 v6.1 (250 m, 16-day) COGs from the Microsoft Planetary Computer,
no login; pixels kept where pixel_reliability is 0 or 1, then averaged to the
CHIRPS 0.05 deg grid.
"""

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import planetary_computer as pc
import pystac_client
import rasterio
import xarray as xr
from rasterio.warp import Resampling, reproject, transform_bounds
from rasterio.windows import from_bounds

WORK = Path(sys.argv[1])
OUT = WORK / "out"
pts = pd.read_csv(WORK / "villages" / "located.csv")
PAD = 0.5
W, E = np.floor(pts.lon.min() - PAD), np.ceil(pts.lon.max() + PAD)
S_, N = np.floor(pts.lat.min() - PAD), np.ceil(pts.lat.max() + PAD)
RES = 0.05
MONTHS = range(3, 10)
THIS_YEAR = 2026
lons = np.arange(W + RES / 2, E, RES)
lats = np.arange(N - RES / 2, S_, -RES)
GRID_TRANSFORM = rasterio.transform.from_origin(W, N, RES, RES)
ENV = dict(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    GDAL_HTTP_MAX_RETRY="4",
    GDAL_HTTP_RETRY_DELAY="2",
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".cog,.tif",
)


def chirps_month(ym):
    y, m = ym
    url = (
        "/vsicurl/https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/"
        f"global/cogs/chirps-v3.0.{y}.{m:02d}.cog"
    )
    with rasterio.Env(**ENV), rasterio.open(url) as src:
        win = (
            from_bounds(W, S_, E, N, src.transform)
            .round_offsets()
            .round_lengths()
        )
        a = src.read(1, window=win).astype("float32")
        assert a.shape == (len(lats), len(lons)), (
            a.shape,
            len(lats),
            len(lons),
        )
        a[a < 0] = np.nan
    return a


def pull_chirps():
    yms = [(y, m) for y in range(1981, THIS_YEAR + 1) for m in MONTHS]
    with ThreadPoolExecutor(8) as ex:
        arrs = list(ex.map(chirps_month, yms))
    da = xr.DataArray(
        np.stack(arrs).reshape(
            THIS_YEAR - 1980, len(MONTHS), len(lats), len(lons)
        ),
        dims=["year", "month", "lat", "lon"],
        coords=dict(
            year=range(1981, THIS_YEAR + 1),
            month=list(MONTHS),
            lat=lats,
            lon=lons,
        ),
        name="precip_mm",
    )
    da.to_netcdf(OUT / "chirps.nc")
    print(
        "chirps", da.shape, float(da.sel(year=THIS_YEAR).sum("month").mean())
    )


def ndvi_item(item):
    """One composite on the 0.05 deg grid; cached on disk, retried on read errors."""
    cache = OUT / "ndvi_cache" / f"{item.id}.npy"
    if cache.exists():
        return np.load(cache)
    for attempt in range(5):
        try:
            out = _ndvi_item(item)
            break
        except rasterio.errors.RasterioIOError:
            if attempt == 4:
                raise
            time.sleep(5 * (attempt + 1))
    np.save(cache, out)
    return out


def _ndvi_item(item):
    item = pc.sign(item)
    out = np.full((len(lats), len(lons)), np.nan, "float32")
    with rasterio.Env(**ENV):
        with rasterio.open(
            item.assets["250m_16_days_NDVI"].href
        ) as src, rasterio.open(
            item.assets["250m_16_days_pixel_reliability"].href
        ) as q:
            b = transform_bounds(
                "EPSG:4326", src.crs, W, S_, E, N, densify_pts=21
            )
            win = (
                from_bounds(*b, src.transform).round_offsets().round_lengths()
            )
            win = win.intersection(
                rasterio.windows.Window(0, 0, src.width, src.height)
            )
            a = src.read(1, window=win).astype("float32")
            r = q.read(1, window=win)
            a[(r > 1) | (a < -2000)] = np.nan
            a *= 1e-4
            reproject(
                a,
                out,
                src_transform=src.window_transform(win),
                src_crs=src.crs,
                dst_transform=GRID_TRANSFORM,
                dst_crs="EPSG:4326",
                resampling=Resampling.average,
                src_nodata=np.nan,
                dst_nodata=np.nan,
            )
    return out


def pull_ndvi():
    cat = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1"
    )
    items = {}
    for y in range(2000, THIS_YEAR + 1):
        res = cat.search(
            collections=["modis-13Q1-061"],
            bbox=[W, S_, E, N],
            datetime=f"{y}-02-25/{y}-09-30",
        )
        for it in res.items():
            if not it.id.startswith("MOD13Q1"):
                continue
            key = (
                it.id.split(".")[1],
                it.id.split(".")[2],
            )  # (Ayyyyddd, tile)
            if key not in items or it.id > items[key].id:  # latest processing
                items[key] = it
    (OUT / "ndvi_cache").mkdir(exist_ok=True)
    per_year = (
        pd.Series([k[0][1:5] for k in items]).value_counts().sort_index()
    )
    print("composites per year\n", per_year[per_year < 14].to_string())
    tiles = sorted({k[1] for k in items})
    print("ndvi items", len(items), "tiles", tiles)
    assert (
        len(tiles) == 1
    ), "bbox spans several MODIS tiles; mosaic not implemented"
    keys = sorted(items)
    with ThreadPoolExecutor(6) as ex:
        arrs = list(ex.map(lambda k: ndvi_item(items[k]), keys))
    dates = pd.to_datetime([k[0][1:] for k in keys], format="%Y%j")
    da = xr.DataArray(
        np.stack(arrs),
        dims=["time", "lat", "lon"],
        coords=dict(time=dates, lat=lats, lon=lons),
        name="ndvi",
    )
    da.to_netcdf(OUT / "ndvi.nc")
    print("ndvi", da.shape, float(da.isnull().mean()))


if __name__ == "__main__":
    which = sys.argv[2] if len(sys.argv) > 2 else "both"
    if which in ("both", "chirps"):
        pull_chirps()
    if which in ("both", "ndvi"):
        pull_ndvi()
