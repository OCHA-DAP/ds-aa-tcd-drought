"""Build drought-risk indicators per département (ADM2) for the TCD HNRP 2027 sheet."""  # noqa: E501

import os
import re
import sys
import unicodedata
from pathlib import Path

WORK = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
os.chdir(WORK)
import geopandas as gpd  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 60)
pd.set_option("display.max_rows", 100)


def norm(s):
    s = (
        unicodedata.normalize("NFKD", str(s))
        .encode("ascii", "ignore")
        .decode()
        .lower()
    )
    s = re.sub(r"^(la|le|les)\s+", "", s.strip())
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


SAHARA = {"Borkou", "Ennedi Est", "Ennedi Ouest", "Tibesti"}

# --- base: CODAB ADM2 ---
cod = gpd.read_file("tcd_adm2.gpkg")
base = cod[["ADM1_FR", "ADM1_PCODE", "ADM2_FR", "ADM2_PCODE"]].copy()
base["key"] = base.ADM2_FR.map(norm)
base["pcode_ch"] = base.ADM2_PCODE.str.replace("TD", "TCD")


def key_of(name):
    k = norm(name)
    k = {
        "bahrkoh": "bahrkoh",
        "bahrsignaka": "barhsignaka",
        "baharsignaka": "barhsignaka",
        "djode": "dodje",
        "mayolemye": "mayolemie",
        "amdjarass": "amdjarass",
        "fittri": "fitri",
        "ndjamena": "ndjamena",
        "fouli": "fouli",
    }.get(k, k)
    return k


base["key"] = base.ADM2_FR.map(key_of)

# --- sheet names / pcodes (from 'Listes departements inclus') ---
sheet = pd.read_csv("sheet_adm2.csv")
recap = (
    pd.read_excel("hnrp.xlsx", "Recap", header=None).iloc[6:76, 16].tolist()
)
rk = {key_of(n): n for n in recap}
sheet["ADM2_FR"] = sheet.ADM2_FR.map(lambda n: rk.get(key_of(n), n))
sheet["key"] = sheet.ADM2_FR.map(key_of)
m = base.merge(
    sheet[["ADM2_FR", "ADM2_PCODE", "ADM1_FR", "key"]].rename(
        columns={
            "ADM2_FR": "nom_fichier",
            "ADM2_PCODE": "pcode_fichier",
            "ADM1_FR": "prov_fichier",
        }
    ),
    on="key",
    how="outer",
    indicator=True,
)
assert (m._merge == "both").all(), m[m._merge != "both"][
    ["ADM2_FR", "nom_fichier", "key"]
]
m = m.drop(columns="_merge")

# --- CH / IPC ---
ts = pd.read_parquet("ch_adm2_ts.parquet")
ts = ts[ts.exercise_year >= 2024].copy()


def area_phase(r):
    for p in [5, 4, 3, 2]:
        if sum(r[f"frac_phase{q}"] for q in range(p, 6)) >= 0.2:
            return p
    return 1


ts["area_phase"] = ts.apply(area_phase, axis=1)
cur26 = ts[(ts.exercise_year == 2026) & (ts.chtype == "current")].set_index(
    "ADM2_PCODE"
)
prj26 = ts[(ts.exercise_year == 2026) & (ts.chtype == "projected")].set_index(
    "ADM2_PCODE"
)
g = ts.groupby("ADM2_PCODE")
ch = pd.DataFrame(
    {
        "population_ch_2026": prj26.population,
        "ch_p3_pct_cur_2026": 100 * cur26.frac_phase35,
        "ch_p3_pct_proj_2026": 100 * prj26.frac_phase35,
        "ch_p3_pop_proj_2026": prj26.phase35,
        "ch_p3_pct_max_2024_2026": 100 * g.frac_phase35.max(),
        "ch_phase_max_2024_2026": g.area_phase.max(),
        "ch_n_analyses": g.size(),
    }
)
m = m.merge(ch, left_on="pcode_ch", right_index=True, how="left")

# --- FAO ASI (GAUL admin1) -> ADM2 via area weights ---
d = pd.read_csv("asi_ASI_Dekad_Season1_data.csv")
d.columns = [c.strip() for c in d.columns]
d["Date"] = pd.to_datetime(d.Date)
w = d[
    ((d.Date.dt.month >= 6) & (d.Date.dt.month <= 7))
    | ((d.Date.dt.month == 8) & (d.Date.dt.day <= 21))
]
asi_u = w.pivot_table(
    index="ADM1_CODE", columns="Year", values="Data", aggfunc="mean"
)[[2024, 2025, 2026]]
r = pd.read_csv("asi_rain_adm1_data.csv")
r.columns = [c.strip() for c in r.columns]
r["Date"] = pd.to_datetime(r.Date)
wr = r[
    ((r.Date.dt.month >= 6) & (r.Date.dt.month <= 7))
    | ((r.Date.dt.month == 8) & (r.Date.dt.day <= 21))
]
rs = wr.pivot_table(
    index="ADM1_CODE",
    columns="Year",
    values=["Data", "Data_long_term_Average"],
    aggfunc="sum",
)
rain_u = (100 * rs["Data"] / rs["Data_long_term_Average"])[[2024, 2025, 2026]]
xw = pd.read_parquet("asi_xwalk.parquet")


def weighted(unit_tbl, prefix):
    j = xw.merge(unit_tbl, left_on="adm1_code", right_index=True, how="left")
    out = {}
    for y in [2024, 2025, 2026]:
        jj = j.dropna(subset=[y])
        s = jj.groupby("ADM2_PCODE").apply(
            lambda t: np.average(t[y], weights=t.w)
        )
        out[f"{prefix}_{y}"] = s
    return pd.DataFrame(out)


