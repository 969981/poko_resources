"""M3 aggregation requires exact source coverage, not just a successful scan."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Scripts.unpack import m3_aggregate


class M3AggregateTests(unittest.TestCase):
    def test_expected_ids_coverage(self):
        with tempfile.TemporaryDirectory() as folder:
            src = Path(folder) / "parts"
            src.mkdir()
            fields = ["catalog", "record_id", "record_index", "type_hash", "signature", "status"]
            for name, rows in [
                ("kt.csv", [
                    ["root", "root:0", "0", "abc", "KIDSOBJDB_SIGNATURE", "PROBED"],
                    ["system", "system:0", "0", "def", "UNKNOWN_BINARY", "PROBED"]
                ]),
                ("link.csv", [
                    ["link", "link:0", "0", "", "EMPTY_INDEX", "EMPTY_INDEX"],
                    ["link", "link:1", "1", "", "PNG_IMAGE", "PROBED"]
                ])
            ]:
                with (src / name).open("w", newline="", encoding="utf-8") as stream:
                    out = csv.writer(stream)
                    out.writerow(fields)
                    out.writerows(rows)
            with patch.object(m3_aggregate, "EXPECTED_KT", 2), \
                 patch.object(m3_aggregate, "EXPECTED_LINK_TOTAL", 2), \
                 patch.object(m3_aggregate, "EXPECTED_EMPTY_LINK", 1):
                result = m3_aggregate.run(src, Path(folder) / "output")
            self.assertEqual(result["status"], "PASS_BOUNDED_PREFIX_SCAN")
            self.assertEqual(result["unique_record_ids"], 4)
            summary = json.loads((Path(folder) / "output/m3_signatures_summary.json").read_text())
            self.assertEqual(summary["part_files"], 2)


if __name__ == "__main__":
    unittest.main()
