"""Generate the Chad CH/IPC evolution report (figures + self-contained HTML).

Pulls the processed ADM2 time series and boundaries from blob via the project
data layer, builds the figures, and writes a GitHub-Pages-ready page to
``docs/ipc_ch_evolution/index.html``. The most recent round (CH May 2026,
projecting the Jun–Aug 2026 lean season) is folded into the time series by
``src.datasources.ipc`` and so appears directly in every figure.

Run from the repo root:  python analysis/ipc_ch_evolution/generate_report.py
Refresh the data first with:
    python -c "from src.datasources import ipc; ipc.refresh()"
"""

import base64
import json
import os

import matplotlib as mpl
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from src.constants import NEW_ADM2_AOI_PCODES
from src.datasources import codab, ipc
from src.utils import blob_utils

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


# official CH map images (JPG) shared by OCHA on blob, alongside the workbook
_OCHA_MAPS = {
    "official_current": (
        "Tchad_Courante_Mars_Mai_2026.jpg",
        "Carte CH officielle — situation courante (mars–mai 2026)",
    ),
    "official_projected": (
        "Tchad_Projetee_Juin_Aout_2026.jpg",
        "Carte CH officielle — situation projetée (juin–août 2026)",
    ),
}


def save_official_maps(stage="dev", max_width=1500):
    """Download the OCHA CH map JPGs from blob, downscale, write to FIG.

    The originals are ~5 MB each; the page is self-contained (base64), so they
    are resampled to a web-friendly width before embedding.
    """
    from io import BytesIO

    from PIL import Image

    for name, (fn, _) in _OCHA_MAPS.items():
        raw = blob_utils._load_blob_data(
            f"{blob_utils.PROJECT_PREFIX}/raw/ipc/ocha/{fn}", stage=stage
        )
        im = Image.open(BytesIO(raw)).convert("RGB")
        if im.width > max_width:
            h = round(im.height * max_width / im.width)
            im = im.resize((max_width, h), Image.LANCZOS)
        im.save(f"{FIG}/{name}.jpg", "JPEG", quality=82, optimize=True)


def _img_jpg(name, alt):
    with open(f"{FIG}/{name}.jpg", "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return (
        f'<img src="data:image/jpeg;base64,{b64}" alt="{alt}" loading="lazy">'
    )


def _norm_pcode(s):
    # strip the country prefix so "TD0101" and "TCD0101" both map to "0101";
    # makes the geometry join robust to the CODAB vintage on blob
    return s.str.replace(r"^\D+", "", regex=True)


# CH analysis cycle → projection lead time for the Jun–Aug lean season
_LEAN_LEAD = {"Sep-Dec": "long", "Jan-May": "short", "Jun-Aug": "inseason"}


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
    # CH publishes, twice a year, a lean-season (Jun–Aug) PROJECTION — the
    # annual peak and the standard headline metric — and a post-harvest
    # (Sep–Dec) "current" reading — the annual trough. Plotting one season per
    # line avoids the seasonal sawtooth that comes from mixing them.
    lean = ts[ts["reference_label"] == "Jun-Aug"]

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
    fig, ax = plt.subplots(figsize=(13, 11.5))
    im = ax.imshow(mat.values, aspect="auto", cmap=P3CMAP, vmin=0, vmax=0.5)
    ax.grid(False)  # kill the default major grid (it slices through cells)
    col_labels = [d.strftime("%b %Y") for d in mat.columns]
    ax.set_xticks(range(len(mat.columns)))
    ax.set_xticklabels(col_labels, rotation=90, fontsize=6.5)
    # mirror the time axis on top so it stays readable down the tall heatmap
    secax = ax.secondary_xaxis("top")
    secax.set_xticks(range(len(mat.columns)))
    secax.set_xticklabels(col_labels, rotation=90, fontsize=6.5)
    secax.grid(False)
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
        a.xaxis.set_major_locator(mdates.YearLocator(1))
        a.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        a.tick_params(axis="x", labelrotation=90, labelsize=6.5)
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


