# flake8: noqa
"""Departement biomass by year, read from the table behind the HNRP 2027 page.

    python 04_biomass_from_hnrp.py <repo>/docs/hnrp_2027_secheresse/index.html <work_dir>/bio/bio_adm2_by_year.csv

GeoSahel dry-matter production summed over dekads 10-23 (1 April - 20 August), as % of the
1999-2024 mean and as % of the level the 1999-2024 trend gives for the year (see
analysis/hnrp_2027_secheresse/build_indicators.py). Used because the GeoSahel server
could not be reached when this was built; the HNRP table is the same data.
"""
import json
import sys

import pandas as pd

html = open(sys.argv[1], encoding="utf-8").read()
i = html.index("const D = ") + len("const D = ")
D, _ = json.JSONDecoder().raw_decode(html[i:])
rows = []
for d in D["depts"]:
    v = D["v"][d["pc"]]
    for k, y in enumerate(D["years"]):
        rows.append(
            dict(
                pcode=d["pc"],
                province=d["prov"],
                department=d["dep"],
                year=y,
                bio_pct_trend=v["bio"][k],
                bio_pct_mean=v["bio_raw"][k],
            )
        )
pd.DataFrame(rows).to_csv(sys.argv[2], index=False)
print(len(rows), "rows")
