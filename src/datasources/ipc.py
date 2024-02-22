import os
from pathlib import Path

import pandas as pd
import requests
from pandas import json_normalize

IPC_AUTH = os.getenv("IPC_AUTH")
IPC_BASE_URL = "https://api.ipcinfo.org"

DATA_DIR = Path(os.environ["AA_DATA_DIR_NEW"])
IPC_RAW_DIR = DATA_DIR / "public" / "raw" / "tcd" / "ipc"
IPC_PROC_DIR = DATA_DIR / "public" / "processed" / "tcd" / "ipc"


def download_adm0_ipc_analyses(
    iso2: str = "TD", clobber: bool = False, verbose: bool = False
):
    """Downloads IPC analyses for a given country.
    Saves CSV to data directory.

    Parameters
    ----------
    iso2: str
        ISO2 code of country to download IPC analyses for.

    Returns
    -------
    None
    """
    save_path = IPC_RAW_DIR / f"{iso2}_ipc_analyses.csv"
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    if save_path.exists() and not clobber:
        if verbose:
            print(f"IPC analyses for {iso2} already downloaded.")
        return
    endpoint = "country"
    params = {"format": "json", "key": IPC_AUTH, "country": iso2}
    url = f"{IPC_BASE_URL}/{endpoint}"
    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise Exception(
            f"Error {response.status_code} when downloading IPC analyses."
        )
    df = pd.DataFrame(response.json())
    for from_to in ["from", "to"]:
        df[f"{from_to}_date"] = pd.to_datetime(df[from_to], format="%b %Y")
    df.to_csv(save_path, index=False)


def download_subnational_ipc_analyses(iso2: str = "TD"):
    save_path = IPC_RAW_DIR / f"{iso2}_subnational_ipc_analyses.csv"
    endpoint = "population"
    params = {"format": "json", "key": IPC_AUTH, "country": iso2}
    url = f"{IPC_BASE_URL}/{endpoint}"
    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise Exception(
            f"Error {response.status_code} when downloading IPC analyses."
        )
    json_data = response.json()
    # Normalize the top level
    df_top = json_normalize(json_data)

    # Rename all columns with 'top_' prefix
    df_top.columns = [
        "top_" + col if col != "groups" else col for col in df_top.columns
    ]

    # Explode the 'groups' column
    df_top = df_top.explode("groups").reset_index(drop=True)

    # Normalize the 'groups' column
    df_groups = json_normalize(df_top["groups"])

    # Rename all columns with 'group_' prefix
    df_groups.columns = [
        "group_" + col if col != "areas" else col for col in df_groups.columns
    ]

    # Merge the top level DataFrame with the groups DataFrame
    df_merged = pd.concat([df_top.drop(columns=["groups"]), df_groups], axis=1)

    # Explode the 'areas' column
    df_merged = df_merged.explode("areas").reset_index(drop=True)

    # Normalize the 'areas' column
    df_areas = json_normalize(df_merged["areas"])

    # Rename all columns with 'area_' prefix
    df_areas.columns = ["area_" + col for col in df_areas.columns]

    # Merge everything into a final DataFrame
    final_df = pd.concat([df_merged.drop(columns=["areas"]), df_areas], axis=1)

    final_df.to_csv(save_path, index=False)


def load_adm0_ipc_analyses():
    filename = "TD_ipc_analyses.csv"
    return pd.read_csv(
        IPC_RAW_DIR / filename, parse_dates=["from_date", "to_date"]
    )


def load_subnational_ipc_analyses():
    filename = "TD_subnational_ipc_analyses.csv"
    return pd.read_csv(IPC_RAW_DIR / filename)


def process_tcd_hdx_ipc():
    filename = "cadre_harmonise_caf_ipc.xlsx"
    df = pd.read_excel(IPC_RAW_DIR / filename)
    dff = df[df["adm0_pcod3"] == "TCD"]
    save_filename = "TCD_cadre_harmonise_ipc.csv"
    dff.to_csv(IPC_PROC_DIR / save_filename, index=False)


def load_tcd_hdx_ipc():
    filename = "TCD_cadre_harmonise_ipc.csv"
    return pd.read_csv(IPC_PROC_DIR / filename)


def process_tcd_hdx_ipc_for_fw(aoi_only: bool = True):
    pass
