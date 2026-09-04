"""Build drought-risk indicators per département (COD ADM2) for the TCD HNRP 2027 sheet.

Pillars (2024-2026, worst year): Cadre Harmonisé phase-3+ share; FAO ASI (detrended);
GeoSahel biomass (detrended). Also writes the per-year table used by the page explorer.
Usage: build_indicators.py <workdir>  -> indicators.csv, indicators_by_year.csv
"""

# flake8: noqa

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

SAHARA = {"Borkou", "Ennedi Est", "Ennedi Ouest", "Tibesti"}
NEW_ADM1_AOI_PCODES = [
    "TD07",
    "TD06",
    "TD19",
    "TD01",
    "TD17",
    "TD21",
    "TD14",
]  # src/constants.py
TREND_Y0, TREND_Y1 = (
    1999,
    2024,
)  # trend-fit / baseline period (same as the AA framework's W3 construct)
WINDOW = (
    2024,
    2025,
)  # complete seasons only; 2026 is still running (dekad 23) and stays as context
WEIGHTS = {"score_ch": 0.4, "score_asi": 0.3, "score_bio": 0.3}


def key_of(name):
    k = (
        unicodedata.normalize("NFKD", str(name))
        .encode("ascii", "ignore")
        .decode()
        .lower()
    )
    k = re.sub(r"^(la|le|les)\s+", "", k.strip())
    k = re.sub(r"[^a-z0-9]+", "", k)
    return {
        "bahrsignaka": "barhsignaka",
        "baharsignaka": "barhsignaka",
        "djode": "dodje",
        "mayolemye": "mayolemie",
        "fittri": "fitri",
    }.get(k, k)


def clip(s):
    return s.clip(0, 1)


# ---------------- base: CODAB ADM2 + workbook names ----------------
cod = gpd.read_file("tcd_adm2.gpkg")
base = cod[["ADM1_FR", "ADM1_PCODE", "ADM2_FR", "ADM2_PCODE"]].copy()
base["key"] = base.ADM2_FR.map(key_of)
base["pcode_ch"] = base.ADM2_PCODE.str.replace("TD", "TCD")
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
sah = m.ADM1_FR.isin(SAHARA)

# ---------------- per-year pillar tables (wide: index ADM2_PCODE, columns years) ----------------
# CH: max phase-3+ share over the analyses of each exercise year (2014->)
ts = pd.read_parquet("ch_adm2_ts.parquet")
ch_year = (
    100 * ts.groupby(["ADM2_PCODE", "exercise_year"]).frac_phase35.max()
).unstack()
ch_year.index = ch_year.index.str.replace("TCD", "TD")

# FAO ASIS (GAUL units) -> ADM2 by area weights; seasonal mean of dekads 1 Jun - 21 Aug
xw = pd.read_parquet("asi_xwalk.parquet")


def season_window(df):
    d = df.Date.dt
    return df[
        ((d.month >= 6) & (d.month <= 7)) | ((d.month == 8) & (d.day <= 21))
    ]


def to_adm2(unit_tbl):
    j = xw.merge(unit_tbl, left_on="adm1_code", right_index=True, how="inner")
    yrs = list(unit_tbl.columns)
    out = {}
    for pc, g in j.groupby("ADM2_PCODE"):
        vals = {}
        for y in yrs:
            gg = g.dropna(subset=[y])
            vals[y] = np.average(gg[y], weights=gg.w) if len(gg) else np.nan
        out[pc] = vals
    return pd.DataFrame(out).T


d = pd.read_csv("asi_ASI_Dekad_Season1_data.csv")
d.columns = [c.strip() for c in d.columns]
d["Date"] = pd.to_datetime(d.Date)
asi_u = season_window(d).pivot_table(
    index="ADM1_CODE", columns="Year", values="Data", aggfunc="mean"
)
asi_raw = to_adm2(asi_u)

# GeoSahel biomass: cumulative DMP dekads 10-23 (1 Apr - 20 Aug) per year
b = pd.read_parquet("bio_adm2_tcd.parquet").set_index("adm2_pcode")


def cum(y, d1=10, d2=23):
    cols = [f"DMP_{y}{k:02d}" for k in range(d1, d2 + 1)]
    return b[cols].where(b[cols] > -9000).sum(axis=1)


bio_cum = pd.DataFrame({y: cum(y) for y in range(1999, 2027)})


