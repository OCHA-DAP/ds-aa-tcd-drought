"""Cadre Harmonisé (CH) / IPC food insecurity data for Chad.

Primary source is the consolidated West & Central Africa CH/IPC file published
on HDX (https://data.humdata.org/dataset/cadre-harmonise), which covers
2014→present at the ADM2 (département) level — the finest level available for
Chad. The raw file is mirrored to blob and a Chad-only ADM2 time series is
derived and stored alongside it.

The IPC API (https://api.ipcinfo.org) carries the same recent rounds but only
back to November 2020, so it is used here purely as a cross-check on the latest
HDX-published projection (November 2025), not as the historical backbone. See
``crosscheck_latest_with_api`` below.

The most recent round is the **May 2026** CH analysis (current Mar–May 2026 +
projected Jun–Aug 2026 lean season). It is not yet on HDX/API, so the official
workbook shared by OCHA Chad is mirrored to
``raw/ipc/ocha/`` and folded into the processed full table + ADM2 time series
by :func:`build_ocha_ch_rows` / :func:`process_ch`. Its headline national
figures are also captured in ``LATEST_REPORTED`` for the report callout.
"""

import io
import os
from typing import Literal

import pandas as pd
import requests

from src.constants import ISO3, NEW_ADM2_AOI_PCODES
from src.utils import blob_utils

IPC_AUTH = os.getenv("IPC_AUTH")
IPC_API_BASE = "https://api.ipcinfo.org"

HDX_PACKAGE = "cadre-harmonise"
HDX_PACKAGE_URL = "https://data.humdata.org/api/3/action/package_show"

XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# representative month for each CH analysis window (mid-window), used to place
# each analysis on a continuous time axis
PERIOD_MONTH = {"Jan-May": 3, "Jun-Aug": 7, "Sep-Dec": 10}

# stable processed-blob names (raw keeps the HDX filename to preserve vintage)
PROC_FULL_BLOB = f"{blob_utils.PROJECT_PREFIX}/processed/ipc/tcd_cadre_harmonise_full.parquet"  # noqa: E501
PROC_TS_BLOB = f"{blob_utils.PROJECT_PREFIX}/processed/ipc/tcd_ch_adm2_timeseries.parquet"  # noqa: E501


def _raw_blob(filename: str) -> str:
    return f"{blob_utils.PROJECT_PREFIX}/raw/ipc/{filename}"


# Headline figures from the most recent (May 2026) CH analysis, VERIFIED
# against the official CH workbook shared by OCHA Chad (mirrored to
# ``raw/ipc/ocha/``). The projected Jun–Aug 2026 total is 3,176,885 people =
# 17.5% of the 18,171,281 analysed population; the six provinces below hold
# 1.45M (46%, "nearly half") of that burden — matching the OCHA narrative.
# These now come from real per-département data folded into the time series;
# this dict is kept for the report callout / narrative.
LATEST_REPORTED = {
    "analysis": "Cadre Harmonisé mai 2026",
    "reference_label": "Jun-Aug",
    "reference_year": 2026,
    "valid_date": pd.Timestamp("2026-07-01"),
    "phase3plus_people": 3_176_885,
    "phase3plus_pct_total_pop": 0.175,
    "total_population": 18_171_281,
    "phase3plus_people_2025_lean": 3_000_000,
    "concentration_people": 1_446_024,
    "concentration_provinces": [
        "Logone Occidental",
        "Ouaddaï",
        "Batha",
        "Guéra",
        "Lac",
        "Tandjilé",
    ],
    "source": "Analyse Cadre Harmonisé Tchad, mai 2026 (fichier officiel CH)",
    "source_url": "https://www.ipcinfo.org/ch/",
    "note": (
        "Analyse CH de mai 2026 (courante mars–mai, projetée juin–août) ; "
        "pas encore publiée sur HDX/API IPC au moment de l'analyse. Chiffres "
        "vérifiés à partir du classeur CH officiel."
    ),
}