def _lean_series_data(ts):
    """Per-(geography, lead/observed) lean-season series for the widget."""
    full = ipc.load_ch_full()
    piv = lean_estimates_by_lead(full).pivot(
        index="reference_year", columns="lead", values="frac_phase35"
    )
    piv_aoi = lean_estimates_by_lead(full, aoi_only=True, min_areas=15).pivot(
        index="reference_year", columns="lead", values="frac_phase35"
    )
    ph = ts[ts["reference_label"] == "Sep-Dec"]
    natl_ph = ipc.aggregate(ph)
    natl_ph.index = natl_ph.index.year
    aoi_ph = ipc.aggregate(ph[ph["is_aoi"]])
    aoi_ph.index = aoi_ph.index.year

    def pts(srs):
        return [(int(y), float(v)) for y, v in srs.dropna().items()]

    return {
        "country": {
            "obs": pts(natl_ph["frac_phase35"]),
            "long": pts(piv["long"]),
            "short": pts(piv["short"]),
        },
        "aa": {
            "obs": pts(aoi_ph["frac_phase35"]),
            "long": pts(piv_aoi["long"]),
            "short": pts(piv_aoi["short"]),
        },
    }


# JS that draws the SVG from embedded data and wires the checkboxes. Visibility
# of a line = its geography box AND its series box are both checked.
_LEAN_JS = """
(function(){
  var w = document.currentScript.parentNode;
  var d = JSON.parse(w.querySelector('.lean-data').textContent);
  var W=900,H=470,ML=58,MR=126,MT=16,MB=42,PW=W-ML-MR,PH=H-MT-MB;
  var COL={obs:'#6b8e23',long:'#5d6677',short:'#b35f00'};
  var all=[],yrs=[];
  ['country','aa'].forEach(function(g){['obs','long','short'].forEach(function(t){
    (d[g][t]||[]).forEach(function(p){all.push(p[1]);yrs.push(p[0]);});});});
  var ymax=Math.max.apply(null,all)*1.06;
  var xmin=Math.min.apply(null,yrs)-0.4, xmax=Math.max.apply(null,yrs)+0.4;
  function sx(y){return ML+(y-xmin)/(xmax-xmin)*PW;}
  function sy(v){return MT+(1-v/ymax)*PH;}
  var NS='http://www.w3.org/2000/svg';
  function el(n,a){var e=document.createElementNS(NS,n);for(var k in a)e.setAttribute(k,a[k]);return e;}
  var svg=el('svg',{viewBox:'0 0 '+W+' '+H,class:'leansvg'});
  for(var t=0;t<=ymax+1e-9;t+=0.05){
    svg.appendChild(el('line',{x1:ML,y1:sy(t),x2:ML+PW,y2:sy(t),stroke:'#e8e8e8'}));
    var yl=el('text',{x:ML-8,y:sy(t)+3,'text-anchor':'end',class:'ax'});
    yl.textContent=Math.round(t*100)+'%'; svg.appendChild(yl);
  }
  var y0=Math.ceil(Math.min.apply(null,yrs));
  for(var yr=y0; yr<=Math.max.apply(null,yrs); yr+=1){
    var xl=el('text',{x:sx(yr),y:MT+PH+18,'text-anchor':'middle',class:'ax'});
    xl.textContent=yr; svg.appendChild(xl);
  }
  function line(pts,color,dash,cls){
    var g=el('g',{class:cls});
    var pl=el('polyline',{points:pts.map(function(p){return sx(p[0])+','+sy(p[1]);}).join(' '),fill:'none',stroke:color,'stroke-width':2});
    if(dash)pl.setAttribute('stroke-dasharray',dash); g.appendChild(pl);
    pts.forEach(function(p){g.appendChild(el('circle',{cx:sx(p[0]),cy:sy(p[1]),r:2.5,fill:color}));});
    svg.appendChild(g); return g;
  }
  ['country','aa'].forEach(function(geo){
    var dash=geo==='aa'?'6,4':'';
    ['obs','long','short'].forEach(function(t){
      if((d[geo][t]||[]).length) line(d[geo][t],COL[t],dash,'ser geo-'+geo+' typ-'+t);
    });
  });
  // annotate the latest (short-lead) country projection — CH mai 2026
  var cs=d.country.short;
  if(cs.length){
    var lp=cs[cs.length-1];
    var an=el('g',{class:'ser geo-country typ-short'});
    an.appendChild(el('circle',{cx:sx(lp[0]),cy:sy(lp[1]),r:4.5,fill:'white',stroke:COL.short,'stroke-width':2}));
    var o1=el('text',{x:sx(lp[0])+9,y:sy(lp[1])-2,class:'ocha'}); o1.textContent=d.latest_label;
    var o2=el('text',{x:sx(lp[0])+9,y:sy(lp[1])+9,class:'ocha'}); o2.textContent=d.latest_value;
    an.appendChild(o1); an.appendChild(o2); svg.appendChild(an);
  }
  var yl=el('text',{x:ML,y:11,class:'ylab'}); yl.textContent='Part en phase 3+ — soudure';
  svg.appendChild(yl);
  w.querySelector('.lean-plot').appendChild(svg);
  function up(){
    var s={}; w.querySelectorAll('input[data-k]').forEach(function(i){s[i.dataset.k]=i.checked;});
    w.querySelectorAll('.ser').forEach(function(g){
      var geo=(g.classList.contains('geo-country')&&s['geo-country'])||(g.classList.contains('geo-aa')&&s['geo-aa']);
      var ty=(g.classList.contains('typ-obs')&&s['typ-obs'])||(g.classList.contains('typ-long')&&s['typ-long'])||(g.classList.contains('typ-short')&&s['typ-short']);
      g.style.display=(geo&&ty)?'':'none';
    });
  }
  w.querySelectorAll('input[data-k]').forEach(function(i){i.addEventListener('change',up);}); up();
})();
"""


