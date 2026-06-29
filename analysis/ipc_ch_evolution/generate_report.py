"""Generate the Chad CH/IPC evolution report (figures + self-contained HTML).

Pulls the processed ADM2 time series and boundaries from blob via the project
data layer, builds the figures, overlays the latest OCHA-reported (March 2026)
national figure on the historical record, and writes a GitHub-Pages-ready page
to ``docs/ipc_ch_evolution/index.html``.

Run from the repo root:  python analysis/ipc_ch_evolution/generate_report.py
Refresh the data first with:
    python -c "from src.datasources import ipc; ipc.refresh()"
"""

import base64
import os

import matplotlib as mpl
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from src.constants import NEW_ADM2_AOI_PCODES
from src.datasources import codab, ipc

REPO = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
DOCS = os.path.join(REPO, "docs", "ipc_ch_evolution")
FIG = os.path.join(DOCS, "figs")
os.makedirs(FIG, exist_ok=True)

mpl.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": "#e8e8e8",
        "grid.linewidth": 0.8,
        "axes.edgecolor": "#888888",
        "figure.dpi": 130,
    }
)

IPC_PHASE = {
    1: "#d3edb2",
    2: "#fae61e",
    3: "#e67800",
    4: "#c80000",
    5: "#640000",
}
PHASE_NAME = {
    1: "Phase 1 — Minimale",
    2: "Phase 2 — Sous pression",
    3: "Phase 3 — Crise",
    4: "Phase 4 — Urgence",
    5: "Phase 5 — Famine",
}
P3CMAP = LinearSegmentedColormap.from_list(
    "p3", ["#ffffff", "#ffe9b8", "#fdae61", "#e67800", "#c80000", "#7a0000"]
)
RED, GREY, ACCENT = "#c80000", "#5d6677", "#e67800"


