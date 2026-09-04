"""Add an 'Indice sécheresse' sheet + 4 lookup columns on Recap to the HNRP workbook by direct XML edit
(keeps slicers, pivot caches and the Power Pivot data model that openpyxl would drop)."""

# flake8: noqa

import html
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd

SRC = Path(sys.argv[1])
OUT = Path(sys.argv[2])
IND = Path(sys.argv[3])
m = pd.read_csv(IND, keep_default_na=False, na_values=[""])
m = m.sort_values(["ADM1_FR", "ADM2_FR"]).reset_index(drop=True)
N = len(m)
R0 = 6
R1 = R0 + N - 1  # data rows 6..75
SHEET = "Indice sécheresse"


def col(i):  # 1-based -> letters
    s = ""
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def esc(s):
    return html.escape(str(s), quote=False)


def cs(ref, v, s=None):  # inline string cell
    if v is None or (isinstance(v, float) and np.isnan(v)) or v == "":
        return ""
    st = f' s="{s}"' if s is not None else ""
    return f'<c r="{ref}" t="inlineStr"{st}><is><t xml:space="preserve">{esc(v)}</t></is></c>'


def cn(ref, v, s=None):
    if v is None or (isinstance(v, float) and np.isnan(v)) or v == "":
        return ""
    st = f' s="{s}"' if s is not None else ""
    return f'<c r="{ref}"{st}><v>{float(v):.10g}</v></c>'


def cf(ref, formula, cached, s=None):
    st = f' s="{s}"' if s is not None else ""
    if (
        cached is None
        or cached == ""
        or (isinstance(cached, float) and np.isnan(cached))
    ):
        return f'<c r="{ref}" t="str"{st}><f>{esc(formula)}</f></c>'
    if isinstance(cached, str):
        return f'<c r="{ref}" t="str"{st}><f>{esc(formula)}</f><v>{esc(cached)}</v></c>'
    return f'<c r="{ref}"{st}><f>{esc(formula)}</f><v>{float(cached):.10g}</v></c>'


# ---------- styles ----------
S_HDR, S_TITLE, S_INT, S_1DP, S_2DP, S_PARAM, S_NOTE, S_WRAP, S_SUB = (
    65,
    66,
    67,
    68,
    69,
    70,
    71,
    72,
    73,
)
DXF_TE, DXF_E, DXF_M, DXF_F = 63, 64, 65, 66

COLS = [  # header, field, kind
    ("Province", "ADM1_FR", "txt"),
    ("Département", "ADM2_FR", "txt"),
    ("P-code (COD)", "pcode_ch", "txt"),
    ("P-code (fichier HNRP)", "pcode_fichier", "txt"),
    ("Nom (fichier HNRP / Recap)", "nom_fichier", "txt"),
    ("Zone AA sécheresse (cadre CERF 2025)", "zone_aa", "txt"),
    ("Zone saharienne", "zone_saharienne", "txt"),
    ("Population (CH 2026)", "population_ch_2026", "int"),
    ("CH Ph3+ (%) courant mars–mai 2026", "ch_p3_pct_cur_2026", "1dp"),
    ("CH Ph3+ (%) projeté juin–août 2026", "ch_p3_pct_proj_2026", "1dp"),
    ("CH Ph3+ (pers.) projeté juin–août 2026", "ch_p3_pop_proj_2026", "int"),
    (
        "CH Ph3+ (%) max 2024–2026 (8 analyses)",
        "ch_p3_pct_max_2024_2026",
        "1dp",
    ),
    ("CH phase zone max 2024–2026", "ch_phase_max_2024_2026", "int"),
    ("Score CH (0–1)", "score_ch", "f2"),
    ("ASI 2024 (% cultures stressées)", "asi_2024", "1dp"),
    ("ASI 2025 (%)", "asi_2025", "1dp"),
    ("ASI 2026 à date (%)", "asi_2026", "1dp"),
    ("ASI max 2024–2026", "asi_max_2024_2026", "f1"),
    ("Score ASI (0–1)", "score_asi", "f2"),
    ("Biomasse 2024 (% de la moyenne 1999–2024)", "bio_2024", "1dp"),
    ("Biomasse 2025 (%)", "bio_2025", "1dp"),
    ("Biomasse 2026 à date (%)", "bio_2026", "1dp"),
    ("Biomasse min 2024–2026", "bio_min_2024_2026", "f1"),
    ("Score biomasse (0–1)", "score_bio", "f2"),
    ("Pluie 2024 (% de la normale)", "pluie_2024", "1dp"),
    ("Pluie 2025 (%)", "pluie_2025", "1dp"),
    ("Pluie 2026 à date (%)", "pluie_2026", "1dp"),
    ("Pluie min 2024–2026", "pluie_min_2024_2026", "f1"),
    ("Score pluie (0–1)", "score_pluie", "f2"),
    ("INDICE SÉCHERESSE (0–1)", "indice_secheresse", "f2"),
    ("Rang (1 = priorité max.)", "rang", "fint"),
    ("Catégorie", "categorie", "ftxt"),
    (
        "Indicateur_Sécheresse (1 si indice ≥ seuil)",
        "indicateur_secheresse",
        "fint",
    ),
    ("Notes", "notes", "txt"),
]
L = {f: col(i + 1) for i, (h, f, k) in enumerate(COLS)}
assert (
    L["score_ch"] == "N"
    and L["indice_secheresse"] == "AD"
    and L["notes"] == "AH"
), L
LAST = L["notes"]


