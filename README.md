# Chad Anticipatory Action: drought

[![Generic badge](https://img.shields.io/badge/STATUS-ENDORSED-%231EBFB3)](https://shields.io/)

<!-- KB-POINTER:START (generated from the knowledge base — edit there, not here) -->
<!-- markdownlint-disable MD013 -->
> **📚 This framework in the team knowledge base** →
> **[ds-knowledge-base › `frameworks/tcd-drought`](https://github.com/OCHA-DAP/ds-knowledge-base/blob/main/frameworks/tcd-drought/2025-03-03.md)**
>
> A *separate*, central repo that **summarizes and compares** every OCHA AA framework. Go there for the trigger, calibration, discrepancies, and portfolio context — then come **back here** for the analysis and code, which are the source of truth.

| at a glance | |
|---|---|
| **Status** | endorsed |
| **Current version** | 2025-03-03 ([framework PDF](https://www.unocha.org/publications/report/chad/cadre-de-laction-anticipatoire-secheresse-au-tchad-version-finale-du-3-mars-2025)) — supersedes 2022-10-24 |
| **Active branch** | [`2025-monitoring`](https://github.com/OCHA-DAP/ds-aa-tcd-drought/tree/2025-monitoring) — ⚠️ `main` is stale; current work lives here |
| **Canonical trigger code** | `analysis/combined_rp_2025.md`, `analysis/monitoring_2025_*.md`, `src/constants.py`, `src/datasources/` |

_The knowledge base **points and compares**; this repo **is the source of truth** for the analysis. Working here with Claude? See [`CLAUDE.md`](CLAUDE.md)._

<!-- kb-page: frameworks/tcd-drought/2025-03-03.md -->
<!-- kb-repo: OCHA-DAP/ds-knowledge-base -->
<!-- markdownlint-enable MD013 -->
<!-- KB-POINTER:END -->

## Overview

This repository contains recent analysis for the
[Chad Anticipatory Action drought framework](https://reliefweb.int/report/chad/cadre-de-laction-anticipatoire-pilote-au-tchad-secheresse-version-finale-du-24-octobre-2022).
For previous analysis see the [pa-anticipatory-action repo](https://github.com/OCHA-DAP/pa-anticipatory-action).

## Development

All code is formatted according to black and flake8 guidelines.
The repo is set-up to use pre-commit.
Before you start developing in this repository, you will need to run

```shell
pre-commit install
```

The `markdownlint` hook will require
[Ruby](https://www.ruby-lang.org/en/documentation/installation/)
to be installed on your computer.

You can run all hooks against all your files using

```shell
pre-commit run --all-files
```
