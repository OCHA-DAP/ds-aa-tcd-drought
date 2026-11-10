# flake8: noqa
"""Compute village-level rainfall and NDVI statistics and build the encrypted page.

    PAGE_PASSWORD=... python 03_build_page.py <work_dir> <repo_docs_dir>
reads  <work_dir>/villages/located.csv, seats.csv, <work_dir>/out/{chirps,ndvi}.nc,
       <work_dir>/gaz/tcd.shp.zip
writes <repo_docs_dir>/evaluation_villages_2026/{index.html,data.enc}

Everything village-level goes into data.enc (PBKDF2-SHA256, 300k iterations,
AES-256-GCM; base64 of salt|iv|ciphertext), which the page decrypts in the browser.
"""

import base64
import json
import os
import shutil
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from shapely.geometry import box

WORK, DOCS = Path(sys.argv[1]), Path(sys.argv[2])
HERE = Path(__file__).parent
YEAR = 2026
RAIN_BASE, NDVI_BASE = (1991, 2020), (
    2001,
    2023,
)  # the archive lacks an August 2024 composite and all of the 2025 rainy season
MONTH_NAMES = ["Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep"]


def ordinal(n):
    n = int(n)
    suf = (
        "th"
        if 10 <= n % 100 <= 20
        else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    )
    return f"{n}{suf}"


def rank_txt(rank, n, word):
    return (
        f"{word} of {n} years"
        if rank == 1
        else f"{ordinal(rank)} {word} of {n} years"
    )


p = pd.read_csv(WORK / "villages" / "located.csv")
seats = pd.read_csv(WORK / "villages" / "seats.csv")
p["precision"] = np.where(p.precision == "village", "village", "seat")
chirps = xr.open_dataarray(WORK / "out" / "chirps.nc")
ndvi = xr.open_dataarray(WORK / "out" / "ndvi.nc")
sel = dict(
    lon=xr.DataArray(p.lon.values, dims="p"),
    lat=xr.DataArray(p.lat.values, dims="p"),
    method="nearest",
)
is_seat = xr.DataArray((p.precision == "seat").values, dims="p")


def at_points(da):
    """Grid cell value for villages found by name; mean of the 7 x 7 cells (about
    35 km across) around the sous-prefecture town for villages placed there."""
    area = da.rolling(lat=7, lon=7, center=True, min_periods=1).mean()
    return xr.where(is_seat, area.sel(**sel), da.sel(**sel))


# ---- rainfall: June-September total against 1991-2020
jjas_g = chirps.sel(month=[6, 7, 8, 9]).sum("month", skipna=False)
rain_pct_g = (
    100
    * jjas_g.sel(year=YEAR)
    / jjas_g.sel(year=slice(*RAIN_BASE)).mean("year")
)
jjas = at_points(jjas_g)
base = jjas.sel(year=slice(*RAIN_BASE))
p["rain_mm"] = jjas.sel(year=YEAR).values.round(0).astype(int)
p["rain_avg_mm"] = base.mean("year").values.round(0).astype(int)
p["rain_pct"] = (
    (100 * jjas.sel(year=YEAR) / base.mean("year")).values.round(0).astype(int)
)
p["rain_z"] = (
    (jjas.sel(year=YEAR) - base.mean("year")) / base.std("year", ddof=1)
).values.round(2)
p["rain_rank"] = (jjas < jjas.sel(year=YEAR)).sum("year").values + 1
N_RAIN = jjas.sizes["year"]
p["rain_rank_txt"] = [rank_txt(r, N_RAIN, "driest") for r in p.rain_rank]

# ---- NDVI: seasonal greening = August-September mean (composites starting 28 Jul - 14 Sep)
# minus the March-May mean of the same year (bare-soil background), against 2001-2023
doy = ndvi.time.dt.dayofyear


