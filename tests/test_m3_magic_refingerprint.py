"""Test native-prefix reclassification against RDB type-hash evidence."""
import unittest
from unittest.mock import patch

from Scripts.unpack import m3_magic_refingerprint as r


class MagicRefingerprintTests(unittest.TestCase):
    def make(self, rid, magic, typehash=""):
        return (
            {"record_id": rid, "head_64_hex": magic.encode().hex() + "00" * 8,
             "signature": "UNKNOWN_BINARY", "confidence": "NONE", "candidate_extension": ""},
            {"record_id": rid, "type_hash": typehash, "native_extension_hint": "",
             "evidence_grade": "UNKNOWN_NATIVE_FORMAT", "magic_hint": "", "signature": "UNKNOWN_BINARY"}
        )

    def test_native_magic_confirms_tkid_and_linkdata(self):
        examples = [
            ("root:1", "GT1G", "afbec60c"),
            ("root:2", "_A2G", "6fa91671"),
            ("root:3", "_S2G", "7bcd279f"),
            ("root:4", "XF1G", "b097d41f"),
            ("link:5880", "GT1G", ""),
        ]
        signatures = []
        native = []
        for rid, magic, hashname in examples:
            a, b = self.make(rid, magic, hashname)
            signatures.append(a)
            native.append(b)
        with patch.object(r, "EXPECTED_SIGNED", 5), patch.object(r, "EXPECTED_TYPED", 5):
            ss, ts, report = r.refresh(signatures, native, {}, {})
        self.assertEqual(report["new_magic_evidence_records"], 5)
        self.assertEqual(report["linkdata_magic_confirmed_records"], 1)
        self.assertEqual(report["type_evidence_counts"]["MAGIC_AND_TKID"], 4)
        self.assertEqual(report["type_evidence_counts"]["MAGIC_CONFIRMED"], 1)
        self.assertEqual(ss["signatures"]["G1S_NATIVE_CONTAINER"], 1)
        self.assertEqual(ts["extension_hint_counts"][".g1t"], 2)
        self.assertTrue(report["asset_bytes_redownloaded"] == 0)

    def test_genuine_magic_type_conflict_does_not_get_silent_upgrade(self):
        a, b = self.make("root:5", "GT1G", "6fa91671")
        with patch.object(r, "EXPECTED_SIGNED", 1), patch.object(r, "EXPECTED_TYPED", 1):
            with self.assertRaisesRegex(ValueError, "M3_NATIVE_MAGIC_HASH_CONFLICT"):
                r.refresh([a], [b], {}, {})


if __name__ == "__main__":
    unittest.main()
