#!/usr/bin/env python3
"""M8: recover verifiable Pokopia 2.0.1 asset-to-localized-text references.

Evidence is from native decoded LINKDATA bytes and version-pinned PokoHex
parser layouts. MapParts are NOT automatically labeled Buildings.
No heuristic semantic classification or unsourced numeric ID matching.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
from pathlib import Path

try:
    from .recover_native_text_ids import LANGS, parse as parse_text
except ImportError:  # direct `python Scripts/resources/...py`
    from recover_native_text_ids import LANGS, parse as parse_text

VERSION_PIN = "c71d2b73fb9d8cfe99c1067e6bfadfd19f60bf78"
PARSER_SOURCES = {
    "item": f"https://github.com/969981/PokoHex/blob/{VERSION_PIN}/PokoHex.Parsing/GameItemDumper.cs",
    "map": f"https://github.com/969981/PokoHex/blob/{VERSION_PIN}/PokoHex.Parsing/GameMapDumper.cs",
    "ability": f"https://github.com/969981/PokoHex/blob/{VERSION_PIN}/PokoHex.Parsing/GameAbilityDumper.cs",
}
NAME_START = 4645
ROLE_GROUPS = (("Reactions", 2332, 128), ("Skills", 4942, 61))
ITEM_COUNT = 4600


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def check_fixed_table(data: bytes, count: int, version: int, stride: int, label: str) -> None:
    expected = 64 + count * stride
    if (len(data) != expected or u32(data, 0) != count
            or u32(data, 4) != version or data[8:64] != bytes(56)):
        raise ValueError(
            f"{label}: expected size={expected}, count={count}, "
            f"version={version}, stride={stride}; got size={len(data)}"
        )


def save_csv(path: Path, rows: list[dict], cols: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=cols)
        writer.writeheader()
        writer.writerows(rows)


def save_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def link_item_table(item_blob: bytes, tables: dict, catalog: dict) -> tuple[list[dict], dict]:
    """Native Item record +0x22 u16 -> row in each 3001 x 32-byte text table."""
    check_fixed_table(item_blob, ITEM_COUNT, 3, 68, "items/00983.bin")
    assert set(tables) == set(LANGS)
    for lang, table in tables.items():
        if table.count != 3001 or table.width != 32 or table.version != 2:
            raise ValueError(f"item locale {lang}: incompatible native text table")
    out = []
    mismatch = []
    named = 0
    empty_names = 0
    for item_id in range(ITEM_COUNT):
        field = 64 + 68 * item_id + 34
        index = u16(item_blob, field)
        if index >= 3001:
            raise ValueError(f"item {item_id}: invalid text index {index}")
        row = {
            "source_kind": "Item", "source_entry": 983, "source_item_id": item_id,
            "source_field_offset": field, "source_field_encoding": "little_endian_u16",
            "target_group_start": NAME_START,
            "target_text_id": index if index != 0 else "",
            "target_form_index": 0 if index != 0 else "",
            "relationship": "item_name_index",
            "evidence_grade": "NATIVE_FIELD_PLUS_LANGUAGE_TEXT_VERIFIED" if index else "NO_NAME_REFERENCE",
            "category": "Items",
        }
        has_text = False
        for lang, table in tables.items():
            text = table.rows[index][0][0] if index else ("(Empty)" if item_id == 0 else "")
            pos = table.rows[index][1][0] if index else ""
            row[lang] = text
            row[f"{lang}_entry"] = table.entry
            row[f"{lang}_string_offset"] = pos
            want = catalog[lang][item_id]
            if text != want:
                mismatch.append({"item_id": item_id, "language": lang, "actual": text, "expected": want})
            if text and (item_id > 0):
                has_text = True
        if has_text:
            named += 1
        if index == 0:
            empty_names += 1
        out.append(row)
    if mismatch:
        raise ValueError(f"Item source text mismatches: {len(mismatch)} first: {mismatch[:3]}")
    return out, {
        "slots_verified_all_9_languages": len(out),
        "items_with_native_name": named,
        "items_without_name_index": empty_names,
        "language_text_discrepancies": len(mismatch),
    }


def link_map_parts(blobs: dict[int, bytes], items: list[dict]) -> tuple[list[dict], dict]:
    """Map Variation 41 +4:u16 -> Parts 40 +6:u16 -> Item 983 +0x22:u16."""
    p, v, s, m = (blobs[id] for id in (40, 41, 42, 44))
    check_fixed_table(p, 4096, 0, 80, "parts/00040.bin")
    check_fixed_table(v, 4096, 3, 16, "variations/00041.bin")
    check_fixed_table(s, 255, 0, 4, "sizes/00042.bin")
    check_fixed_table(m, 4096, 0, 100, "models/00044.bin")
    rows = []
    item_ids = set()
    for variation_id in range(1, 4096):
        variation_base = 64 + variation_id * 16
        model_id = u16(v, variation_base)
        part_id = u16(v, variation_base + 4)
        if not part_id:
            continue
        if model_id >= 4096 or part_id >= 4096:
            raise ValueError(f"Map variation {variation_id}: out of range part/model")
        part_base = 64 + part_id * 80
        item_id = u16(p, part_base + 6)
        if item_id >= ITEM_COUNT:
            raise ValueError(f"Map variation {variation_id}: invalid item_id={item_id}")
        model_base = 64 + model_id * 100
        shape = m[model_base + 0x5B]
        if shape >= 255:
            raise ValueError(f"Map variation {variation_id}: invalid shape={shape}")
        dims = list(s[64 + shape * 4:64 + shape * 4 + 3])
        source_item = items[item_id]
        if source_item["source_item_id"] != item_id:
            raise AssertionError("Catalog item order changed")
        row = {
            "source_kind": "MapPartVariation", "source_entry": 41,
            "source_record_id": variation_id,
            "variation_part_id_offset": variation_base + 4, "part_id": part_id,
            "part_table_entry": 40, "part_item_id_offset": part_base + 6,
            "item_id": item_id,
            "model_entry": 44, "model_id": model_id,
            "shape_id": shape, "dimensions_xyz": "/".join(str(x) for x in dims),
            "item_table_entry": 983,
            "item_name_index_offset": source_item["source_field_offset"],
            "name_index": source_item["target_text_id"],
            "name_table_first_entry": NAME_START,
            "name_text_form": source_item["target_form_index"],
            "item_name_en": source_item["en"],
            "item_name_zhs": source_item["zhs"],
            "reference_kind": "MapPartVariation->Part->Item->NameIndex",
            "item_name_status": "RESOLVED" if source_item["target_text_id"] != "" else "NO_NAME_INDEX",
            "evidence_grade": "NATIVE_FIELD_CHAIN_PARSER_LAYOUT",
            "category": "MapParts",
            "building_classification": "UNVERIFIED",
        }
        rows.append(row)
        item_ids.add(item_id)
    # Fixed, source-backed regression anchors from PokoHex.Tests/DumpTests.cs.
    for variation_id, item_id in ((1498, 1357), (3197, 1628)):
        actual = next((r["item_id"] for r in rows if r["source_record_id"] == variation_id), None)
        if actual != item_id:
            raise AssertionError(f"MapPart {variation_id} expected Item {item_id}, got {actual}")
    return rows, {
        "linked_map_part_variations": len(rows),
        "unique_item_ids": len(item_ids),
        "layout_anchors": {"1498": 1357, "3197": 1628},
    }


def link_role_group(role: str, start: int, count: int, tables: dict) -> tuple[list[dict], dict]:
    """Role/ID mapping explicitly specified by GameAbilityDumper.cs."""
    if set(tables) != set(LANGS):
        raise ValueError(f"Missing {role} locale")
    nonempty_bitmap = None
    records = []
    flag_differences = 0
    for lang in LANGS:
        table = tables[lang]
        if table.count != count or table.width != 8 or table.version != 2:
            raise ValueError(f"{role}/{lang}: unexpected table layout")
        bitmap = tuple(bool(row[0][0]) for row in table.rows)
        if nonempty_bitmap is not None and bitmap != nonempty_bitmap:
            raise ValueError(f"{role}/{lang}: empty-slot alignment differs")
        nonempty_bitmap = bitmap
    for id in range(count):
        row = {
            "category": role, "entity_id": id, "target_text_id": id,
            "target_group_start": start, "target_form_index": 0,
            "relationship": "explicit_native_role_table",
            "evidence_grade": "PINNED_PARSER_ROLE_PLUS_NATIVE_ROW",
            "parser_source_url": PARSER_SOURCES["ability"],
        }
        flags = []
        for lang in LANGS:
            table = tables[lang]
            row[lang] = table.rows[id][0][0]
            row[f"{lang}_entry"] = table.entry
            row[f"{lang}_byte_offset"] = table.rows[id][1][0]
            row[f"{lang}_raw_flag"] = table.rows[id][2][0]
            flags.append(table.rows[id][2][0])
        if len(set(flags)) > 1:
            flag_differences += 1
        records.append(row)
    return records, {
        "records": count,
        "nonempty_text_ids": sum(nonempty_bitmap),
        "different_raw_flags_across_languages": flag_differences,
        "empty_slot_pattern_consistent": True,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--decoded-root", type=Path, required=True)
    ap.add_argument("--items-text-root", type=Path, default=Path("UnPack/2.0.1/Resources/Items/Text"))
    ap.add_argument("--native-items-validation", type=Path, default=Path("UnPack/2.0.1/Resources/Items/Native_2.0.1/validation.json"))
    ap.add_argument("--m7-report", type=Path, default=Path("UnPack/2.0.1/Resources/Localization/M7/m7_report.json"))
    ap.add_argument("--dest", type=Path, default=Path("UnPack/2.0.1/Resources/Localization/M8"))
    args = ap.parse_args()
    args.dest.mkdir(parents=True, exist_ok=True)

    validation = json.loads(args.native_items_validation.read_text(encoding="utf-8"))
    m7 = json.loads(args.m7_report.read_text(encoding="utf-8"))
    if validation["status"] != "MATCH" or validation["differences"] != 0:
        raise ValueError("Previous native item validation not MATCH")
    if m7["known_anchor_groups"]["4645"] != "PASS":
        raise ValueError("M7 nine-language item-name group not anchored")
    if "verified_languages" in m7 and tuple(m7["verified_languages"]) != LANGS:
        raise ValueError("M7 locale order mismatch")

    provenance = []
    cache = {}
    def blob(entry: int) -> bytes:
        if entry not in cache:
            p=args.decoded_root/f"{entry:05d}.bin"
            data=p.read_bytes()
            cache[entry]=data
            provenance.append({
                "entry":entry, "path":p.as_posix(), "bytes":len(data), "sha256":digest(data)})
        return cache[entry]

    item_blob=blob(983)
    if digest(item_blob) != validation["source"]["items"]["sha256"]:
        raise ValueError("Raw item table SHA-256 mismatch")
    item_names = {}
    for i, lang in enumerate(LANGS):
        entry=NAME_START+i
        data=blob(entry)
        expected=validation["source"]["languages"][lang]
        if entry != expected["entry"] or digest(data) != expected["sha256"]:
            raise ValueError(f"Native item {lang} source SHA-256 mismatch")
        table,status=parse_text(data,entry,(args.decoded_root/f"{entry:05d}.bin").as_posix())
        if status != "PARSED":
            raise ValueError(f"Item name table {lang} rejected: {status}")
        item_names[lang]=table

    catalog={}
    for lang in LANGS:
        path=args.items_text_root/f"text_item_{lang}.txt"
        lines=path.read_text(encoding="utf-8-sig").splitlines()
        if len(lines)!=ITEM_COUNT:
            raise ValueError(f"Item catalog for {lang}: {len(lines)} slots, expected 4600")
        catalog[lang]=lines

    items,item_report=link_item_table(item_blob,item_names,catalog)
    item_cols=list(items[0])
    save_csv(args.dest/"native_item_text_refs.csv",items,item_cols)
    save_json(args.dest/"native_item_text_refs.json",items)

    map_blobs={k:blob(k) for k in (40,41,42,44)}
    map_rows,map_report=link_map_parts(map_blobs,items)
    save_csv(args.dest/"map_part_item_name_refs.csv",map_rows,list(map_rows[0]))
    save_json(args.dest/"map_part_item_name_refs.json",map_rows)

    role_reports={}
    role_rows=[]
    for role,start,count in ROLE_GROUPS:
        tables={}
        for i,lang in enumerate(LANGS):
            entry=start+i
            data=blob(entry)
            table,status=parse_text(data,entry,(args.decoded_root/f"{entry:05d}.bin").as_posix())
            if status!="PARSED":
                raise ValueError(f"{role}/{lang} table rejected: {status}")
            tables[lang]=table
        rows,role_reports[role]=link_role_group(role,start,count,tables)
        role_rows.extend(rows)
    save_csv(args.dest/"native_role_text_refs.csv",role_rows,list(role_rows[0]))
    save_json(args.dest/"native_role_text_refs.json",role_rows)
    save_csv(args.dest/"native_source_hashes.csv",sorted(provenance,key=lambda x:x["entry"]),
             ["entry","path","bytes","sha256"])
    report={
        "status":"M8_VERIFIED_NATIVE_ITEM_MAP_ROLE_EDGES",
        "source": {"native_version":"Pokopia 2.0.1",
                   "layout_parser_commit":VERSION_PIN,
                   "item_parser":PARSER_SOURCES["item"],
                   "map_parser":PARSER_SOURCES["map"],
                   "ability_parser":PARSER_SOURCES["ability"]},
        "item_to_text":item_report,
        "map_part_to_item_to_text":map_report,
        "native_text_roles":role_reports,
        "source_files_sha256_indexed":len(provenance),
        "quest_scene_building_reference_analysis":{
            "Quest":"NO_NATIVE_CALLER_REFERENCE_PROVEN",
            "Dialogue":"NO_NATIVE_CALLER_REFERENCE_PROVEN",
            "Buildings":"MAP_PART_IS_NOT_A_BUILDING_TYPE",
            "UI":"NO_NATIVE_CALLER_REFERENCE_PROVEN",
            "Tutorials":"NO_NATIVE_CALLER_REFERENCE_PROVEN"},
        "provenance_notes":[
            "Item NameIndex is a u16 at 64+item_id*68+34 in decoded Entry 983.",
            "NameIndex resolves to record ID in Entry 4645..4653; text form 0.",
            "MapPart variation maps through native Entries 41, 40, 983 and 4645..4653.",
            "Reaction/Skill roles are backed by version-pinned parser source and native text tables.",
            "Language-specific raw flags differ in some Reaction/Skill entries; all preserved.",
            "MapParts must not be silently reclassified as Buildings.",
            "No scene/quest/mission category assigned without resource-to-text caller identity.",
            "M7 candidate group matching is independent from these explicitly source-anchored roles."
        ]
    }
    save_json(args.dest/"m8_report.json",report)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