def formula(field, r):
    g = f"$G{r}"
    if field == "score_ch":
        return f'IF(ISNUMBER(L{r}),MIN(1,MAX(0,(L{r}-$H$3)/($I$3-$H$3))),"")'
    if field == "asi_max_2024_2026":
        return f'IF(COUNT(O{r}:Q{r})=0,"",MAX(O{r}:Q{r}))'
    if field == "score_asi":
        return f'IF(ISNUMBER(R{r}),MIN(1,MAX(0,R{r}/$J$3)),IF({g}="Oui",0,""))'
    if field == "bio_min_2024_2026":
        return f'IF(COUNT(T{r}:V{r})=0,"",MIN(T{r}:V{r}))'
    if field == "score_bio":
        return f'IF(ISNUMBER(W{r}),MIN(1,MAX(0,(100-W{r})/(100-$K$3))),IF({g}="Oui",0,""))'
    if field == "pluie_min_2024_2026":
        return f'IF(COUNT(Y{r}:AA{r})=0,"",MIN(Y{r}:AA{r}))'
    if field == "score_pluie":
        return f'IF(ISNUMBER(AB{r}),MIN(1,MAX(0,(100-AB{r})/(100-$L$3))),IF({g}="Oui",0,""))'
    if field == "indice_secheresse":
        num = f"IF(ISNUMBER(N{r}),N{r}*$C$3,0)+IF(ISNUMBER(S{r}),S{r}*$D$3,0)+IF(ISNUMBER(X{r}),X{r}*$E$3,0)+IF(ISNUMBER(AC{r}),AC{r}*$F$3,0)"
        den = f"IF(ISNUMBER(N{r}),$C$3,0)+IF(ISNUMBER(S{r}),$D$3,0)+IF(ISNUMBER(X{r}),$E$3,0)+IF(ISNUMBER(AC{r}),$F$3,0)"
        return f'IF(COUNT(N{r},S{r},X{r},AC{r})=0,"",({num})/({den}))'
    if field == "rang":
        return f'IF(ISNUMBER(AD{r}),RANK(AD{r},$AD${R0}:$AD${R1}),"")'
    if field == "categorie":
        return f'IF(ISNUMBER(AD{r}),IF(AD{r}>=0.6,"Très élevé",IF(AD{r}>=0.4,"Élevé",IF(AD{r}>=0.2,"Modéré","Faible"))),"")'
    if field == "indicateur_secheresse":
        return f'IF(ISNUMBER(AD{r}),IF(AD{r}>=$M$3,1,0),"")'
    raise KeyError(field)


