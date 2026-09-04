"""Generate docs/hnrp_2027_secheresse/index.html (French write-up + map + table) from indicators.csv."""

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
adm2 = json.load(open(WORK / "adm2_simpl.geojson"))
adm1 = json.load(open(WORK / "adm1_simpl.geojson"))
m.to_csv(OUT / "indice_secheresse_adm2_2026-09-04.csv", index=False)

# ---------- map ----------
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


RAMP = ["#fff5eb", "#fdd0a2", "#fd8d3c", "#d94801", "#7f2704"]


def hexrgb(h):
    return tuple(int(h[i : i + 2], 16) for i in (1, 3, 5))


def color(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "#d8d8d8"
    t = max(0, min(1, v)) * (len(RAMP) - 1)
    i = int(math.floor(t))
    i = min(i, len(RAMP) - 2)
    f = t - i
    a, b = hexrgb(RAMP[i]), hexrgb(RAMP[i + 1])
    return "#%02x%02x%02x" % tuple(
        int(round(a[k] + (b[k] - a[k]) * f)) for k in range(3)
    )


byp = m.set_index("ADM2_PCODE")
paths = []
for f in adm2["features"]:
    pc = f["properties"]["ADM2_PCODE"]
    r = byp.loc[pc]
    paths.append(
        f'<path class="dep" data-pc="{pc}" d="{path(f["geometry"])}" fill="{color(r.indice_secheresse)}"/>'
    )
p1 = "".join(f'<path d="{path(f["geometry"])}"/>' for f in adm1["features"])
grad = "".join(
    f'<stop offset="{i/(len(RAMP)-1)*100:.0f}%" stop-color="{c}"/>'
    for i, c in enumerate(RAMP)
)
svg_map = (
    f'<svg viewBox="0 0 {W:.0f} {H:.0f}" role="img" aria-label="Carte de l\'indice sécheresse par département">'
    f'<g id="deps">{"".join(paths)}</g><g class="adm1" fill="none">{p1}</g></svg>'
)
legend = (
    f'<svg class="legend" viewBox="0 0 320 52" aria-hidden="true"><defs><linearGradient id="g">{grad}</linearGradient></defs>'
    '<rect x="10" y="16" width="300" height="12" fill="url(#g)" rx="2"/>'
    + "".join(
        f'<line x1="{10+300*v}" y1="14" x2="{10+300*v}" y2="32" class="tickline"/><text x="{10+300*v}" y="45" class="tick" text-anchor="middle">{v:.1f}</text>'
        for v in [0, 0.2, 0.4, 0.6, 0.8, 1.0]
    )
    + '<text x="40" y="10" class="tick" text-anchor="middle">Faible</text><text x="100" y="10" class="tick" text-anchor="middle">Modéré</text><text x="160" y="10" class="tick" text-anchor="middle">Élevé</text><text x="250" y="10" class="tick" text-anchor="middle">Très élevé</text></svg>'
)


# ---------- data for JS ----------
def f1(v):
    return None if pd.isna(v) else round(float(v), 1)


def f2(v):
    return None if pd.isna(v) else round(float(v), 2)


rows = []
for _, r in m.iterrows():
    rows.append(
        dict(
            pc=r.ADM2_PCODE,
            prov=r.ADM1_FR,
            dep=r.ADM2_FR,
            nom=r.nom_fichier,
            aa=r.zone_aa,
            sah=r.zone_saharienne,
            pop=(
                None
                if pd.isna(r.population_ch_2026)
                else int(r.population_ch_2026)
            ),
            idx=f2(r.indice_secheresse),
            rang=int(r.rang),
            cat=r.categorie,
            ind=int(r.indicateur_secheresse),
            s_ch=f2(r.score_ch),
            s_asi=f2(r.score_asi),
            s_bio=f2(r.score_bio),
            s_pl=f2(r.score_pluie),
            ch_proj=f1(r.ch_p3_pct_proj_2026),
            ch_max=f1(r.ch_p3_pct_max_2024_2026),
            ch_ph=(
                None
                if pd.isna(r.ch_phase_max_2024_2026)
                else int(r.ch_phase_max_2024_2026)
            ),
            asi24=f1(r.asi_2024),
            asi25=f1(r.asi_2025),
            asi26=f1(r.asi_2026),
            asi_max=f1(r.asi_max_2024_2026),
            bio24=f1(r.bio_2024),
            bio25=f1(r.bio_2025),
            bio26=f1(r.bio_2026),
            bio_min=f1(r.bio_min_2024_2026),
            pl24=f1(r.pluie_2024),
            pl25=f1(r.pluie_2025),
            pl26=f1(r.pluie_2026),
            pl_min=f1(r.pluie_min_2024_2026),
            notes=r.notes or "",
        )
    )
DATA = json.dumps(rows, ensure_ascii=False)

n_te = (m.categorie == "Très élevé").sum()
n_e = (m.categorie == "Élevé").sum()
n_ind = int(m.indicateur_secheresse.sum())
pop_ind = m[m.indicateur_secheresse == 1].population_ch_2026.sum() / 1e6
aa = m[m.zone_aa == "Oui"]
aa_te = (aa.categorie == "Très élevé").sum()
aa_e = (aa.categorie == "Élevé").sum()
top = m.head(10)
top_rows = "".join(
    f'<tr><td>{r.rang}</td><td>{html.escape(r.ADM2_FR)}</td><td>{html.escape(r.ADM1_FR)}</td><td class="num">{r.indice_secheresse:.2f}</td><td><span class="pill c-{r.categorie[0]}">{r.categorie}</span></td><td class="num">{r.score_ch:.2f}</td><td class="num">{r.score_asi:.2f}</td><td class="num">{r.score_bio:.2f}</td><td class="num">{r.score_pluie:.2f}</td><td>{r.zone_aa}</td></tr>'
    for _, r in top.iterrows()
)

page = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tchad HNRP 2027 — indice de risque sécheresse par département</title>
<style>
:root {{ color-scheme: light; --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink-2:#52514e; --muted:#898781; --grid:#e1e0d9; --border:rgba(11,11,11,.10);
  --accent:#d94801; --warn-bg:#fff7ec; --warn-border:#d94801; --te:#7f2704; --e:#d94801; --m:#fd8d3c; --f:#fdd0a2; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ color-scheme:dark; --page:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink-2:#c3c2b7; --muted:#898781; --grid:#2c2c2a; --border:rgba(255,255,255,.12); --warn-bg:#2a1c10; }} }}
:root[data-theme="dark"] {{ color-scheme:dark; --page:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink-2:#c3c2b7; --muted:#898781; --grid:#2c2c2a; --border:rgba(255,255,255,.12); --warn-bg:#2a1c10; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--page); color:var(--ink); font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif; }}
main {{ max-width:1080px; margin:0 auto; padding:24px 20px 64px; }}
a {{ color:var(--accent); }}
.home {{ display:inline-block; font-size:.85rem; color:var(--ink-2); text-decoration:none; border:1px solid var(--border); border-radius:6px; padding:3px 10px; }}
h1 {{ font-size:1.5rem; margin:18px 0 4px; }} h2 {{ font-size:1.12rem; margin:38px 0 10px; border-bottom:1px solid var(--grid); padding-bottom:4px; }} h3 {{ font-size:1rem; margin:20px 0 6px; }}
.sub {{ color:var(--ink-2); margin:0 0 16px; }}
.banner {{ background:var(--warn-bg); border:2px solid var(--warn-border); border-radius:10px; padding:12px 18px; margin:16px 0 22px; }}
.banner strong {{ display:block; margin-bottom:4px; }}
.tiles {{ display:flex; flex-wrap:wrap; gap:12px; margin:0 0 20px; }}
.tile {{ flex:1 1 180px; background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:12px 16px 14px; }}
.tile .k {{ font-size:.76rem; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; }}
.tile .v {{ font-size:1.6rem; font-weight:650; margin-top:2px; }} .tile .d {{ font-size:.82rem; color:var(--ink-2); }}
.maprow {{ display:grid; grid-template-columns: minmax(280px, 480px) 1fr; gap:20px; align-items:start; }}
@media (max-width:760px) {{ .maprow {{ grid-template-columns:1fr; }} }}
figure {{ margin:0; background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:12px; }}
figcaption {{ font-size:.82rem; color:var(--ink-2); padding:6px 4px 2px; }}
svg {{ width:100%; height:auto; display:block; }}
.dep {{ stroke:#fff; stroke-width:.6; cursor:pointer; }} .dep:hover {{ stroke:var(--ink); stroke-width:1.6; }}
.adm1 path {{ stroke:#5a5a5a; stroke-width:1.1; pointer-events:none; }}
.legend {{ max-width:340px; margin:6px 0 0; }} .tick {{ font:10.5px system-ui,sans-serif; fill:var(--muted); }} .tickline {{ stroke:var(--muted); stroke-width:1; }}
#tip {{ position:fixed; pointer-events:none; background:var(--surface); color:var(--ink); border:1px solid var(--border); border-radius:8px; padding:8px 10px; font-size:.82rem; box-shadow:0 4px 14px rgba(0,0,0,.15); display:none; max-width:280px; z-index:10; }}
#tip b {{ display:block; font-size:.9rem; }}
table {{ border-collapse:collapse; width:100%; font-size:.85rem; }} th, td {{ padding:5px 7px; border-bottom:1px solid var(--grid); text-align:left; vertical-align:top; }}
th {{ background:var(--surface); position:sticky; top:0; cursor:pointer; user-select:none; font-weight:600; white-space:nowrap; }} th.sorted::after {{ content:" ▾"; color:var(--muted); }} th.asc::after {{ content:" ▴"; }}
td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
.tablewrap {{ overflow-x:auto; border:1px solid var(--border); border-radius:10px; background:var(--surface); max-height:640px; overflow-y:auto; }}
.pill {{ display:inline-block; padding:1px 8px; border-radius:999px; font-size:.78rem; font-weight:600; color:#fff; white-space:nowrap; }}
.c-T {{ background:var(--te); }} .c-É {{ background:var(--e); }} .c-M {{ background:var(--m); color:#1a1a19; }} .c-F {{ background:var(--f); color:#1a1a19; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:12px; }}
.card {{ background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:12px 16px; font-size:.9rem; }}
.card h3 {{ margin:0 0 6px; }} .card dl {{ margin:0; }} .card dt {{ color:var(--muted); font-size:.75rem; text-transform:uppercase; letter-spacing:.04em; margin-top:8px; }} .card dd {{ margin:0; }}
code {{ background:var(--grid); padding:1px 5px; border-radius:4px; font-size:.85em; }}
.formula {{ background:var(--surface); border:1px solid var(--border); border-radius:8px; padding:10px 14px; font-family:ui-monospace,Menlo,monospace; font-size:.85rem; overflow-x:auto; white-space:pre; }}
.small {{ font-size:.85rem; color:var(--ink-2); }}
.dl {{ margin:0 0 16px; font-size:.95rem; }} .dl a {{ font-weight:600; }}
ul {{ padding-left:20px; }} li {{ margin:3px 0; }}
.ctrl {{ margin:8px 0; font-size:.85rem; color:var(--ink-2); }} .ctrl input {{ padding:4px 8px; border:1px solid var(--border); border-radius:6px; background:var(--surface); color:var(--ink); }}
</style>
</head>
<body>
<main>
<a class="home" href="../">← ds-aa-tcd-drought · rapports</a>
<h1>Tchad — HNRP 2027 : indice de risque sécheresse par département</h1>
<p class="sub">Données secondaires 2024–2026 (Cadre Harmonisé, FAO ASI, biomasse GeoSahel, pluie) combinées en un indice 0–1 pour les 70 départements, à verser dans la feuille « Indice sécheresse » du classeur <em>TCD_HNRP 2027_ANALYSE DES CHOCS</em>. Construit le 4 septembre 2026 par OCHA CHD Data Science.</p>

<div class="banner"><strong>À lire avant usage</strong>
L'indice est un outil de <em>priorisation relative</em> entre départements, sur le même principe que les pondérations « Priorisationzone » déjà utilisées dans le classeur (scores 0–1, moyenne pondérée). La saison 2026 est en cours : les valeurs 2026 d'ASI, de biomasse et de pluie s'arrêtent au 21 août / à la décade 23 et seront révisées. Les seuils et poids sont des choix de méthode, exposés ci-dessous et modifiables directement dans la feuille Excel (ligne 3).
Le classeur contient déjà des impacts « catastrophe naturelle » 2022 et 2024 (inondations) : aucun indice inondation n'a été ajouté — voir la section dédiée.</div>

<p class="dl"><a href="TCD_HNRP_2027_ANALYSE_DES_CHOCS_ALL_v2_secheresse.xlsx" download>⬇ Télécharger le classeur Excel mis à jour (v2_secheresse, 0,4 Mo)</a> · <a href="indice_secheresse_adm2_2026-09-04.csv" download>CSV de l'indice</a></p>
<div class="tiles">
<div class="tile"><div class="k">Très élevé</div><div class="v">{n_te}</div><div class="d">départements (indice ≥ 0,60)</div></div>
<div class="tile"><div class="k">Élevé</div><div class="v">{n_e}</div><div class="d">départements (0,40 – 0,59)</div></div>
<div class="tile"><div class="k">Indicateur_Sécheresse = 1</div><div class="v">{n_ind}</div><div class="d">départements avec indice ≥ 0,50 — {pop_ind:.1f} M habitants (pop. CH 2026)</div></div>
<div class="tile"><div class="k">Zone AA sécheresse (22 dép.)</div><div class="v">{aa_te + aa_e}</div><div class="d">{aa_te} très élevé + {aa_e} élevé ; cadre CERF activé fenêtres 1 &amp; 2 en 2026</div></div>
</div>

<h2>Carte et classement</h2>
<div class="maprow">
<figure>{svg_map}{legend}<figcaption>Indice sécheresse 0–1 par département (COD ADM2). Traits foncés : provinces. Survoler un département pour le détail.</figcaption></figure>
<div>
<h3 style="margin-top:0">Dix départements les plus prioritaires</h3>
<div class="tablewrap" style="max-height:none"><table><thead><tr><th>#</th><th>Département</th><th>Province</th><th>Indice</th><th>Catégorie</th><th>CH</th><th>ASI</th><th>Biom.</th><th>Pluie</th><th>Zone AA</th></tr></thead><tbody>{top_rows}</tbody></table></div>
<p class="small">Colonnes CH / ASI / Biom. / Pluie = scores 0–1 de chaque pilier. Lecture : les départements sahéliens de la zone AA (Kanem, Lac, Ouaddaï, Wadi Fira, Batha, Barh-El-Gazel) cumulent une insécurité alimentaire élevée depuis 2024 et un effondrement de la biomasse en 2026 ; les départements du sud (Logone Occidental et Oriental, Mandoul, Tandjilé) ressortent par le stress agricole (ASI) des saisons 2025 et 2026.</p>
</div>
</div>

<h2>Tableau complet (70 départements)</h2>
<div class="ctrl">Filtrer : <input id="q" placeholder="département, province, catégorie…"> · cliquer un en-tête pour trier · <a href="indice_secheresse_adm2_2026-09-04.csv">télécharger le CSV</a></div>
<div class="tablewrap"><table id="tbl"><thead><tr>
<th data-k="rang">Rang</th><th data-k="dep">Département</th><th data-k="prov">Province</th><th data-k="idx">Indice</th><th data-k="cat">Catégorie</th><th data-k="ind">Indic.</th><th data-k="aa">Zone AA</th>
<th data-k="s_ch">Score CH</th><th data-k="ch_proj">CH Ph3+ % proj. 2026</th><th data-k="ch_max">CH Ph3+ % max 24–26</th>
<th data-k="s_asi">Score ASI</th><th data-k="asi_max">ASI max 24–26 (%)</th>
<th data-k="s_bio">Score biom.</th><th data-k="bio_min">Biom. min 24–26 (%)</th>
<th data-k="s_pl">Score pluie</th><th data-k="pl_min">Pluie min 24–26 (%)</th><th data-k="pop">Pop. CH 2026</th></tr></thead><tbody id="tb"></tbody></table></div>

<h2>Indicateurs retenus</h2>
<p>Quatre piliers, tous à l'échelle du département (COD ADM2, 70 unités), sur la fenêtre 2024–2026 pour rester cohérent avec la portée « données secondaires » du classeur. Un pilier « résultat » (insécurité alimentaire) et trois piliers « aléa » (cultures, pâturages, pluie) qui décrivent la sécheresse agro-pastorale elle-même.</p>
<div class="cards">
<div class="card"><h3>1 · Cadre Harmonisé (CH/IPC)</h3><dl>
<dt>Source</dt><dd>Fichier consolidé CH sur HDX (<code>cadre-harmonise</code>) + classeur officiel CH mai 2026 partagé par OCHA Tchad. Pipeline <code>src/datasources/ipc.py</code> de ce dépôt.</dd>
<dt>Couverture</dt><dd>8 analyses de 2024 à 2026 : courant mars–mai et projeté juin–août de chaque cycle, plus courant oct–déc 2024 et 2025. 69 départements (N'Djaména non analysé).</dd>
<dt>Variables</dt><dd>% de population en phase 3+ : projeté juin–août 2026 (soudure en cours), et <strong>maximum sur les 8 analyses</strong> ; phase de zone maximale (règle des 20 %) ; personnes en phase 3+.</dd>
<dt>Pourquoi</dt><dd>Résultat humanitaire directement lié aux chocs sécheresse récents ; c'est aussi la donnée que les clusters connaissent.</dd></dl></div>
<div class="card"><h3>2 · FAO ASI — stress agricole</h3><dl>
<dt>Source</dt><dd>FAO GIEWS ASIS, série décadaire par unité administrative (<code>ASI_Dekad_Season1</code>, masque cultures), page pays TCD.</dd>
<dt>Définition</dt><dd>% de la surface cultivée dont l'indice de santé de la végétation (VHI) est &lt; 35. Moyenne des décades du <strong>1er juin au 21 août</strong> de chaque année (même fenêtre pour 2024, 2025 et 2026 afin d'être comparable avec la saison 2026 en cours) ; valeur retenue = maximum 2024–2026.</dd>
<dt>Échelle</dt><dd>FAO publie sur les 28 anciens départements (GAUL 2015). Report sur les 70 départements COD par intersection surfacique (moyenne pondérée par la surface) — la valeur est donc partagée par les départements issus d'une même ancienne unité.</dd>
<dt>Pourquoi</dt><dd>Signal « cultures » qui capte les poches sèches du sud (Logone, Mandoul, Tandjilé) invisibles dans la biomasse pastorale.</dd></dl></div>
<div class="card"><h3>3 · Biomasse — GeoSahel / Action contre la Faim</h3><dl>
<dt>Source</dt><dd>Couche WFS <code>Biomass:WA_BIO_ADM2_v4</code> (productivité de matière sèche DMP décadaire, 1999→décade 23 de 2026), même fournisseur que la fenêtre 3 du cadre AA sécheresse.</dd>
<dt>Définition</dt><dd>Production cumulée des décades 10 à 23 (1er avril – 20 août) rapportée à la moyenne 1999–2024 de la même fenêtre, en % ; valeur retenue = minimum 2024–2026. Non applicable dans les provinces sahariennes (Borkou, Ennedi Est/Ouest, Tibesti : production de base quasi nulle).</dd>
<dt>Pourquoi</dt><dd>Signal « pâturages / élevage » ; 2026 est la pire saison de la série dans la bande sahélienne (Kanem, Lac, Batha, Wadi Fira, Ouaddaï à 30–60 % de la normale).</dd></dl></div>
<div class="card"><h3>4 · Pluie estimée (FEWS NET RFE via FAO ASIS)</h3><dl>
<dt>Source</dt><dd>Série <code>rain_adm1_data</code> de FAO ASIS (RFE FEWS NET, masque cultures, avec normale de long terme), mêmes 28 unités GAUL reportées sur les 70 départements.</dd>
<dt>Définition</dt><dd>Cumul du 1er juin au 21 août en % de la normale ; valeur retenue = minimum 2024–2026. Non applicable en zone saharienne.</dd>
<dt>Pourquoi</dt><dd>Aléa météorologique brut, indépendant des masques cultures/pâturages ; confirme le déficit 2026 sur l'est et le nord (Wadi Fira, Batha Est ≈ 73–78 % de la normale).</dd></dl></div>
</div>
<p class="small">Colonnes de contexte ajoutées sans entrer dans l'indice : population CH 2026, appartenance à la zone du cadre d'action anticipatoire sécheresse (7 provinces : Batha, Kanem, Lac, Wadi Fira, Barh-El-Gazel, Sila, Ouaddaï ; fenêtres 1 et 2 déclenchées les 30 avril et 9 mai 2026, fenêtre 3 en cours de vérification sur la décade 24), p-codes COD et p-codes/orthographes du classeur HNRP.</p>

<h2>Construction de l'indice</h2>
<p>Chaque pilier est transformé en un <strong>score 0–1</strong> par interpolation linéaire entre deux seuils fixes (0 = pas de signal, 1 = signal maximal, bornés), puis les scores sont moyennés avec des poids. Les seuils sont absolus (pas des rangs) pour que l'indice reste comparable si l'on met à jour une seule source.</p>
<div class="formula">Score CH        = clip( (CH Ph3+ max 2024–2026  − 10 %) / (40 % − 10 %) , 0, 1 )
Score ASI       = clip(  ASI max 2024–2026 / 40 %                     , 0, 1 )
Score biomasse  = clip( (100 % − biomasse min 2024–2026) / (100 % − 50 %) , 0, 1 )
Score pluie     = clip( (100 % − pluie min 2024–2026)    / (100 % − 60 %) , 0, 1 )

Indice sécheresse = ( 0,4·CH + 0,2·ASI + 0,2·biomasse + 0,2·pluie ) / (somme des poids des scores disponibles)

Catégorie : Très élevé ≥ 0,60 · Élevé 0,40–0,59 · Modéré 0,20–0,39 · Faible &lt; 0,20
Indicateur_Sécheresse = 1 si indice ≥ 0,50 (même logique que le seuil 50 % du classeur), sinon 0</div>
<ul>
<li><strong>Poids</strong> : 40 % au résultat (CH), 60 % répartis également entre les trois signaux d'aléa, de façon à ce que l'indice ne soit pas une simple copie du CH mais reflète bien la sécheresse agro-pastorale 2024–2026.</li>
<li><strong>Seuils</strong> : 10–40 % de population en phase 3+ couvre l'étendue observée (9–44 %) ; 40 % de surface cultivée stressée correspond à un stress sévère au sens FAO ; 50 % de la biomasse normale et 60 % de la pluie normale marquent les pires années de la série dans le Sahel tchadien.</li>
<li><strong>Zone saharienne</strong> (8 départements de Borkou, Ennedi Est, Ennedi Ouest, Tibesti) : ASI, biomasse et pluie n'ont pas de sens (pas de cultures, production de base ≈ 0, anomalies pluie de plusieurs centaines de %). Les scores d'aléa y sont fixés à 0 — l'indice n'y reflète que le CH, pondéré à 0,4 — plutôt que de laisser un CH seul remonter ces départements en tête. Leur insécurité alimentaire (22–31 % en phase 3+) est bien visible dans les colonnes CH.</li>
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
<li><strong>Saison 2026 en cours</strong> : ASI, biomasse et pluie 2026 s'arrêtent au 21 août (décade 23). Ils seront mis à jour quand la décade 24 sera publiée (vérification officielle de la fenêtre 3 du cadre AA) ; le CH de novembre 2026 pourra remplacer la projection juin–août.</li>
<li><strong>Report des anciennes unités FAO</strong> : ASI et pluie sont publiés par FAO sur 28 unités (GAUL 2015, ≈ anciens départements). Les départements actuels d'une même ancienne unité partagent la même valeur — l'ASI ne différencie pas, par exemple, les quatre départements du Logone Occidental.</li>
<li><strong>Biomasse au niveau département</strong> : dans les départements à faible production de base (Barh-El-Gazel Nord, Nord Kanem, Mégri, Biltine), l'anomalie relative est bruitée ; elle reste cohérente avec le signal provincial (Kanem ≈ 30 % de la normale) utilisé par le cadre AA.</li>
<li><strong>P-codes et noms du classeur</strong> : la feuille « Listes departements inclus » intervertit les p-codes d'Abdi (COD TCD1402, Ouaddaï) et de Djourf Al Ahmar (COD TCD2102, Sila) et code Mourtcha TCD2302 (COD TCD2303). La jointure a été faite sur les noms ; les deux p-codes sont fournis dans la feuille.</li>
<li><strong>Population</strong> : la population « CH 2026 » sert de contexte ; elle diffère des populations utilisées dans les feuilles conflit/épidémie du classeur.</li>
<li><strong>Un indice n'est pas une décision</strong> : il ordonne les départements sur le seul aléa sécheresse et ses effets alimentaires récents ; il doit être lu avec les pondérations conflit, épidémie et inondation du Recap et les retours des clusters.</li>
</ul>

<h2>Fichiers et reproduction</h2>
<ul>
<li>Classeur mis à jour : <a href="TCD_HNRP_2027_ANALYSE_DES_CHOCS_ALL_v2_secheresse.xlsx" download><strong>TCD_HNRP 2027_ANALYSE DES CHOCS_ALL_v2_secheresse.xlsx</strong></a> (classeur original + feuille « Indice sécheresse » + colonnes AI–AL du Recap).</li>
<li>Table plate : <a href="indice_secheresse_adm2_2026-09-04.csv">indice_secheresse_adm2_2026-09-04.csv</a> (toutes les colonnes de la feuille, en anglais technique).</li>
<li>Scripts : <code>analysis/hnrp_2027_secheresse/</code> dans le dépôt <a href="https://github.com/OCHA-DAP/ds-aa-tcd-drought">ds-aa-tcd-drought</a> — <code>fetch_data.sh</code> (téléchargements FAO ASIS, GeoSahel, GAUL), <code>build_indicators.py</code> (calcul), <code>inject_xlsx.py</code> (insertion dans le classeur sans casser les segments et le modèle de données), <code>gen_page.py</code> (cette page).</li>
<li>Contexte CH par département 2014–2026 : <a href="../ipc_ch_evolution/">rapport d'évolution CH/IPC</a>. Suivi biomasse 2026 : <a href="../biomasse_check_2026/">vérification fenêtre 3</a>.</li>
</ul>
<p class="small">Sources : CILSS/Cadre Harmonisé via HDX et OCHA Tchad ; FAO GIEWS ASIS (ASI, RFE FEWS NET) ; Action contre la Faim / GeoSahel BioGenerator ; OCHA COD-AB Tchad. Les seuils, poids et règles d'agrégation sont ceux d'OCHA CHD Data Science et n'engagent pas ces producteurs.</p>
</main>
<div id="tip"></div>
<script>
const DATA = {DATA};
const byPc = Object.fromEntries(DATA.map(d=>[d.pc,d]));
const fmt = (v,d=1)=> v==null? '—' : v.toLocaleString('fr-FR',{{minimumFractionDigits:d, maximumFractionDigits:d}});
const tip = document.getElementById('tip');
document.querySelectorAll('.dep').forEach(p=>{{
  p.addEventListener('mousemove', e=>{{
    const d = byPc[p.dataset.pc]; if(!d) return;
    tip.innerHTML = `<b>${{d.dep}} <span style="color:var(--muted);font-weight:400">(${{d.prov}})</span></b>Indice <strong>${{fmt(d.idx,2)}}</strong> · ${{d.cat}} · rang ${{d.rang}}/70<br>CH ${{fmt(d.s_ch,2)}} (Ph3+ max ${{fmt(d.ch_max,0)}} %, proj. 2026 ${{fmt(d.ch_proj,0)}} %)<br>ASI ${{fmt(d.s_asi,2)}} (max ${{fmt(d.asi_max)}} %) · Biomasse ${{fmt(d.s_bio,2)}} (min ${{fmt(d.bio_min,0)}} %) · Pluie ${{fmt(d.s_pl,2)}} (min ${{fmt(d.pl_min,0)}} %)${{d.aa==='Oui'?'<br>Zone AA sécheresse':''}}${{d.sah==='Oui'?'<br>Zone saharienne : scores aléa = 0':''}}`;
    tip.style.display='block'; tip.style.left=(e.clientX+14)+'px'; tip.style.top=(e.clientY+14)+'px';
  }});
  p.addEventListener('mouseleave', ()=>tip.style.display='none');
}});
let sortK='rang', asc=true;
function render(){{
  const q=(document.getElementById('q').value||'').toLowerCase();
  let rows = DATA.filter(d=>!q || [d.dep,d.prov,d.cat,d.nom,d.aa].join(' ').toLowerCase().includes(q));
  rows.sort((a,b)=>{{ let x=a[sortK], y=b[sortK]; if(x==null) return 1; if(y==null) return -1; if(typeof x==='string') return asc? x.localeCompare(y,'fr') : y.localeCompare(x,'fr'); return asc? x-y : y-x; }});
  document.getElementById('tb').innerHTML = rows.map(d=>`<tr><td class="num">${{d.rang}}</td><td>${{d.dep}}</td><td>${{d.prov}}</td><td class="num"><strong>${{fmt(d.idx,2)}}</strong></td><td><span class="pill c-${{d.cat[0]}}">${{d.cat}}</span></td><td class="num">${{d.ind}}</td><td>${{d.aa}}</td><td class="num">${{fmt(d.s_ch,2)}}</td><td class="num">${{fmt(d.ch_proj,0)}}</td><td class="num">${{fmt(d.ch_max,0)}}</td><td class="num">${{fmt(d.s_asi,2)}}</td><td class="num">${{fmt(d.asi_max)}}</td><td class="num">${{fmt(d.s_bio,2)}}</td><td class="num">${{fmt(d.bio_min,0)}}</td><td class="num">${{fmt(d.s_pl,2)}}</td><td class="num">${{fmt(d.pl_min,0)}}</td><td class="num">${{d.pop==null?'—':d.pop.toLocaleString('fr-FR')}}</td></tr>`).join('');
  document.querySelectorAll('#tbl th').forEach(th=>{{ th.classList.toggle('sorted', th.dataset.k===sortK); th.classList.toggle('asc', th.dataset.k===sortK && asc); }});
}}
document.querySelectorAll('#tbl th').forEach(th=>th.addEventListener('click', ()=>{{ if(sortK===th.dataset.k) asc=!asc; else {{ sortK=th.dataset.k; asc = !['idx','s_ch','s_asi','s_bio','s_pl','ch_proj','ch_max','asi_max','pop','ind'].includes(sortK); }} render(); }}));
document.getElementById('q').addEventListener('input', render);
render();
</script>
</body>
</html>"""
(OUT / "index.html").write_text(page + "\n", encoding="utf-8")
print("wrote", OUT / "index.html", len(page))
