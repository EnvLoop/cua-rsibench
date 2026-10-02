"""Check that a CSV-derived reserve remains bound to its official ZIP bytes."""

from __future__ import annotations

import csv
from datetime import date
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from native_desktop_factory import source as wdi
from ppt_wdi_factory import verify
from ppt_wdi_factory.plan import canonical, sha
from tools.extract_wdi_country_csv_reserve_v1 import extract


def synthetic_country_zip(*, missing: bool = False) -> bytes:
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["Data Source", "World Development Indicators", ""])
    writer.writerow([])
    writer.writerow(["Last Updated Date", "2026-07-13", ""])
    writer.writerow([])
    writer.writerow(["Country Name", "Country Code", "Indicator Name",
                     "Indicator Code", *wdi.YEARS, ""])
    for indicator_number, indicator in enumerate(wdi.INDICATORS):
        values = [str(100 + indicator_number * 10 + year_number)
                  for year_number in range(len(wdi.YEARS))]
        if missing and indicator_number == 2:
            values[3] = ""
        writer.writerow(["Synthetic Testland", "ZZZ", "Synthetic indicator",
                         indicator, *values, ""])
    primary = "API_ZZZ_DS2_en_csv_v2_test.csv"
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(primary, stream.getvalue())
        archive.writestr("Metadata_Country_" + primary, "synthetic metadata")
        archive.writestr("Metadata_Indicator_" + primary, "synthetic metadata")
    return output.getvalue()


class WdiCountryCsvReserveTests(unittest.TestCase):
    def test_exact_country_zip_and_snapshot_binding(self):
        raw_zip = synthetic_country_zip()
        snapshot, detail = extract(raw_zip, "ZZZ")
        self.assertEqual(detail["numeric_observation_count"], 30)
        self.assertEqual(detail["data_last_updated"], "2026-07-13")
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            (package / "source-snapshot.private.json").write_bytes(snapshot)
            (package / "source-country.private.zip").write_bytes(raw_zip)
            provenance = {
                "schema": "envloop-wdi-official-country-csv-extract-private-v1",
                "source_type": "worldbank_official_country_csv_zip",
                "country_iso": "ZZZ", "zip_sha256": sha(raw_zip),
                "snapshot_sha256": sha(snapshot),
                "download_date": "2026-09-27", "catalog_license": "CC BY 4.0",
                "official_download_url":
                    "https://api.worldbank.org/v2/en/country/ZZZ?downloadformat=csv",
                "official_page_url": "https://data.worldbank.org/country/testland",
                **detail,
            }
            raw_provenance = canonical(provenance)
            (package / "source-provenance.private.json").write_bytes(raw_provenance)
            task = {"source_scope": "private_wdi_country_csv_reserve_v1",
                    "source_group": "ZZZ",
                    "source_snapshot_sha256": sha(snapshot),
                    "source_snapshot_date": "2026-09-27",
                    "source_zip_sha256": sha(raw_zip),
                    "source_provenance_sha256": sha(raw_provenance)}
            facts = verify._reserve_country_facts(task, package / "source.pptx")
            self.assertEqual(facts["iso3"], "ZZZ")
            self.assertEqual(len(facts["years"]), 6)
            (package / "source-country.private.zip").write_bytes(raw_zip + b"tamper")
            with self.assertRaisesRegex(ValueError, "source hash changed"):
                verify._reserve_country_facts(task, package / "source.pptx")

    def test_missing_numeric_observation_rejected(self):
        with self.assertRaisesRegex(ValueError, "observation is missing"):
            extract(synthetic_country_zip(missing=True), "ZZZ")


if __name__ == "__main__":
    unittest.main()
