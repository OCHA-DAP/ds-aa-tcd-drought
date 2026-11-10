# flake8: noqa
"""Place a list of villages (province, department, sous-prefecture, village; no
coordinates) on the map by name.

    python 01_locate.py <work_dir>
reads  <work_dir>/villages/*.xlsx and the gazetteers in <work_dir>/gaz/
       (OCHA/INSEED settlements and HOT OSM populated places from HDX, COD-AB
       from fieldmaps.io)
writes <work_dir>/villages/located.csv and seats.csv

A village is matched to a gazetteer name in the same province, within 45 km of
its sous-prefecture town (60 km for a near-exact name). Villages with no match
are placed at the sous-prefecture town. The village list is not public, so
inputs and outputs stay outside the repo.
"""

import glob
import re
import sys
import unicodedata
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
from rapidfuzz import fuzz

warnings.filterwarnings("ignore")
S = sys.argv[1]


def norm(s):
    s = (
        unicodedata.normalize("NFKD", str(s))
        .encode("ascii", "ignore")
        .decode()
        .lower()
    )
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def core(s):
    s = re.sub(r"\(.*?\)", "", str(s))
    s = re.sub(r"(?i)^commune de ", "", s)
    s = norm(s)
    s = re.sub(r"\s+(\d+|i+)$", "", s)
    return s.replace(" ", "")


v = pd.read_excel(f"{S}/villages/Villages list AA Evaluation Chad.xlsx")
v.columns = ["adm1", "adm2", "adm3", "village"]
v.insert(0, "row_id", range(1, len(v) + 1))
a1 = gpd.read_file(f"zip://{S}/gaz/tcd.shp.zip!tcd_adm1.shp").to_crs(4326)
print(a1[["ADM1_FR", "ADM1_PCODE"]].to_string())
A1 = {"Bahr-El-Gazel": "Barh-El-Gazel", "Batha": "Batha", "Kanem": "Kanem"}
names = a1.ADM1_FR.tolist()
A1 = {k: max(names, key=lambda n: fuzz.ratio(core(k), core(n))) for k in A1}
print(A1)
sub = a1[a1.ADM1_FR.isin(A1.values())]
o = gpd.read_file(
    glob.glob(f"{S}/gaz/ocha/**/*.shp", recursive=True)[0]
).to_crs(4326)
rows = []
for n, alt, g in zip(o.Nom, o.Alt_names, o.geometry):
    for nm in [n] + str(alt or "").split(","):
        if nm and nm.strip() and nm != "None":
            rows.append((nm.strip(), g.x, g.y, "OCHA/INSEED", ""))
m = gpd.read_parquet(f"{S}/gaz/osm.parquet")
c = m.geom.representative_point()
for cols in zip(m.name, m.name_fr, m.name_latin, m.name_en, c.x, c.y, m.place):
    seen = set()
    for nm in cols[:4]:
        for p in str(nm or "").split(";"):
            p = p.strip()
            if p and p != "None" and p not in seen:
                seen.add(p)
                rows.append((p, cols[4], cols[5], "OSM", cols[6]))
g = gpd.GeoDataFrame(
    pd.DataFrame(rows, columns=["name", "lon", "lat", "src", "place"])
)
g = g.set_geometry(gpd.points_from_xy(g.lon, g.lat), crs=4326)
g = gpd.sjoin(g, sub[["ADM1_FR", "geometry"]], predicate="within").drop(
    columns="index_right"
)
g["k"] = g.name.map(core)
g = g[g.k.str.len() >= 3].reset_index(drop=True)


def km(lon1, lat1, lon2, lat2):
    return 111.2 * np.hypot(
        (lon1 - lon2) * np.cos(np.radians(lat1)), lat1 - lat2
    )


# sous-prefecture seats
seats = {}
for p, s3 in v[["adm1", "adm3"]].drop_duplicates().itertuples(index=False):
    k = core(s3.replace(" Rural", ""))
    c = g[(g.ADM1_FR == A1[p])].copy()
    c["s"] = [fuzz.ratio(k, x) for x in c.k]
    c = c[c.s >= 88].sort_values(["s"], ascending=False)
    c["town"] = c.place.isin(["town", "city", "village"]).astype(int)
    c = c.sort_values(["s", "town"], ascending=False)
    print(
        p,
        "|",
        s3,
        "->",
        [
            (
                r.name,
                r.src,
                r.place,
                round(r.lat, 2),
                round(r.lon, 2),
                int(r.s),
            )
            for r in c.head(4).itertuples()
        ],
    )
    if not len(c):
        c = g[(g.ADM1_FR == A1[p])].copy()
        c["s"] = [fuzz.ratio(k, x) for x in c.k]
        c = c[c.s >= 85].sort_values("s", ascending=False)
        print(
            "   relaxed ->",
            [
                (r.name, r.src, round(r.lat, 2), round(r.lon, 2), int(r.s))
                for r in c.head(3).itertuples()
            ],
        )
    if len(c):
        seats[(p, s3)] = (c.lon.iloc[0], c.lat.iloc[0])
out = []
for r in v.itertuples():
    k = core(r.village)
    seat = seats.get((r.adm1, r.adm3))
    c = g[g.ADM1_FR == A1[r.adm1]].copy()
    # a place named in brackets ("hamlet (parent village)") is the anchor when it can be found
    br = [
        core(x)
        for b in re.findall(r"\((.*?)\)", str(r.village))
        for x in b.split("-")
        if core(x) not in ("canton", "")
    ]
    c["s"] = [max([fuzz.ratio(b, x) for b in br] + [0]) for x in c.k]
    if not (c.s >= 85).any():
        c["s"] = [fuzz.ratio(k, x) for x in c.k]
    c = c[c.s >= 85]
    if seat is not None and len(c):
        c["d"] = km(c.lon, c.lat, seat[0], seat[1])
        c = c[(c.d <= 45) | ((c.s >= 90) & (c.d <= 60))]
    else:
        c["d"] = np.nan
    c = c.sort_values(["s", "d"], ascending=[False, True])
    if len(c):
        b = c.iloc[0]
        n_alt = (
            (c.s >= b.s - 3) & (km(c.lon, c.lat, b.lon, b.lat) > 10)
        ).sum()
        out.append(
            dict(
                row_id=r.row_id,
                lon=b.lon,
                lat=b.lat,
                match_name=b["name"],
                match_src=b.src,
                score=b.s,
                km_from_seat=b.d,
                ambiguous=int(n_alt),
                precision="village",
            )
        )
    elif seat is not None:
        out.append(
            dict(
                row_id=r.row_id,
                lon=seat[0],
                lat=seat[1],
                match_name="",
                match_src="",
                score=np.nan,
                km_from_seat=0,
                ambiguous=0,
                precision="sous-prefecture seat",
            )
        )
    else:
        out.append(dict(row_id=r.row_id, precision="none"))
res = v.merge(pd.DataFrame(out), on="row_id")
pd.set_option("display.width", 250)
print(
    res[res.precision == "village"].drop(columns=["adm2"]).round(2).to_string()
)
print(res.precision.value_counts())
res.to_csv(f"{S}/villages/located.csv", index=False)
pd.DataFrame(
    [dict(adm1=k[0], adm3=k[1], lon=x, lat=y) for k, (x, y) in seats.items()]
).to_csv(f"{S}/villages/seats.csv", index=False)
