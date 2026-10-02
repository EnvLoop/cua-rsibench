"""Pinned World Development Indicators source for original desktop tasks.

This module never substitutes missing observations.  `snapshot.json` is the
exact JSON response to SOURCE_URL on 2026-09-25; the dataset's catalog page
identifies World Development Indicators as CC BY 4.0.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "sources" / "wdi-2019-2024.json"
SOURCE_URL = (
    "https://api.worldbank.org/v2/country/"
    "USA;CAN;MEX;GBR;FRA;DEU;ESP;ITA;NLD;SWE;"
    "NOR;FIN;POL;CZE;TUR;JPN;KOR;CHN;IND;IDN;"
    "THA;MYS;PHL;VNM;AUS;NZL;ZAF;EGY;KEN;NGA;"
    "BRA;CHL;ARG;COL;PER/indicator/"
    "NY.GDP.MKTP.CD;NY.GDP.PCAP.CD;FP.CPI.TOTL.ZG;"
    "SP.POP.TOTL;SL.UEM.TOTL.ZS"
    "?source=2&format=json&date=2019:2024&per_page=20000"
)
CATALOG_URL = "https://datacatalog.worldbank.org/search/dataset/0037712/world-development-indicators"
LICENSE_URL = "https://datacatalog.worldbank.org/public-licenses"
INDICATORS = (
    "NY.GDP.MKTP.CD", "NY.GDP.PCAP.CD", "FP.CPI.TOTL.ZG",
    "SP.POP.TOTL", "SL.UEM.TOTL.ZS",
)
COUNTRIES = (
    "USA", "CAN", "MEX", "GBR", "FRA", "DEU", "ESP", "ITA", "NLD", "SWE",
    "NOR", "FIN", "POL", "CZE", "TUR", "JPN", "KOR", "CHN", "IND", "IDN",
    "THA", "MYS", "PHL", "VNM", "AUS", "NZL", "ZAF", "EGY", "KEN", "NGA",
    "BRA", "CHL", "ARG", "COL", "PER",
)
YEARS = tuple(str(y) for y in range(2019, 2025))
EXPECTED_SHA256 = "cad6aafbd856ebb78f3f50106ab1b5b38ac369a2da251e2442268e296fde6d9f"


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load() -> dict:
    raw = SNAPSHOT.read_bytes()
    if sha256(raw) != EXPECTED_SHA256:
        raise ValueError("WDI source snapshot SHA-256 changed")
    payload = json.loads(raw)
    if not isinstance(payload, list) or len(payload) != 2:
        raise ValueError("Invalid WDI response envelope")
    header, rows = payload
    if header.get("page") != 1 or header.get("pages") != 1 or header.get("total") != 1050:
        raise ValueError("WDI response was partial or changed")
    if len(rows) != 1050:
        raise ValueError("WDI response row count changed")
    allowed = set(COUNTRIES)
    if len(allowed) != 35:
        raise ValueError("Duplicate country in source inventory")
    observations = {}
    names = {}
    for row in rows:
        iso = row.get("countryiso3code")
        indicator = row.get("indicator", {}).get("id")
        year = row.get("date")
        value = row.get("value")
        key = (iso, indicator, year)
        if iso not in allowed or indicator not in INDICATORS or year not in YEARS:
            raise ValueError("Unexpected WDI observation")
        if key in observations or isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Missing, duplicate, or nonnumeric WDI observation")
        observations[key] = value
        names[iso] = row["country"]["value"]
    if len(observations) != 35 * len(INDICATORS) * len(YEARS):
        raise ValueError("WDI observation cube is incomplete")
    return {"metadata": header, "observations": observations, "names": names,
            "source_sha256": EXPECTED_SHA256}


def country_facts(source: dict, iso: str) -> dict:
    if iso not in source["names"]:
        raise ValueError("Unknown country")
    return {"iso3": iso, "name": source["names"][iso],
            "years": {year: {indicator: source["observations"][(iso, indicator, year)]
                             for indicator in INDICATORS} for year in YEARS}}
