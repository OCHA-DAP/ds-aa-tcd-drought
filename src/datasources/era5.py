import os
from pathlib import Path

import cdsapi

from src.datasources import codab

DATA_DIR = Path(os.environ["AA_DATA_DIR_NEW"])
ERA5_RAW_DIR = DATA_DIR / "public" / "raw" / "tcd" / "era5"


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


def download_era5_hourly(year: int = 2023):
    adm2 = codab.load_codab()
    bounds = adm2.total_bounds
    area = [bounds[3] + 1, bounds[0], bounds[1], bounds[2] + 1]
    client = cdsapi.Client()
    fileformat = "grib"
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
    filename = f"ecmwf-reanalysis-hourly-precipitation.{fileformat}"
    client.retrieve(
        "reanalysis-era5-single-levels",
        data_request,
        ERA5_RAW_DIR / filename,
    )