# ------------------------------------------------------------ OCHA workbooks
# CH analyses shared directly by OCHA Chad that are not yet on HDX. Each entry
# describes one analysis so its per-département rows can be parsed into the
# same schema as the HDX consolidated file and folded into the processed data.
OCHA_CH_WORKBOOKS = [
    {
        "blob": (
            f"{blob_utils.PROJECT_PREFIX}/raw/ipc/ocha/"
            "Copie de Tchad_Analyse CH mai 2026_Pop locale_revu_CT_VF.xlsx"
        ),
        "sheet": "Tchad-mai26",
        "reference_year": 2026,
        "exercise_year": 2026,
        "exercise_label": "Jan-May",  # analysis conducted in May 2026
        "cols": {
            "adm1_name": 1,
            "adm2_name": 2,
            "adm2_pcod2": 3,
            "population": 5,
            # per-phase population blocks (0-based column indices)
            "current": {
                "phase1": 13,
                "phase2": 14,
                "phase3": 15,
                "phase4": 16,
                "phase5": 17,
                "phase35": 18,
            },
            "projected": {
                "phase1": 25,
                "phase2": 26,
                "phase3": 27,
                "phase4": 28,
                "phase5": 29,
                "phase35": 30,
            },
        },
    },
]

# CH situation → (reference_label, chtype). "current" is the Mar–May reading;
# "projected" is the Jun–Aug lean-season projection.
_OCHA_SITUATIONS = {
    "current": ("Jan-May", "current"),
    "projected": ("Jun-Aug", "projected"),
}


# --------------------------------------------------------------------- HDX
def get_latest_hdx_resource() -> dict:
    """Metadata for the most recent XLSX resource on the HDX CH dataset."""
    r = requests.get(HDX_PACKAGE_URL, params={"id": HDX_PACKAGE}, timeout=60)
    r.raise_for_status()
    xlsx = [
        x for x in r.json()["result"]["resources"] if x["format"] == "XLSX"
    ]
    if not xlsx:
        raise RuntimeError("No XLSX resource found on HDX CH dataset.")
    return max(xlsx, key=lambda d: d["last_modified"])


def download_ch_from_hdx(
    stage: Literal["prod", "dev"] = "dev", verbose: bool = True
) -> str:
    """Download the latest consolidated CH file from HDX, mirror raw to blob.

    Returns the raw blob name (which embeds the HDX filename / vintage).
    """
    res = get_latest_hdx_resource()
    content = requests.get(res["url"], timeout=300).content
    blob_name = _raw_blob(res["name"])
    blob_utils._upload_blob_data(
        content, blob_name, stage=stage, content_type=XLSX_CONTENT_TYPE
    )
    if verbose:
        print(
            f"Downloaded {res['name']} (HDX modified {res['last_modified']}) "
            f"-> {blob_name}"
        )
    return blob_name


def build_ocha_ch_rows(stage: Literal["prod", "dev"] = "dev") -> pd.DataFrame:
    """Parse OCHA-shared CH workbooks into HDX-consolidated-file schema.

    Each workbook holds one département per row with a current (Mar–May) and a
    projected (Jun–Aug) situation. Both are emitted as separate rows so they
    slot straight into the same processing as the HDX file.
    """
    frames = []
    for wb in OCHA_CH_WORKBOOKS:
        raw = blob_utils._load_blob_data(wb["blob"], stage=stage)
        d = pd.read_excel(io.BytesIO(raw), sheet_name=wb["sheet"], header=None)
        c = wb["cols"]
        code = d[c["adm2_pcod2"]].astype("string")
        d = d[code.str.match(r"^TD\d+$", na=False)].copy()
        base = {
            "adm0_pcod3": ISO3,
            "adm1_name": d[c["adm1_name"]].values,
            "adm2_name": d[c["adm2_name"]].values,
            "adm2_pcod2": d[c["adm2_pcod2"]].values,
            "population": d[c["population"]].astype(float).values,
            "reference_year": wb["reference_year"],
            "exercise_year": wb["exercise_year"],
            "exercise_label": wb["exercise_label"],
        }
        for situ, (ref_label, chtype) in _OCHA_SITUATIONS.items():
            row = dict(base)
            row["reference_label"] = ref_label
            row["chtype"] = chtype
            for ph, col in c[situ].items():
                row[ph] = d[col].astype(float).values
            frames.append(pd.DataFrame(row))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


