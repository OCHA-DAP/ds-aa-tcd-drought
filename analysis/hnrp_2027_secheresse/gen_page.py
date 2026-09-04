"""Generate docs/hnrp_2027_secheresse/index.html: bilingual (FR/EN) write-up, categorical map,
interactive explorer (year / indicator selection) and time-series chart.
Usage: gen_page.py <workdir> <outdir>   (needs indicators.csv, indicators_by_year.csv, *_simpl.geojson)
"""

# flake8: noqa
import html
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

WORK = Path(sys.argv[1])
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
m = pd.read_csv(
    WORK / "indicators.csv", keep_default_na=False, na_values=[""]
).sort_values("rang")
ty = pd.read_csv(
    WORK / "indicators_by_year.csv", keep_default_na=False, na_values=[""]
)
adm2 = json.load(open(WORK / "adm2_simpl.geojson"))
adm1 = json.load(open(WORK / "adm1_simpl.geojson"))
m.to_csv(OUT / "indice_secheresse_adm2_2026-09-04.csv", index=False)
ty.to_csv(OUT / "indicateurs_par_annee_adm2.csv", index=False)
XLSX = "TCD_HNRP_2027_ANALYSE_DES_CHOCS_ALL_v2_secheresse.xlsx"

# ---------- map geometry ----------
LON0, LON1, LAT0, LAT1 = 13.4, 24.1, 7.3, 23.5
W = 520
K = math.cos(math.radians(15.5))
H = W * (LAT1 - LAT0) / ((LON1 - LON0) * K)


def xy(lon, lat):
    return (W * (lon - LON0) / (LON1 - LON0), H * (LAT1 - lat) / (LAT1 - LAT0))


def path(geom):
    polys = (
        geom["coordinates"]
        if geom["type"] == "MultiPolygon"
        else [geom["coordinates"]]
    )
    d = []
    for poly in polys:
        for ring in poly:
            pts = [xy(*p[:2]) for p in ring]
            d.append("M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z")
    return "".join(d)


DEP_PATHS = "".join(
    f'<path class="dep" data-pc="{f["properties"]["ADM2_PCODE"]}" d="{path(f["geometry"])}"/>'
    for f in adm2["features"]
)
ADM1_PATHS = "".join(
    f'<path d="{path(f["geometry"])}"/>' for f in adm1["features"]
)


# ---------- data ----------
def f1(v):
    return None if pd.isna(v) else round(float(v), 1)


def f2(v):
    return None if pd.isna(v) else round(float(v), 2)


CATKEY = {"Très élevé": "TE", "Élevé": "E", "Modéré": "M", "Faible": "F"}
depts = []
for _, r in m.iterrows():
    depts.append(
        dict(
            pc=r.ADM2_PCODE,
            prov=r.ADM1_FR,
            dep=r.ADM2_FR,
            nom=r.nom_fichier,
            aa=r.zone_aa == "Oui",
            sah=r.zone_saharienne == "Oui",
            pop=(
                None
                if pd.isna(r.population_ch_2026)
                else int(r.population_ch_2026)
            ),
            idx=f2(r.indice_secheresse),
            rang=int(r.rang),
            cat=CATKEY[r.categorie],
            ind=int(r.indicateur_secheresse),
            s_ch=f2(r.score_ch),
            s_asi=f2(r.score_asi),
            s_bio=f2(r.score_bio),
            ch_proj=f1(r.ch_p3_pct_proj_2026),
            ch_max=f1(r.ch_p3_pct_max_2024_2026),
            asi_max=f1(r.asi_max_2024_2026),
            asi_raw=f1(r.asi_raw_max_2024_2026),
            bio_min=f1(r.bio_min_2024_2026),
            bio_raw=f1(r.bio_raw_min_2024_2026),
            asi_tr=f2(r.asi_trend_pts_per_yr),
            bio_tr=f2(r.bio_trend_pct_per_yr),
            notes="" if pd.isna(r.notes) else r.notes,
        )
    )
YEARS = sorted(ty.year.unique().tolist())
V = {}
for pc, g in ty.groupby("ADM2_PCODE"):
    g = g.set_index("year").reindex(YEARS)
    V[pc] = {
        k: [f1(v) for v in g[c]]
        for k, c in [
            ("ch", "ch"),
            ("asi", "asi"),
            ("bio", "bio"),
            ("asi_raw", "asi_raw"),
            ("bio_raw", "bio_raw"),
        ]
    }
DATA = json.dumps(
    {"depts": depts, "years": YEARS, "v": V},
    ensure_ascii=False,
    separators=(",", ":"),
)

n_te = (m.categorie == "Très élevé").sum()
n_e = (m.categorie == "Élevé").sum()
n_ind = int(m.indicateur_secheresse.sum())
pop_ind = m[m.indicateur_secheresse == 1].population_ch_2026.sum() / 1e6
aa = m[m.zone_aa == "Oui"]
aa_te = (aa.categorie == "Très élevé").sum()
aa_e = (aa.categorie == "Élevé").sum()
CATCLASS = {"Très élevé": "TE", "Élevé": "E", "Modéré": "M", "Faible": "F"}


def catspan(c):
    return f'<span class="pill c-{CATCLASS[c]}"><span class="fr">{c}</span><span class="en">{ {"Très élevé":"Very high","Élevé":"High","Modéré":"Moderate","Faible":"Low"}[c] }</span></span>'


top_rows = "".join(
    f"<tr><td>{r.rang}</td><td>{html.escape(r.ADM2_FR)}</td><td>{html.escape(r.ADM1_FR)}</td><td class='num'>{r.indice_secheresse:.2f}</td><td>{catspan(r.categorie)}</td><td class='num'>{r.score_ch:.2f}</td><td class='num'>{r.score_asi:.2f}</td><td class='num'>{r.score_bio:.2f}</td><td>{'<span class=fr>Oui</span><span class=en>Yes</span>' if r.zone_aa=='Oui' else '<span class=fr>Non</span><span class=en>No</span>'}</td></tr>"
    for _, r in m.head(10).iterrows()
)

