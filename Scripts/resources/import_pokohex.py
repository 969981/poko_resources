#!/usr/bin/env python3
"""Build an ID-addressed Pokopia item resource index using the pinned PokoHex dump.

This imports known PokoHex images/text and indexes existing M3 g1t candidates.
PokoHex icons are not claimed to be independently re-extracted from 2.0.1.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import struct
from pathlib import Path

LANGUAGES = ("en", "jp", "de", "es", "fr", "it", "ko", "zhs", "zht")
SOURCE_COMMIT = "c71d2b73fb9d8cfe99c1067e6bfadfd19f60bf78"
ITEM_COUNT = 4600


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_csv(path: Path, header: list[str], rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def import_items(source: Path, dest: Path) -> dict:
    texts = {}
    for lang in LANGUAGES:
        original = source / "PokoHex.Core" / "Resources" / "text" / lang / f"text_item_{lang}.txt"
        content = original.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        lines = content.splitlines()
        if len(lines) != ITEM_COUNT:
            raise ValueError(f"{lang}: expected 4600 item lines, got {len(lines)}")
        texts[lang] = lines
        output = dest / "Items" / "Text" / f"text_item_{lang}.txt"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(lines) + "\n", encoding="utf-8")

    mapping_path = source / "PokoHex.Core" / "Resources" / "byte" / "item_menuicon.bin"
    mapping_data = mapping_path.read_bytes()
    if len(mapping_data) != ITEM_COUNT * 2:
        raise ValueError("Unexpected item_menuicon.bin size")
    mapping = struct.unpack(f"<{ITEM_COUNT}H", mapping_data)

    icon_input = source / "PokoHex" / "Resources" / "MenuIcon"
    icons = {}
    for original in sorted(icon_input.glob("item_*.png")):
        if not original.stem[5:].isdigit():
            raise ValueError(f"Unrecognized icon filename: {original.name}")
        item_id = int(original.stem[5:])
        if not 0 <= item_id < ITEM_COUNT or item_id in icons:
            raise ValueError(f"Bad or duplicate item icon ID: {item_id}")
        if original.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"Not a PNG: {original}")
        target = dest / "Items" / "Icons" / original.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        icons[item_id] = "Items/Icons/" + original.name

    header = ["item_id", *LANGUAGES, "pokohex_menuicon_raw_u16",
              "icon_path", "has_pokohex_icon"]
    rows = []
    missing = []
    named = 0
    named_with_icon = 0
    for item_id in range(ITEM_COUNT):
        names = [texts[lang][item_id] for lang in LANGUAGES]
        has_name = any(names)
        icon = icons.get(item_id, "")
        if has_name:
            named += 1
            if icon:
                named_with_icon += 1
            else:
                missing.append([item_id, texts["zhs"][item_id], texts["en"][item_id]])
        rows.append([item_id, *names, mapping[item_id], icon, int(bool(icon))])
    save_csv(dest / "Items" / "item_catalog.csv", header, rows)
    save_csv(dest / "Items" / "missing_pokohex_icons.csv",
             ["item_id", "zhs", "en"], missing)
    return {
        "item_slots": ITEM_COUNT,
        "named_items": named,
        "pokohex_icon_files": len(icons),
        "named_items_with_icons": named_with_icon,
        "named_items_without_pokohex_icons": len(missing),
        "language_counts": {lang: sum(bool(t) for t in texts[lang]) for lang in LANGUAGES},
        "menuicon_map_sha256": sha256(mapping_path),
    }


def index_g1t(source_index: Path, dest: Path) -> int:
    if not source_index.is_file():
        raise FileNotFoundError(f"Missing local M3 index: {source_index}")
    cols = ["record_id", "source_path", "name_hash", "type_hash",
            "output_path", "output_sha256", "native_extension_hint", "evidence_grade"]
    rows = []
    with source_index.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not set(cols).issubset(reader.fieldnames or []):
            raise ValueError("M3 index lacks required provenance columns")
        for row in reader:
            if row.get("native_extension_hint", "").lower() == ".g1t":
                rows.append([row.get(k, "") for k in cols])
    save_csv(dest / "Textures" / "g1t_candidates.csv", cols, rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Pinned PokoHex checkout")
    parser.add_argument("--dest", type=Path, default=Path("UnPack/2.0.1/Resources"))
    parser.add_argument("--m3-index", type=Path, default=Path(
        "UnPack/2.0.1/_reports/m3_resource_type_index.csv"))
    args = parser.parse_args()

    statistics = import_items(args.source, args.dest)
    statistics["g1t_candidate_records"] = index_g1t(args.m3_index, args.dest)
    statistics["upstream"] = {
        "repository": "https://github.com/969981/PokoHex",
        "commit": SOURCE_COMMIT,
        "text_source": "PokoHex.Core/Resources/text/<lang>/text_item_<lang>.txt",
        "icon_source": "PokoHex/Resources/MenuIcon/item_*.png",
        "mapping_source": "PokoHex.Core/Resources/byte/item_menuicon.bin",
        "m3_source": "UnPack/2.0.1/_reports/m3_resource_type_index.csv",
    }
    statistics["warnings"] = [
        "PokoHex assets are a separately sourced dataset, not proven native 2.0.1 extraction.",
        "G1T candidates are NOT mapped to item IDs; type hashes alone do not prove item identity.",
        "Missing PokoHex PNG does NOT prove there is no corresponding texture in the game.",
    ]
    dest = args.dest
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "SOURCE_AND_COVERAGE.json").write_text(
        json.dumps(statistics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(statistics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