# ----------------------------------------------------------------- process
def _add_phase_fractions(df: pd.DataFrame) -> pd.DataFrame:
    for x in [1, 2, 3, 4, 5, "35"]:
        df[f"frac_phase{x}"] = df[f"phase{x}"] / df["population"]
    return df


def build_adm2_timeseries(tcd: pd.DataFrame) -> pd.DataFrame:
    """Collapse the Chad CH rows to one best estimate per (département, period).

    The observed "current" classification is preferred over "projected"; among
    ties, the most recently issued analysis wins. Each row is dated at the
    middle of its analysis window so all rounds sit on one continuous axis.
    """
    adm2 = tcd[tcd["adm2_pcod2"].notnull()].copy()
    adm2["valid_date"] = pd.to_datetime(
        dict(
            year=adm2["reference_year"],
            month=adm2["reference_label"].map(PERIOD_MONTH),
            day=1,
        )
    )
    adm2["exercise_date"] = pd.to_datetime(
        dict(
            year=adm2["exercise_year"],
            month=adm2["exercise_label"].map(PERIOD_MONTH),
            day=1,
        )
    )
    adm2["_type_rank"] = (adm2["chtype"] == "current").astype(int)
    adm2 = (
        adm2.sort_values(["_type_rank", "exercise_date"])
        .drop_duplicates(["adm2_pcod2", "valid_date"], keep="last")
        .sort_values(["adm2_pcod2", "valid_date"])
    )
    # CH pcodes are "TD0101"; CODAB / FieldMaps use "TCD0101"
    adm2["ADM2_PCODE"] = "TCD" + adm2["adm2_pcod2"].str[2:]
    adm2["is_aoi"] = adm2["adm2_pcod2"].isin(NEW_ADM2_AOI_PCODES)

    keep = [
        "ADM2_PCODE",
        "adm2_pcod2",
        "adm1_name",
        "adm2_name",
        "is_aoi",
        "valid_date",
        "exercise_date",
        "reference_year",
        "reference_label",
        "exercise_year",
        "exercise_label",
        "chtype",
        "population",
        "phase1",
        "phase2",
        "phase3",
        "phase4",
        "phase5",
        "phase35",
        "frac_phase1",
        "frac_phase2",
        "frac_phase3",
        "frac_phase4",
        "frac_phase5",
        "frac_phase35",
    ]
    return adm2[keep].reset_index(drop=True)


def process_ch(
    raw_blob_name: str | None = None,
    stage: Literal["prod", "dev"] = "dev",
    verbose: bool = True,
) -> pd.DataFrame:
    """Read the raw CH file from blob, filter to Chad, and write processed blobs.

    Writes both the full Chad table (all admin levels / phases) and the derived
    ADM2 time series. Returns the time series.
    """
    if raw_blob_name is None:
        raw_blob_name = _raw_blob(get_latest_hdx_resource()["name"])
    raw = blob_utils._load_blob_data(raw_blob_name, stage=stage)
    df = pd.read_excel(io.BytesIO(raw))
    tcd = df[df["adm0_pcod3"] == ISO3].copy()
    # fold in OCHA-shared analyses not yet on HDX (e.g. May 2026). HDX rows are
    # kept preferentially if the same analysis later appears there.
    ocha = build_ocha_ch_rows(stage=stage)
    if not ocha.empty:
        # canonical département/province names from the HDX backbone, so OCHA
        # rows inherit consistent labels (the two sources disagree on the
        # spelling of a few provinces and on the province of geocodes TD1402 /
        # TD2102); the geometry join uses the numeric pcode, not these labels.
        nm = (
            tcd.dropna(subset=["adm2_pcod2"])
            .drop_duplicates("adm2_pcod2")
            .set_index("adm2_pcod2")
        )
        tcd = pd.concat([tcd, ocha], ignore_index=True)
        for col in ["adm1_name", "adm2_name"]:
            tcd[col] = tcd["adm2_pcod2"].map(nm[col]).fillna(tcd[col])
        key = [
            "adm2_pcod2",
            "reference_year",
            "reference_label",
            "exercise_year",
            "exercise_label",
            "chtype",
        ]
        tcd = tcd.drop_duplicates(key, keep="first")
    tcd = _add_phase_fractions(tcd)
    blob_utils.upload_parquet_to_blob(tcd, PROC_FULL_BLOB, stage=stage)
    ts = build_adm2_timeseries(tcd)
    blob_utils.upload_parquet_to_blob(ts, PROC_TS_BLOB, stage=stage)
    if verbose:
        print(
            f"Processed Chad CH: {ts['ADM2_PCODE'].nunique()} départements, "
            f"{ts['valid_date'].nunique()} periods "
            f"({ts['valid_date'].min():%b %Y} → "
            f"{ts['valid_date'].max():%b %Y})"
        )
    return ts


