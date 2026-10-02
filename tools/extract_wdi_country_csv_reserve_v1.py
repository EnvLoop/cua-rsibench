"""Pin one official World Bank country CSV ZIP as 30 WDI observations.

The output is evaluator-private. The JSON observation envelope is a verified
extract of the official CSV, not a response returned by the World Bank API.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import os
from pathlib import Path
from urllib.parse import urlparse
import zipfile

from native_desktop_factory import source as wdi
from ppt_wdi_factory.plan import canonical


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_new(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def extract(raw_zip: bytes, expected_iso: str) -> tuple[bytes, dict]:
    require(len(raw_zip) < 10_000_000, "World Bank country ZIP too large")
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
        infos = archive.infolist()
        require(len(infos) == 3 and
                len({item.filename for item in infos}) == 3 and
                all(not item.is_dir() and item.file_size < 5_000_000 and
                    ".." not in Path(item.filename).parts for item in infos) and
                sum(item.file_size for item in infos) < 10_000_000 and
                archive.testzip() is None,
                "Official country ZIP member/CRC contract changed")
        names = [item.filename for item in infos]
        prefix = f"API_{expected_iso}_DS2_en_csv_"
        primary = [name for name in names
                   if name.startswith(prefix) and name.endswith(".csv")]
        require(len(primary) == 1 and
                sorted(name for name in names if name != primary[0]) ==
                sorted(("Metadata_Country_" + primary[0],
                        "Metadata_Indicator_" + primary[0])),
                "Official World Bank country ZIP filenames changed")
        csv_raw = archive.read(primary[0])
    reader = list(csv.reader(io.StringIO(csv_raw.decode("utf-8-sig"))))
    require(len(reader) >= 6 and reader[0][:2] ==
            ["Data Source", "World Development Indicators"] and
            reader[2][0] == "Last Updated Date",
            "World Bank WDI CSV metadata changed")
    updated = reader[2][1]
    date.fromisoformat(updated)
    header = reader[4]
    require(header[:4] == ["Country Name", "Country Code", "Indicator Name",
                           "Indicator Code"] and
            len(header) == len(set(header)) and header[-1] == "" and
            all(header.count(year) == 1 for year in wdi.YEARS),
            "World Bank WDI CSV header changed")
    indices = {year: header.index(year) for year in wdi.YEARS}
    wanted = set(wdi.INDICATORS)
    found: dict[str, dict] = {}
    countries = set()
    for row in reader[5:]:
        if len(row) != len(header):
            continue
        if row[1] != expected_iso or row[3] not in wanted:
            continue
        indicator = row[3]
        require(indicator not in found, "Duplicate WDI indicator in country CSV")
        countries.add(row[0])
        values = {}
        for year, index in indices.items():
            raw = row[index]
            require(raw != "", "Required WDI country observation is missing")
            try:
                value = Decimal(raw)
            except InvalidOperation as error:
                raise ValueError("WDI country observation is not numeric") from error
            require(value.is_finite(), "Nonfinite WDI country observation")
            values[year] = {"raw_csv_value": raw, "value": float(value)}
        found[indicator] = {"name": row[2], "values": values}
    require(set(found) == wanted and len(countries) == 1,
            "Five complete WDI indicators from one country required")
    name = next(iter(countries))
    observations = []
    for indicator in wdi.INDICATORS:
        for year in wdi.YEARS:
            item = found[indicator]["values"][year]
            observations.append({"country": {"value": name},
                                 "countryiso3code": expected_iso,
                                 "indicator": {"id": indicator,
                                               "value": found[indicator]["name"]},
                                 "date": year, "value": item["value"],
                                 "raw_csv_value": item["raw_csv_value"]})
    envelope = [{"page": 1, "pages": 1, "total": len(observations)},
                observations]
    return canonical(envelope), {"data_member": primary[0],
                                 "data_member_sha256": sha(csv_raw),
                                 "data_last_updated": updated,
                                 "country_iso": expected_iso,
                                 "country_name": name,
                                 "numeric_observation_count": len(observations)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-zip", type=Path, required=True)
    parser.add_argument("--expected-zip-sha256", required=True)
    parser.add_argument("--country-iso", required=True)
    parser.add_argument("--official-download-url", required=True)
    parser.add_argument("--official-page-url", required=True)
    parser.add_argument("--download-date", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    out = args.out_dir.resolve()
    require(out.is_relative_to((Path.cwd() / "work").resolve()) and
            not out.exists() and len(args.country_iso) == 3 and
            args.country_iso.isalpha() and args.country_iso.isupper(),
            "fresh private output and ISO3 country required")
    date.fromisoformat(args.download_date)
    require(urlparse(args.official_download_url).hostname == "api.worldbank.org" and
            urlparse(args.official_page_url).hostname == "data.worldbank.org",
            "Official World Bank download/page provenance required")
    raw_zip = args.official_zip.read_bytes()
    require(sha(raw_zip) == args.expected_zip_sha256,
            "Official country ZIP digest changed")
    snapshot, detail = extract(raw_zip, args.country_iso)
    provenance = {"schema": "envloop-wdi-official-country-csv-extract-private-v1",
                  "source_type": "worldbank_official_country_csv_zip",
                  "official_download_url": args.official_download_url,
                  "official_page_url": args.official_page_url,
                  "zip_sha256": sha(raw_zip),
                  "snapshot_sha256": sha(snapshot),
                  "download_date": args.download_date,
                  "catalog_license": "CC BY 4.0", **detail}
    out.mkdir(parents=True, mode=0o700)
    write_new(out / "source-snapshot.private.json", snapshot)
    write_new(out / "source-provenance.private.json", canonical(provenance))
    print(json.dumps({"status": "official_csv_extracted_evaluator_private",
                      "zip_sha256": sha(raw_zip),
                      "snapshot_sha256": sha(snapshot),
                      "provenance_sha256": sha(canonical(provenance)),
                      "numeric_observation_count": detail["numeric_observation_count"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