asi = weighted(asi_u, "asi")
rain = weighted(rain_u, "pluie")
m = m.merge(asi, left_on="ADM2_PCODE", right_index=True, how="left").merge(
    rain, left_on="ADM2_PCODE", right_index=True, how="left"
)
m["asi_unit_fao"] = m.ADM2_PCODE.map(
    xw.sort_values("w", ascending=False)
    .drop_duplicates("ADM2_PCODE")
    .set_index("ADM2_PCODE")
    .adm1_name
)

# --- Biomasse (GeoSahel DMP, ADM2 v4) ---
b = pd.read_parquet("bio_adm2_tcd.parquet")


def cum(y, d1=10, d2=23):
    cols = [f"DMP_{y}{k:02d}" for k in range(d1, d2 + 1)]
    return b[cols].where(b[cols] > -9000).sum(axis=1)


to23 = pd.DataFrame({y: cum(y) for y in range(1999, 2027)})
basel = to23[list(range(1999, 2025))].mean(axis=1)
bio = pd.DataFrame({"ADM2_PCODE": b.adm2_pcode})
for y in [2024, 2025, 2026]:
    bio[f"bio_{y}"] = 100 * to23[y] / basel
bio["bio_baseline_kgha"] = basel * 365.25 / 36
bio["bio_rank_2026"] = to23.rank(axis=1)[2026]
m = m.merge(bio, on="ADM2_PCODE", how="left")

# --- Saharan mask: ASI / biomasse / pluie not meaningful ---
sah = m.ADM1_FR.isin(SAHARA)
for c in [
    c
    for c in m.columns
    if c.startswith(("asi_2", "pluie_", "bio_2", "bio_rank"))
]:
    m.loc[sah, c] = np.nan

# --- aggregates + scores ---
m["asi_max_2024_2026"] = m[["asi_2024", "asi_2025", "asi_2026"]].max(axis=1)
m["bio_min_2024_2026"] = m[["bio_2024", "bio_2025", "bio_2026"]].min(axis=1)
m["pluie_min_2024_2026"] = m[["pluie_2024", "pluie_2025", "pluie_2026"]].min(
    axis=1
)


def clip(s):
    return s.clip(0, 1)


m["score_ch"] = clip((m.ch_p3_pct_max_2024_2026 - 10) / 30)
m["score_asi"] = clip(m.asi_max_2024_2026 / 40)
m["score_bio"] = clip((100 - m.bio_min_2024_2026) / 50)
m["score_pluie"] = clip((100 - m.pluie_min_2024_2026) / 40)
for c in ["score_asi", "score_bio", "score_pluie"]:
    m.loc[sah, c] = 0.0
m["zone_saharienne"] = np.where(sah, "Oui", "Non")
W = {"score_ch": 0.4, "score_asi": 0.2, "score_bio": 0.2, "score_pluie": 0.2}
sc = m[list(W)]
wmat = pd.DataFrame(
    {k: [v] * len(m) for k, v in W.items()}, index=m.index
).where(sc.notna())
m["indice_secheresse"] = (sc * wmat).sum(axis=1) / wmat.sum(axis=1)
m["rang"] = m.indice_secheresse.rank(ascending=False, method="min").astype(int)


def cat(v):
    return (
        "Très élevé"
        if v >= 0.6
        else "Élevé" if v >= 0.4 else "Modéré" if v >= 0.2 else "Faible"
    )


m["categorie"] = m.indice_secheresse.map(cat)
m["indicateur_secheresse"] = (m.indice_secheresse >= 0.5).astype(int)
NEW_ADM1_AOI_PCODES = [
    "TD07",
    "TD06",
    "TD19",
    "TD01",
    "TD17",
    "TD21",
    "TD14",
]  # src/constants.py
m["zone_aa"] = np.where(m.ADM1_PCODE.isin(NEW_ADM1_AOI_PCODES), "Oui", "Non")
notes = []
for _, r_ in m.iterrows():
    n = []
    if r_.ADM1_FR in SAHARA:
        n.append(
            "Zone saharienne : ASI, biomasse et pluie non applicables (scores aléa = 0)"  # noqa: E501
        )
    if pd.isna(r_.ch_p3_pct_max_2024_2026):
        n.append("Non couvert par le Cadre Harmonisé (indice sans CH)")
    if r_.nom_fichier != r_.ADM2_FR:
        n.append(f"Orthographe fichier HNRP : {r_.nom_fichier}")
    if r_.pcode_fichier != r_.pcode_ch:
        n.append(
            f"P-code fichier HNRP ({r_.pcode_fichier}) ≠ COD ({r_.pcode_ch})"
        )
    notes.append(" ; ".join(n))
m["notes"] = notes
m = m.sort_values(["ADM1_FR", "ADM2_FR"]).reset_index(drop=True)
m.to_parquet("indicators.parquet")
m.to_csv("indicators.csv", index=False)
print(
    m[
        [
            "ADM1_FR",
            "ADM2_FR",
            "population_ch_2026",
            "ch_p3_pct_proj_2026",
            "ch_p3_pct_max_2024_2026",
            "asi_max_2024_2026",
            "bio_min_2024_2026",
            "pluie_min_2024_2026",
            "score_ch",
            "score_asi",
            "score_bio",
            "score_pluie",
            "indice_secheresse",
            "rang",
            "categorie",
            "zone_aa",
        ]
    ]
    .round(2)
    .sort_values("rang")
    .to_string()
)
print(m.categorie.value_counts())
print(m.indicateur_secheresse.sum())
