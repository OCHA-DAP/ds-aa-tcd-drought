import os
from pathlib import Path
from typing import List

import cdsapi
import pandas as pd
import xarray as xr
from tqdm import tqdm

from src import utils
from src.datasources import codab

DATA_DIR = Path(os.environ["AA_DATA_DIR_NEW"])
ERA5_RAW_DIR = DATA_DIR / "public" / "raw" / "tcd" / "era5"
ERA5_RAW_HOURLY_DIR = ERA5_RAW_DIR / "hourly"
ERA5_PROC_DIR = DATA_DIR / "public" / "processed" / "tcd" / "era5"


def download_era5_monthly():
    """
    Download ERA5 data from the Copernicus Climate Data Store.
    """
    adm2 = codab.load_codab()
    bounds = adm2.total_bounds
    area = [bounds[3] + 1, bounds[0], bounds[1], bounds[2] + 1]
    client = cdsapi.Client()
    start_year = 1981
    end_year = 2023
    fileformat = "grib"
    data_request = {
        "format": fileformat,
        "variable": "total_precipitation",
        "product_type": "monthly_averaged_reanalysis",
        "year": [f"{d}" for d in range(start_year, end_year + 1)],
        "month": [f"{d:02d}" for d in range(1, 13)],
        "area": area,
        "time": "00:00",
    }
    filename = f"ecmwf-reanalysis-monthly-precipitation.{fileformat}"
    client.retrieve(
        "reanalysis-era5-single-levels-monthly-means",
        data_request,
        ERA5_RAW_DIR / filename,
    )


def download_era5_hourly(years: List[int], clobber: bool = False):
    adm2 = codab.load_codab()
    bounds = adm2.total_bounds
    area = [bounds[3] + 1, bounds[0], bounds[1], bounds[2] + 1]
    client = cdsapi.Client()
    fileformat = "grib"
    for year in years:
        data_request = {
            "product_type": "ensemble_mean",
            "format": fileformat,
            "variable": "total_precipitation",
            "year": f"{year}",
            "month": [
                "01",
                "02",
                "03",
                "04",
                "05",
                "06",
                "07",
                "08",
                "09",
                "10",
                "11",
                "12",
            ],
            "day": [
                "01",
                "02",
                "03",
                "04",
                "05",
                "06",
                "07",
                "08",
                "09",
                "10",
                "11",
                "12",
                "13",
                "14",
                "15",
                "16",
                "17",
                "18",
                "19",
                "20",
                "21",
                "22",
                "23",
                "24",
                "25",
                "26",
                "27",
                "28",
                "29",
                "30",
                "31",
            ],
            "time": [
                "00:00",
                "03:00",
                "06:00",
                "09:00",
                "12:00",
                "15:00",
                "18:00",
                "21:00",
            ],
            "area": area,
        }
        filename = f"ecmwf-reanalysis-hourly-precipitation-{year}.{fileformat}"
        save_path = ERA5_RAW_HOURLY_DIR / filename
        if clobber or not save_path.exists():
            client.retrieve(
                "reanalysis-era5-single-levels",
                data_request,
                save_path,
            )
        else:
            print(f"File {save_path} already exists.")


def load_era5_hourly(year: int = 2023) -> xr.DataArray:
    filename = f"ecmwf-reanalysis-hourly-precipitation-{year}.grib"
    ds = xr.load_dataset(ERA5_RAW_HOURLY_DIR / filename, engine="cfgrib")
    da = ds["tp"]
    return da


def load_era5_monthly() -> xr.DataArray:
    filename = "ecmwf-reanalysis-monthly-precipitation.grib"
    ds = xr.load_dataset(
        ERA5_RAW_DIR / filename,
        engine="cfgrib",
        backend_kwargs={"indexpath": ""},
    )
    da = ds["tp"]
    return da


def process_combine_era5_hourly():
    """
    Combine all ERA5 hourly files into a single file.
    """
    files = list(
        ERA5_RAW_HOURLY_DIR.glob(
            "ecmwf-reanalysis-hourly-precipitation-*.grib"
        )
    )
    das = []
    for file in tqdm(files):
        ds = xr.load_dataset(
            file, engine="cfgrib", backend_kwargs={"indexpath": ""}
        )
        da_in = ds["tp"]
        das.append(da_in)

    ds_out = xr.merge(das)
    ds_out.to_netcdf(
        ERA5_PROC_DIR / "ecmwf-reanalysis-hourly-precipitation-combined.nc"
    )


def load_combined_era5_hourly() -> xr.DataArray:
    return xr.load_dataset(
        ERA5_PROC_DIR / "ecmwf-reanalysis-hourly-precipitation-combined.nc"
    )["tp"]


def process_era5_hourly_to_daily():
    hourly_combined = load_combined_era5_hourly()
    hourly_combined["valid_time_m1"] = hourly_combined["valid_time"] - 1
    daily = (
        hourly_combined.groupby("valid_time_m1.date")
        .sum()
        .isel(date=slice(1, -1))
    )
    daily["date"] = pd.to_datetime(daily["date"])
    daily.to_netcdf(ERA5_PROC_DIR / "ecmwf-reanalysis-daily-precipitation.nc")


def load_era5_daily() -> xr.DataArray:
    da = xr.load_dataset(
        ERA5_PROC_DIR / "ecmwf-reanalysis-daily-precipitation.nc"
    )["tp"]
    da = da.rio.write_crs("EPSG:4326")
    return da


def calculate_daily_rasterstats():
    daily = load_era5_daily()
    adm2 = codab.load_codab()
    daily_up = utils.upsample_dataarray(daily)
    raster_stats = daily_up.oap.compute_raster_stats(
        gdf=adm2, feature_col="ADM2_PCODE"
    )
    raster_stats = raster_stats.drop(columns=["number", "surface"])
    filename = "era5-daily-tcd-adm2-rasterstats.parquet"
    raster_stats.to_parquet(ERA5_PROC_DIR / filename, index=False)


def load_era5_daily_rasterstats() -> pd.DataFrame:
    filename = "era5-daily-tcd-adm2-rasterstats.parquet"
    return pd.read_parquet(ERA5_PROC_DIR / filename)