PAGE = r"""<!DOCTYPE html>
<html lang="fr" data-lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tchad HNRP 2027 — indice de risque sécheresse par département</title>
<style>
:root { color-scheme: light; --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink-2:#52514e; --muted:#898781; --grid:#e1e0d9; --border:rgba(11,11,11,.10);
  --accent:#b34a00; --warn-bg:#fff7ec; --warn-border:#d95f0e; --te:#662506; --e:#d95f0e; --m:#fe9929; --f:#fee391; --na:#d5d5d0; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { color-scheme:dark; --page:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink-2:#c3c2b7; --muted:#898781; --grid:#2c2c2a; --border:rgba(255,255,255,.12); --warn-bg:#2a1c10; --accent:#f59a4a; --na:#3a3a38; } }
:root[data-theme="dark"] { color-scheme:dark; --page:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink-2:#c3c2b7; --muted:#898781; --grid:#2c2c2a; --border:rgba(255,255,255,.12); --warn-bg:#2a1c10; --accent:#f59a4a; --na:#3a3a38; }
* { box-sizing:border-box; }
body { margin:0; background:var(--page); color:var(--ink); font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif; }
main { max-width:1100px; margin:0 auto; padding:24px 20px 64px; }
a { color:var(--accent); }
[data-lang="fr"] .en { display:none !important; } [data-lang="en"] .fr { display:none !important; }
.topbar { display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap; }
.home { display:inline-block; font-size:.85rem; color:var(--ink-2); text-decoration:none; border:1px solid var(--border); border-radius:6px; padding:3px 10px; }
.langtoggle { display:inline-flex; border:1px solid var(--border); border-radius:6px; overflow:hidden; font-size:.85rem; }
.langtoggle button { border:0; background:var(--surface); color:var(--ink-2); padding:4px 12px; cursor:pointer; }
.langtoggle button.on { background:var(--accent); color:#fff; }
h1 { font-size:1.5rem; margin:18px 0 4px; } h2 { font-size:1.12rem; margin:38px 0 10px; border-bottom:1px solid var(--grid); padding-bottom:4px; } h3 { font-size:1rem; margin:20px 0 6px; }
.sub { color:var(--ink-2); margin:0 0 16px; }
.banner { background:var(--warn-bg); border:2px solid var(--warn-border); border-radius:10px; padding:12px 18px; margin:16px 0 18px; }
.banner strong { display:block; margin-bottom:4px; }
.dl { margin:0 0 16px; font-size:.95rem; } .dl a { font-weight:600; }
.tiles { display:flex; flex-wrap:wrap; gap:12px; margin:0 0 20px; }
.tile { flex:1 1 180px; background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:12px 16px 14px; }
.tile .k { font-size:.76rem; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; }
.tile .v { font-size:1.6rem; font-weight:650; margin-top:2px; } .tile .d { font-size:.82rem; color:var(--ink-2); }
.maprow { display:grid; grid-template-columns: minmax(280px, 460px) 1fr; gap:20px; align-items:start; }
@media (max-width:760px) { .maprow { grid-template-columns:1fr; } }
figure { margin:0; background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:12px; }
figcaption { font-size:.82rem; color:var(--ink-2); padding:6px 4px 2px; }
svg { width:100%; height:auto; display:block; }
.dep { stroke:#fff; stroke-width:.6; cursor:pointer; } .dep:hover { stroke:var(--ink); stroke-width:1.6; }
.adm1 path { stroke:#4a4a48; stroke-width:1.1; pointer-events:none; }
.legend { display:flex; flex-wrap:wrap; gap:10px 16px; font-size:.82rem; margin:8px 2px 0; }
.legend span { display:inline-flex; align-items:center; gap:6px; } .legend i { width:16px; height:12px; border-radius:2px; display:inline-block; border:1px solid rgba(0,0,0,.15); }
#tip { position:fixed; pointer-events:none; background:var(--surface); color:var(--ink); border:1px solid var(--border); border-radius:8px; padding:8px 10px; font-size:.82rem; box-shadow:0 4px 14px rgba(0,0,0,.15); display:none; max-width:300px; z-index:10; }
#tip b { display:block; font-size:.9rem; }
table { border-collapse:collapse; width:100%; font-size:.85rem; } th, td { padding:5px 7px; border-bottom:1px solid var(--grid); text-align:left; vertical-align:top; }
th { background:var(--surface); position:sticky; top:0; cursor:pointer; user-select:none; font-weight:600; white-space:nowrap; } th.sorted::after { content:" ▾"; color:var(--muted); } th.asc::after { content:" ▴"; }
td.num { text-align:right; font-variant-numeric:tabular-nums; }
.tablewrap { overflow-x:auto; border:1px solid var(--border); border-radius:10px; background:var(--surface); max-height:640px; overflow-y:auto; }
.pill { display:inline-block; padding:1px 8px; border-radius:999px; font-size:.78rem; font-weight:600; color:#fff; white-space:nowrap; }
.c-TE { background:var(--te); } .c-E { background:var(--e); } .c-M { background:var(--m); color:#1a1a19; } .c-F { background:var(--f); color:#1a1a19; } .c-NA { background:var(--na); color:var(--ink-2); }
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:12px; }
.card { background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:12px 16px; font-size:.9rem; }
.card h3 { margin:0 0 6px; } .card dl { margin:0; } .card dt { color:var(--muted); font-size:.75rem; text-transform:uppercase; letter-spacing:.04em; margin-top:8px; } .card dd { margin:0; }
code { background:var(--grid); padding:1px 5px; border-radius:4px; font-size:.85em; }
.formula { background:var(--surface); border:1px solid var(--border); border-radius:8px; padding:10px 14px; font-family:ui-monospace,Menlo,monospace; font-size:.85rem; overflow-x:auto; white-space:pre; }
.small { font-size:.85rem; color:var(--ink-2); }
ul { padding-left:20px; } li { margin:3px 0; }
.ctrl { margin:8px 0; font-size:.85rem; color:var(--ink-2); } .ctrl input[type=text] { padding:4px 8px; border:1px solid var(--border); border-radius:6px; background:var(--surface); color:var(--ink); }
.panel { background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:12px 14px; margin:0 0 14px; display:flex; flex-wrap:wrap; gap:10px 22px; font-size:.86rem; align-items:flex-start; }
.panel fieldset { border:0; padding:0; margin:0; min-width:150px; } .panel legend { font-weight:600; padding:0; margin-bottom:4px; color:var(--ink-2); font-size:.78rem; text-transform:uppercase; letter-spacing:.04em; }
.panel label { display:block; margin:2px 0; white-space:nowrap; } .panel select, .panel input[type=range] { font:inherit; }
.panel select { padding:3px 6px; border:1px solid var(--border); border-radius:6px; background:var(--page); color:var(--ink); }
.panel .w { color:var(--muted); font-size:.78rem; }
.statline { font-size:.86rem; color:var(--ink-2); margin:6px 0 10px; }
.official { display:inline-block; font-size:.76rem; padding:1px 8px; border-radius:999px; background:var(--warn-bg); border:1px solid var(--warn-border); margin-left:6px; }
.tsline { fill:none; stroke-width:1.8; opacity:.75; } .tsline:hover, .tsline.hi { stroke-width:3.2; opacity:1; }
.tsdim { opacity:.15; }
.axis text { font:10.5px system-ui,sans-serif; fill:var(--muted); } .axis line, .axis path { stroke:var(--grid); }
.tslabel { font:10.5px system-ui,sans-serif; fill:var(--ink-2); paint-order:stroke; stroke:var(--surface); stroke-width:3px; }
.note { font-size:.8rem; color:var(--muted); }
</style>
</head>
<body>
<main>
<div class="topbar"><a class="home" href="../">← ds-aa-tcd-drought · <span class="fr">rapports</span><span class="en">reports</span></a>
<div class="langtoggle" role="group" aria-label="Langue / Language"><button data-l="fr" class="on">Français</button><button data-l="en">English</button></div></div>

<h1><span class="fr">Tchad — HNRP 2027 : indice de risque sécheresse par département</span><span class="en">Chad — HNRP 2027: drought-risk index by département</span></h1>
<p class="sub"><span class="fr">Données secondaires 2024–2026 (Cadre Harmonisé, FAO ASI et biomasse GeoSahel, ces deux dernières corrigées de leur tendance) combinées en un indice 0–1 pour les 70 départements, à verser dans la feuille « Indice sécheresse » du classeur <em>TCD_HNRP 2027_ANALYSE DES CHOCS</em>. Construit le 4 septembre 2026 par OCHA CHD Data Science.</span>
<span class="en">Secondary data for 2024–2026 (Cadre Harmonisé, FAO ASI and GeoSahel biomass, the latter two detrended) combined into a 0–1 index for the 70 départements, delivered as the “Indice sécheresse” sheet of the <em>TCD_HNRP 2027_ANALYSE DES CHOCS</em> workbook. Built on 4 September 2026 by OCHA CHD Data Science.</span></p>

<div class="banner"><strong><span class="fr">À lire avant usage</span><span class="en">Read before use</span></strong>
<span class="fr">L'indice est un outil de <em>priorisation relative</em> entre départements, sur le même principe que les pondérations « Priorisationzone » déjà utilisées dans le classeur (scores 0–1, moyenne pondérée). La saison 2026 est en cours : les valeurs 2026 d'ASI et de biomasse s'arrêtent au 21 août / à la décade 23 et seront révisées. Les seuils et poids sont des choix de méthode, exposés ci-dessous et modifiables directement dans la feuille Excel (ligne 3). Le classeur contient déjà des impacts « catastrophe naturelle » 2022 et 2024 (inondations) : aucun indice inondation n'a été ajouté — voir la section dédiée.</span>
<span class="en">The index is a tool for <em>relative prioritisation</em> across départements, built on the same principle as the “Priorisationzone” weights already in the workbook (0–1 scores, weighted mean). The 2026 season is still running: the 2026 ASI and biomass values stop at 21 August / dekad 23 and will be revised. Thresholds and weights are methodological choices, documented below and editable directly in the Excel sheet (row 3). The workbook already holds 2022 and 2024 “natural disaster” impacts (floods): no flood index was added — see the dedicated section.</span></div>

<p class="dl"><a href="@@XLSX@@" download>⬇ <span class="fr">Télécharger le classeur Excel mis à jour (v2_secheresse, 0,4 Mo)</span><span class="en">Download the updated Excel workbook (v2_secheresse, 0.4 MB)</span></a> · <a href="indice_secheresse_adm2_2026-09-04.csv" download><span class="fr">CSV de l'indice</span><span class="en">Index CSV</span></a> · <a href="indicateurs_par_annee_adm2.csv" download><span class="fr">CSV par année (1999–2026)</span><span class="en">Per-year CSV (1999–2026)</span></a></p>

<div class="tiles">
<div class="tile"><div class="k"><span class="fr">Très élevé</span><span class="en">Very high</span></div><div class="v">@@N_TE@@</div><div class="d"><span class="fr">départements (indice ≥ 0,60)</span><span class="en">départements (index ≥ 0.60)</span></div></div>
<div class="tile"><div class="k"><span class="fr">Élevé</span><span class="en">High</span></div><div class="v">@@N_E@@</div><div class="d"><span class="fr">départements (0,40 – 0,59)</span><span class="en">départements (0.40 – 0.59)</span></div></div>
<div class="tile"><div class="k">Indicateur_Sécheresse = 1</div><div class="v">@@N_IND@@</div><div class="d"><span class="fr">départements avec indice ≥ 0,50 — @@POP_IND@@ M habitants (pop. CH 2026)</span><span class="en">départements with index ≥ 0.50 — @@POP_IND@@ M people (CH 2026 pop.)</span></div></div>
<div class="tile"><div class="k"><span class="fr">Zone AA sécheresse (22 dép.)</span><span class="en">AA drought zone (22 dép.)</span></div><div class="v">@@AA_N@@</div><div class="d"><span class="fr">@@AA_TE@@ très élevé + @@AA_E@@ élevé ; cadre CERF activé fenêtres 1 &amp; 2 en 2026</span><span class="en">@@AA_TE@@ very high + @@AA_E@@ high; CERF framework triggered windows 1 &amp; 2 in 2026</span></div></div>
</div>

<h2><span class="fr">Carte et classement (indice consolidé 2024–2026)</span><span class="en">Map and ranking (consolidated 2024–2026 index)</span></h2>
<div class="maprow">
<figure><svg id="map0" viewBox="0 0 @@W@@ @@H@@" role="img" aria-label="Carte"><g class="deps">@@DEP_PATHS@@</g><g class="adm1" fill="none">@@ADM1_PATHS@@</g></svg>
<div class="legend" id="legend0"></div>
<figcaption><span class="fr">Catégorie de l'indice sécheresse par département (COD ADM2). Traits foncés : provinces. Survoler un département pour le détail.</span><span class="en">Drought-index category by département (COD ADM2). Dark lines: provinces. Hover a département for details.</span></figcaption></figure>
<div>
<h3 style="margin-top:0"><span class="fr">Dix départements les plus prioritaires</span><span class="en">Ten highest-priority départements</span></h3>
<div class="tablewrap" style="max-height:none"><table><thead><tr><th>#</th><th><span class="fr">Département</span><span class="en">Département</span></th><th>Province</th><th><span class="fr">Indice</span><span class="en">Index</span></th><th><span class="fr">Catégorie</span><span class="en">Category</span></th><th>CH</th><th>ASI</th><th><span class="fr">Biom.</span><span class="en">Biom.</span></th><th><span class="fr">Zone AA</span><span class="en">AA zone</span></th></tr></thead><tbody>@@TOP_ROWS@@</tbody></table></div>
<p class="small"><span class="fr">Colonnes CH / ASI / Biom. = scores 0–1 de chaque pilier. Lecture : une fois retirée la tendance au verdissement, les départements sahéliens de la zone AA (Kanem, Lac, Batha, Ouaddaï, Wadi Fira, Barh-El-Gazel) dominent le classement — insécurité alimentaire élevée depuis 2024, effondrement de la biomasse et stress cultural marqué en 2026 ; les départements du sud (Logone Occidental et Oriental, Mandoul, Tandjilé) ressortent par le seul stress agricole (ASI) des saisons 2025 et 2026.</span>
<span class="en">CH / ASI / Biom. columns are the 0–1 pillar scores. Reading: once the greening trend is removed, the Sahelian départements of the AA zone (Kanem, Lac, Batha, Ouaddaï, Wadi Fira, Barh-El-Gazel) dominate the ranking — high food insecurity since 2024, a collapse of biomass and marked crop stress in 2026; the southern départements (Logone Occidental and Oriental, Mandoul, Tandjilé) stand out for agricultural stress (ASI) alone in the 2025 and 2026 seasons.</span></p>
</div>
</div>

<h2><span class="fr">Explorateur : une année, ou une plage d'années, et les indicateurs de votre choix</span><span class="en">Explorer: one year, or a range of years, with the indicators of your choice</span></h2>
<p class="small"><span class="fr">L'indice consolidé ci-dessus retient, pour chaque pilier, la <strong>pire année</strong> de 2024–2026 (maximum pour le CH et l'ASI, minimum pour la biomasse), puis calcule les scores. L'explorateur permet de recalculer l'indice pour une seule année (1999–2026 ; le CH n'existe qu'à partir de 2014, l'indice est alors calculé sur les piliers disponibles), pour une autre plage d'années, en moyenne plutôt qu'en pire année, ou avec un sous-ensemble d'indicateurs (poids renormalisés).</span>
<span class="en">The consolidated index above keeps, for each pillar, the <strong>worst year</strong> of 2024–2026 (maximum for CH and ASI, minimum for biomass), then computes the scores. The explorer recomputes the index for a single year (1999–2026; CH only exists from 2014, so earlier years use the available pillars), for another year range, as an average rather than the worst year, or with a subset of indicators (weights renormalised).</span></p>
<div class="panel">
<fieldset><legend><span class="fr">Période</span><span class="en">Period</span></legend>
<label><input type="radio" name="mode" value="year"> <span class="fr">Année</span><span class="en">Year</span> <select id="yr"></select></label>
<label><input type="radio" name="mode" value="range" checked> <span class="fr">Consolidé</span><span class="en">Consolidated</span> <select id="y0"></select> – <select id="y1"></select></label>
<label style="margin-left:22px"><input type="radio" name="agg" value="worst" checked> <span class="fr">pire année (max / min)</span><span class="en">worst year (max / min)</span></label>
<label style="margin-left:22px"><input type="radio" name="agg" value="mean"> <span class="fr">moyenne des années</span><span class="en">mean of the years</span></label>
</fieldset>
<fieldset><legend><span class="fr">Indicateurs</span><span class="en">Indicators</span></legend>
<label><input type="checkbox" class="ind" value="ch" checked> <span class="fr">Cadre Harmonisé (Ph3+ %)</span><span class="en">Cadre Harmonisé (Ph3+ %)</span> <span class="w">× 0,4</span></label>
<label><input type="checkbox" class="ind" value="asi" checked> <span class="fr">ASI détendancié (stress agricole)</span><span class="en">Detrended ASI (crop stress)</span> <span class="w">× 0,3</span></label>
<label><input type="checkbox" class="ind" value="bio" checked> <span class="fr">Biomasse détendanciée</span><span class="en">Detrended biomass</span> <span class="w">× 0,3</span></label>
</fieldset>
</div>
<div class="statline" id="xstat"></div>
<div class="maprow">
<figure><svg id="map1" viewBox="0 0 @@W@@ @@H@@" role="img" aria-label="Carte explorateur"></svg><div class="legend" id="legend1"></div>
<figcaption id="xcap"></figcaption></figure>
<div><h3 style="margin-top:0"><span class="fr">Classement pour cette sélection</span><span class="en">Ranking for this selection</span></h3>
<div class="tablewrap" style="max-height:520px"><table id="xtbl"><thead><tr><th>#</th><th>Département</th><th>Province</th><th><span class="fr">Indice</span><span class="en">Index</span></th><th><span class="fr">Catégorie</span><span class="en">Category</span></th><th>CH</th><th>ASI</th><th>Biom.</th></tr></thead><tbody id="xtb"></tbody></table></div>
<p class="note"><span class="fr">Valeurs des piliers pour la sélection (CH et ASI détendancié en %, biomasse détendanciée en % de la tendance) ; le score est calculé sur ces valeurs.</span><span class="en">Pillar values for the selection (CH and detrended ASI in %, detrended biomass in % of trend); the score is computed on these values.</span></p></div>
</div>

<h2><span class="fr">Séries temporelles par département</span><span class="en">Time series by département</span></h2>
<div class="panel">
<fieldset><legend><span class="fr">Variable</span><span class="en">Variable</span></legend>
<select id="tsvar"><option value="idx">Indice / Index</option><option value="ch">CH Ph3+ (%)</option><option value="asi">ASI détendancié / detrended (%)</option><option value="asi_raw">ASI brut / raw (%)</option><option value="bio">Biomasse détendanciée / detrended (% tendance)</option><option value="bio_raw">Biomasse brute / raw (% moyenne 1999–2024)</option></select>
<div id="tsindwrap" style="margin-top:6px">
<label><input type="checkbox" class="tsind" value="ch" checked> CH <span class="w">× 0,4</span></label>
<label><input type="checkbox" class="tsind" value="asi" checked> ASI <span class="w">× 0,3</span></label>
<label><input type="checkbox" class="tsind" value="bio" checked> <span class="fr">Biomasse</span><span class="en">Biomass</span> <span class="w">× 0,3</span></label></div>
</fieldset>
<fieldset><legend><span class="fr">Départements (catégorie de l'indice consolidé)</span><span class="en">Départements (consolidated-index category)</span></legend>
<label><input type="checkbox" class="tscat" value="TE" checked> <span class="pill c-TE"><span class="fr">Très élevé</span><span class="en">Very high</span></span></label>
<label><input type="checkbox" class="tscat" value="E"> <span class="pill c-E"><span class="fr">Élevé</span><span class="en">High</span></span></label>
<label><input type="checkbox" class="tscat" value="M"> <span class="pill c-M"><span class="fr">Modéré</span><span class="en">Moderate</span></span></label>
<label><input type="checkbox" class="tscat" value="F"> <span class="pill c-F"><span class="fr">Faible</span><span class="en">Low</span></span></label>
</fieldset>
<fieldset><legend>Province</legend><select id="tsprov"><option value="">—</option></select>
<div style="margin-top:6px"><label><input type="checkbox" id="tsaa"> <span class="fr">zone AA seulement</span><span class="en">AA zone only</span></label></div>
<div style="margin-top:6px"><span class="fr">Années</span><span class="en">Years</span> <select id="tsy0"></select> – <select id="tsy1"></select></div></fieldset>
</div>
<figure><svg id="ts" viewBox="0 0 960 440" role="img" aria-label="Séries temporelles"></svg>
<div class="legend" id="legend2"></div>
<figcaption id="tscap"></figcaption></figure>
<p class="note"><span class="fr">Une ligne par département, colorée selon sa catégorie dans l'indice consolidé 2024–2026 ; survoler une ligne pour l'identifier. Avec « Indice », la valeur d'une année est l'indice recalculé sur cette seule année avec les indicateurs cochés (avant 2014, sans CH).</span><span class="en">One line per département, coloured by its category in the consolidated 2024–2026 index; hover a line to identify it. With “Index”, a year's value is the index recomputed on that single year with the ticked indicators (before 2014, without CH).</span></p>

<h2><span class="fr">Tableau complet (70 départements, indice consolidé)</span><span class="en">Full table (70 départements, consolidated index)</span></h2>
<div class="ctrl"><span class="fr">Filtrer :</span><span class="en">Filter:</span> <input type="text" id="q" placeholder="…"> · <span class="fr">cliquer un en-tête pour trier</span><span class="en">click a header to sort</span> · <a href="indice_secheresse_adm2_2026-09-04.csv">CSV</a></div>
<div class="tablewrap"><table id="tbl"><thead><tr>
<th data-k="rang"><span class="fr">Rang</span><span class="en">Rank</span></th><th data-k="dep">Département</th><th data-k="prov">Province</th><th data-k="idx"><span class="fr">Indice</span><span class="en">Index</span></th><th data-k="cat"><span class="fr">Catégorie</span><span class="en">Category</span></th><th data-k="ind">Indic.</th><th data-k="aa"><span class="fr">Zone AA</span><span class="en">AA zone</span></th>
<th data-k="s_ch">Score CH</th><th data-k="ch_proj"><span class="fr">CH Ph3+ % proj. 2026</span><span class="en">CH Ph3+ % proj. 2026</span></th><th data-k="ch_max">CH Ph3+ % max 24–26</th>
<th data-k="s_asi">Score ASI</th><th data-k="asi_max"><span class="fr">ASI détend. max 24–26 (%)</span><span class="en">Detr. ASI max 24–26 (%)</span></th><th data-k="asi_raw"><span class="fr">ASI brut max</span><span class="en">Raw ASI max</span></th>
<th data-k="s_bio"><span class="fr">Score biom.</span><span class="en">Biom. score</span></th><th data-k="bio_min"><span class="fr">Biom. détend. min 24–26 (%)</span><span class="en">Detr. biom. min 24–26 (%)</span></th><th data-k="bio_raw"><span class="fr">Biom. brute min</span><span class="en">Raw biom. min</span></th><th data-k="pop">Pop. CH 2026</th></tr></thead><tbody id="tb"></tbody></table></div>

<div class="fr">
<h2>Indicateurs retenus</h2>
<p>Trois piliers, tous à l'échelle du département (COD ADM2, 70 unités), sur la fenêtre 2024–2026 pour rester cohérent avec la portée « données secondaires » du classeur. Un pilier « résultat » (insécurité alimentaire) et deux piliers « aléa » (cultures, pâturages) qui décrivent la sécheresse agro-pastorale elle-même.</p>
<p>Les deux piliers d'aléa sont <strong>corrigés de leur tendance 1999–2024</strong>. Le Sahel tchadien verdit : la biomasse progresse de 2 à 6 % de sa moyenne par an dans le Kanem, le Barh-El-Gazel et le Wadi Fira, et l'ASI y recule d'environ 1 point par an. Comparer une saison à la moyenne brute de 26 ans la ferait donc paraître moins mauvaise qu'elle ne l'est au regard de ce que les dernières années ont établi. La pluie estimée (RFE de FEWS NET) a été examinée puis écartée : elle est déjà intégrée par les deux signaux de végétation, elle n'existe que sur les anciennes unités FAO, et son retrait ne déplace que marginalement le haut du classement.</p>
<div class="cards">
<div class="card"><h3>1 · Cadre Harmonisé (CH/IPC)</h3><dl>
<dt>Source</dt><dd>Fichier consolidé CH sur HDX (<code>cadre-harmonise</code>) + classeur officiel CH mai 2026 partagé par OCHA Tchad. Pipeline <code>src/datasources/ipc.py</code> de ce dépôt.</dd>
<dt>Couverture</dt><dd>8 analyses de 2024 à 2026 : courant mars–mai et projeté juin–août de chaque cycle, plus courant oct–déc 2024 et 2025. 69 départements (N'Djaména non analysé). Série complète depuis 2014 dans l'explorateur.</dd>
<dt>Variables</dt><dd>% de population en phase 3+ : projeté juin–août 2026 (soudure en cours), et <strong>maximum sur les 8 analyses</strong> ; phase de zone maximale (règle des 20 %) ; personnes en phase 3+.</dd>
<dt>Pourquoi</dt><dd>Résultat humanitaire directement lié aux chocs sécheresse récents ; c'est aussi la donnée que les clusters connaissent.</dd></dl></div>
<div class="card"><h3>2 · FAO ASI — stress agricole (détendancié)</h3><dl>
<dt>Source</dt><dd>FAO GIEWS ASIS, série décadaire par unité administrative (<code>ASI_Dekad_Season1</code>, masque cultures), page pays TCD.</dd>
<dt>Définition</dt><dd>% de la surface cultivée dont l'indice de santé de la végétation (VHI) est &lt; 35. Moyenne des décades du <strong>1er juin au 21 août</strong> de chaque année (même fenêtre toutes les années, pour rester comparable avec la saison 2026 en cours). <strong>Correction de tendance</strong> : droite ajustée sur 1999–2024 par unité ; ASI corrigé = ASI brut − (valeur de la tendance pour l'année − moyenne 1999–2024), borné à 0–100. Valeur retenue = maximum 2024–2026 de l'ASI corrigé ; l'ASI brut figure à côté.</dd>
<dt>Échelle</dt><dd>FAO publie sur les 28 anciens départements (GAUL 2015). Report sur les 70 départements COD par intersection surfacique (moyenne pondérée par la surface) — la valeur est donc partagée par les départements issus d'une même ancienne unité.</dd>
<dt>Pourquoi</dt><dd>Signal « cultures », qui capte les poches sèches du sud (Logone, Mandoul, Tandjilé) invisibles dans la biomasse pastorale. Sans correction, l'ASI récent du Sahel est proche de zéro par construction — le VHI est normalisé sur un historique que le verdissement a déplacé ; corrigé, le stress 2026 du Kanem, du Batha et du Barh-El-Gazel ressort à 15–22 %.</dd></dl></div>
<div class="card"><h3>3 · Biomasse — GeoSahel / Action contre la Faim (détendanciée)</h3><dl>
<dt>Source</dt><dd>Couche WFS <code>Biomass:WA_BIO_ADM2_v4</code> (productivité de matière sèche DMP décadaire, 1999 → décade 23 de 2026), même fournisseur que la fenêtre 3 du cadre AA sécheresse.</dd>
<dt>Définition</dt><dd>Production cumulée des décades 10 à 23 (1er avril – 20 août). <strong>Correction de tendance identique à celle du cadre AA</strong> : droite ajustée sur 1999–2024 par département ; biomasse corrigée = cumul de l'année / valeur attendue par la tendance pour cette année, en % (tendance plancher à 10 % de la moyenne pour éviter les divisions par une valeur quasi nulle). Valeur retenue = minimum 2024–2026 ; l'anomalie brute (en % de la moyenne 1999–2024) figure à côté. Non applicable dans les provinces sahariennes (Borkou, Ennedi Est/Ouest, Tibesti : production de base quasi nulle).</dd>
<dt>Pourquoi</dt><dd>Signal « pâturages / élevage » ; 2026 est la pire saison de la série dans la bande sahélienne. Une fois la tendance retirée, le Kanem et le Nord Kanem tombent à 16–26 % de la production attendue, et le Batha, le Wadi Fira et le Barh-El-Gazel Nord à 35–46 %.</dd></dl></div>
</div>
<p class="small">Colonnes de contexte ajoutées sans entrer dans l'indice : population CH 2026, ASI brut et biomasse brute (avant correction de tendance), pentes des tendances 1999–2024, appartenance à la zone du cadre d'action anticipatoire sécheresse (7 provinces : Batha, Kanem, Lac, Wadi Fira, Barh-El-Gazel, Sila, Ouaddaï ; fenêtres 1 et 2 déclenchées les 30 avril et 9 mai 2026, fenêtre 3 en cours de vérification sur la décade 24), p-codes COD et p-codes/orthographes du classeur HNRP.</p>

<h2>Construction de l'indice</h2>
<p>Chaque pilier est transformé en un <strong>score 0–1</strong> par interpolation linéaire entre deux seuils fixes (0 = pas de signal, 1 = signal maximal, bornés), puis les scores sont moyennés avec des poids. Les seuils sont absolus (pas des rangs) pour que l'indice reste comparable si l'on met à jour une seule source. La consolidation 2024–2026 retient la pire année de chaque pilier (max / min), pas la moyenne — l'explorateur permet de comparer les deux.</p>
<div class="formula">Score CH        = clip( (CH Ph3+ max 2024–2026  − 10 %) / (40 % − 10 %) , 0, 1 )
Score ASI       = clip(  ASI détendancié max 2024–2026 / 40 %              , 0, 1 )
Score biomasse  = clip( (100 % − biomasse détendanciée min 2024–2026) / (100 % − 50 %) , 0, 1 )

où  ASI détendancié      = ASI brut − (tendance de l'année − moyenne 1999–2024), borné 0–100
et  biomasse détendanciée = 100 % × cumul de l'année / valeur attendue par la tendance 1999–2024

Indice sécheresse = ( 0,4·CH + 0,3·ASI + 0,3·biomasse ) / (somme des poids des scores disponibles)

Catégorie : Très élevé ≥ 0,60 · Élevé 0,40–0,59 · Modéré 0,20–0,39 · Faible &lt; 0,20
Indicateur_Sécheresse = 1 si indice ≥ 0,50 (même logique que le seuil 50 % du classeur), sinon 0</div>
<ul>
<li><strong>Poids</strong> : 40 % au résultat (CH), 60 % répartis également entre les deux signaux d'aléa (cultures, pâturages), de façon à ce que l'indice ne soit pas une simple copie du CH mais reflète bien la sécheresse agro-pastorale 2024–2026.</li>
<li><strong>Seuils</strong> : 10–40 % de population en phase 3+ couvre l'étendue observée (9–44 %) ; 40 % de surface cultivée stressée correspond à un stress sévère au sens FAO ; 50 % de la biomasse attendue marque les pires années de la série dans le Sahel tchadien.</li>
<li><strong>Zone saharienne</strong> (8 départements de Borkou, Ennedi Est, Ennedi Ouest, Tibesti) : ASI et biomasse n'ont pas de sens (pas de cultures, production de base ≈ 0). Les scores d'aléa y sont fixés à 0 — l'indice n'y reflète que le CH, pondéré à 0,4 — plutôt que de laisser un CH seul remonter ces départements en tête. Leur insécurité alimentaire (22–31 % en phase 3+) est bien visible dans les colonnes CH.</li>
<li><strong>Données manquantes</strong> : N'Djaména n'est pas couvert par le CH ; l'indice y est calculé sur les seuls scores d'aléa (renormalisation des poids) et signalé dans la colonne Notes.</li>
<li><strong>Pourquoi max / min sur 2024–2026</strong> : la feuille doit refléter « ce qui s'est passé récemment » ; prendre l'extrême sur les trois saisons capte un choc même s'il n'est pas dans la dernière analyse (ex. Dababa : 31 % en phase 3+ en 2024, 10 % projeté 2026). La dernière projection CH (juin–août 2026) est fournie à côté pour la lecture.</li>
</ul>
<p>Dans la feuille Excel, tous les scores, l'indice, le rang, la catégorie et l'indicateur binaire sont des <strong>formules</strong> qui lisent les poids et seuils de la ligne 3 (cellules jaunes) : changer un poids recalcule tout. Les quatre colonnes ajoutées à droite de la feuille Recap (AI–AL) sont des <code>INDEX/MATCH</code> sur le nom du département vers cette feuille.</p>

<h2>Inondations : rien d'ajouté, et pourquoi</h2>
<p>La feuille « Choc Catastrophe Naturel » du classeur contient déjà, par département, les personnes affectées, têtes de bétail perdues, hectares détruits et décès des saisons <strong>2022 et 2024</strong> — les deux grandes années d'inondations récentes — avec le score « Priorisationzone » correspondant, repris dans le Recap. Conformément à la demande, aucun indice inondation n'a été construit par-dessus. Deux remarques pour la suite :</p>
<ul>
<li>Le choc est libellé « catastrophe naturelle » sans distinguer inondation / autres aléas, et les saisons 2023 et 2025 n'y figurent pas ; si le comité veut un indicateur inondation explicite, la même structure (personnes affectées / population, bétail, hectares, décès) peut être complétée avec les bilans 2025 de la Direction de la protection civile et d'OCHA, et enrichie d'une exposition observée par satellite (FloodScan, suivi par l'équipe pour le cadre AA inondations Chari / N'Djaména et Mayo-Kebbi Est).</li>
<li>Les colonnes ajoutées ne touchent pas à ces feuilles ni aux tableaux croisés dynamiques : le classeur original est conservé, la version « v2_secheresse » ajoute une feuille et quatre colonnes.</li>
</ul>

<h2>Limites et points d'attention</h2>
<ul>
<li><strong>Saison 2026 en cours</strong> : ASI et biomasse 2026 s'arrêtent au 21 août (décade 23). Ils seront mis à jour quand la décade 24 sera publiée (vérification officielle de la fenêtre 3 du cadre AA) ; le CH de novembre 2026 pourra remplacer la projection juin–août.</li>
<li><strong>La correction de tendance est une hypothèse</strong> : une droite sur 26 saisons est le modèle le plus simple possible. Pour la biomasse, c'est la méthode déjà retenue par le cadre AA sécheresse. Pour l'ASI, borné entre 0 et 100, la correction additive ajoute jusqu'à 15–17 points dans les unités sahéliennes où la droite descend vers zéro : c'est bien l'ordre de grandeur du biais de verdissement, mais il vaut mieux lire ASI brut et ASI corrigé côte à côte — les deux figurent dans la feuille, le tableau et l'explorateur.</li>
<li><strong>Report des anciennes unités FAO</strong> : l'ASI est publié par FAO sur 28 unités (GAUL 2015, ≈ anciens départements). Les départements actuels d'une même ancienne unité partagent la même valeur — l'ASI ne différencie pas, par exemple, les quatre départements du Logone Occidental.</li>
<li><strong>Biomasse au niveau département</strong> : dans les départements à faible production de base (Barh-El-Gazel Nord, Nord Kanem, Mégri, Biltine), l'anomalie relative est bruitée ; elle reste cohérente avec le signal provincial (Kanem ≈ 30 % de la normale) utilisé par le cadre AA.</li>
<li><strong>P-codes et noms du classeur</strong> : la feuille « Listes departements inclus » intervertit les p-codes d'Abdi (COD TCD1402, Ouaddaï) et de Djourf Al Ahmar (COD TCD2102, Sila) et code Mourtcha TCD2302 (COD TCD2303). La jointure a été faite sur les noms ; les deux p-codes sont fournis dans la feuille.</li>
<li><strong>Population</strong> : la population « CH 2026 » sert de contexte ; elle diffère des populations utilisées dans les feuilles conflit/épidémie du classeur.</li>
<li><strong>Un indice n'est pas une décision</strong> : il ordonne les départements sur le seul aléa sécheresse et ses effets alimentaires récents ; il doit être lu avec les pondérations conflit, épidémie et inondation du Recap et les retours des clusters.</li>
</ul>

<h2>Fichiers et reproduction</h2>
<ul>
<li>Classeur mis à jour : <a href="@@XLSX@@" download><strong>TCD_HNRP 2027_ANALYSE DES CHOCS_ALL_v2_secheresse.xlsx</strong></a> (classeur original + feuille « Indice sécheresse » + colonnes AI–AL du Recap).</li>
<li>Tables plates : <a href="indice_secheresse_adm2_2026-09-04.csv">indice_secheresse_adm2_2026-09-04.csv</a> (toutes les colonnes de la feuille) et <a href="indicateurs_par_annee_adm2.csv">indicateurs_par_annee_adm2.csv</a> (valeurs des piliers par département et par année, 1999–2026, brutes et corrigées de la tendance, utilisées par l'explorateur).</li>
<li>Scripts : <code>analysis/hnrp_2027_secheresse/</code> dans le dépôt <a href="https://github.com/OCHA-DAP/ds-aa-tcd-drought">ds-aa-tcd-drought</a> — <code>fetch_data.sh</code> (téléchargements FAO ASIS, GeoSahel, GAUL), <code>build_indicators.py</code> (calcul, y compris les tendances et la table par année), <code>inject_xlsx.py</code> (insertion dans le classeur sans casser les segments et le modèle de données), <code>gen_page.py</code> (cette page).</li>
<li>Contexte CH par département 2014–2026 : <a href="../ipc_ch_evolution/">rapport d'évolution CH/IPC</a>. Suivi biomasse 2026 : <a href="../biomasse_check_2026/">vérification fenêtre 3</a>.</li>
</ul>
<p class="small">Sources : CILSS/Cadre Harmonisé via HDX et OCHA Tchad ; FAO GIEWS ASIS (ASI) ; Action contre la Faim / GeoSahel BioGenerator ; OCHA COD-AB Tchad. Les seuils, poids et règles d'agrégation sont ceux d'OCHA CHD Data Science et n'engagent pas ces producteurs.</p>
</div>

<div class="en">
<h2>Indicators used</h2>
<p>Three pillars, all at département level (COD ADM2, 70 units), over the 2024–2026 window to stay consistent with the workbook's “secondary data” scope. One <em>outcome</em> pillar (food insecurity) and two <em>hazard</em> pillars (crops, pasture) that describe the agro-pastoral drought itself.</p>
<p>Both hazard pillars are <strong>corrected for their 1999–2024 trend</strong>. The Chadian Sahel is greening: biomass rises by 2–6% of its own mean per year in Kanem, Barh-El-Gazel and Wadi Fira, and ASI there falls by about 1 point per year. Comparing a season with the raw 26-year mean would therefore make it look less bad than it is against what recent years have established. Estimated rainfall (FEWS NET RFE) was examined and dropped: it is already integrated by the two vegetation signals, it only exists on FAO's legacy units, and removing it barely moves the top of the ranking.</p>
<div class="cards">
<div class="card"><h3>1 · Cadre Harmonisé (CH/IPC)</h3><dl>
<dt>Source</dt><dd>Consolidated CH file on HDX (<code>cadre-harmonise</code>) plus the official May 2026 CH workbook shared by OCHA Chad. Pipeline <code>src/datasources/ipc.py</code> in this repository.</dd>
<dt>Coverage</dt><dd>8 analyses from 2024 to 2026: current March–May and projected June–August of each cycle, plus current Oct–Dec 2024 and 2025. 69 départements (N'Djaména not analysed). Full series since 2014 in the explorer.</dd>
<dt>Variables</dt><dd>Share of population in phase 3+: projected June–August 2026 (current lean season) and the <strong>maximum over the 8 analyses</strong>; maximum area phase (20% rule); people in phase 3+.</dd>
<dt>Why</dt><dd>The humanitarian outcome most directly tied to recent drought shocks, and the dataset the clusters already know.</dd></dl></div>
<div class="card"><h3>2 · FAO ASI — agricultural stress (detrended)</h3><dl>
<dt>Source</dt><dd>FAO GIEWS ASIS, dekadal series by administrative unit (<code>ASI_Dekad_Season1</code>, cropland mask), TCD country page.</dd>
<dt>Definition</dt><dd>Share of cropland whose Vegetation Health Index (VHI) is below 35. Mean of the dekads from <strong>1 June to 21 August</strong> each year (the same window every year, so the running 2026 season stays comparable). <strong>Trend correction</strong>: a straight line fitted over 1999–2024 per unit; adjusted ASI = raw ASI − (the trend's value for that year − the 1999–2024 mean), clipped to 0–100. Value used = the 2024–2026 maximum of the adjusted ASI; raw ASI is shown alongside.</dd>
<dt>Scale</dt><dd>FAO publishes on the 28 former départements (GAUL 2015). Transferred to the 70 COD départements by area-weighted intersection — départements carved from the same former unit therefore share a value.</dd>
<dt>Why</dt><dd>A crop signal that captures the dry pockets of the south (Logone, Mandoul, Tandjilé) that pastoral biomass does not see. Without the correction, recent Sahelian ASI is near zero by construction — VHI is normalised on a history that greening has shifted; adjusted, the 2026 stress in Kanem, Batha and Barh-El-Gazel comes out at 15–22%.</dd></dl></div>
<div class="card"><h3>3 · Biomass — GeoSahel / Action contre la Faim (detrended)</h3><dl>
<dt>Source</dt><dd>WFS layer <code>Biomass:WA_BIO_ADM2_v4</code> (dekadal dry-matter productivity, DMP, 1999 → dekad 23 of 2026), the same provider as window 3 of the AA drought framework.</dd>
<dt>Definition</dt><dd>Cumulative production over dekads 10–23 (1 April – 20 August). <strong>Trend correction identical to the AA framework's</strong>: a straight line fitted over 1999–2024 per département; adjusted biomass = the year's total / the trend-expected value for that year, in % (the trend is floored at 10% of the mean to avoid dividing by a near-zero value). Value used = the 2024–2026 minimum; the raw anomaly (% of the 1999–2024 mean) is shown alongside. Not applicable in the Saharan provinces (Borkou, Ennedi Est/Ouest, Tibesti: near-zero baseline production).</dd>
<dt>Why</dt><dd>A pasture / livestock signal; 2026 is the worst season on record across the Sahelian belt. Once the trend is removed, Kanem and Nord Kanem fall to 16–26% of expected production, and Batha, Wadi Fira and Barh-El-Gazel Nord to 35–46%.</dd></dl></div>
</div>
<p class="small">Context columns added without entering the index: CH 2026 population, raw ASI and raw biomass (before the trend correction), the 1999–2024 trend slopes, membership of the anticipatory-action drought framework zone (7 provinces: Batha, Kanem, Lac, Wadi Fira, Barh-El-Gazel, Sila, Ouaddaï; windows 1 and 2 triggered on 30 April and 9 May 2026, window 3 being checked on dekad 24), COD p-codes and the HNRP workbook's own p-codes/spellings.</p>

<h2>How the index is built</h2>
<p>Each pillar becomes a <strong>0–1 score</strong> by linear interpolation between two fixed thresholds (0 = no signal, 1 = maximum signal, clipped), and the scores are then averaged with weights. Thresholds are absolute (not ranks) so the index stays comparable when a single source is updated. The 2024–2026 consolidation keeps the worst year of each pillar (max / min), not the average — the explorer lets you compare both.</p>
<div class="formula">CH score        = clip( (CH Ph3+ max 2024–2026  − 10%) / (40% − 10%) , 0, 1 )
ASI score       = clip(  detrended ASI max 2024–2026 / 40%                 , 0, 1 )
Biomass score   = clip( (100% − detrended biomass min 2024–2026) / (100% − 50%) , 0, 1 )

where  detrended ASI     = raw ASI − (the trend's value for the year − the 1999–2024 mean), clipped 0–100
and    detrended biomass = 100% × the year's total / the value expected from the 1999–2024 trend

Drought index = ( 0.4·CH + 0.3·ASI + 0.3·biomass ) / (sum of the weights of the available scores)

Category: Very high ≥ 0.60 · High 0.40–0.59 · Moderate 0.20–0.39 · Low &lt; 0.20
Indicateur_Sécheresse = 1 if index ≥ 0.50 (same logic as the workbook's 50% threshold), else 0</div>
<ul>
<li><strong>Weights</strong>: 40% on the outcome (CH), 60% split equally across the two hazard signals (crops, pasture), so that the index is not a copy of the CH but reflects the 2024–2026 agro-pastoral drought.</li>
<li><strong>Thresholds</strong>: 10–40% of population in phase 3+ spans the observed range (9–44%); 40% of stressed cropland corresponds to severe stress in FAO's terms; 50% of expected biomass marks the worst years on record in the Chadian Sahel.</li>
<li><strong>Saharan zone</strong> (8 départements of Borkou, Ennedi Est, Ennedi Ouest, Tibesti): ASI and biomass are meaningless there (no cropland, baseline production ≈ 0). Their hazard scores are set to 0 — the index there reflects only the CH, weighted 0.4 — rather than letting a lone CH push these départements to the top. Their food insecurity (22–31% in phase 3+) remains visible in the CH columns.</li>
<li><strong>Missing data</strong>: N'Djaména is not covered by the CH; its index uses the hazard scores only (weights renormalised) and is flagged in the Notes column.</li>
<li><strong>Why max / min over 2024–2026</strong>: the sheet must reflect “what happened recently”; taking the extreme over the three seasons captures a shock even if it is absent from the latest analysis (e.g. Dababa: 31% in phase 3+ in 2024, 10% projected for 2026). The latest CH projection (June–August 2026) is shown alongside for reading.</li>
</ul>
<p>In the Excel sheet, every score, the index, rank, category and binary indicator are <strong>formulas</strong> reading the weights and thresholds in row 3 (yellow cells): changing a weight recomputes everything. The four columns added to the right of the Recap sheet (AI–AL) are <code>INDEX/MATCH</code> lookups on the département name into that sheet.</p>

<h2>Floods: nothing added, and why</h2>
<p>The workbook's “Choc Catastrophe Naturel” sheet already holds, per département, people affected, livestock lost, hectares destroyed and deaths for the <strong>2022 and 2024</strong> seasons — the two major recent flood years — with the matching “Priorisationzone” score carried into the Recap. As requested, no flood index was built on top of it. Two remarks for later:</p>
<ul>
<li>The shock is labelled “natural disaster” without separating floods from other hazards, and the 2023 and 2025 seasons are missing; if the committee wants an explicit flood indicator, the same structure (people affected / population, livestock, hectares, deaths) can be completed with the 2025 tallies from the civil-protection directorate and OCHA, and enriched with satellite-observed exposure (FloodScan, which the team already tracks for the Chari / N'Djaména and Mayo-Kebbi Est flood AA framework).</li>
<li>The added columns do not touch those sheets or the pivot tables: the original workbook is preserved, and the “v2_secheresse” version adds one sheet and four columns.</li>
</ul>

<h2>Limitations and points of attention</h2>
<ul>
<li><strong>2026 season still running</strong>: 2026 ASI and biomass stop at 21 August (dekad 23). They will be updated once dekad 24 is published (the official window-3 check of the AA framework); the November 2026 CH can replace the June–August projection.</li>
<li><strong>The trend correction is an assumption</strong>: a straight line over 26 seasons is the simplest possible model. For biomass it is the method the AA drought framework already uses. For ASI, bounded between 0 and 100, the additive correction adds up to 15–17 points in the Sahelian units where the line falls towards zero: that is the right order of magnitude for the greening bias, but raw and adjusted ASI are best read side by side — both are in the sheet, the table and the explorer.</li>
<li><strong>Transfer from FAO's legacy units</strong>: ASI is published by FAO on 28 units (GAUL 2015, ≈ the former départements). Current départements from the same former unit share one value — ASI does not, for example, separate the four départements of Logone Occidental.</li>
<li><strong>Biomass at département level</strong>: in low-baseline départements (Barh-El-Gazel Nord, Nord Kanem, Mégri, Biltine) the relative anomaly is noisy; it remains consistent with the provincial signal (Kanem ≈ 30% of normal) used by the AA framework.</li>
<li><strong>Workbook p-codes and names</strong>: the “Listes departements inclus” sheet swaps the p-codes of Abdi (COD TCD1402, Ouaddaï) and Djourf Al Ahmar (COD TCD2102, Sila) and codes Mourtcha as TCD2302 (COD TCD2303). The join was made on names; both p-codes are given in the sheet.</li>
<li><strong>Population</strong>: the “CH 2026” population is context only; it differs from the populations used in the workbook's conflict/epidemic sheets.</li>
<li><strong>An index is not a decision</strong>: it ranks départements on the drought hazard and its recent food-security effects alone; it must be read together with the conflict, epidemic and flood weights of the Recap and the clusters' feedback.</li>
</ul>

<h2>Files and reproduction</h2>
<ul>
<li>Updated workbook: <a href="@@XLSX@@" download><strong>TCD_HNRP 2027_ANALYSE DES CHOCS_ALL_v2_secheresse.xlsx</strong></a> (original workbook + “Indice sécheresse” sheet + Recap columns AI–AL).</li>
<li>Flat tables: <a href="indice_secheresse_adm2_2026-09-04.csv">indice_secheresse_adm2_2026-09-04.csv</a> (every column of the sheet) and <a href="indicateurs_par_annee_adm2.csv">indicateurs_par_annee_adm2.csv</a> (pillar values per département and year, 1999–2026, raw and detrended, used by the explorer).</li>
<li>Scripts: <code>analysis/hnrp_2027_secheresse/</code> in the <a href="https://github.com/OCHA-DAP/ds-aa-tcd-drought">ds-aa-tcd-drought</a> repository — <code>fetch_data.sh</code> (FAO ASIS, GeoSahel, GAUL downloads), <code>build_indicators.py</code> (computation, including the trends and the per-year table), <code>inject_xlsx.py</code> (insertion into the workbook without breaking slicers and the data model), <code>gen_page.py</code> (this page).</li>
<li>CH context by département 2014–2026: <a href="../ipc_ch_evolution/">CH/IPC evolution report</a>. 2026 biomass tracking: <a href="../biomasse_check_2026/">window-3 check</a>.</li>
</ul>
<p class="small">Sources: CILSS/Cadre Harmonisé via HDX and OCHA Chad; FAO GIEWS ASIS (ASI); Action contre la Faim / GeoSahel BioGenerator; OCHA COD-AB Chad. Thresholds, weights and aggregation rules are OCHA CHD Data Science's and do not commit those producers.</p>
</div>
</main>
<div id="tip"></div>
<script>
const D = @@DATA@@;
const DEPTS = D.depts, YEARS = D.years, V = D.v;
const byPc = Object.fromEntries(DEPTS.map(d=>[d.pc,d]));
const CATCOL = {TE:'var(--te)', E:'var(--e)', M:'var(--m)', F:'var(--f)', NA:'var(--na)'};
const PAL = ['#2a78d6','#eb6834','#1baf7a','#7b5cd6','#e87ba4','#008300','#eda100','#c23b8f'];  // validated categorical palette (per-département lines when ≤ 8)
const W = {ch:.4, asi:.3, bio:.3};
const SC = {ch:v=>clip((v-10)/30), asi:v=>clip(v/40), bio:v=>clip((100-v)/50)};
const AGG = {ch:'max', asi:'max', bio:'min'};
function clip(x){ return Math.max(0, Math.min(1, x)); }
function catOf(v){ return v==null? 'NA' : v>=.6? 'TE' : v>=.4? 'E' : v>=.2? 'M' : 'F'; }
const TXT = {
  fr:{TE:'Très élevé',E:'Élevé',M:'Modéré',F:'Faible',NA:'Non disponible', idx:'Indice', rank:'rang', ch:'CH Ph3+', asi:'ASI détend.', bio:'Biomasse détend.', asi_raw:'ASI brut', bio_raw:'Biomasse brute', aa:'Zone AA sécheresse', sah:'Zone saharienne : scores aléa = 0',
      year:'Année', cons:'Consolidé', worst:'pire année', mean:'moyenne', official:'= indice officiel', none:'Aucun indicateur sélectionné', deps:'départements',
      capx:'Catégorie de l\'indice recalculé pour la sélection ci-dessus.', capts:'Une ligne par département ; couleur = catégorie de l\'indice consolidé 2024–2026 (plus de 8 lignes : survoler pour identifier).', captsd:'Une ligne par département, une couleur par département (légende ci-dessus).', nolines:'Aucun département dans la sélection.', val:'valeur', ofnormal:'% de la tendance', pct:'%'},
  en:{TE:'Very high',E:'High',M:'Moderate',F:'Low',NA:'Not available', idx:'Index', rank:'rank', ch:'CH Ph3+', asi:'Detr. ASI', bio:'Detr. biomass', asi_raw:'Raw ASI', bio_raw:'Raw biomass', aa:'AA drought zone', sah:'Saharan zone: hazard scores = 0',
      year:'Year', cons:'Consolidated', worst:'worst year', mean:'mean', official:'= official index', none:'No indicator selected', deps:'départements',
      capx:'Category of the index recomputed for the selection above.', capts:'One line per département; colour = category in the consolidated 2024–2026 index (more than 8 lines: hover to identify).', captsd:'One line per département, one colour per département (legend above).', nolines:'No département in the selection.', val:'value', ofnormal:'% of trend', pct:'%'}
};
let LANG = 'fr';
function T(k){ return TXT[LANG][k] || k; }
function fmt(v,d=1){ return v==null? '—' : v.toLocaleString(LANG==='fr'?'fr-FR':'en-GB',{minimumFractionDigits:d, maximumFractionDigits:d}); }
function setLang(l){ LANG=l; document.documentElement.dataset.lang=l; document.documentElement.lang=l; document.querySelectorAll('.langtoggle button').forEach(b=>b.classList.toggle('on', b.dataset.l===l)); try{localStorage.setItem('lang',l);}catch(e){} renderAll(); }
document.querySelectorAll('.langtoggle button').forEach(b=>b.addEventListener('click', ()=>setLang(b.dataset.l)));

// ---------- pillar values / index ----------
function pillar(pc, k, y0, y1, agg){
  const arr = V[pc][k]; const vals=[];
  for (let i=0;i<YEARS.length;i++){ if (YEARS[i]>=y0 && YEARS[i]<=y1 && arr[i]!=null) vals.push(arr[i]); }
  if (!vals.length) return null;
  if (agg==='mean') return vals.reduce((a,b)=>a+b,0)/vals.length;
  return AGG[k]==='max'? Math.max(...vals) : Math.min(...vals);
}
function scoreOf(pc, k, v){ if (v!=null) return SC[k](v); if (k!=='ch' && byPc[pc].sah) return 0; return null; }
function indexOf(pc, sel, y0, y1, agg){
  let num=0, den=0, parts={};
  for (const k of sel){ const v=pillar(pc,k,y0,y1,agg); const s=scoreOf(pc,k,v); parts[k]={v,s}; if (s==null) continue; num+=W[k]*s; den+=W[k]; }
  return {idx: den? num/den : null, parts};
}

// ---------- maps ----------
const tip = document.getElementById('tip');
function showTip(e, htmlStr){ tip.innerHTML=htmlStr; tip.style.display='block'; tip.style.left=(e.clientX+14)+'px'; tip.style.top=(e.clientY+14)+'px'; }
function legendHtml(el){ el.innerHTML = ['TE','E','M','F','NA'].map(c=>`<span><i style="background:${CATCOL[c]}"></i>${T(c)}</span>`).join(''); }
function paintMap(svg, valueFn, tipFn){
  svg.querySelectorAll('.dep').forEach(p=>{ const r=valueFn(p.dataset.pc); p.setAttribute('fill', CATCOL[catOf(r)]); p.onmousemove=e=>showTip(e, tipFn(p.dataset.pc)); p.onmouseleave=()=>tip.style.display='none'; });
}
const map0 = document.getElementById('map0'), map1 = document.getElementById('map1');
map1.innerHTML = map0.innerHTML;
function tip0(pc){ const d=byPc[pc]; return `<b>${d.dep} <span style="color:var(--muted);font-weight:400">(${d.prov})</span></b>${T('idx')} <strong>${fmt(d.idx,2)}</strong> · ${T(d.cat)} · ${T('rank')} ${d.rang}/70<br>CH ${fmt(d.s_ch,2)} (Ph3+ max ${fmt(d.ch_max,0)}%, 2026 ${fmt(d.ch_proj,0)}%)<br>ASI ${fmt(d.s_asi,2)} (max ${fmt(d.asi_max)}%) · ${T('bio')} ${fmt(d.s_bio,2)} (min ${fmt(d.bio_min,0)}%)${d.aa?'<br>'+T('aa'):''}${d.sah?'<br>'+T('sah'):''}`; }

// ---------- explorer ----------
const yrSel=document.getElementById('yr'), y0Sel=document.getElementById('y0'), y1Sel=document.getElementById('y1');
for (const s of [yrSel,y0Sel,y1Sel]) YEARS.forEach(y=>{ const o=document.createElement('option'); o.value=y; o.textContent=y; s.appendChild(o); });
yrSel.value=2026; y0Sel.value=2024; y1Sel.value=2026;
function xstate(){
  const mode=document.querySelector('input[name=mode]:checked').value; const agg=document.querySelector('input[name=agg]:checked').value;
  const sel=[...document.querySelectorAll('.ind:checked')].map(i=>i.value);
  let y0,y1; if (mode==='year'){ y0=y1=+yrSel.value; } else { y0=Math.min(+y0Sel.value,+y1Sel.value); y1=Math.max(+y0Sel.value,+y1Sel.value); }
  return {mode,agg,sel,y0,y1};
}
function renderExplorer(){
  const s=xstate(); const res={}; DEPTS.forEach(d=>res[d.pc]=indexOf(d.pc,s.sel,s.y0,s.y1,s.agg));
  paintMap(map1, pc=>res[pc].idx, pc=>{ const d=byPc[pc], r=res[pc]; const lines=s.sel.map(k=>`${T(k)} ${r.parts[k].s==null?'—':fmt(r.parts[k].s,2)} (${fmt(r.parts[k].v, k==='ch'||k==='asi'?0:0)}${k==='ch'||k==='asi'?'%':' '+T('ofnormal')})`).join('<br>'); return `<b>${d.dep} <span style="color:var(--muted);font-weight:400">(${d.prov})</span></b>${T('idx')} <strong>${fmt(r.idx,2)}</strong> · ${T(catOf(r.idx))}<br>${lines}${d.sah?'<br>'+T('sah'):''}`; });
  legendHtml(document.getElementById('legend1'));
  const counts={TE:0,E:0,M:0,F:0,NA:0}; DEPTS.forEach(d=>counts[catOf(res[d.pc].idx)]++);
  const isOfficial = s.mode==='range' && s.y0===2024 && s.y1===2026 && s.agg==='worst' && s.sel.length===3;
  const per = s.mode==='year'? `${T('year')} ${s.y0}` : `${T('cons')} ${s.y0}–${s.y1}, ${T(s.agg)}`;
  document.getElementById('xstat').innerHTML = s.sel.length? `${per} · ${s.sel.map(T).join(' + ')} → ${['TE','E','M','F','NA'].map(c=>`<span class="pill c-${c}">${T(c)} ${counts[c]}</span>`).join(' ')}${isOfficial?`<span class="official">${T('official')}</span>`:''}` : T('none');
  document.getElementById('xcap').textContent = T('capx');
  const rows = DEPTS.map(d=>({d, r:res[d.pc]})).filter(x=>x.r.idx!=null).sort((a,b)=>b.r.idx-a.r.idx);
  document.getElementById('xtb').innerHTML = rows.map((x,i)=>`<tr><td class="num">${i+1}</td><td>${x.d.dep}</td><td>${x.d.prov}</td><td class="num"><strong>${fmt(x.r.idx,2)}</strong></td><td><span class="pill c-${catOf(x.r.idx)}">${T(catOf(x.r.idx))}</span></td>${['ch','asi','bio'].map(k=>`<td class="num">${x.r.parts[k]? fmt(x.r.parts[k].v,0):'—'}</td>`).join('')}</tr>`).join('');
}
document.querySelectorAll('input[name=mode],input[name=agg],.ind,#yr,#y0,#y1').forEach(el=>el.addEventListener('change', renderExplorer));

// ---------- time series ----------
const tsvar=document.getElementById('tsvar'), tsprov=document.getElementById('tsprov'), tsy0=document.getElementById('tsy0'), tsy1=document.getElementById('tsy1');
[...new Set(DEPTS.map(d=>d.prov))].sort((a,b)=>a.localeCompare(b,'fr')).forEach(p=>{ const o=document.createElement('option'); o.value=p; o.textContent=p; tsprov.appendChild(o); });
for (const s of [tsy0,tsy1]) YEARS.forEach(y=>{ const o=document.createElement('option'); o.value=y; o.textContent=y; s.appendChild(o); });
tsy0.value=YEARS[0]; tsy1.value=YEARS[YEARS.length-1];
function renderTS(){
  const vr=tsvar.value; document.getElementById('tsindwrap').style.display = vr==='idx'?'':'none';
  const sel=[...document.querySelectorAll('.tsind:checked')].map(i=>i.value);
  const cats=new Set([...document.querySelectorAll('.tscat:checked')].map(i=>i.value)); const prov=tsprov.value; const aaOnly=document.getElementById('tsaa').checked;
  const y0=Math.min(+tsy0.value,+tsy1.value), y1=Math.max(+tsy0.value,+tsy1.value);
  const deps = DEPTS.filter(d=>cats.has(d.cat) && (!prov || d.prov===prov) && (!aaOnly || d.aa));
  const series = deps.map(d=>{ const pts=[]; YEARS.forEach((y,i)=>{ if (y<y0||y>y1) return; let v; if (vr==='idx'){ v = sel.length? indexOf(d.pc,sel,y,y,'worst').idx : null; } else { v=V[d.pc][vr][i]; } if (v!=null) pts.push([y,v]); }); return {d, pts}; }).filter(s=>s.pts.length);
  const svg=document.getElementById('ts'); const Wd=960, Ht=440, ml=48, mr=130, mt=16, mb=34;
  const xs=YEARS.filter(y=>y>=y0&&y<=y1); const x0=xs[0], x1=xs[xs.length-1];
  let ymax = vr==='idx'?1: vr==='ch'||vr==='asi'||vr==='asi_raw'? 100 : Math.min(300, Math.max(120, Math.ceil(Math.max(0,...series.flatMap(s=>s.pts.map(p=>p[1])))/20)*20));
  const X=y=> ml + (x1===x0?0:(y-x0)/(x1-x0))*(Wd-ml-mr), Y=v=> mt + (1-Math.min(v,ymax)/ymax)*(Ht-mt-mb);
  let g=''; const nty = vr==='idx'?5:5;
  for (let i=0;i<=nty;i++){ const v=ymax*i/nty; g+=`<line class="grid" x1="${ml}" x2="${Wd-mr}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--grid)"/><text class="tick" x="${ml-6}" y="${Y(v)+3.5}" text-anchor="end" style="font:10.5px system-ui;fill:var(--muted)">${vr==='idx'?v.toFixed(1):Math.round(v)}</text>`; }
  const step = xs.length>16?2:1; xs.forEach((y,i)=>{ if (y===x1 || (i%step===0 && x1-y>=step)) g+=`<text x="${X(y)}" y="${Ht-mb+16}" text-anchor="middle" style="font:10.5px system-ui;fill:var(--muted)">${y}</text>`; });
  if (vr==='bio'||vr==='bio_raw') g+=`<line x1="${ml}" x2="${Wd-mr}" y1="${Y(100)}" y2="${Y(100)}" stroke="var(--ink-2)" stroke-dasharray="4 4"/>`;
  if (vr==='idx') [.2,.4,.6].forEach(c=>{ g+=`<line x1="${ml}" x2="${Wd-mr}" y1="${Y(c)}" y2="${Y(c)}" stroke="var(--warn-border)" stroke-dasharray="2 5" opacity=".6"/>`; });
  let lines='', labels='';
  const perDept = series.length<=PAL.length; const colOf = (s,i)=> perDept? PAL[i] : CATCOL[s.d.cat];
  series.forEach((s,i)=>{ const dpath=s.pts.map((p,j)=>(j?'L':'M')+X(p[0]).toFixed(1)+','+Y(p[1]).toFixed(1)).join(' '); lines+=`<path class="tsline" data-i="${i}" d="${dpath}" stroke="${colOf(s,i)}"/>`; });
  if (series.length<=14){ const placed=[]; series.slice().sort((a,b)=>b.pts[b.pts.length-1][1]-a.pts[a.pts.length-1][1]).forEach(s=>{ const p=s.pts[s.pts.length-1]; let y=Y(p[1]); while (placed.some(q=>Math.abs(q-y)<11)) y+=11; placed.push(y); labels+=`<text class="tslabel" x="${X(p[0])+6}" y="${y+3.5}">${s.d.dep}</text>`; }); }
  svg.innerHTML = `<g class="axis">${g}</g><g id="tslines">${lines}</g><g>${labels}</g>`;
  svg.querySelectorAll('.tsline').forEach(p=>{ p.addEventListener('mousemove', e=>{ const s=series[+p.dataset.i]; svg.querySelectorAll('.tsline').forEach(q=>q.classList.toggle('tsdim', q!==p)); p.classList.add('hi');
      const pt=svg.createSVGPoint(); pt.x=e.clientX; pt.y=e.clientY; const loc=pt.matrixTransform(svg.getScreenCTM().inverse()); const yr=Math.round(x0+(loc.x-ml)/(Wd-ml-mr)*(x1-x0)); const hit=s.pts.find(q=>q[0]===yr);
      showTip(e, `<b>${s.d.dep} <span style="color:var(--muted);font-weight:400">(${s.d.prov})</span></b>${hit? yr+' : <strong>'+fmt(hit[1], vr==='idx'?2:0)+(vr==='idx'?'':vr==='ch'||vr==='asi'||vr==='asi_raw'?' %':vr==='bio'?' '+T('ofnormal'):' %')+'</strong><br>':''}${T('cons')} 2024–2026 : ${fmt(s.d.idx,2)} · ${T(s.d.cat)}`); });
    p.addEventListener('mouseleave', ()=>{ svg.querySelectorAll('.tsline').forEach(q=>{q.classList.remove('tsdim'); q.classList.remove('hi');}); tip.style.display='none'; }); });
  const lg=document.getElementById('legend2');
  if (perDept) lg.innerHTML = series.map((s,i)=>`<span><i style="background:${PAL[i]}"></i>${s.d.dep} <span class="pill c-${s.d.cat}" style="font-size:.68rem;padding:0 6px">${T(s.d.cat)}</span></span>`).join(''); else legendHtml(lg);
  document.getElementById('tscap').textContent = series.length? `${T(perDept?'captsd':'capts')} ${series.length} ${T('deps')}.` : T('nolines');
}
document.querySelectorAll('#tsvar,.tsind,.tscat,#tsprov,#tsaa,#tsy0,#tsy1').forEach(el=>el.addEventListener('change', renderTS));

// ---------- full table ----------
let sortK='rang', asc=true;
function renderTable(){
  const q=(document.getElementById('q').value||'').toLowerCase();
  let rows = DEPTS.filter(d=>!q || [d.dep,d.prov,T(d.cat),d.nom].join(' ').toLowerCase().includes(q));
  rows.sort((a,b)=>{ let x=a[sortK], y=b[sortK]; if (sortK==='cat'){ x=a.idx; y=b.idx; } if(x==null) return 1; if(y==null) return -1; if(typeof x==='string') return asc? x.localeCompare(y,'fr') : y.localeCompare(x,'fr'); if (typeof x==='boolean'){ x=+x; y=+y; } return asc? x-y : y-x; });
  const yn = b=> b? (LANG==='fr'?'Oui':'Yes') : (LANG==='fr'?'Non':'No');
  document.getElementById('tb').innerHTML = rows.map(d=>`<tr><td class="num">${d.rang}</td><td>${d.dep}</td><td>${d.prov}</td><td class="num"><strong>${fmt(d.idx,2)}</strong></td><td><span class="pill c-${d.cat}">${T(d.cat)}</span></td><td class="num">${d.ind}</td><td>${yn(d.aa)}</td><td class="num">${fmt(d.s_ch,2)}</td><td class="num">${fmt(d.ch_proj,0)}</td><td class="num">${fmt(d.ch_max,0)}</td><td class="num">${fmt(d.s_asi,2)}</td><td class="num">${fmt(d.asi_max)}</td><td class="num">${fmt(d.asi_raw)}</td><td class="num">${fmt(d.s_bio,2)}</td><td class="num">${fmt(d.bio_min,0)}</td><td class="num">${fmt(d.bio_raw,0)}</td><td class="num">${d.pop==null?'—':d.pop.toLocaleString(LANG==='fr'?'fr-FR':'en-GB')}</td></tr>`).join('');
  document.querySelectorAll('#tbl th').forEach(th=>{ th.classList.toggle('sorted', th.dataset.k===sortK); th.classList.toggle('asc', th.dataset.k===sortK && asc); });
}
document.querySelectorAll('#tbl th').forEach(th=>th.addEventListener('click', ()=>{ if(sortK===th.dataset.k) asc=!asc; else { sortK=th.dataset.k; asc = !['idx','cat','s_ch','s_asi','s_bio','ch_proj','ch_max','asi_max','asi_raw','bio_min','bio_raw','pop','ind','aa'].includes(sortK); } renderTable(); }));
document.getElementById('q').addEventListener('input', renderTable);

function renderAll(){ paintMap(map0, pc=>byPc[pc].idx, tip0); legendHtml(document.getElementById('legend0')); renderExplorer(); renderTS(); renderTable(); }
let l0='fr'; try{ l0 = new URLSearchParams(location.search).get('lang') || localStorage.getItem('lang') || 'fr'; }catch(e){}
setLang(l0==='en'?'en':'fr');
</script>
</body>
</html>
"""
page = (
    PAGE.replace("@@DATA@@", DATA)
    .replace("@@DEP_PATHS@@", DEP_PATHS)
    .replace("@@ADM1_PATHS@@", ADM1_PATHS)
    .replace("@@W@@", f"{W:.0f}")
    .replace("@@H@@", f"{H:.0f}")
    .replace("@@TOP_ROWS@@", top_rows)
    .replace("@@XLSX@@", XLSX)
    .replace("@@N_TE@@", str(n_te))
    .replace("@@N_E@@", str(n_e))
    .replace("@@N_IND@@", str(n_ind))
    .replace("@@POP_IND@@", f"{pop_ind:.1f}")
    .replace("@@AA_N@@", str(aa_te + aa_e))
    .replace("@@AA_TE@@", str(aa_te))
    .replace("@@AA_E@@", str(aa_e))
)
assert "@@" not in page
(OUT / "index.html").write_text(page, encoding="utf-8")
print("wrote", OUT / "index.html", len(page))