# ---------- new sheet XML ----------
rows = []
rows.append(
    f'<row r="1">{cs("A1","Indice de risque sécheresse par département — données secondaires 2024–2026 (CH/IPC, FAO ASI, biomasse GeoSahel, pluie)", S_TITLE)}</row>'
)
params = [
    ("C", "Poids CH", 0.4),
    ("D", "Poids ASI", 0.2),
    ("E", "Poids biomasse", 0.2),
    ("F", "Poids pluie", 0.2),
    ("H", "CH : score 0 si Ph3+ ≤ (%)", 10),
    ("I", "CH : score 1 si Ph3+ ≥ (%)", 40),
    ("J", "ASI : score 1 si ≥ (%)", 40),
    ("K", "Biomasse : score 1 si ≤ (% moy.)", 50),
    ("L", "Pluie : score 1 si ≤ (% normale)", 60),
    ("M", "Seuil Indicateur_Sécheresse", 0.5),
]
r2 = cs("A2", "Paramètres (modifiables) :", S_NOTE) + "".join(
    cs(f"{c}2", lab, S_NOTE) for c, lab, v in params
)
r3 = "".join(cn(f"{c}3", v, S_PARAM) for c, lab, v in params)
rows.append(f'<row r="2" ht="30" customHeight="1">{r2}</row>')
rows.append(f'<row r="3">{r3}</row>')
rows.append(
    f'<row r="4">{cs("A4","Méthode, sources et limites : https://ocha-dap.github.io/ds-aa-tcd-drought/hnrp_2027_secheresse/ — construit le 2026-09-04 (OCHA CHD Data Science). Scores : 0 = pas de signal, 1 = signal maximal ; indice = moyenne pondérée des scores disponibles. Zone saharienne : ASI/biomasse/pluie non applicables (scores aléa = 0). Vide = non disponible.", S_SUB)}</row>'
)
hdr = "".join(cs(f"{col(i+1)}5", h, S_HDR) for i, (h, f, k) in enumerate(COLS))
rows.append(f'<row r="5" ht="78" customHeight="1">{hdr}</row>')
for i, rec in m.iterrows():
    r = R0 + i
    cells = []
    for j, (h, f, k) in enumerate(COLS):
        ref = f"{col(j+1)}{r}"
        v = rec[f]
        if k == "txt":
            cells.append(cs(ref, v, S_WRAP if f == "notes" else None))
        elif k == "int":
            cells.append(cn(ref, v, S_INT))
        elif k == "1dp":
            cells.append(cn(ref, v, S_1DP))
        elif k == "f1":
            cells.append(cf(ref, formula(f, r), v, S_1DP))
        elif k == "f2":
            cells.append(cf(ref, formula(f, r), v, S_2DP))
        elif k == "fint":
            cells.append(cf(ref, formula(f, r), v, S_INT))
        elif k == "ftxt":
            cells.append(cf(ref, formula(f, r), v))
    rows.append(f'<row r="{r}">{"".join(cells)}</row>')
