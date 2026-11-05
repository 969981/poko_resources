#!/usr/bin/env python3
"""Export auditable, deliberately unlabelled item fields from Pokopia 2.0.1 LINKDATA.

No per-item stack limit or official category enum is claimed by this parser.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
from collections import defaultdict
from pathlib import Path

ROW_COUNT = 4600
HEADER_SIZE = 64
STRIDE = 68
EXPECTED_SHA256 = "2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f"
COLUMNS = [
    "item_id", "name_en", "name_zhs", "native_name_index_u16_at_0x22",
    "value_u32_at_0x08", "value_u32_at_0x0c", "value_u32_at_0x10",
    "value_u32_at_0x14", "category_candidate_u8_at_0x26",
    "subcategory_raw_u8_at_0x27", "group_raw_u8_at_0x2a",
    "flag_raw_u8_at_0x2b", "type_raw_u8_at_0x36",
    "type_raw_u8_at_0x37", "subtype_raw_u8_at_0x38",
    "group_raw_u8_at_0x39", "group_raw_u8_at_0x3a",
    "group_raw_u8_at_0x3b", "flags_u8_at_0x41",
    "flags_u8_at_0x42", "native_max_stack", "raw_record_hex",
]
BYTE_OFFSETS = [38, 39, 42, 54, 55, 56, 57, 58, 59, 65, 66]


def read_names(path: Path) -> list[str]:
    names = path.read_text(encoding="utf-8-sig").splitlines()
    if len(names) != ROW_COUNT:
        raise ValueError(f"{path}: expected {ROW_COUNT} lines, got {len(names)}")
    return names


def run(root: Path, output: Path, allow_other_sha: bool = False) -> dict:
    source = root / "UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin"
    text_root = root / "UnPack/2.0.1/Resources/Items/Native_2.0.1/Text"
    content = source.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if digest != EXPECTED_SHA256 and not allow_other_sha:
        raise ValueError(f"Wrong native 2.0.1 item-table SHA-256: {digest}")
    if len(content) != HEADER_SIZE + ROW_COUNT * STRIDE:
        raise ValueError("Unexpected size or stride of 00983.bin")
    count, version = struct.unpack_from("<II", content)
    if (count, version) != (ROW_COUNT, 3):
        raise ValueError(f"Unexpected table header: {count}, v{version}")

    en, zhs = read_names(text_root / "text_item_en.txt"), read_names(text_root / "text_item_zhs.txt")
    groups: dict[str, dict[str, dict]] = {f"0x{o:x}": {} for o in BYTE_OFFSETS}
    output.mkdir(parents=True, exist_ok=True)
    with (output / "native_item_raw_fields.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for item_id in range(ROW_COUNT):
            row = content[HEADER_SIZE + item_id * STRIDE:HEADER_SIZE + (item_id + 1) * STRIDE]
            u8 = lambda pos: row[pos]
            u16 = lambda pos: struct.unpack_from("<H", row, pos)[0]
            u32 = lambda pos: struct.unpack_from("<I", row, pos)[0]
            writer.writerow([
                item_id, en[item_id], zhs[item_id], u16(34), u32(8), u32(12),
                u32(16), u32(20), u8(38), u8(39), u8(42), u8(43),
                u8(54), u8(55), u8(56), u8(57), u8(58), u8(59),
                u8(65), u8(66), "", row.hex(),
            ])
            if item_id == 0 or not en[item_id]:
                continue
            for offset in BYTE_OFFSETS:
                group = groups[f"0x{offset:x}"].setdefault(str(u8(offset)), {"count": 0, "samples": []})
                group["count"] += 1
                if len(group["samples"]) < 8:
                    group["samples"].append({"id": item_id, "en": en[item_id], "zhs": zhs[item_id]})

    report = {
        "version": "2.0.1",
        "source": "UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin",
        "expected_sha256": EXPECTED_SHA256,
        "observed_sha256": digest,
        "byte_length": len(content),
        "header_size": HEADER_SIZE,
        "record_size": STRIDE,
        "record_count": ROW_COUNT,
        "named_item_count": sum(bool(v) for v in en[1:]),
        "table_version": version,
        "verified_name_index_offset": "0x22 (u16 little-endian)",
        "raw_category_candidates": {
            "byte_0x26": "Strong item-kind candidate; type labels not formally verified",
            "byte_0x3a": "Second grouping candidate; not interchangeable with 0x26",
            "byte_0x39": "Additional classification/display grouping candidate",
        },
        "known_quantity_limits": {
            "native_per_item_stack_field": "UNRESOLVED",
            "save_file_storage": "one uint8 quantity (0-255 representable) per PokoHex.Core/Structures/Item.cs",
            "gameplay_stack_limit": "99 reported by GameSpot; not proven from 00983.bin",
            "bag_slot_count": "separate from per-stack count",
        },
        "field_groups": groups,
    }
    (output / "native_item_field_analysis.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--allow-other-sha", action="store_true")
    args = parser.parse_args()
    out = args.out or args.root / "UnPack/2.0.1/Resources/Items/Native_2.0.1"
    report = run(args.root, out, allow_other_sha=args.allow_other_sha)
    print(json.dumps({
        "status": "EXPORTED_NATIVE_RAW_FIELDS",
        "count": report["record_count"],
        "named": report["named_item_count"],
        "native_stack_limit": "UNRESOLVED",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
