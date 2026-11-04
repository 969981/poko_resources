#!/usr/bin/env python3
"""Join native TEXINFO sprite records to existing KIDSOBJDB layout index edges.

Index evidence is not pixel evidence: a matching G1T hash cannot establish
that a generated PNG has correct swizzle, orientation, alpha, or item identity.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

TEXINFO_HASH = re.compile(r"root_\d+_([0-9a-fA-F]{8})\.texinfo$")
SPRITE_NAME = re.compile(r"item_(\d+)(?:_m)?$", re.I)
FIELDS = (
    "item_id", "zhs", "en", "sprite_name", "variant", "has_pokohex_png",
    "texinfo_hash", "texinfo_path", "texinfo_record_index", "texinfo_record_count",
    "atlas_u0", "atlas_v0", "atlas_u1", "atlas_v1", "uv_status",
    "g1t_hash", "g1t_pack", "g1t_bytes", "objdb_file", "object_hash",
    "link_evidence", "pixel_validation",
)


def load_rows(path: Path, delimiter: str = ",") -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter=delimiter))


def save_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def make_links(texinfo: list[dict[str, str]],
               mapping: list[dict[str, str]],
               layout: list[dict[str, str]],
               catalog: list[dict[str, str]]) -> tuple[list[dict[str, str]], dict]:
    catalog_by_id = {int(r["item_id"]): r for r in catalog}
    if len(catalog_by_id) != len(catalog):
        raise ValueError("duplicate item IDs in catalog")

    names: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for entry in texinfo:
        match = TEXINFO_HASH.search(entry["texinfo_path"])
        if match and entry["texture_name"]:
            names[(match.group(1).lower(), entry["texture_name"])].append(entry)

    edges: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for entry in layout:
        pair = (entry["texinfo_hash"].lower(), entry["g1t_hash"].lower())
        edges[pair].add((entry["objdb_file"], entry["object_hash"]))

    rows: list[dict[str, str]] = []
    evidence = Counter()
    for entry in mapping:
        item_id = int(entry["item_id"])
        if item_id not in catalog_by_id:
            raise ValueError(f"missing catalog item_id {item_id}")
        sprite = entry["sprite_name"]
        match = SPRITE_NAME.fullmatch(sprite)
        if not match or int(match.group(1)) != item_id:
            raise ValueError(f"sprite name / item ID disagreement: {sprite} / {item_id}")

        th, gh = entry["texinfo_hash"].lower(), entry["g1t_hash"].lower()
        pair = (th, gh)
        refs = sorted(edges.get(pair, ()))
        if not refs:
            raise ValueError(f"missing indexed KIDSOBJDB layout edge: {th} -> {gh}")
        if entry["g1t_index_match"] != "True":
            raise ValueError(f"unverified G1T index marker: {sprite}")

        matches = names.get((th, sprite), [])
        if len(matches) == 1:
            record = matches[0]
            grade = "TEXINFO_NAME_UV_AND_LAYOUT_INDEX"
        elif not matches:
            record = {}
            grade = "LAYOUT_INDEX_ONLY_TEXINFO_NOT_SCANNED"
        else:
            record = {}
            grade = "AMBIGUOUS_MULTIPLE_TEXINFO_RECORDS"

        cat = catalog_by_id[item_id]
        row = {
            "item_id": str(item_id), "zhs": cat["zhs"], "en": cat["en"],
            "sprite_name": sprite, "variant": entry["variant"],
            "has_pokohex_png": cat["has_pokohex_icon"],
            "texinfo_hash": th, "texinfo_path": record.get("texinfo_path", ""),
            "texinfo_record_index": record.get("record_index", ""),
            "texinfo_record_count": record.get("record_count", ""),
            "atlas_u0": record.get("atlas_u0", ""),
            "atlas_v0": record.get("atlas_v0", ""),
            "atlas_u1": record.get("atlas_u1", ""),
            "atlas_v1": record.get("atlas_v1", ""),
            "uv_status": record.get("uv_status", ""),
            "g1t_hash": gh, "g1t_pack": entry["g1t_pack"],
            "g1t_bytes": entry["g1t_bytes"],
            "objdb_file": "|".join(sorted({p for p, _ in refs})),
            "object_hash": "|".join(sorted({obj for _, obj in refs})),
            "link_evidence": grade, "pixel_validation": "NOT_VISUALLY_VERIFIED",
        }
        rows.append(row)
        evidence[grade] += 1

    rows.sort(key=lambda r: (int(r["item_id"]), r["variant"], r["sprite_name"]))
    mapped_ids = {int(r["item_id"]) for r in rows}
    named = {
        item_id for item_id, r in catalog_by_id.items()
        if r["en"] not in ("", "(Empty)")
    }
    with_icon = {
        item_id for item_id, r in catalog_by_id.items()
        if r["has_pokohex_icon"] == "1"
    }
    atlas_rows = [r for r in rows if
                  r["texinfo_record_count"].isdigit() and
                  int(r["texinfo_record_count"]) > 1]
    repeated = Counter((r["texinfo_hash"], r["g1t_hash"]) for r in rows)
    report = {
        "scope": "2.0.1 indexed TEXINFO names and KIDSOBJDB layout edges; "
                 "G1T pixels have not been visually validated",
        "item_slots": len(catalog_by_id),
        "named_items": len(named),
        "pokohex_png_item_ids": len(with_icon),
        "indexed_item_ids": len(mapped_ids),
        "index_edges": len(rows),
        "texinfo_record_matches": evidence["TEXINFO_NAME_UV_AND_LAYOUT_INDEX"],
        "atlas_record_link_rows": len(atlas_rows),
        "evidence": dict(sorted(evidence.items())),
        "named_without_pokohex_png": len(named - with_icon),
        "missing_png_items_in_current_map": len((named - with_icon) & mapped_ids),
        "top_shared_g1t_references": [
            {"texinfo_hash": th, "g1t_hash": gh, "sprite_links": n}
            for (th, gh), n in repeated.most_common(10)
        ],
        "warnings": [
            "PokoHex PNG copies are not native 2.0.1 G1T exports.",
            "A shared G1T must be cropped by per-sprite TEXINFO UVs, not assigned whole to each item.",
            "NO_TEXINFO_IN_SCANNED_PACK does not prove the game has no texture.",
            "Correct swizzle, alpha, vertical origin and PNG visual identity remain unverified.",
        ],
    }
    return rows, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resources", type=Path,
                        default=Path("UnPack/2.0.1/Resources"))
    args = parser.parse_args()
    root = args.resources
    rows, audit = make_links(
        load_rows(root / "Textures" / "texinfo_names.csv"),
        load_rows(root / "Textures" / "Indexes" / "item-texture-map.tsv", "\t"),
        load_rows(root / "Textures" / "Indexes" / "layout-textures.tsv", "\t"),
        load_rows(root / "Items" / "item_catalog.csv"),
    )
    target = root / "Textures" / "Indexes"
    save_rows(target / "item_native_texture_links.csv", rows)
    (target / "item_native_texture_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