widths = {
    "A": 16,
    "B": 20,
    "C": 11,
    "D": 12,
    "E": 20,
    "F": 12,
    "G": 11,
    "H": 12,
    "AF": 12,
    "AH": 70,
}
cols_xml = "".join(
    f'<col min="{i+1}" max="{i+1}" width="{widths.get(col(i+1),11)}" customWidth="1"/>'
    for i in range(len(COLS))
)
cf_xml = (
    f'<conditionalFormatting sqref="AF{R0}:AF{R1}">'
    f'<cfRule type="cellIs" dxfId="{DXF_TE}" priority="1" operator="equal"><formula>"Très élevé"</formula></cfRule>'
    f'<cfRule type="cellIs" dxfId="{DXF_E}" priority="2" operator="equal"><formula>"Élevé"</formula></cfRule>'
    f'<cfRule type="cellIs" dxfId="{DXF_M}" priority="3" operator="equal"><formula>"Modéré"</formula></cfRule>'
    f'<cfRule type="cellIs" dxfId="{DXF_F}" priority="4" operator="equal"><formula>"Faible"</formula></cfRule></conditionalFormatting>'
    f'<conditionalFormatting sqref="AD{R0}:AD{R1}"><cfRule type="colorScale" priority="5"><colorScale><cfvo type="num" val="0"/><cfvo type="num" val="1"/><color rgb="FFFFF5EB"/><color rgb="FFC00000"/></colorScale></cfRule></conditionalFormatting>'
    f'<conditionalFormatting sqref="N{R0}:N{R1} S{R0}:S{R1} X{R0}:X{R1} AC{R0}:AC{R1}"><cfRule type="colorScale" priority="6"><colorScale><cfvo type="num" val="0"/><cfvo type="num" val="1"/><color rgb="FFFFFFFF"/><color rgb="FFF4B183"/></colorScale></cfRule></conditionalFormatting>'
)
sheet_xml = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    f'<dimension ref="A1:{LAST}{R1}"/><sheetViews><sheetView tabSelected="1" zoomScale="90" workbookViewId="0"><pane xSplit="2" ySplit="5" topLeftCell="C6" activePane="bottomRight" state="frozen"/>'
    '<selection pane="topRight"/><selection pane="bottomLeft"/><selection pane="bottomRight" activeCell="C6" sqref="C6"/></sheetView></sheetViews>'
    f'<sheetFormatPr baseColWidth="10" defaultRowHeight="14.5"/><cols>{cols_xml}</cols><sheetData>{"".join(rows)}</sheetData>'
    f'<autoFilter ref="A5:{LAST}{R1}"/>{cf_xml}<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/></worksheet>'
)

# ---------- unpack, edit, repack ----------
work = OUT.parent / "_xlsx_work"
shutil.rmtree(work, ignore_errors=True)
with zipfile.ZipFile(SRC) as z:
    z.extractall(work)
    order = [i.filename for i in z.infolist()]


def rd(p):
    return (work / p).read_text(encoding="utf-8")


def wr(p, s):
    (work / p).write_text(s, encoding="utf-8")


def sub1(s, pat, rep, cnt=1):
    s2, n = re.subn(pat, rep, s, count=cnt)
    assert n == cnt, pat
    return s2


(work / "xl/worksheets/sheet8.xml").write_text(sheet_xml, encoding="utf-8")
ct = rd("[Content_Types].xml")
ct = sub1(
    ct,
    r"</Types>",
    '<Override PartName="/xl/worksheets/sheet8.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
)
wr("[Content_Types].xml", ct)
rels = rd("xl/_rels/workbook.xml.rels")
rels = sub1(
    rels,
    r"</Relationships>",
    '<Relationship Id="rId100" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet8.xml"/></Relationships>',
)
wr("xl/_rels/workbook.xml.rels", rels)
wb = rd("xl/workbook.xml")
wb = sub1(
    wb,
    r'(<sheet name="Recap" [^>]*/>)',
    rf'\1<sheet name="{SHEET}" sheetId="14" r:id="rId100"/>',
)
wb = sub1(wb, r'activeTab="\d+"', 'activeTab="1"')
wb = sub1(
    wb,
    r"<definedNames>",
    f'<definedNames><definedName name="_xlnm._FilterDatabase" localSheetId="1" hidden="1">\'{SHEET}\'!$A$5:${LAST}${R1}</definedName>',
)
wb = sub1(wb, r"<calcPr ", '<calcPr fullCalcOnLoad="1" ')
wr("xl/workbook.xml", wb)
app = rd("docProps/app.xml")
app = sub1(app, r"<vt:i4>7</vt:i4>", "<vt:i4>8</vt:i4>")
app = sub1(
    app,
    r'<vt:vector size="7" baseType="lpstr"><vt:lpstr>Recap</vt:lpstr>',
    f'<vt:vector size="8" baseType="lpstr"><vt:lpstr>Recap</vt:lpstr><vt:lpstr>{SHEET}</vt:lpstr>',
)
wr("docProps/app.xml", app)
for p in sorted((work / "xl/worksheets").glob("sheet*.xml")):
    if p.name != "sheet8.xml":
        s = p.read_text(encoding="utf-8")
        if 'tabSelected="1"' in s:
            p.write_text(s.replace(' tabSelected="1"', ""), encoding="utf-8")
