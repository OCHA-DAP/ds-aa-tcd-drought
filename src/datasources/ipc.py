"""Cadre Harmonisé (CH) / IPC food insecurity data for Chad.

Primary source is the consolidated West & Central Africa CH/IPC file published
on HDX (https://data.humdata.org/dataset/cadre-harmonise), which covers
2014→present at the ADM2 (département) level — the finest level available for
Chad. The raw file is mirrored to blob and a Chad-only ADM2 time series is
derived and stored alongside it.

The IPC API (https://api.ipcinfo.org) carries the same recent rounds but only
back to November 2020, so it is used here purely as a cross-check on the latest
projection, not as the historical backbone. See ``crosscheck_latest_with_api``
below.

The most recent published CH analysis (as of this writing, November 2025)
projects the June–August 2026 lean season. A newer round (March 2026) has been
reported by OCHA but is not yet in the CH dataset (API or HDX); its headline
figures are captured in ``LATEST_REPORTED`` for reference/overlay.
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


# Headline figures from the most recent CH analysis reported by OCHA but not
# yet present in the machine-readable CH dataset (IPC API / HDX). Source:
# OCHA Chad digital situation reports (March 2026 Cadre Harmonisé analysis)
# https://reports.unocha.org/en/country/chad/
LATEST_REPORTED = {
    "analysis": "Cadre Harmonisé mars 2026",
    "reference_label": "Jun-Aug",
    "reference_year": 2026,
    "valid_date": pd.Timestamp("2026-07-01"),
    "phase3plus_people": 3_180_000,
    "phase3plus_pct_total_pop": 0.175,
    "total_population": 18_600_000,
    "phase3plus_people_2025_lean": 3_000_000,
    "concentration_people": 1_400_000,
    "concentration_provinces": [
        "Logone Occidental",
        "Ouaddaï",
        "Batha",
        "Guéra",
        "Lac",
        "Tandjilé",
    ],
    "source": "OCHA Tchad — rapport de situation (Cadre Harmonisé mars 2026)",
    "source_url": "https://reports.unocha.org/en/country/chad/",
    "note": (
        "Non publié dans le jeu de données CH (API IPC / HDX) au moment de "
        "l'analyse ; pourcentage rapporté sur la population totale estimée."
    ),
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
    """Compare the latest projected national phase-3+ total: HDX vs IPC API.

    Returns a dict with both totals and their absolute difference (in people).
    """
    if ts is None:
        ts = load_adm2_timeseries()
    hdx_p35 = aggregate(ts)["phase35"].iloc[-1]

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
