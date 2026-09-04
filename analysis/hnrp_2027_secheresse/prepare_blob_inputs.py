"""Pull CH/IPC ADM2 timeseries + CODAB ADM2 from the project blob, build the
FAO-unit crosswalk, convert the GeoSahel CSV to parquet.

Run from the repo root:
  PYTHONPATH=. .venv/bin/python analysis/hnrp_2027_secheresse/prepare_blob_inputs.py work
"""  # noqa: E501

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

from src.datasources import codab, ipc

WORK = Path(sys.argv[1] if len(sys.argv) > 1 else "work")
ipc.load_adm2_timeseries().to_parquet(WORK / "ch_adm2_ts.parquet")
cod = codab.load_codab_from_blob(admin_level=2)
cod.to_file(WORK / "tcd_adm2.gpkg", driver="GPKG")

# GeoSahel csv -> parquet (drop geometry)
b = pd.read_csv(WORK / "bio_adm2.csv").drop(columns=["the_geom"])
b.to_parquet(WORK / "bio_adm2_tcd.parquet")

# FAO GAUL admin1 -> COD ADM2 area-weighted crosswalk
g = gpd.read_file(WORK / "gaul1_tcd.json")
if g.crs is None:
    g = g.set_crs(3857)
ea = "EPSG:32634"
cod_e = cod.to_crs(ea)
g_e = g.to_crs(ea)
cod_e["dep_area"] = cod_e.area
inter = gpd.overlay(
    cod_e[["ADM2_PCODE", "ADM2_FR", "dep_area", "geometry"]],
    g_e[["adm1_code", "adm1_name", "geometry"]],
    how="intersection",
)
inter["w"] = inter.area / inter.dep_area
xw = inter[["ADM2_PCODE", "ADM2_FR", "adm1_code", "adm1_name", "w"]]
xw = xw[xw.w > 0.02].sort_values(["ADM2_PCODE", "w"], ascending=[True, False])
xw.to_parquet(WORK / "asi_xwalk.parquet")

# simplified boundaries for the page map
c4 = cod.to_crs(4326).copy()
c4["geometry"] = c4.geometry.simplify(0.03, preserve_topology=True)
c4[["ADM2_PCODE", "geometry"]].to_file(
    WORK / "adm2_simpl.geojson", driver="GeoJSON"
)
a1 = cod.to_crs(4326).dissolve("ADM1_PCODE").reset_index()
a1["geometry"] = a1.geometry.simplify(0.03, preserve_topology=True)
a1[["ADM1_PCODE", "geometry"]].to_file(
    WORK / "adm1_simpl.geojson", driver="GeoJSON"
)
print("ok", len(xw), "crosswalk rows")