# ---------------- detrending ----------------
def linfit(wide, y0=TREND_Y0, y1=TREND_Y1):
    """Row-wise OLS line over y0..y1; returns (slope, intercept) and fitted values for all columns."""
    yrs = [y for y in wide.columns if y0 <= y <= y1]
    X = np.array(yrs, dtype=float)
    Y = wide[yrs].to_numpy(dtype=float)
    xm = X.mean()
    slope = ((X - xm) * (Y - Y.mean(axis=1, keepdims=True))).sum(axis=1) / (
        (X - xm) ** 2
    ).sum()
    intercept = Y.mean(axis=1) - slope * xm
    allx = np.array(list(wide.columns), dtype=float)
    fit = pd.DataFrame(
        np.outer(slope, allx) + intercept[:, None],
        index=wide.index,
        columns=wide.columns,
    )
    return slope, intercept, fit


# biomass: ratio to the trend-expected value of that year (framework construct), trend floored at 10 % of the mean
bio_slope, _, bio_fit = linfit(bio_cum)
bio_mean = bio_cum[
    [y for y in bio_cum.columns if TREND_Y0 <= y <= TREND_Y1]
].mean(axis=1)
bio_fit = bio_fit.clip(lower=0.1 * bio_mean.to_numpy()[:, None])
bio_adj = 100 * bio_cum / bio_fit
bio_rawpct = 100 * bio_cum.div(bio_mean, axis=0)

# ASI: additive detrending re-centred on the 1999-2024 mean, clipped to [0, 100]
asi_slope, _, asi_fit = linfit(asi_raw)
asi_mean = asi_raw[
    [y for y in asi_raw.columns if TREND_Y0 <= y <= TREND_Y1]
].mean(axis=1)
asi_adj = (asi_raw - asi_fit.sub(asi_mean, axis=0)).clip(lower=0, upper=100)

# ---------------- long per-year table ----------------
years = list(range(1999, 2027))
long = []
for _, r in m.iterrows():
    pc = r.ADM2_PCODE
    for y in years:
        long.append(
            dict(
                ADM1_FR=r.ADM1_FR,
                ADM2_FR=r.ADM2_FR,
                ADM2_PCODE=pc,
                year=y,
                ch=(
                    ch_year.at[pc, y]
                    if (pc in ch_year.index and y in ch_year.columns)
                    else np.nan
                ),
                asi=(
                    asi_adj.at[pc, y]
                    if (pc in asi_adj.index and y in asi_adj.columns)
                    else np.nan
                ),
                asi_raw=(
                    asi_raw.at[pc, y]
                    if (pc in asi_raw.index and y in asi_raw.columns)
                    else np.nan
                ),
                bio=bio_adj.at[pc, y] if pc in bio_adj.index else np.nan,
                bio_raw=(
                    bio_rawpct.at[pc, y] if pc in bio_rawpct.index else np.nan
                ),
            )
        )
ty = pd.DataFrame(long)
ty.loc[ty.ADM1_FR.isin(SAHARA), ["asi", "asi_raw", "bio", "bio_raw"]] = np.nan
ty.to_csv("indicators_by_year.csv", index=False)

# ---------------- consolidated 2024-2025 indicators (2026 kept as context) ----------------
y0, y1 = WINDOW
w = ty[ty.year.between(y0, y1)].groupby("ADM2_PCODE")
cons = pd.DataFrame(
    {
        "ch_p3_pct_max_2024_2025": w.ch.max(),
        "asi_2024": ty[ty.year == 2024].set_index("ADM2_PCODE").asi,
        "asi_2025": ty[ty.year == 2025].set_index("ADM2_PCODE").asi,
        "asi_2026": ty[ty.year == 2026].set_index("ADM2_PCODE").asi,
        "asi_max_2024_2025": w.asi.max(),
        "asi_raw_max_2024_2025": w.asi_raw.max(),
        "bio_2024": ty[ty.year == 2024].set_index("ADM2_PCODE").bio,
        "bio_2025": ty[ty.year == 2025].set_index("ADM2_PCODE").bio,
        "bio_2026": ty[ty.year == 2026].set_index("ADM2_PCODE").bio,
        "bio_min_2024_2025": w.bio.min(),
        "bio_raw_min_2024_2025": w.bio_raw.min(),
    }
)
m = m.merge(cons, left_on="ADM2_PCODE", right_index=True, how="left")
m["asi_trend_pts_per_yr"] = m.ADM2_PCODE.map(
    pd.Series(asi_slope, index=asi_raw.index)
)
m["bio_trend_pct_per_yr"] = m.ADM2_PCODE.map(
    100 * pd.Series(bio_slope, index=bio_cum.index) / bio_mean
)
m["bio_baseline_kgha"] = m.ADM2_PCODE.map(bio_mean * 365.25 / 36)
m["asi_unit_fao"] = m.ADM2_PCODE.map(
    xw.sort_values("w", ascending=False)
    .drop_duplicates("ADM2_PCODE")
    .set_index("ADM2_PCODE")
    .adm1_name
)
m.loc[
    sah, ["asi_trend_pts_per_yr", "bio_trend_pct_per_yr", "bio_baseline_kgha"]
] = np.nan