_cube = ndvi.assign_coords(
    yr=("time", ndvi.time.dt.year.values),
    slot=("time", ((doy.values - 1) // 16)),
)
_cube = (
    _cube.set_index(time=["yr", "slot"]).unstack("time").rename(yr="year")
)  # (lat, lon, year, slot)
_cube = _cube.sel(
    year=[
        y
        for y in _cube.year.values
        if NDVI_BASE[0] <= y <= NDVI_BASE[1] or y == YEAR
    ]
)


def window_mean(lo, hi):
    """Mean over the 16-day composites starting between day-of-year lo and hi. Each cell uses
    only the composites that are cloud-free there in 2026 (at least 3), and a year counts only
    if it has all of those, so every year is averaged over the same dates."""
    w = _cube.sel(
        slot=[s for s in _cube.slot.values if lo <= s * 16 + 1 <= hi]
    )
    use = w.sel(year=YEAR).notnull()
    wm = w.where(use)
    ok = (wm.notnull() == use).all("slot") & (use.sum("slot") >= 3)
    return wm.mean("slot").where(ok)


raw_peak_y = window_mean(209, 258)
peak_y = raw_peak_y - window_mean(60, 150)
nbase_g = peak_y.sel(year=slice(*NDVI_BASE))
ndvi_pct_g = (
    (100 * peak_y.sel(year=YEAR) / nbase_g.mean("year"))
    .where(nbase_g.mean("year") >= 0.02)
    .clip(0, 300)
)
pk = at_points(peak_y)
nb = pk.sel(year=slice(*NDVI_BASE))
p["ndvi_peak"] = at_points(raw_peak_y).sel(year=YEAR).values.round(3)
p["ndvi_val"] = pk.sel(year=YEAR).values.round(3)
p["ndvi_avg"] = nb.mean("year").values.round(3)
p["ndvi_pct"] = (100 * pk.sel(year=YEAR) / nb.mean("year")).values.round(0)
p["ndvi_z"] = (
    (pk.sel(year=YEAR) - nb.mean("year")) / nb.std("year", ddof=1)
).values.round(2)
p["ndvi_rank"] = (pk < pk.sel(year=YEAR)).sum("year").values + 1
p["ndvi_n"] = pk.notnull().sum("year").values
p["ndvi_rank_txt"] = [
    rank_txt(r, n, "lowest") for r, n in zip(p.ndvi_rank, p.ndvi_n)
]
assert p[["rain_pct", "ndvi_pct"]].notnull().all().all(), p[
    p.ndvi_pct.isnull()
]
p["ndvi_pct"] = p.ndvi_pct.astype(int)

# ---- ordering, labels, jitter
prov_order = p.groupby("adm1").rain_pct.median().sort_values().index.tolist()
p["adm3_label"] = p.adm3
a3 = p.groupby(["adm1", "adm3_label"]).rain_pct.median().reset_index()
a3["po"] = a3.adm1.map(prov_order.index)
a3 = a3.sort_values(["po", "rain_pct"])
p["jit"] = 0.0
for _, gidx in p.groupby("adm3_label").groups.items():
    n = len(gidx)
    p.loc[gidx, "jit"] = np.linspace(-0.3, 0.3, n) if n > 1 else 0.0
# spread markers that share a map coordinate on a small ring
p["lon_j"], p["lat_j"] = p.lon, p.lat
for _, gidx in p.groupby([p.lon.round(4), p.lat.round(4)]).groups.items():
    n = len(gidx)
    if n > 1:
        r = 0.018 + 0.004 * n
        ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
        p.loc[gidx, "lon_j"] = p.loc[gidx, "lon"].values + r * np.cos(ang)
        p.loc[gidx, "lat_j"] = p.loc[gidx, "lat"].values + r * np.sin(ang)

# ---- monthly by province
monthly = {}
vr = at_points(chirps)
vn = at_points(ndvi)
ndoy = vn.time.dt.dayofyear.values
slot = ((ndoy - 1) // 16).astype(int)  # 16-day composite index within the year
vn = vn.assign_coords(slot=("time", slot), yr=("time", vn.time.dt.year.values))
for prov in prov_order:
    m = (p.adm1 == prov).values
    r = vr.isel(p=m).mean("p")
    nv = vn.isel(p=m).mean("p").to_series().reset_index(drop=True)
    df = pd.DataFrame({"v": nv.values, "slot": slot, "yr": vn.yr.values})
    piv = df.pivot_table(index="slot", columns="yr", values="v")
    b = piv.loc[:, NDVI_BASE[0] : NDVI_BASE[1]]
    x = [
        (
            pd.Timestamp(YEAR, 1, 1) + pd.Timedelta(days=int(s) * 16 + 8)
        ).strftime("%Y-%m-%d")
        for s in piv.index
    ]
    monthly[prov] = dict(
        rain_2026=r.sel(year=YEAR).values.round(1).tolist(),
        rain_avg=r.sel(year=slice(*RAIN_BASE))
        .mean("year")
        .values.round(1)
        .tolist(),
        ndvi_x=x,
        ndvi_2026=[
            None if np.isnan(v) else round(float(v), 3)
            for v in piv[YEAR].values
        ],
        ndvi_med=b.median(axis=1).round(3).tolist(),
        ndvi_lo=b.quantile(0.25, axis=1).round(3).tolist(),
        ndvi_hi=b.quantile(0.75, axis=1).round(3).tolist(),
    )
rain_max = max(max(v["rain_2026"] + v["rain_avg"]) for v in monthly.values())
nd_all = [
    x
    for v in monthly.values()
    for k in ("ndvi_2026", "ndvi_hi", "ndvi_lo")
    for x in v[k]
    if x is not None
]

# ---- map layers
W, E = float(chirps.lon.min()) - 0.025, float(chirps.lon.max()) + 0.025
S_, N = float(chirps.lat.min()) - 0.025, float(chirps.lat.max()) + 0.025
xr_ = [p.lon.min() - 0.6, p.lon.max() + 0.6]
yr_ = [p.lat.min() - 0.45, p.lat.max() + 0.45]
adm1 = gpd.read_file(f"zip://{WORK}/gaz/tcd.shp.zip!tcd_adm1.shp").to_crs(4326)
borders = []
for geom in (
    adm1.boundary.simplify(0.01)
    .clip(box(W, S_, E, N))
    .explode(index_parts=False)
):
    if geom.is_empty:
        continue
    xs, ys = geom.xy
    borders.append(
        dict(x=[round(v, 3) for v in xs], y=[round(v, 3) for v in ys], w=0.9)
    )
towns = (
    seats.assign(name=seats.adm3.str.replace(" Rural", "", regex=False))
    .drop_duplicates("name")
    .copy()
)
n_here = p.groupby([p.lon.round(4), p.lat.round(4)]).size()
ring = [
    0.018 + 0.004 * n_here.get((round(x, 4), round(y, 4)), 0)
    for x, y in zip(towns.lon, towns.lat)
]
# label below the town when another town sits just to the north, otherwise above
below = [
    any(
        (0 < o.lat - t.lat < 0.25) and abs(o.lon - t.lon) < 0.5
        for o in towns.itertuples()
    )
    for t in towns.itertuples()
]
towns["pos"] = np.where(below, "bottom center", "top center")
towns["lat"] = towns.lat + np.where(below, -1, 1) * (np.array(ring) + 0.01)


def grid_list(da):
    a = da.sel(lat=slice(None, None, -1)).values  # south to north
    return [
        [None if np.isnan(v) else round(float(v)) for v in row] for row in a
    ]


# ---- text
def rng(s):
    return (
        f"{int(s.min())}–{int(s.max())}%"
        if s.min() != s.max()
        else f"{int(s.min())}%"
    )


tiles = []
for prov in prov_order:
    d = p[p.adm1 == prov]
    r0, r1 = d.rain_rank.min(), d.rain_rank.max()
    rk = ordinal(r0) if r0 == r1 else f"{ordinal(r0)} to {ordinal(r1)}"
    tiles.append(
        dict(
            k=f"{prov} · {len(d)} villages",
            v=rng(d.rain_pct),
            d=f"of average June–September rainfall; {rk} driest of {N_RAIN} years",
        )
    )
n_v, n_s = int((p.precision == "village").sum()), int(
    (p.precision == "seat").sum()
)
lede = (
    f"{len(p)} villages in {len(prov_order)} provinces. Rainfall and vegetation greenness in 2026, "
    "compared with each place's own average."
)
notes = [
    "Rainfall is CHIRPS v3 monthly (satellite and rain gauges, about 5 km grid), 1981–2026. "
    "The June–September total is compared with the 1991–2020 average at the same grid cell.",
    "NDVI is MODIS Terra MOD13Q1 (250 m, 16-day), 2000–2026, cloud-screened and averaged to the same 5 km grid. "
    "Seasonal greening is the August–September mean minus the March–May mean of the same year, which removes the "
    "bare-soil background. It is compared with the 2001–2023 average at the same grid cell, using the same "
    "cloud-free dates in every year. 2024 and 2025 are left out because rainy-season images are missing from "
    "the archive used.",
    "Where vegetation is very sparse, as in northern Kanem, the greening percentages are ratios of small numbers. "
    "The rank is the safer measure there.",
    "In the downloads, row_id is the row order of the village list as received.",
    f"The list has no coordinates. {n_v} villages were found by name in the OCHA/INSEED or OpenStreetMap settlement "
    f"lists, within the right province and near their sous-préfecture town. The other {n_s} are placed at the "
    "sous-préfecture town and take the average of the area about 35 km across around it, so they share one value. "
    "GPS points from the household survey would replace both.",
    "Villages a few kilometres apart fall in the same or neighbouring grid cells, so differences between them are "
    "small by construction. Differences between sous-préfectures and provinces are the reliable signal.",
    "March–May rainfall is close to zero in these provinces every year, so the comparison uses June–September.",
    f"The list is used as given ({len(p)} rows). Some names appear under two sous-préfectures or with two spellings.",
    "ERA5 rainfall is not used: it shows a much larger 2026 deficit over Chad than CHIRPS does.",
]
ind = dict(
    rain=dict(
        map_title="June–September 2026 rainfall, % of the 1991–2020 average",
        strip_title="June–September 2026 rainfall at each village, % of the 1991–2020 average",
        axis="% of average June–September rainfall",
        zmin=40,
        zmax=160,
        strip_min=35.0,
        strip_max=float(max(105, p.rain_pct.max() + 5)),
        note="CHIRPS v3, about 5 km grid",
    ),
    ndvi=dict(
        map_title="2026 seasonal greening (NDVI), % of the 2001–2023 average",
        strip_title="2026 seasonal greening (NDVI) at each village, % of the 2001–2023 average",
        axis="% of average seasonal greening",
        zmin=0,
        zmax=200,
        strip_min=float(min(0, p.ndvi_pct.min() - 5)),
        strip_max=float(max(105, p.ndvi_pct.max() + 5)),
        note="MODIS NDVI rise from the dry season to August–September, averaged to the same 5 km grid",
    ),
)

# ---- CSVs
summary_cols = [
    "row_id",
    "adm1",
    "adm2",
    "adm3",
    "village",
    "lon",
    "lat",
    "precision",
    "match_name",
    "match_src",
    "score",
    "rain_mm",
    "rain_avg_mm",
    "rain_pct",
    "rain_z",
    "rain_rank",
    "ndvi_peak",
    "ndvi_val",
    "ndvi_avg",
    "ndvi_pct",
    "ndvi_z",
    "ndvi_rank",
    "ndvi_n",
]
summ = p[summary_cols].rename(
    columns=dict(
        adm1="province",
        adm2="department",
        adm3="sous_prefecture",
        precision="location_precision",
        match_name="matched_name",
        match_src="matched_source",
        score="match_score",
        rain_mm="rain_jjas_2026_mm",
        rain_avg_mm="rain_jjas_avg_1991_2020_mm",
        rain_pct="rain_jjas_pct_of_avg",
        rain_z="rain_jjas_zscore",
        rain_rank=f"rain_jjas_rank_driest_of_{N_RAIN}",
        ndvi_peak="ndvi_augsep_2026",
        ndvi_val="ndvi_greening_2026",
        ndvi_avg="ndvi_greening_avg_2001_2023",
        ndvi_pct="ndvi_greening_pct_of_avg",
        ndvi_z="ndvi_greening_zscore",
        ndvi_rank="ndvi_greening_rank_lowest",
        ndvi_n="ndvi_years_in_rank",
    )
)
summ[["lon", "lat"]] = summ[["lon", "lat"]].round(4)
vn_month = vn
long_rows = []
for i, r in p.iterrows():
    s = vn_month.isel(p=i).to_series()
    s26 = (
        s[s.index.year == YEAR]
        .groupby(s[s.index.year == YEAR].index.month)
        .mean()
    )
    sb = s[(s.index.year >= NDVI_BASE[0]) & (s.index.year <= NDVI_BASE[1])]
    sb = sb.groupby(sb.index.month).mean()
    for k, m in enumerate(range(3, 10)):
        long_rows.append(
            dict(
                row_id=r.row_id,
                province=r.adm1,
                sous_prefecture=r.adm3,
                village=r.village,
                year=YEAR,
                month=m,
                rain_mm=round(float(vr.isel(p=i).sel(year=YEAR, month=m)), 1),
                rain_avg_1991_2020_mm=round(
                    float(
                        vr.isel(p=i)
                        .sel(year=slice(*RAIN_BASE), month=m)
                        .mean()
                    ),
                    1,
                ),
                ndvi=round(float(s26.get(m, np.nan)), 3),
                ndvi_avg_2001_2023=round(float(sb.get(m, np.nan)), 3),
            )
        )
long = pd.DataFrame(long_rows)

vill = p[
    [
        "row_id",
        "adm1",
        "adm3",
        "adm3_label",
        "village",
        "precision",
        "lon_j",
        "lat_j",
        "jit",
        "rain_mm",
        "rain_pct",
        "rain_rank",
        "rain_rank_txt",
        "ndvi_val",
        "ndvi_pct",
        "ndvi_rank",
        "ndvi_rank_txt",
    ]
].copy()
vill[["lon_j", "lat_j", "jit"]] = vill[["lon_j", "lat_j", "jit"]].round(4)
vill["loc_txt"] = np.where(
    vill.precision == "village", "found on a map", "sous-préfecture town"
)
D = dict(
    lede=lede,
    tiles=tiles,
    notes=notes,
    ind=ind,
    provinces=prov_order,
    adm3_order=a3.adm3_label.tolist(),
    adm3_prov=dict(zip(a3.adm3_label, a3.adm1)),
    villages=json.loads(vill.to_json(orient="records")),
    grid=dict(
        lon=[round(float(v), 3) for v in chirps.lon.values],
        lat=[round(float(v), 3) for v in chirps.lat.values[::-1]],
        rain=grid_list(rain_pct_g),
        ndvi=grid_list(ndvi_pct_g),
        xr=xr_,
        yr=yr_,
    ),
    borders=borders,
    towns=json.loads(
        towns[["name", "lon", "lat", "pos"]].round(3).to_json(orient="records")
    ),
    monthly=monthly,
    month_names=MONTH_NAMES,
    monthly_rain_max=float(np.ceil(rain_max / 10) * 10 + 5),
    monthly_ndvi_range=[
        max(0, round(min(nd_all) - 0.02, 2)),
        round(max(nd_all) + 0.02, 2),
    ],
    table_cols=[
        dict(k="adm1", t="Province"),
        dict(k="adm3", t="Sous-préfecture"),
        dict(k="village", t="Village"),
        dict(k="loc_txt", t="Location"),
        dict(k="rain_mm", t="Rain Jun–Sep (mm)", n=1),
        dict(k="rain_pct", t="% of average", n=1),
        dict(k="rain_rank", t=f"Rank, driest of {N_RAIN}", n=1),
        dict(k="ndvi_val", t="NDVI greening", n=1),
        dict(k="ndvi_pct", t="% of average", n=1),
        dict(k="ndvi_rank", t="Rank, lowest", n=1),
    ],
    csv_summary=summ.to_csv(index=False),
    csv_long=long.to_csv(index=False),
)

# ---- encrypt and write
pw = os.environ["PAGE_PASSWORD"]
salt, iv = os.urandom(16), os.urandom(12)
key = PBKDF2HMAC(
    algorithm=hashes.SHA256(), length=32, salt=salt, iterations=300000
).derive(pw.encode())
ct = AESGCM(key).encrypt(iv, json.dumps(D, ensure_ascii=False).encode(), None)
out = DOCS / "evaluation_villages_2026"
out.mkdir(exist_ok=True)
(out / "data.enc").write_text(base64.b64encode(salt + iv + ct).decode() + "\n")
shutil.copy(HERE / "page_template.html", out / "index.html")
summ.to_csv(WORK / "out" / "summary.csv", index=False)
long.to_csv(WORK / "out" / "monthly.csv", index=False)
(WORK / "out" / "data.json").write_text(json.dumps(D, ensure_ascii=False))
print(pd.DataFrame(tiles).to_string())
print(
    p.groupby("adm1")[["rain_pct", "ndvi_pct", "ndvi_z", "ndvi_rank"]]
    .describe()
    .T.round(1)
    .to_string()
)
print("payload kB", len(ct) // 1024)