# styles
st = rd("xl/styles.xml")
st = sub1(
    st,
    r'<numFmts count="2">',
    '<numFmts count="3"><numFmt numFmtId="164" formatCode="0.0"/>',
)
FONT = '<font><sz val="11"/><color theme="1"/><name val="Aptos Narrow"/><family val="2"/><scheme val="minor"/></font>'
newfonts = (
    '<font><b/><sz val="11"/><color theme="1"/><name val="Aptos Narrow"/><family val="2"/><scheme val="minor"/></font>'  # 10 bold
    '<font><b/><sz val="14"/><color theme="1"/><name val="Aptos Narrow"/><family val="2"/><scheme val="minor"/></font>'  # 11 title
    '<font><i/><sz val="9"/><color rgb="FF595959"/><name val="Aptos Narrow"/><family val="2"/><scheme val="minor"/></font>'
)  # 12 note
st = sub1(st, r'<fonts count="10"([^>]*)>', r'<fonts count="13"\1>')
st = sub1(st, r"</fonts>", newfonts + "</fonts>")
newfills = (
    '<fill><patternFill patternType="solid"><fgColor rgb="FFD9E1F2"/><bgColor indexed="64"/></patternFill></fill>'  # 15 header
    '<fill><patternFill patternType="solid"><fgColor rgb="FFFFF2CC"/><bgColor indexed="64"/></patternFill></fill>'
)  # 16 param
st = sub1(st, r'<fills count="15">', '<fills count="17">')
st = sub1(st, r"</fills>", newfills + "</fills>")
newxfs = (
    '<xf numFmtId="0" fontId="10" fillId="15" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>'  # 65 hdr
    '<xf numFmtId="0" fontId="11" fillId="0" borderId="0" xfId="0" applyFont="1"/>'  # 66 title
    '<xf numFmtId="3" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'  # 67 int
    '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'  # 68 1dp
    '<xf numFmtId="2" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'  # 69 2dp
    '<xf numFmtId="0" fontId="10" fillId="16" borderId="0" xfId="0" applyFont="1" applyFill="1"/>'  # 70 param
    '<xf numFmtId="0" fontId="12" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>'  # 71 note
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>'  # 72 wrap
    '<xf numFmtId="0" fontId="12" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
)  # 73 sub
st = sub1(st, r'<cellXfs count="65">', '<cellXfs count="74">')
st = sub1(st, r"</cellXfs>", newxfs + "</cellXfs>")
newdxfs = (
    '<dxf><font><b/><color rgb="FFFFFFFF"/></font><fill><patternFill><bgColor rgb="FFC00000"/></patternFill></fill></dxf>'
    '<dxf><fill><patternFill><bgColor rgb="FFF4B183"/></patternFill></fill></dxf>'
    '<dxf><fill><patternFill><bgColor rgb="FFFFE699"/></patternFill></fill></dxf>'
    '<dxf><fill><patternFill><bgColor rgb="FFC6E0B4"/></patternFill></fill></dxf>'
)
st = sub1(st, r'<dxfs count="63">', '<dxfs count="67">')
st = sub1(st, r"</dxfs>", newdxfs + "</dxfs>")
wr("xl/styles.xml", st)

# Recap: lookup columns AI..AL rows 6..76
s1 = rd("xl/worksheets/sheet1.xml")
byname = m.set_index("nom_fichier")
recap_names = pd.read_excel(SRC, "Recap", header=None).iloc[6:76, 16].tolist()


