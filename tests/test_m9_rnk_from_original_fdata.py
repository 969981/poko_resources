"""M9.8: synthetic IDRK -> native RNK/IRNK validation, never inferred FKs."""
import csv
import json
import struct
import tempfile
import unittest
from pathlib import Path
from Scripts.resources.m9_rnk_from_original_fdata import decode_native, run

TYPE = "bf6b52c7"
HASHES = ("a91711c6", "aa91cb96", "cb3c8b15")


def sample_rnk():
    record = b"IRNK0000" + struct.pack("<III", 28, 0x12345678, 1)
    record += struct.pack("<I", 24) + b"abc\0"
    assert len(record) == 28
    return b"_RNK0000" + struct.pack("<IIII", 24, 0, 1, 24 + len(record)) + record


def csv_row(key, filename):
    return {
        "expected_rnk_hash":key, "record_id":"root:1",
        "candidate_source_paths":json.dumps([f"romfs/{filename}"]),
        "type_hash":TYPE, "fdata_offset":"16", "fdata_entry_size":"100",
        "uncompressed_size":"52", "footer_magic":"0x0401",
    }


class FdataRecoveryTests(unittest.TestCase):
    def test_exact_fdata_header_and_irnk_bytes(self):
        blob=sample_rnk()
        self.assertEqual(len(blob),52)
        row=csv_row(HASHES[0],"source.fdata")
        header=struct.pack("<8sQQQIIII",b"IDRK0000",48+len(blob),len(blob),len(blob),
                           0,int(row["expected_rnk_hash"],16),int(TYPE,16),0)
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"source.fdata"
            p.write_bytes(b"\0"*16+header+blob)
            entries, meta, checksum=decode_native(p,row)
            self.assertEqual(meta["entries"],1)
            self.assertEqual(entries[0]["strings"][0]["text"],"abc")
            self.assertEqual(len(checksum),64)
            bad=dict(row, type_hash="00000001")
            with self.assertRaises(ValueError):
                decode_native(p,bad)

    def test_missing_sources_stay_unverified(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            csvpath=base/"audit.csv"
            with csvpath.open("w",newline="",encoding="utf-8") as f:
                writer=csv.DictWriter(f,fieldnames=list(csv_row(HASHES[0],"a.fdata")))
                writer.writeheader()
                for i,h in enumerate(HASHES):
                    writer.writerow(csv_row(h,f"missing{i}.fdata"))
            report=run(csvpath,base/"missing_input",base/"out")
            self.assertEqual(report["verified_original_rnk_sources"],0)
            self.assertEqual(report["native_irnk_strings_extracted"],0)
            self.assertEqual(report["new_script_scene_quest_building_text_foreign_keys"],0)
            self.assertEqual(len(report["sources"]),3)
            self.assertTrue(all(x["status"]=="ORIGINAL_FDATA_NOT_PRESENT" for x in report["sources"]))


if __name__=="__main__":
    unittest.main()