def _save(fig, name):
    fig.savefig(f"{FIG}/{name}.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _norm_pcode(s):
    # strip the country prefix so "TD0101" and "TCD0101" both map to "0101";
    # makes the geometry join robust to the CODAB vintage on blob
    return s.str.replace(r"^\D+", "", regex=True)


# CH analysis cycle → projection lead time for the Jun–Aug lean season
_LEAN_LEAD = {"Sep-Dec": "long", "Jan-May": "short", "Jun-Aug": "inseason"}
_LEAD_LABEL = {
    "long": "Projection long terme (analyse nov., ~8 mois avant)",
    "short": "Projection court terme (analyse mars, ~4 mois avant)",
}


def lean_estimates_by_lead(full, aoi_only=False, min_areas=50):
    """National (or AOI) lean-season phase-3+ share per (year, projection lead).

    Each Jun–Aug lean season is projected by two analyses — the prior November
    cycle (long lead) and the March cycle (short lead). Returns one row per
    (reference_year, lead) so the forecast revision is visible.
    Partial-coverage analyses (< ``min_areas``) are dropped to keep national
    totals comparable.
    """
    adm2 = full[full["adm2_pcod2"].notnull()].copy()
    lean = adm2[adm2["reference_label"] == "Jun-Aug"].copy()
    if aoi_only:
        lean = lean[lean["adm2_pcod2"].isin(NEW_ADM2_AOI_PCODES)]
    lean["lead"] = lean["exercise_label"].map(_LEAN_LEAD)
    cov = lean.groupby(["reference_year", "lead"])["adm2_pcod2"].transform(
        "nunique"
    )
    lean = lean[cov >= min_areas]
    g = lean.groupby(["reference_year", "lead"]).agg(
        population=("population", "sum"), phase35=("phase35", "sum")
    )
    g["frac_phase35"] = g["phase35"] / g["population"]
    return g.reset_index()


def make_figures(ts, adm2_geo, adm1_geo):
    ts = ts.copy()
    adm2_geo = adm2_geo.copy()
    ts["adm2_key"] = _norm_pcode(ts["ADM2_PCODE"])
    adm2_geo["adm2_key"] = _norm_pcode(adm2_geo["ADM2_PCODE"])
    aoi_pcode = set(ts[ts["is_aoi"]]["ADM2_PCODE"])  # heatmap row labels
    aoi_key = set(ts[ts["is_aoi"]]["adm2_key"])  # geometry boundaries
    rep = ipc.LATEST_REPORTED
    # CH publishes, twice a year, a lean-season (Jun–Aug) PROJECTION — the
    # annual peak and the standard headline metric — and a post-harvest
    # (Sep–Dec) "current" reading — the annual trough. Plotting one season per
    # line avoids the seasonal sawtooth that comes from mixing them.
    lean = ts[ts["reference_label"] == "Jun-Aug"]
    ph = ts[ts["reference_label"] == "Sep-Dec"]
    natl_lean = ipc.aggregate(lean)
    aoi_lean = ipc.aggregate(lean[lean["is_aoi"]])
    natl_ph = ipc.aggregate(ph)
    xmax = pd.Timestamp("2026-12-31")

    # --- 1. national vs AOI at the lean-season peak, with March-2026 star --
    fig, ax = plt.subplots(figsize=(11, 4.6))
    ax.plot(
        natl_lean.index,
        natl_lean["frac_phase35"],
        color=GREY,
        lw=2.2,
        marker="o",
        ms=5,
        label="Pays entier (70 départements)",
    )
    ax.plot(
        aoi_lean.index,
        aoi_lean["frac_phase35"],
        color=RED,
        lw=2.4,
        marker="o",
        ms=5,
        label="Zone du cadre d'AA (22 départements)",
    )
    ax.fill_between(
        aoi_lean.index,
        natl_lean["frac_phase35"].reindex(aoi_lean.index),
        aoi_lean["frac_phase35"],
        color=RED,
        alpha=0.08,
        interpolate=True,
    )
    rep_frac = rep["phase3plus_pct_total_pop"]
    ax.plot(
        rep["valid_date"],
        rep_frac,
        marker="*",
        ms=20,
        color="#111",
        mfc="#ffd24d",
        mec="#111",
        zorder=6,
        label=f"{rep['analysis']} (OCHA) · "
        f"{rep['phase3plus_people']/1e6:.2f} M",
    )
    ax.annotate(
        f"{rep['phase3plus_people']/1e6:.2f} M\n({rep_frac*100:.1f} %)",
        xy=(rep["valid_date"], rep_frac),
        xytext=(-2, 16),
        textcoords="offset points",
        ha="right",
        fontsize=8.5,
        fontweight="bold",
        color="#7a0000",
    )
    ax.set_ylim(0, None)
    ax.set_xlim(natl_lean.index.min(), xmax)
    ax.yaxis.set_major_formatter(mpl.ticker.PercentFormatter(1.0))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_ylabel("Part en phase 3+ — soudure (juin–août)")
    ax.set_title(
        "Phase CH 3+ à la soudure — zone du cadre d'AA vs pays "
        "entier, 2015–2026",
        fontweight="bold",
        loc="left",
    )
    ax.legend(loc="upper left", framealpha=0.9, fontsize=8.5)
    _save(fig, "natl_vs_aoi")

    # --- 1b. seasonal contrast: lean-season peak vs post-harvest trough ----
    fig, ax = plt.subplots(figsize=(11, 4.0))
    ax.plot(
        natl_lean.index,
        natl_lean["frac_phase35"],
        color="#b35f00",
        lw=2.4,
        marker="o",
        ms=5,
        label="Soudure juin–août (pic projeté)",
    )
    ax.plot(
        natl_ph.index,
        natl_ph["frac_phase35"],
        color="#6b8e23",
        lw=2.0,
        marker="o",
        ms=4,
        ls="--",
        label="Post-récolte sep–déc (creux observé)",
    )
    ax.fill_between(
        natl_lean.index,
        natl_ph["frac_phase35"].reindex(natl_lean.index),
        natl_lean["frac_phase35"],
        color="#b35f00",
        alpha=0.07,
        interpolate=True,
    )
    ax.set_ylim(0, None)
    ax.set_xlim(min(natl_lean.index.min(), natl_ph.index.min()), xmax)
    ax.yaxis.set_major_formatter(mpl.ticker.PercentFormatter(1.0))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_ylabel("Part de population en phase 3+")
    ax.set_title(
        "Amplitude saisonnière nationale — soudure vs post-récolte",
        fontweight="bold",
        loc="left",
    )
    ax.legend(loc="upper left", framealpha=0.9, fontsize=9)
    _save(fig, "seasonal")

    # --- 1c. lean-season projection revision (long vs short lead) ----------
    # A single lean season is projected twice — by the prior November analysis
    # (~8 mo ahead) and the March analysis (~4 mo ahead). There is no in-season
    # "observation": the soudure is always forecast, never measured after.
    le = lean_estimates_by_lead(ipc.load_ch_full())
    piv = le.pivot(
        index="reference_year", columns="lead", values="frac_phase35"
    )
    yrs = piv.index
    fig, ax = plt.subplots(figsize=(11, 4.4))
    for y in yrs:  # vertical connector = how much the outlook was revised
        if {"long", "short"} <= set(piv.columns) and not piv.loc[
            y, ["long", "short"]
        ].isna().any():
            ax.plot(
                [y, y],
                [piv.loc[y, "long"], piv.loc[y, "short"]],
                color="#ccced6",
                lw=1.2,
                zorder=1,
            )
    ax.plot(
        yrs,
        piv.get("long"),
        "o-",
        color=GREY,
        lw=2.0,
        ms=6,
        label=_LEAD_LABEL["long"],
        zorder=3,
    )
    ax.plot(
        yrs,
        piv.get("short"),
        "o-",
        color="#b35f00",
        lw=2.2,
        ms=6,
        label=_LEAD_LABEL["short"],
        zorder=4,
    )
    ax.plot(
        rep["reference_year"],
        rep["phase3plus_pct_total_pop"],
        marker="*",
        ms=20,
        color="#111",
        mfc="#ffd24d",
        mec="#111",
        zorder=6,
        label=f"{rep['analysis']} court terme (OCHA) · "
        f"{rep['phase3plus_people']/1e6:.2f} M",
    )
    ax.set_ylim(0, None)
    ax.yaxis.set_major_formatter(mpl.ticker.PercentFormatter(1.0))
    ax.xaxis.set_major_locator(mpl.ticker.MultipleLocator(1))
    ax.set_xlabel("Saison de soudure (juin–août)")
    ax.set_ylabel("Part nationale en phase 3+")
    ax.set_title(
        "Révision de la projection de soudure — chaque saison est "
        "projetée deux fois",
        fontweight="bold",
        loc="left",
    )
    ax.legend(loc="upper left", framealpha=0.9, fontsize=8.5)
    _save(fig, "lean_revision")

    # --- 2. national phase composition at the lean-season peak ------------
    nat = lean.groupby("valid_date")[
        ["population", "phase1", "phase2", "phase3", "phase4", "phase5"]
    ].sum()
    for x in [1, 2, 3, 4, 5]:
        nat[f"f{x}"] = nat[f"phase{x}"] / nat["population"]
    fig, ax = plt.subplots(figsize=(11, 4.6))
    bottom = np.zeros(len(nat))
    for p in [1, 2, 3, 4, 5]:
        ax.fill_between(
            nat.index,
            bottom,
            bottom + nat[f"f{p}"],
            color=IPC_PHASE[p],
            label=PHASE_NAME[p],
            step="mid",
            linewidth=0,
        )
        bottom = bottom + nat[f"f{p}"].values
    ax.plot(
        nat.index,
        1 - nat["f1"] - nat["f2"],
        color="#3a3a3a",
        lw=2.2,
        marker="o",
        ms=4,
        label="Phase 3+ (frontière)",
    )
    ax.set_ylim(0, 1)
    ax.set_xlim(nat.index.min(), nat.index.max())
    ax.yaxis.set_major_formatter(mpl.ticker.PercentFormatter(1.0))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_ylabel("Part de la population")
    ax.set_title(
        "Chad — composition CH/IPC à la soudure (juin–août), " "2015–2026",
        fontweight="bold",
        loc="left",
    )
    ax.legend(ncol=3, fontsize=8, loc="upper left", framealpha=0.9)
    _save(fig, "national")

    # --- 3. heatmap département x period ----------------------------------
    piv = ts.pivot_table(
        index="ADM2_PCODE", columns="valid_date", values="frac_phase35"
    )
    names = ts.drop_duplicates("ADM2_PCODE").set_index("ADM2_PCODE")[
        ["adm1_name", "adm2_name"]
    ]
    piv["_mean"] = piv.mean(axis=1)
    piv["_aoi"] = [pc in aoi_pcode for pc in piv.index]
    piv = piv.sort_values(["_aoi", "_mean"], ascending=[False, False])
    order = piv.index
    mat = piv.drop(columns=["_mean", "_aoi"])
    fig, ax = plt.subplots(figsize=(13, 14))
    im = ax.imshow(mat.values, aspect="auto", cmap=P3CMAP, vmin=0, vmax=0.5)
    ax.set_xticks(range(len(mat.columns)))
    ax.set_xticklabels(
        [d.strftime("%b %Y") for d in mat.columns], rotation=90, fontsize=6.5
    )
    ax.set_yticks(range(len(mat)))
    ax.set_yticklabels(
        [
            f"{'★ ' if pc in aoi_pcode else '   '}{names.loc[pc, 'adm2_name']}"
            f"  ({names.loc[pc, 'adm1_name']})"
            for pc in order
        ],
        fontsize=6.5,
    )
    for tick, pc in zip(ax.get_yticklabels(), order):
        if pc in aoi_pcode:
            tick.set_fontweight("bold")
            tick.set_color("#7a0000")
    ax.set_title(
        "Évolution de la part de population en phase CH 3+ par "
        "département (★ = zone du cadre d'AA)",
        fontweight="bold",
        loc="left",
        fontsize=11,
    )
    cb = fig.colorbar(im, ax=ax, shrink=0.4, pad=0.01)
    cb.set_label("Part en phase 3+")
    cb.ax.yaxis.set_major_formatter(mpl.ticker.PercentFormatter(1.0))
    ax.set_xticks(np.arange(-0.5, len(mat.columns), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(mat), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=0.5)
    ax.tick_params(which="minor", length=0)
    _save(fig, "heatmap")

    # --- 4. AOI lines by province (lean-season peak) ----------------------
    aoi_ts = lean[lean["is_aoi"]]
    provs = sorted(aoi_ts["adm1_name"].unique())
    fig, axs = plt.subplots(2, 4, figsize=(17, 7.5), sharey=True, sharex=True)
    axs = axs.flatten()
    for i, prov in enumerate(provs):
        a = axs[i]
        for dep, g in aoi_ts[aoi_ts["adm1_name"] == prov].groupby("adm2_name"):
            g = g.sort_values("valid_date")
            a.plot(
                g["valid_date"],
                g["frac_phase35"],
                marker="o",
                ms=3,
                lw=1.4,
                label=dep,
            )
        a.set_title(prov, fontweight="bold", fontsize=10)
        a.yaxis.set_major_formatter(mpl.ticker.PercentFormatter(1.0))
        a.xaxis.set_major_locator(mdates.YearLocator(2))
        a.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        a.legend(fontsize=6.5, loc="upper left")
    # explicit shared y-limit with headroom so peak departments aren't clipped
    axs[0].set_ylim(0, aoi_ts["frac_phase35"].max() * 1.08)
    for j in range(len(provs), len(axs)):
        axs[j].axis("off")
    fig.suptitle(
        "Zone du cadre d'AA — phase CH 3+ à la soudure (juin–août) "
        "par département",
        fontweight="bold",
        fontsize=13,
    )
    fig.supylabel("Part en phase 3+")
    fig.tight_layout()
    _save(fig, "aoi_lines")

    # --- 5. soudure maps ---------------------------------------------------
    lean = ts[ts["reference_label"] == "Jun-Aug"]
    years = sorted(lean["reference_year"].unique())[-8:]
    fig, axs = plt.subplots(2, 4, figsize=(17, 8.5))
    axs = axs.flatten()
    for i, yr in enumerate(years):
        a = axs[i]
        g = lean[lean["reference_year"] == yr]
        m = adm2_geo.merge(
            g[["adm2_key", "frac_phase35"]], on="adm2_key", how="left"
        )
        m.plot(
            column="frac_phase35",
            cmap=P3CMAP,
            vmin=0,
            vmax=0.5,
            ax=a,
            edgecolor="#bbbbbb",
            linewidth=0.2,
            missing_kwds={
                "color": "#f2f2f2",
                "edgecolor": "#cccccc",
                "linewidth": 0.2,
            },
        )
        adm2_geo[adm2_geo["adm2_key"].isin(aoi_key)].boundary.plot(
            ax=a, color="#1f1f1f", linewidth=0.7
        )
        a.set_title(f"Soudure juin–août {yr}", fontsize=10, fontweight="bold")
        a.axis("off")
    for j in range(len(years), len(axs)):
        axs[j].axis("off")
    sm = plt.cm.ScalarMappable(cmap=P3CMAP, norm=plt.Normalize(0, 0.5))
    cb = fig.colorbar(sm, ax=axs, shrink=0.5, pad=0.01)
    cb.set_label("Part en phase 3+")
    cb.ax.yaxis.set_major_formatter(mpl.ticker.PercentFormatter(1.0))
    fig.suptitle(
        "Projection CH soudure (juin–août) par département — contour "
        "= zone d'AA",
        fontweight="bold",
        fontsize=13,
    )
    _save(fig, "maps")

    # --- 6. latest map -----------------------------------------------------
    latest_date = ts["valid_date"].max()
    g = ts[ts["valid_date"] == latest_date]
    lab = g.iloc[0]
    fig, ax = plt.subplots(figsize=(9, 8))
    m = adm2_geo.merge(
        g[["adm2_key", "frac_phase35"]], on="adm2_key", how="left"
    )
    m.plot(
        column="frac_phase35",
        cmap=P3CMAP,
        vmin=0,
        vmax=0.5,
        ax=ax,
        edgecolor="#cccccc",
        linewidth=0.3,
        legend=True,
        legend_kwds={"shrink": 0.5, "label": "Part en phase 3+"},
        missing_kwds={"color": "#f2f2f2"},
    )
    fig.axes[-1].yaxis.set_major_formatter(mpl.ticker.PercentFormatter(1.0))
    adm2_geo[adm2_geo["adm2_key"].isin(aoi_key)].boundary.plot(
        ax=ax, color="#1f1f1f", linewidth=0.9
    )
    adm1_geo.boundary.plot(ax=ax, color="#999999", linewidth=0.4)
    ax.set_title(
        f"Projection CH la plus récente — {lab['reference_label']} "
        f"{lab['reference_year']:.0f} (analyse {lab['exercise_label']}"
        f" {lab['exercise_year']:.0f})\ncontour noir = zone d'AA",
        fontweight="bold",
        fontsize=11,
        loc="left",
    )
    ax.axis("off")
    _save(fig, "latest_map")


def compute_summary(ts):
    natl, aoi = ipc.aggregate(ts), ipc.aggregate(ts[ts["is_aoi"]])
    latest = ts["valid_date"].max()
    lat = ts[ts["valid_date"] == latest].iloc[0]
    return {
        "n_departments": ts["ADM2_PCODE"].nunique(),
        "n_aoi": ts[ts["is_aoi"]]["ADM2_PCODE"].nunique(),
        "n_periods": ts["valid_date"].nunique(),
        "first_period": ts["valid_date"].min(),
        "latest_period": latest,
        "latest_label": (
            f"{lat['reference_label']} {lat['reference_year']:.0f}"
        ),
        "cty_p35_people": natl["phase35"].iloc[-1],
        "cty_p35_frac": natl["frac_phase35"].iloc[-1],
        "cty_pop": natl["population"].iloc[-1],
        "cty_peak_frac": natl["frac_phase35"].max(),
        "cty_peak_date": natl["frac_phase35"].idxmax(),
        "aoi_p35_people": aoi["phase35"].iloc[-1],
        "aoi_p35_frac": aoi["frac_phase35"].iloc[-1],
        "aoi_pop": aoi["population"].iloc[-1],
        "aoi_peak_frac": aoi["frac_phase35"].max(),
        "aoi_peak_date": aoi["frac_phase35"].idxmax(),
        "aoi_share_of_national": aoi["phase35"].iloc[-1]
        / natl["phase35"].iloc[-1],
        "crosscheck": ipc.crosscheck_latest_with_api(ts),
    }


def _b64(name):
    with open(f"{FIG}/{name}.png", "rb") as f:
        return base64.b64encode(f.read()).decode()


def _img(name, alt):
    return (
        f'<img src="data:image/png;base64,{_b64(name)}" alt="{alt}" '
        f'loading="lazy">'
    )


def build_html(ts, s):
    rep = ipc.LATEST_REPORTED
    latest = pd.Timestamp(s["latest_period"]).strftime("%b %Y")
    first = pd.Timestamp(s["first_period"]).strftime("%b %Y")
    cty_peak = pd.Timestamp(s["cty_peak_date"]).strftime("%b %Y")
    aoi_peak = pd.Timestamp(s["aoi_peak_date"]).strftime("%b %Y")
    cc = s["crosscheck"]

    lean = ts[ts["reference_label"] == "Jun-Aug"]
    yr = lean["reference_year"].max()
    ll = lean[lean["reference_year"] == yr]

    def table(df):
        rows = "".join(
            f"<tr><td>{r.adm2_name}{' ★' if r.is_aoi else ''}</td>"
            f"<td>{r.adm1_name}</td>"
            f"<td class='num'>{r.frac_phase35*100:.0f}%</td>"
            f"<td class='num'>{r.phase35:,.0f}</td></tr>"
            for r in df.itertuples()
        )
        return (
            "<table><thead><tr><th>Département</th><th>Province</th>"
            "<th class='num'>Part 3+</th><th class='num'>Pers. 3+</th>"
            f"</tr></thead><tbody>{rows}</tbody></table>"
        )

    aoi_tbl = table(
        ll[ll["is_aoi"]].sort_values("frac_phase35", ascending=False).head(10)
    )
    cty_tbl = table(ll.sort_values("frac_phase35", ascending=False).head(12))
    provs = ", ".join(rep["concentration_provinces"])

    html = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tchad — évolution CH/IPC par département</title>
<style>
:root {{ --ink:#1d2330; --muted:#5d6677; --line:#e6e8ee; --bg:#f7f8fa;
  --accent:#e67800; --accent-dk:#b35f00; --red:#c80000; --card:#fff; }}
*{{box-sizing:border-box;}}
body{{margin:0;background:var(--bg);color:var(--ink);line-height:1.55;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,
  Arial,sans-serif;}}
.wrap{{max-width:1080px;margin:0 auto;padding:0 22px 80px;}}
header{{background:linear-gradient(135deg,#7a0000,#e67800);color:#fff;
  padding:46px 0 38px;margin-bottom:34px;}}
header .wrap{{padding-bottom:0;}}
header .kicker{{text-transform:uppercase;letter-spacing:.14em;font-size:.72rem;
  opacity:.85;font-weight:600;}}
header h1{{margin:.25em 0 .15em;font-size:2.05rem;line-height:1.12;}}
header p{{margin:.2em 0 0;max-width:62ch;opacity:.95;}}
.vintage{{margin-top:16px;font-size:.8rem;opacity:.9;}}
.groups{{display:grid;grid-template-columns:1fr 1fr;gap:18px;
  margin:-58px 0 28px;}}
.grp{{background:var(--card);border:1px solid var(--line);border-radius:14px;
  padding:16px 18px 18px;box-shadow:0 1px 3px rgba(20,30,50,.05);}}
.grp.aoi{{border-top:4px solid var(--red);}}
.grp.cty{{border-top:4px solid var(--muted);}}
.grp h3{{margin:0 0 2px;font-size:.95rem;}}
.grp .scope{{color:var(--muted);font-size:.76rem;margin-bottom:12px;}}
.kpis{{display:grid;grid-template-columns:1fr 1fr;gap:12px;}}
.kpi .v{{font-size:1.55rem;font-weight:700;line-height:1;}}
.grp.aoi .kpi .v{{color:var(--red);}}
.grp.cty .kpi .v{{color:var(--accent-dk);}}
.kpi .l{{font-size:.72rem;color:var(--muted);margin-top:5px;}}
section{{margin:0 0 42px;}}
h2{{font-size:1.32rem;margin:0 0 .25em;border-left:4px solid var(--accent);
  padding-left:12px;}}
h2+.sub{{color:var(--muted);margin:0 0 18px;padding-left:16px;font-size:.92rem;
  max-width:78ch;}}
figure{{margin:0;background:var(--card);border:1px solid var(--line);
  border-radius:12px;padding:14px;overflow-x:auto;}}
figure img{{width:100%;height:auto;display:block;min-width:520px;}}
figure figcaption{{color:var(--muted);font-size:.82rem;margin-top:10px;
  padding:0 4px;}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:20px;}}
.cols h3{{font-size:1rem;margin:0 0 10px;}}
table{{border-collapse:collapse;width:100%;background:var(--card);
  border:1px solid var(--line);border-radius:12px;overflow:hidden;
  font-size:.88rem;}}
th,td{{text-align:left;padding:8px 13px;border-bottom:1px solid var(--line);}}
th{{background:#fbf3ea;color:var(--accent-dk);font-weight:600;font-size:.76rem;
  text-transform:uppercase;letter-spacing:.03em;}}
td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums;}}
tr:last-child td{{border-bottom:none;}}
.callout{{background:#fdeaea;border:1px solid #f0c4c4;border-radius:12px;
  padding:14px 18px;font-size:.86rem;color:#5a2a2a;margin-bottom:18px;}}
.callout b{{color:var(--red);}}
.note{{background:#fff8f0;border:1px solid #f1ddc4;border-radius:12px;
  padding:18px 20px;font-size:.88rem;color:#4a4031;}}
.note h3{{margin:0 0 .4em;font-size:1rem;color:var(--accent-dk);}}
.note code{{background:#f0e7da;padding:1px 6px;border-radius:5px;
  font-size:.85em;}}
.note ul{{margin:.4em 0;padding-left:1.2em;}}
footer{{color:var(--muted);font-size:.8rem;text-align:center;
  border-top:1px solid var(--line);padding-top:22px;}}
a{{color:var(--accent-dk);}}
@media (max-width:720px){{.groups,.cols{{grid-template-columns:1fr;
  margin-top:-40px;}} header h1{{font-size:1.6rem;}}}}
</style></head><body>
<header><div class="wrap">
  <div class="kicker">Tchad · Action anticipatoire sécheresse</div>
  <h1>Évolution de l'insécurité alimentaire CH/IPC<br>
  par département, 2014–2026</h1>
  <p>Part de la population en phase 3+ du Cadre Harmonisé, au niveau
  administratif le plus fin disponible (ADM2 / département) — pour le pays
  entier et la zone du cadre d'AA, avec la projection la plus récente
  rapportée.</p>
  <div class="vintage">Source : Cadre Harmonisé (CILSS/HDX), dernière analyse
  publiée <b>novembre 2025</b> · {s['n_departments']} départements ·
  {s['n_periods']} périodes ({first} → {latest})</div>
</div></header>
<div class="wrap">
<div class="groups">
  <div class="grp aoi"><h3>Zone du cadre d'AA</h3>
    <div class="scope">{s['n_aoi']} départements ·
      projection soudure {latest}</div>
    <div class="kpis">
      <div class="kpi"><div class="v">{s['aoi_p35_people']/1e6:.2f} M</div>
        <div class="l">personnes en phase 3+</div></div>
      <div class="kpi"><div class="v">{s['aoi_p35_frac']*100:.1f}%</div>
        <div class="l">de la population de la zone</div></div>
      <div class="kpi">
        <div class="v">{s['aoi_share_of_national']*100:.0f}%</div>
        <div class="l">du fardeau national phase 3+</div></div>
      <div class="kpi"><div class="v">{s['aoi_peak_frac']*100:.0f}%</div>
        <div class="l">pic de la série ({aoi_peak})</div></div>
    </div></div>
  <div class="grp cty"><h3>Pays entier</h3>
    <div class="scope">{s['n_departments']} départements ·
      projection soudure {latest}</div>
    <div class="kpis">
      <div class="kpi"><div class="v">{s['cty_p35_people']/1e6:.2f} M</div>
        <div class="l">personnes en phase 3+</div></div>
      <div class="kpi"><div class="v">{s['cty_p35_frac']*100:.1f}%</div>
        <div class="l">de la population analysée</div></div>
      <div class="kpi"><div class="v">{s['cty_pop']/1e6:.1f} M</div>
        <div class="l">population analysée</div></div>
      <div class="kpi"><div class="v">{s['cty_peak_frac']*100:.0f}%</div>
        <div class="l">pic de la série ({cty_peak})</div></div>
    </div></div>
</div>
<div class="callout">
  <b>Projection la plus récente ({rep['analysis']}) :</b>
  {rep['phase3plus_people']/1e6:.2f} M de personnes
  ({rep['phase3plus_pct_total_pop']*100:.1f} % d'une population estimée à
  {rep['total_population']/1e6:.1f} M) en phase 3+ pour la soudure juin–août
  2026, contre ~{rep['phase3plus_people_2025_lean']/1e6:.0f} M lors de la
  soudure 2025. Près de la moitié ({rep['concentration_people']/1e6:.1f} M) se
  concentre dans six provinces : {provs}. Cette analyse n'est pas encore
  publiée dans le jeu de données CH ; la dernière analyse disponible (nov.
  2025) projetait {s['cty_p35_people']/1e6:.2f} M / {s['cty_p35_frac']*100:.1f}
  % pour la même soudure. Source :
  <a href="{rep['source_url']}">{rep['source']}</a>.
</div>
<section><h2>1. Cadre d'AA vs pays entier — à la soudure</h2>
  <p class="sub">On suit la <b>projection de soudure (juin–août)</b> de chaque
  cycle CH : c'est le pic annuel d'insécurité alimentaire et la métrique
  rapportée par défaut (FAO, GRFC, OCHA), et c'est précisément la fenêtre que
  le cadre d'AA cherche à anticiper. Un point par an évite les « dents de
  scie » dues au mélange des saisons. La zone du cadre (22 départements
  sahéliens) est <b>systématiquement plus touchée</b> que la moyenne nationale,
  et l'écart se creuse depuis 2022. L'étoile marque la projection
  {rep['analysis']} rapportée par OCHA (non encore intégrée au jeu de données
  CH).</p>
  <figure>{_img('natl_vs_aoi', 'Phase 3+ zone AA vs national, soudure')}
  <figcaption>Part de population en phase 3+ à la soudure ; rouge = zone d'AA,
  gris = pays entier. ★ = projection mars 2026 (OCHA, % sur population totale ;
  les séries CH sont en % de la population analysée).</figcaption></figure>
</section>
<section><h2>2. Révision de la projection de soudure</h2>
  <p class="sub">Chaque soudure est projetée <b>deux fois</b> : par
  l'analyse de novembre (long terme, ~8 mois avant) puis affinée par
  l'analyse de mars (court terme, ~4 mois avant). Le CH ne produit pas
  d'<i>observation</i> en
  saison — la soudure est toujours une projection. Le trait court terme passe
  le plus souvent <b>au-dessus</b> du long terme : l'analyse de mars revoit la
  situation à la hausse. L'étoile = projection court terme mars 2026 (OCHA),
  cohérente avec ce schéma, mais pas encore dans le jeu de données CH.</p>
  <figure>{_img('lean_revision', 'Révision projection soudure')}
  <figcaption>National. Gris = projection long terme (analyse nov.) ; orange =
  projection court terme (analyse mars) ; trait vertical = ampleur de la
  révision.</figcaption></figure>
</section>
<section><h2>3. Pourquoi la soudure ? Amplitude saisonnière</h2>
  <p class="sub">Le CH analyse deux fois par an et publie, à chaque fois, une
  situation « courante » (pic après récolte, sep–déc = creux) et une projection
  de <b>soudure (juin–août)</b> = pic. Les deux saisons se dégradent depuis
  2022, mais c'est le pic de soudure qui pilote les besoins ; le suivre seul
  donne une tendance lisible.</p>
  <figure>{_img('seasonal', 'Soudure vs post-récolte national')}
  <figcaption>National. Trait plein = soudure juin–août (pic projeté) ;
  pointillé = post-récolte sep–déc (creux observé).</figcaption></figure>
</section>
<section><h2>4. Composition nationale par phase (soudure)</h2>
  <p class="sub">Décomposition de la population par phase CH à chaque soudure
  juin–août.</p>
  <figure>{_img('national', 'Composition CH nationale soudure')}
  <figcaption>Aires empilées = part de chaque phase ; ligne noire = seuil
  cumulé phase 3+.</figcaption></figure>
</section>
<section><h2>5. Évolution par département</h2>
  <p class="sub">Une ligne par département, une colonne par période d'analyse
  (toutes saisons), triées par sévérité moyenne. Les départements de la zone
  d'AA (★, en rouge) dominent le haut du classement ; l'alternance de bandes
  claires/foncées est le cycle saisonnier soudure/récolte.</p>
  <figure>{_img('heatmap', 'Heatmap département x période')}
  <figcaption>Cases blanches = département non évalué cette
  période.</figcaption>
  </figure>
</section>
<section><h2>6. Zone du cadre d'AA — détail par province (soudure)</h2>
  <p class="sub">Les {s['n_aoi']} départements de la zone, par province,
  projection de soudure juin–août — un point par an.</p>
  <figure>{_img('aoi_lines', 'Séries par département zone AA, soudure')}
  <figcaption>Part de population en phase 3+ à la soudure ; un trait par
  département.</figcaption></figure>
</section>
<section><h2>7. Cartographie de la soudure (juin–août)</h2>
  <p class="sub">Projection CH de la soudure sur les huit dernières années.
  Contour noir = zone d'AA.</p>
  <figure>{_img('maps', 'Cartes soudure')}
  <figcaption>Échelle commune 0–50 %. Gris = non évalué.</figcaption></figure>
  <figure style="margin-top:16px">{_img('latest_map', 'Carte récente')}
  <figcaption>Projection la plus récente du jeu de données CH.</figcaption>
  </figure>
</section>
<section><h2>8. Départements les plus touchés — soudure {latest}</h2>
  <p class="sub">Classement par part de population en phase 3+. ★ = zone du
  cadre d'AA.</p>
  <div class="cols">
    <div><h3>Zone du cadre d'AA</h3>{aoi_tbl}</div>
    <div><h3>Pays entier</h3>{cty_tbl}</div>
  </div>
</section>
<section><div class="note"><h3>Méthodologie &amp; provenance</h3><ul>
  <li><b>Source</b> : fichier consolidé CH/IPC (Afrique de l'Ouest et centrale)
  sur HDX, filtré sur le Tchad. HDX couvre 2014→présent et sert de référence ;
  l'API IPC ne remonte qu'à nov. 2020.</li>
  <li><b>Recoupement API IPC</b> : projection nationale juin–août 2026 — HDX
  {cc['hdx_phase3plus']/1e6:.3f} M vs API IPC {cc['api_phase3plus']/1e6:.3f} M
  (écart {cc['diff_people']:.0f} pers.).</li>
  <li><b>Niveau admin</b> : ADM2 (département) — niveau le plus fin du CH pour
  le Tchad.</li>
  <li><b>Série</b> : une estimation par (département × période), l'observé
  « courant » primant sur la projection ; à égalité, l'analyse la plus
  récente.</li>
  <li><b>Tendances saisonnières</b> : les courbes ne suivent qu'<i>une</i>
  saison à la fois — la projection de <b>soudure (juin–août)</b>, pic annuel et
  métrique de référence (FAO/GRFC/OCHA) — pour éviter le motif en dents de scie
  produit par le mélange soudure/post-récolte. La carte thermique conserve
  toutes les saisons.</li>
  <li><b>Phase 3+</b> = phases 3+4+5, agrégats pondérés par la population
  analysée.</li>
  <li><b>Code</b> : <code>src/datasources/ipc.py</code> (données),
  <code>analysis/ipc_ch_evolution/generate_report.py</code> (rapport).</li>
  <li><b>Blob</b> (<code>projects</code>, dev) :
  <code>ds-aa-tcd-drought/processed/ipc/tcd_ch_adm2_timeseries.parquet</code>.</li>
</ul></div></section>
<footer>Cadre Harmonisé nov. 2025 (HDX, recoupé API IPC) + projection mars 2026
  (OCHA) · projet <code>ds-aa-tcd-drought</code></footer>
</div></body></html>"""
    with open(f"{DOCS}/index.html", "w") as f:
        f.write(html + "\n")
    return f"{DOCS}/index.html"


def main():
    ts = ipc.load_adm2_timeseries()
    adm2_geo = codab.load_codab_from_blob(admin_level=2)
    adm1_geo = codab.load_codab_from_blob(admin_level=1)
    make_figures(ts, adm2_geo, adm1_geo)
    s = compute_summary(ts)
    path = build_html(ts, s)
    sz = os.path.getsize(path) / 1e6
    print(f"wrote {path} ({sz:.2f} MB)")
    print(
        f"AOI latest:  {s['aoi_p35_people']/1e6:.2f} M / "
        f"{s['aoi_p35_frac']*100:.1f}%"
    )
    print(
        f"Country:     {s['cty_p35_people']/1e6:.2f} M / "
        f"{s['cty_p35_frac']*100:.1f}%"
    )


if __name__ == "__main__":
    main()