def look(colL, r):
    return f"IFERROR(INDEX('{SHEET}'!${colL}${R0}:${colL}${R1},MATCH($Q{r},'{SHEET}'!$E${R0}:$E${R1},0)),\"\")"


add = {
    5: cs(
        "AI5",
        "Indice sécheresse (données secondaires 2024–2026) — détail et paramètres dans la feuille « "
        + SHEET
        + " »",
        S_SUB,
    ),
    6: cs("AI6", "Indice sécheresse (0–1)", S_HDR)
    + cs("AJ6", "Catégorie sécheresse", S_HDR)
    + cs("AK6", "Indicateur_Sécheresse", S_HDR)
    + cs("AL6", "Rang sécheresse", S_HDR),
}
for i, name in enumerate(recap_names):
    r = 7 + i
    rec = byname.loc[name]
    add[r] = (
        cf(f"AI{r}", look("AD", r), rec.indice_secheresse, S_2DP)
        + cf(f"AJ{r}", look("AF", r), rec.categorie)
        + cf(f"AK{r}", look("AG", r), rec.indicateur_secheresse, S_INT)
        + cf(f"AL{r}", look("AE", r), rec.rang, S_INT)
    )
for r, cells in add.items():
    pat = rf'(<row r="{r}"[^>]*>)(.*?)(</row>)'
    mo = re.search(pat, s1, flags=re.S)
    assert mo, r
    head = (
        mo.group(1)
        .replace('spans="1:33"', 'spans="1:38"')
        .replace('spans="3:32"', 'spans="3:38"')
    )
    s1 = (
        s1[: mo.start()]
        + head
        + mo.group(2)
        + cells
        + mo.group(3)
        + s1[mo.end() :]
    )
s1 = sub1(s1, r'<dimension ref="A1:AG77"/>', '<dimension ref="A1:AL77"/>')
s1 = sub1(
    s1,
    r"</cols>",
    '<col min="35" max="35" width="14" customWidth="1"/><col min="36" max="36" width="16" customWidth="1"/><col min="37" max="37" width="14" customWidth="1"/><col min="38" max="38" width="10" customWidth="1"/></cols>',
)
cf1 = (
    '<conditionalFormatting sqref="AJ7:AJ76">'
    f'<cfRule type="cellIs" dxfId="{DXF_TE}" priority="20" operator="equal"><formula>"Très élevé"</formula></cfRule>'
    f'<cfRule type="cellIs" dxfId="{DXF_E}" priority="21" operator="equal"><formula>"Élevé"</formula></cfRule>'
    f'<cfRule type="cellIs" dxfId="{DXF_M}" priority="22" operator="equal"><formula>"Modéré"</formula></cfRule>'
    f'<cfRule type="cellIs" dxfId="{DXF_F}" priority="23" operator="equal"><formula>"Faible"</formula></cfRule></conditionalFormatting>'
    '<conditionalFormatting sqref="AI7:AI76"><cfRule type="colorScale" priority="24"><colorScale><cfvo type="num" val="0"/><cfvo type="num" val="1"/><color rgb="FFFFF5EB"/><color rgb="FFC00000"/></colorScale></cfRule></conditionalFormatting>'
)
s1 = sub1(s1, r"<pageMargins", cf1 + "<pageMargins")
wr("xl/worksheets/sheet1.xml", s1)

# validate XML well-formedness of every edited part
for p in [
    "[Content_Types].xml",
    "xl/_rels/workbook.xml.rels",
    "xl/workbook.xml",
    "docProps/app.xml",
    "xl/styles.xml",
    "xl/worksheets/sheet1.xml",
    "xl/worksheets/sheet8.xml",
]:
    ET.fromstring((work / p).read_bytes())
# repack (keep original order, new part at the end)
if OUT.exists():
    OUT.unlink()
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for name in order + ["xl/worksheets/sheet8.xml"]:
        z.write(work / name, name)
shutil.rmtree(work)
print("wrote", OUT, OUT.stat().st_size)