# CH detail columns (current / projected 2026, phase, population)
def area_phase(r):
    for p in [5, 4, 3, 2]:
        if sum(r[f"frac_phase{q}"] for q in range(p, 6)) >= 0.2:
            return p
    return 1


t24 = ts[ts.exercise_year >= 2024].copy()
t24["area_phase"] = t24.apply(area_phase, axis=1)
cur26 = t24[(t24.exercise_year == 2026) & (t24.chtype == "current")].set_index(
    "ADM2_PCODE"
)
prj26 = t24[
    (t24.exercise_year == 2026) & (t24.chtype == "projected")
].set_index("ADM2_PCODE")
g = t24.groupby("ADM2_PCODE")
ch = pd.DataFrame(
    {
        "population_ch_2026": prj26.population,
        "ch_p3_pct_cur_2026": 100 * cur26.frac_phase35,
        "ch_p3_pct_proj_2026": 100 * prj26.frac_phase35,
        "ch_p3_pop_proj_2026": prj26.phase35,
        "ch_phase_max_2024_2026": g.area_phase.max(),
        "ch_n_analyses": g.size(),
    }
)
m = m.merge(ch, left_on="pcode_ch", right_index=True, how="left")

# ---------------- scores + index ----------------
m["score_ch"] = clip((m.ch_p3_pct_max_2024_2025 - 10) / 30)
m["score_asi"] = clip(m.asi_max_2024_2025 / 40)
m["score_bio"] = clip((100 - m.bio_min_2024_2025) / 50)
for c in ["score_asi", "score_bio"]:
    m.loc[sah, c] = 0.0
m["zone_saharienne"] = np.where(sah, "Oui", "Non")
sc = m[list(WEIGHTS)]
wmat = pd.DataFrame(
    {k: [v] * len(m) for k, v in WEIGHTS.items()}, index=m.index
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
m["zone_aa"] = np.where(m.ADM1_PCODE.isin(NEW_ADM1_AOI_PCODES), "Oui", "Non")
notes = []
for _, r in m.iterrows():
    n = []
    if r.ADM1_FR in SAHARA:
        n.append(
            "Zone saharienne : ASI et biomasse non applicables (scores aléa = 0)"
        )
    if pd.isna(r.ch_p3_pct_max_2024_2025):
        n.append("Non couvert par le Cadre Harmonisé (indice sans CH)")
    if r.nom_fichier != r.ADM2_FR:
        n.append(f"Orthographe fichier HNRP : {r.nom_fichier}")
    if r.pcode_fichier != r.pcode_ch:
        n.append(
            f"P-code fichier HNRP ({r.pcode_fichier}) ≠ COD ({r.pcode_ch})"
        )
    notes.append(" ; ".join(n))
m["notes"] = notes
m = m.sort_values(["ADM1_FR", "ADM2_FR"]).reset_index(drop=True)
m.to_csv("indicators.csv", index=False)
cols = [
    "ADM1_FR",
    "ADM2_FR",
    "ch_p3_pct_max_2024_2025",
    "asi_raw_max_2024_2025",
    "asi_max_2024_2025",
    "bio_raw_min_2024_2025",
    "bio_min_2024_2025",
    "score_ch",
    "score_asi",
    "score_bio",
    "indice_secheresse",
    "rang",
    "categorie",
    "zone_aa",
]
print(m[cols].round(2).sort_values("rang").to_string())
print(m.categorie.value_counts())
print("Indicateur=1:", int(m.indicateur_secheresse.sum()))
