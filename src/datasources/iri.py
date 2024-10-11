import os
from pathlib import Path

import requests
import xarray as xr

IRI_AUTH = os.getenv("IRI_AUTH")
DATA_DIR = Path(os.getenv("AA_DATA_DIR_NEW"))
IRI_RAW_DIR = DATA_DIR / "public" / "raw" / "glb" / "iri"
IRI_BASE_URL = (
    "https://iridl.ldeo.columbia.edu/SOURCES/.IRI/.FD/"
    ".NMME_Seasonal_Forecast/.Precipitation_ELR/.prob/"
)


def download_iri():
    lon_min, lon_max, lat_min, lat_max = -180, 180, -90, 90
    url = (
        f"{IRI_BASE_URL}"
        f"X/%28{lon_min}%29%28{lon_max}"
        f"%29RANGEEDGES/"
        f"Y/%28{lat_max}%29%28{lat_min}"
        f"%29RANGEEDGES/"
        "data.nc"
    )
    response = requests.get(url, cookies={"__dlauth_id": IRI_AUTH})
    print(response.content)
    if response.headers["Content-Type"] != "application/x-netcdf":
        msg = (
            "The request returned headers indicating that the expected "
            "file type was not returned. In some cases th  is may be due "
            "to an issue with the authentication. Please check the "
            "validity of the authentication key found in your "
            "IRI_AUTH environment variable and try again."
        )
        raise requests.RequestException(msg)
    filepath = IRI_RAW_DIR / "iri.nc"
    with open(filepath, "wb") as out_file:
        out_file.write(response.content)


def load_raw_iri():
    ds = xr.open_dataset(IRI_RAW_DIR / "iri.nc", decode_times=False)
    ds["F"].attrs["calendar"] = "360_day"
    ds = xr.decode_cf(ds)
    return ds
