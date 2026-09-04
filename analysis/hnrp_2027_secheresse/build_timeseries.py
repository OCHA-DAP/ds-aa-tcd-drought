"""Per-département, per-year pillar values (all available years) for the page explorer.

Same constructs as build_indicators.py: CH = max phase-3+ share over the analyses of
that year; ASI = mean dekadal ASI 1 Jun-21 Aug; biomasse = DMP cumsum dekads 10-23 as %
of the 1999-2024 mean; pluie = RFE 1 Jun-21 Aug as % of the long-term average.
Usage: build_timeseries.py <workdir>  (after build_indicators.py) -> indicators_by_year.csv
"""  # noqa: E501

import os
import sys
from pathlib import Path

WORK = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
os.chdir(WORK)
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

SAHARA = {"Borkou", "Ennedi Est", "Ennedi Ouest", "Tibesti"}
ind = pd.read_csv("indicators.csv", keep_default_na=False, na_values=[""])
base = ind[["ADM1_FR", "ADM2_FR", "ADM2_PCODE", "pcode_ch"]]

# CH: max phase 3+ share per exercise year
ts = pd.read_parquet("ch_adm2_ts.parquet")
ch = (
    (100 * ts.groupby(["ADM2_PCODE", "exercise_year"]).frac_phase35.max())
    .rename("ch")
    .reset_index()
)
ch = ch.rename(columns={"ADM2_PCODE": "pcode_ch", "exercise_year": "year"})

# FAO ASIS (GAUL units) -> ADM2
xw = pd.read_parquet("asi_xwalk.parquet")


def season_window(df):
    d = df.Date.dt
    return df[
        ((d.month >= 6) & (d.month <= 7)) | ((d.month == 8) & (d.day <= 21))
    ]


def to_adm2(unit_tbl, name):
    j = xw.merge(unit_tbl, left_on="adm1_code", right_index=True, how="inner")
    long = j.melt(
        id_vars=["ADM2_PCODE", "w"],
        value_vars=list(unit_tbl.columns),
        var_name="year",
        value_name="v",
    ).dropna()
    long["wv"] = long.v * long.w
    g = long.groupby(["ADM2_PCODE", "year"]).agg(
        wv=("wv", "sum"), w=("w", "sum")
    )
    return (g.wv / g.w).rename(name).reset_index()


d = pd.read_csv("asi_ASI_Dekad_Season1_data.csv")
d.columns = [c.strip() for c in d.columns]
d["Date"] = pd.to_datetime(d.Date)
asi_u = season_window(d).pivot_table(
    index="ADM1_CODE", columns="Year", values="Data", aggfunc="mean"
)
asi = to_adm2(asi_u, "asi")

r = pd.read_csv("asi_rain_adm1_data.csv")
r.columns = [c.strip() for c in r.columns]
r["Date"] = pd.to_datetime(r.Date)
rs = season_window(r).pivot_table(
    index="ADM1_CODE",
    columns="Year",
    values=["Data", "Data_long_term_Average"],
    aggfunc="sum",
)
rain_u = 100 * rs["Data"] / rs["Data_long_term_Average"]
rain = to_adm2(rain_u, "pluie")

# Biomasse
b = pd.read_parquet("bio_adm2_tcd.parquet")


def cum(y, d1=10, d2=23):
    cols = [f"DMP_{y}{k:02d}" for k in range(d1, d2 + 1)]
    return b[cols].where(b[cols] > -9000).sum(axis=1)


to23 = pd.DataFrame({y: cum(y) for y in range(1999, 2027)})
basel = to23[list(range(1999, 2025))].mean(axis=1)
bio = (100 * to23.div(basel, axis=0)).assign(ADM2_PCODE=b.adm2_pcode.values)
bio = bio.melt(id_vars="ADM2_PCODE", var_name="year", value_name="bio")

years = range(1999, 2027)
grid = base.merge(pd.DataFrame({"year": list(years)}), how="cross")
out = (
    grid.merge(ch, on=["pcode_ch", "year"], how="left")
    .merge(asi, on=["ADM2_PCODE", "year"], how="left")
    .merge(bio, on=["ADM2_PCODE", "year"], how="left")
    .merge(rain, on=["ADM2_PCODE", "year"], how="left")
)
sah = out.ADM1_FR.isin(SAHARA)
out.loc[sah, ["asi", "bio", "pluie"]] = np.nan
out = out.sort_values(["ADM1_FR", "ADM2_FR", "year"]).reset_index(drop=True)
out.to_csv("indicators_by_year.csv", index=False)

# consistency check against the official 2024-2026 consolidation
w = (
    out[out.year.between(2024, 2026)]
    .groupby("ADM2_PCODE")
    .agg(
        ch=("ch", "max"),
        asi=("asi", "max"),
        bio=("bio", "min"),
        pluie=("pluie", "min"),
    )
)
chk = ind.set_index("ADM2_PCODE")[
    [
        "ch_p3_pct_max_2024_2026",
        "asi_max_2024_2026",
        "bio_min_2024_2026",
        "pluie_min_2024_2026",
    ]
]
chk.columns = ["ch", "asi", "bio", "pluie"]
diff = (w - chk.loc[w.index]).abs().max()
print("max abs diff vs indicators.csv:", diff.round(6).to_dict())
print(out.groupby("year")[["ch", "asi", "bio", "pluie"]].count().T)
