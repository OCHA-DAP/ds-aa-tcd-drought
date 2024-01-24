# Chad Anticipatory Action: drought

[![Generic badge](https://img.shields.io/badge/STATUS-ENDORSED-%231EBFB3)](https://shields.io/)

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
