# Working in this repo — ds-aa-tcd-drought

<!-- markdownlint-disable MD013 -->

This repo is the **spoke** for the knowledge-base page
**[`frameworks/tcd-drought/2025-03-03.md`](https://github.com/OCHA-DAP/ds-knowledge-base/blob/main/frameworks/tcd-drought/2025-03-03.md)**
(the **hub**, in
[OCHA-DAP/ds-knowledge-base](https://github.com/OCHA-DAP/ds-knowledge-base)).

## Before you work

1. **Read the KB page** above — it carries the authoritative trigger, the
   reconciliation / `discrepancies`, funding, monitoring, and how this
   framework fits the portfolio. Don't re-derive what's already summarised.
2. Skim the KB conventions: `INGESTION.md` and `docs/DESIGN.md` in the KB repo.
3. **Work is usually NOT on `main`.** The active branch is **`2025-monitoring`**
   (`main` is ~3 months stale). The KB page's `source_branch` is the source of
   truth for which branch to read.

## Authority & where the trigger lives

- The **latest framework PDF**
  ([2025-03-03](https://www.unocha.org/publications/report/chad/cadre-de-laction-anticipatoire-secheresse-au-tchad-version-finale-du-3-mars-2025))
  is authoritative for the trigger; this repo *derives/implements* it. If code
  and PDF disagree, the **PDF wins** and the gap is a `discrepancy` on the KB
  page.
- Canonical trigger code: `analysis/combined_rp_2025.md`,
  `analysis/monitoring_2025_seas5.md`, `analysis/monitoring_2025_biomasse.md`,
  `src/constants.py`, `src/datasources/{seas5,biomasse}.py`.
- ⚠️ The README **Overview** still links the old 2022 PDF and
  `pa-anticipatory-action`; the KB header supersedes it.

## After real work

**Capture-as-you-go:** if you change the trigger, thresholds, or monitoring,
update the KB page (and this file if the repo's orientation changed). The KB
stays useful only if work flows back into it.

## Team conventions

Follow the team's global config (`~/.claude/CLAUDE.dsci.md`): `ocha-stratus`
for all blob/DB access, `ocha-lens` for common processing, marimo for apps,
`PROJECT_PREFIX` from `src.constants`. Note: **`ocha-anticipy` is deprecated**
— relevant for reading older frameworks, but not used for new work.