def refresh(stage: Literal["prod", "dev"] = "dev") -> pd.DataFrame:
    """Pull latest CH from HDX, mirror to blob, process. Returns ts."""
    raw_blob_name = download_ch_from_hdx(stage=stage)
    return process_ch(raw_blob_name, stage=stage)


# -------------------------------------------------------------------- load
def load_ch_full(stage: Literal["prod", "dev"] = "dev") -> pd.DataFrame:
    """Full Chad CH table (all phases, current + projected rows)."""
    return blob_utils.load_parquet_from_blob(PROC_FULL_BLOB, stage=stage)


def load_adm2_timeseries(
    stage: Literal["prod", "dev"] = "dev"
) -> pd.DataFrame:
    """Chad ADM2 CH time series (one estimate per département/period)."""
    return blob_utils.load_parquet_from_blob(PROC_TS_BLOB, stage=stage)


# back-compat alias for the old local-file loader
def load_tcd_hdx_ipc(stage: Literal["prod", "dev"] = "dev") -> pd.DataFrame:
    return load_ch_full(stage=stage)


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """Population-weighted phase-3+ headcount and share per analysis period."""
    g = df.groupby("valid_date").agg(
        population=("population", "sum"),
        phase35=("phase35", "sum"),
    )
    g["frac_phase35"] = g["phase35"] / g["population"]
    return g


# ----------------------------------------------------------------- IPC API
def load_ipc_api_analyses(iso2: str = "TD") -> list:
    """List of CH/IPC analyses available from the IPC API for a country."""
    r = requests.get(
        f"{IPC_API_BASE}/analyses",
        params={"format": "json", "key": IPC_AUTH, "country": iso2},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def load_ipc_api_population(iso2: str = "TD") -> list:
    """Area-level CH/IPC population data (per phase) from the IPC API."""
    r = requests.get(
        f"{IPC_API_BASE}/population",
        params={"format": "json", "key": IPC_AUTH, "country": iso2},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


def crosscheck_latest_with_api(
    ts: pd.DataFrame | None = None, iso2: str = "TD"
) -> dict:
    """Compare the latest HDX-published projection against the IPC API.

    Validates the HDX backbone, so the HDX side uses the most recent
    **long-lead** Jun–Aug projection (the November analysis, ``exercise_label``
    = "Sep-Dec") — which is what the API currently serves as its latest — not
    the newer OCHA May analysis, which is not yet on the API.

    Returns a dict with both totals and their absolute difference (in people).
    """
    full = load_ch_full()
    lean = full[
        (full["reference_label"] == "Jun-Aug")
        & (full["exercise_label"] == "Sep-Dec")
        & full["adm2_pcod2"].notnull()
    ]
    yr = lean["reference_year"].max()
    hdx_p35 = lean[lean["reference_year"] == yr]["phase35"].sum()

    pop = load_ipc_api_population(iso2)
    latest = max(pop, key=lambda a: a["id"])
    areas = [ar for g in latest["groups"] for ar in g["areas"]]
    api_p35 = sum(a["p3plus_projected"] for a in areas)
    return {
        "analysis": latest.get("title"),
        "hdx_phase3plus": float(hdx_p35),
        "api_phase3plus": float(api_p35),
        "diff_people": float(abs(hdx_p35 - api_p35)),
    }
