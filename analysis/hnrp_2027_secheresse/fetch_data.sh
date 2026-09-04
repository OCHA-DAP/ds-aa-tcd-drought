#!/usr/bin/env bash
# Download the raw inputs for the HNRP 2027 drought index into a work dir (default: ./work).
# CH/IPC ADM2 timeseries + CODAB ADM2 come from the project blob via src/datasources (see prepare_blob_inputs.py).
set -euo pipefail
WORK=${1:-work}; mkdir -p "$WORK"; cd "$WORK"
B="https://www.fao.org/giews/earthobservation/asis/data/country/TCD"
curl -sL "$B/MAP_ASI/DATA/ASI_Dekad_Season1_data.csv" -o asi_ASI_Dekad_Season1_data.csv
curl -sL "$B/MAP_ASI/DATA/ASI_AnnualSummary_Season1_data.csv" -o asi_ASI_AnnualSummary_Season1_data.csv
curl -sL "$B/GRAPH_RAIN_AGRI/rain_adm1_data.csv" -o asi_rain_adm1_data.csv
# GeoSahel biomasse (DMP) at ADM2, Chad only
curl -s --max-time 300 "http://213.206.230.89:8080/geoserver/Biomass/wfs?service=WFS&version=1.0.0&request=GetFeature&typeName=Biomass:WA_BIO_ADM2_v4&outputFormat=csv&CQL_FILTER=adm0_pcode%3D%27TD%27" -o bio_adm2.csv
# FAO GAUL 2015 admin-1 (the units FAO ASIS reports on), Chad only
curl -sL --max-time 180 "https://data.apps.fao.org/map/gsrv/gsrv1/gaul/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=gaul:g2015_2014_1&outputFormat=application/json&CQL_FILTER=adm0_name%3D%27Chad%27" -o gaul1_tcd.json
ls -la
