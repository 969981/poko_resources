"""Synthetic-fixture regression tests for M7 native tables without a locale match."""
import csv
import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Scripts" / "resources"))
from export_unlinked_native_text import run, unlinked_entries


def native_bin(values, forms=1):
    width = 8 if forms == 1 else 32
    b = bytearray(64 + len(values) * width)
    struct.pack_into("<II", b, 0, len(values), 0)
    for row, value in enumerate(values):
        fields = [value] if forms == 1 else value
        for form, s in enumerate(fields):
            ptr = 64 + row * width + form * 4
            struct.pack_into("<I", b, ptr, len(b) - ptr)
            b.extend(s.encode("utf-8") + b"\0")
        if forms == 1:
            struct.pack_into("<I", b, 64 + row * width + 4, 0x1234)
        else:
            struct.pack_into("<II", b, 64 + row * width + 24, 0xAB, 0xCD)
    return bytes(b)


def fixture(root):
    decoded = root / "decoded"
    decoded.mkdir()
    inventory = root / "native_table_inventory.csv"
    groups = root / "nine_language_groups.csv"
    originals = {
        10: native_bin(["Line one\\literal\nwith newline", ""]),
        20: native_bin([["First", "One\tTwo", "三", "", "x", "🎮"],
                        ["", "", "", "", "", ""]], forms=6),
        50: native_bin(["same", "native"]),
    }
    with inventory.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "entry", "path", "bytes", "sha256", "status", "record_count", "record_width"
        ])
        w.writeheader()
        for entry in [10, 20, *range(50, 59)]:
            b = originals.get(entry, originals[50])
            (decoded / f"{entry:05d}.bin").write_bytes(b)
            w.writerow(dict(
                entry=entry, path=f"decoded/{entry:05d}.bin", bytes=len(b),
                sha256=hashlib.sha256(b).hexdigest(), status="PARSED",
                record_count=2, record_width=32 if entry == 20 else 8
            ))
    with groups.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "start_entry", "end_entry", "record_count", "forms",
            "locale_order", "evidence_grade", "category"
        ])
        w.writeheader()
        w.writerow(dict(
            start_entry=50, end_entry=58, record_count=2, forms=1,
            locale_order="jp,en,fr,it,de,es,zht,ko,zhs",
            evidence_grade="STRUCTURE_ONLY", category="UNKNOWN"
        ))
    return decoded, groups, inventory


class UnlinkedNativeText(unittest.TestCase):
    def test_export_native_text_not_linked_in_any_nine_language_group(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            decoded, groups, inventory = fixture(root)
            candidates = unlinked_entries(groups, inventory)
            self.assertEqual(sorted(candidates), [10, 20])
            report = run(decoded, groups, inventory, root / "out")
            self.assertEqual(report["tables_exported"], 2)
            self.assertEqual(report["native_records"], 4)
            self.assertEqual(report["native_record_form_slots"], 14)
            manifest = json.loads((root / "out/table_00020/manifest.json").read_text())
            self.assertEqual(manifest["language"], "UNKNOWN")
            self.assertEqual(manifest["category"], "UNKNOWN")
            self.assertEqual(manifest["forms_per_record"], 6)
            records = [json.loads(line) for line in
                       (root / "out/table_00020/unknown.forms.jsonl")
                       .read_text(encoding="utf-8").splitlines()]
            self.assertEqual(records[0]["forms"], ["First", "One\tTwo", "三", "", "x", "🎮"])
            self.assertEqual(records[0]["raw_metadata_u32"], [0xAB, 0xCD])
            self.assertEqual((root / "out/table_00010/unknown.txt")
                             .read_text(encoding="utf-8"),
                             "Line one\\\\literal\\nwith newline\n\n")
            self.assertFalse((root / "out/table_00050").exists())

    def test_rejects_inventory_sha_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            decoded, groups, inventory = fixture(root)
            inventory.write_text(
                inventory.read_text().replace(
                    hashlib.sha256((decoded / "00010.bin").read_bytes()).hexdigest(),
                    "0" * 64, 1
                ), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "source SHA/size mismatch"):
                run(decoded, groups, inventory, root / "out")

    def test_rejects_group_entry_from_subset(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            decoded, groups, inventory = fixture(root)
            with self.assertRaisesRegex(ValueError, "Unlinked M7 entries missing"):
                run(decoded, groups, inventory, root / "out", {50})

    def test_selected_entry_keeps_independent_report(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            decoded, groups, inventory = fixture(root)
            report = run(decoded, groups, inventory, root / "out", {20})
            self.assertEqual(report["tables_exported"], 1)
            self.assertEqual(report["native_record_form_slots"], 12)
            self.assertFalse((root / "out/table_00010").exists())


if __name__ == "__main__":
    unittest.main()
