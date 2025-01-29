import os
import shutil
from pathlib import Path

import geopandas as gpd
import requests

from src.constants import ISO3, NEW_ADM1_AOI_PCODES
from src.utils import blob_utils

DATA_DIR = Path(os.environ["AA_DATA_DIR_NEW"])
CODAB_RAW_DIR = DATA_DIR / "public" / "raw" / "tcd" / "codab"


def get_blob_name(iso3: str = ISO3):
    iso3 = iso3.lower()
    return f"{blob_utils.PROJECT_PREFIX}/raw/codab/{iso3}.shp.zip"


def download_codab(local: bool = False):
    url = "https://data.fieldmaps.io/cod/originals/tcd.shp.zip"
    response = requests.get(url, stream=True)

    if response.status_code == 200:
        if local:
            with open(CODAB_RAW_DIR / "tcd.shp.zip", "wb") as f:
                response.raw.decode_content = True
                shutil.copyfileobj(response.raw, f)
        else:
            blob_name = get_blob_name()
            blob_utils._upload_blob_data(
                response.content, blob_name, stage="dev"
            )
    else:
        print(
            f"Failed to download file. "
            f"HTTP response code: {response.status_code}"
        )


def load_codab():
    return gpd.read_file(CODAB_RAW_DIR / "tcd.shp.zip")


def load_codab_from_blob(
    iso3: str = ISO3, admin_level: int = 0, aoi_only: bool = False
):
    iso3 = iso3.lower()
    shapefile = f"{iso3}_adm{admin_level}.shp"
    gdf = blob_utils.load_shp_from_blob(
        blob_name=get_blob_name(iso3),
        shapefile=shapefile,
        stage="dev",
    )
    if admin_level > 0 & aoi_only:
        gdf = gdf[gdf["ADM1_PCODE"].isin(NEW_ADM1_AOI_PCODES)]
    return gdf