def _lean_overview_widget(ts):
    rep = ipc.LATEST_REPORTED
    data = _lean_series_data(ts)
    data["latest_label"] = "CH mai 2026"
    data["latest_value"] = (
        f"{rep['phase3plus_people'] / 1e6:.2f} M · "
        f"{rep['phase3plus_pct_total_pop'] * 100:.1f} %"
    )
    payload = json.dumps(data)
    controls = (
        '<div class="ctrls">'
        "<fieldset><legend>Couverture</legend>"
        '<label><input type="checkbox" data-k="geo-country" checked>'
        '<span class="sw line"></span>Pays entier</label>'
        '<label><input type="checkbox" data-k="geo-aa">'
        '<span class="sw line dash"></span>Zone d\'AA</label>'
        "</fieldset>"
        "<fieldset><legend>Type</legend>"
        '<label><input type="checkbox" data-k="typ-obs" checked>'
        '<span class="sw" style="background:#6b8e23"></span>'
        "Post-récolte (observé)</label>"
        '<label><input type="checkbox" data-k="typ-long" checked>'
        '<span class="sw" style="background:#5d6677"></span>'
        "Soudure long terme (nov.)</label>"
        '<label><input type="checkbox" data-k="typ-short" checked>'
        '<span class="sw" style="background:#b35f00"></span>'
        "Soudure court terme (mars–mai)</label>"
        "</fieldset></div>"
    )
    return (
        '<div class="leanwidget">'
        + controls
        + '<div class="lean-plot"></div>'
        + f'<script type="application/json" class="lean-data">{payload}</script>'
        + f"<script>{_LEAN_JS}</script>"
        + "</div>"
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

    # November-2025 long-lead projection of the same (2026) lean season, for the
    # forecast-revision comparison in the callout
    full = ipc.load_ch_full()
    long26 = full[
        (full["reference_year"] == yr)
        & (full["reference_label"] == "Jun-Aug")
        & (full["exercise_label"] == "Sep-Dec")
        & full["adm2_pcod2"].notnull()
    ]
    long_people = long26["phase35"].sum()
    long_frac = long_people / long26["population"].sum()
    conc_pct = rep["concentration_people"] / rep["phase3plus_people"] * 100

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
.leanwidget{{background:var(--card);border:1px solid var(--line);
  border-radius:12px;padding:14px 16px 8px;}}
.leanwidget .leansvg{{width:100%;height:auto;display:block;min-width:520px;}}
.leansvg .ax{{font-size:11px;fill:#5d6677;}}
.leansvg .ylab{{font-size:11px;fill:#5d6677;font-weight:600;}}
.leansvg .ocha{{font-size:11px;fill:#7a0000;font-weight:700;}}
.lean-plot{{overflow-x:auto;}}
.ctrls{{display:flex;flex-wrap:wrap;gap:14px;margin-bottom:8px;}}
.ctrls fieldset{{border:1px solid var(--line);border-radius:8px;
  padding:4px 12px 8px;margin:0;}}
.ctrls legend{{font-size:.7rem;text-transform:uppercase;letter-spacing:.04em;
  color:var(--muted);padding:0 4px;}}
.ctrls label{{display:flex;align-items:center;gap:7px;font-size:.84rem;
  cursor:pointer;padding:2px 0;}}
.ctrls .sw{{width:16px;height:11px;border-radius:2px;display:inline-block;
  flex:0 0 auto;}}
.ctrls .sw.line{{height:0;border-radius:0;background:none;
  border-top:3px solid #5d6677;}}
.ctrls .sw.line.dash{{border-top-style:dashed;}}
.ctrls .sw.dot{{background:repeating-linear-gradient(90deg,#b35f00 0 3px,
  transparent 3px 6px);}}
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
  <div class="vintage">Source : Cadre Harmonisé (CILSS/HDX + classeur CH
  officiel), dernière analyse <b>mai 2026</b> · {s['n_departments']}
  départements · {s['n_periods']} périodes ({first} → {latest})</div>
</div></header>
<div class="wrap">
<div class="groups">
  <div class="grp aoi"><h3>Zone du cadre d'AA</h3>
    <div class="scope">{s['n_aoi']} départements ·
      projection soudure juin–août {int(yr)}</div>
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
      projection soudure juin–août {int(yr)}</div>
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
  <b>Analyse la plus récente ({rep['analysis']}) :</b>
  {s['cty_p35_people']/1e6:.2f} M de personnes
  ({s['cty_p35_frac']*100:.1f} % de la population analysée de
  {s['cty_pop']/1e6:.1f} M) en phase 3+ pour la soudure juin–août 2026 — le pic
  annuel. Près de la moitié ({rep['concentration_people']/1e6:.2f} M,
  {conc_pct:.0f} %) se concentre dans six provinces : {provs}. C'est une
  révision <b>à la hausse</b> de la projection long terme de novembre 2025
  ({long_people/1e6:.2f} M / {long_frac*100:.1f} %) pour la même soudure, et
  au-dessus des ~{rep['phase3plus_people_2025_lean']/1e6:.0f} M de la soudure
  2025. Chiffres vérifiés à partir du classeur CH officiel. Source :
  <a href="{rep['source_url']}">{rep['source']}</a>.
</div>
<section><h2>1. Soudure — zone d'AA vs pays, observé vs projeté</h2>
  <p class="sub">On suit la <b>projection de soudure (juin–août)</b> de chaque
  cycle CH — pic annuel d'insécurité alimentaire et métrique rapportée par
  défaut (FAO, GRFC, OCHA), précisément la fenêtre que le cadre d'AA cherche à
  anticiper. La <b>zone du cadre</b> (traits tiretés) est <b>systématiquement
  plus touchée</b> que la moyenne nationale (traits pleins), et l'écart se
  creuse depuis 2022. Le CH n'analyse <b>jamais</b> la soudure en cours : elle
  est <i>toujours</i> projetée — deux fois, à long terme (analyse nov.) puis
  affinée à court terme (analyse mars–mai) — jamais observée. La seule lecture
  <i>observée</i> est le creux de post-récolte (sep–déc), qui mesure la reprise
  après récolte, pas la soudure : il n'existe pas de vérité-terrain CH pour la
  soudure. Le dernier point court terme est l'analyse {rep['analysis']}
  (3,18 M / 17,5 % projetés pour juin–août 2026).</p>
  <p class="sub">Cochez/décochez pour afficher les séries — par couverture
  (pays / zone d'AA) et par type (observé / projections). Par défaut, seules
  les séries du pays entier sont affichées. Couleur = type, style de trait =
  couverture (plein = pays, tireté = zone d'AA).</p>
  {_lean_overview_widget(ts)}
</section>
<section><h2>2. Composition nationale par phase (soudure)</h2>
  <p class="sub">Décomposition de la population par phase CH à chaque soudure
  juin–août.</p>
  <figure>{_img('national', 'Composition CH nationale soudure')}
  <figcaption>Aires empilées = part de chaque phase ; ligne noire = seuil
  cumulé phase 3+.</figcaption></figure>
</section>
<section><h2>3. Évolution par département</h2>
  <p class="sub">Une ligne par département, une colonne par période d'analyse
  (toutes saisons), triées par sévérité moyenne. Les départements de la zone
  d'AA (★, en rouge) dominent le haut du classement ; l'alternance de bandes
  claires/foncées est le cycle saisonnier soudure/récolte.</p>
  <figure>{_img('heatmap', 'Heatmap département x période')}
  <figcaption>Cases blanches = département non évalué cette
  période.</figcaption>
  </figure>
</section>
<section><h2>4. Zone du cadre d'AA — détail par province (soudure)</h2>
  <p class="sub">Les {s['n_aoi']} départements de la zone, par province,
  projection de soudure juin–août — un point par an.</p>
  <figure>{_img('aoi_lines', 'Séries par département zone AA, soudure')}
  <figcaption>Part de population en phase 3+ à la soudure ; un trait par
  département.</figcaption></figure>
</section>
<section><h2>5. Cartographie de la soudure (juin–août)</h2>
  <p class="sub">Projection CH de la soudure sur les huit dernières années.
  Contour noir = zone d'AA.</p>
  <figure>{_img('maps', 'Cartes soudure')}
  <figcaption>Échelle commune 0–50 %. Gris = non évalué.</figcaption></figure>
  <figure style="margin-top:16px">{_img('latest_map', 'Carte récente')}
  <figcaption>Projection la plus récente du jeu de données CH (analyse mai
  2026, par département).</figcaption>
  </figure>
  <p class="sub" style="margin-top:22px">Cartes officielles du Cadre Harmonisé
  (analyse mai 2026) telles que diffusées — situation courante (mars–mai) et
  projetée (juin–août 2026).</p>
  <div class="cols">
    <figure>{_img_jpg('official_current', _OCHA_MAPS['official_current'][1])}
    <figcaption>{_OCHA_MAPS['official_current'][1]}.</figcaption></figure>
    <figure>{_img_jpg('official_projected',
      _OCHA_MAPS['official_projected'][1])}
    <figcaption>{_OCHA_MAPS['official_projected'][1]}.</figcaption></figure>
  </div>
</section>
<section><h2>6. Départements les plus touchés — soudure juin–août {int(yr)}</h2>
  <p class="sub">Classement par part de population en phase 3+. ★ = zone du
  cadre d'AA.</p>
  <div class="cols">
    <div><h3>Zone du cadre d'AA</h3>{aoi_tbl}</div>
    <div><h3>Pays entier</h3>{cty_tbl}</div>
  </div>
</section>
<section><div class="note"><h3>Méthodologie &amp; provenance</h3><ul>
  <li><b>Source</b> : fichier consolidé CH/IPC (Afrique de l'Ouest et centrale)
  sur HDX, filtré sur le Tchad (2014→présent, référence). La dernière analyse
  (<b>mai 2026</b>), pas encore sur HDX, provient du classeur CH officiel
  partagé par OCHA Tchad et est intégrée à la série. L'API IPC ne remonte qu'à
  nov. 2020.</li>
  <li><b>Recoupement API IPC</b> : projection nationale long terme (nov. 2025)
  juin–août 2026 — HDX {cc['hdx_phase3plus']/1e6:.3f} M vs API IPC
  {cc['api_phase3plus']/1e6:.3f} M (écart {cc['diff_people']:.0f} pers.).</li>
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
<footer>Cadre Harmonisé — historique HDX (recoupé API IPC) + analyse mai 2026
  (classeur CH officiel, OCHA Tchad) · projet
  <code>ds-aa-tcd-drought</code></footer>
</div></body></html>"""
    with open(f"{DOCS}/index.html", "w") as f:
        f.write(html + "\n")
    return f"{DOCS}/index.html"


def main():
    ts = ipc.load_adm2_timeseries()
    adm2_geo = codab.load_codab_from_blob(admin_level=2)
    adm1_geo = codab.load_codab_from_blob(admin_level=1)
    make_figures(ts, adm2_geo, adm1_geo)
    save_official_maps()
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
