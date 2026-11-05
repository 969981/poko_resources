#!/usr/bin/env python3
"""Reconcile PokoHex reference icons against already-exported Pokopia 2.0.1 ROMFS PNGs.

This never assumes numerical equality between PokoHex portrait/reaction/skill IDs
and native TEXINFO sprite names. Source-qualified native PNGs come from the M5/M9
TEXINFO -> KIDSOBJDB -> G1T decoding pipeline. Only *pixel-exact* matches link
reference IDs; any remaining identity is explicitly unverified.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

ROOT = Path("UnPack/2.0.1/Resources")
ROMFS_NATIVE = "UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native"
HEADERS = [
    "reference_sprite_id", "reference_png", "reference_png_sha256",
    "reference_game_ids_from_pokohex", "status", "match_count",
    "native_texture_name", "native_png", "native_export_png",
    "native_png_sha256", "native_texinfo_path", "native_g1t_path",
    "native_texinfo_hash", "native_g1t_hash", "native_record_index",
    "native_layer", "native_source_kind", "pixel_rgba_sha256",
]


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, records: list[dict[str, str]], headers=HEADERS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        w.writeheader()
        w.writerows(records)


def pixel_identity(path: Path) -> tuple[int, int, str]:
    """RGBA pixel hash, ignoring invisible RGB in fully transparent pixels."""
    with Image.open(path) as im:
        rgba = im.convert("RGBA")
        width, height = rgba.size
        pixels = bytearray(rgba.tobytes())
    for i in range(0, len(pixels), 4):
        if pixels[i + 3] == 0:
            pixels[i:i + 3] = b"\x00\x00\x00"
    return width, height, hashlib.sha256(pixels).hexdigest()


def check_file(path: Path, expected_sha256: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Original indexed PNG is absent: {path}")
    got = hashlib.sha256(path.read_bytes()).hexdigest()
    if got.lower() != expected_sha256.lower():
        raise ValueError(f"Original PNG SHA256 mismatch: {path}: {got} != {expected_sha256}")


def collect_misc(category: str) -> list[dict[str, str]]:
    pattern = (r"icon_emote_\d{3}" if category == "Reactions"
               else r"icon_skill_\d{3}")
    records = []
    for batch in ("14", "15"):
        src = ROOT / "Textures/MiscNativeBatches" / f"batch_{batch}/misc_native_sample_manifest.csv"
        for row in load_csv(src):
            if not re.fullmatch(pattern, row["texture_name"]):
                continue
            if not row["png_path"]:
                raise ValueError(f"Missing native PNG: {row['texture_name']}")
            records.append({
                "name": row["texture_name"],
                "path": row["png_path"],
                "sha": row["png_sha256"],
                "texinfo": row["texinfo_path"],
                "g1t": row["g1t_path"],
                "thash": row["texinfo_hash"],
                "ghash": row["g1t_hash"],
                "record": row["record_index"],
                "layer": row["layer"],
                "kind": "ORIGINAL_NATIVE_G1T",
                "raw_status": row["status"],
            })
    expected = 40 if category == "Reactions" else 14
    if len(records) != expected:
        raise ValueError(f"{category}: expected {expected} exact native TEXINFO rows, got {len(records)}")
    return records


def collect_pokemon() -> list[dict[str, str]]:
    src = ROOT / "Pokemon/NativeCandidates/pokemon_native_manifest.csv"
    records = []
    for row in load_csv(src):
        if not re.fullmatch(r"icon_poke_(?:uni_)?\d{4}_\d{2}_\d{2}_\d{2}", row["texture_name"]):
            continue
        records.append({
            "name": row["texture_name"],
            "path": row["png_path"],
            "sha": row["png_sha256"],
            "texinfo": ROMFS_NATIVE + "/" + row["texinfo_file"],
            "g1t": (ROMFS_NATIVE + "/" + row["g1t_file"]
                    if row["source_kind"] == "ORIGINAL_NATIVE_G1T"
                    else "ALIAS_RECOVERED:" + row["g1t_file"]),
            "thash": row["texinfo_hash"],
            "ghash": row["g1t_hash"],
            "record": row["texinfo_record_index"],
            "layer": row["texture_layer"],
            "kind": row["source_kind"],
            "raw_status": row["status"],
        })
    if len(records) != 609:
        raise ValueError(f"Expected 609 original/alias Pokémon PNG rows, got {len(records)}")
    return records


def reference_game_ids(category: str) -> dict[str, list[str]]:
    stem = {"Villagers": "villager", "Reactions": "reaction", "Skills": "skill"}[category]
    ids = defaultdict(list)
    for row in load_csv(ROOT / category / f"{stem}_catalog.csv"):
        icon = row["icon_path"]
        if icon:
            sprite = re.search(r"_(\d{4})\.png$", icon)
            if sprite:
                ids[str(int(sprite.group(1)))].append(row[f"{stem}_id"])
    return ids


def export_category(category: str, native: list[dict[str, str]], copy_native: bool) -> dict[str, object]:
    dest = ROOT / category / "Native_2.0.1"
    refs = load_csv(ROOT / category / "pokohex_icon_sources.csv")
    ids = reference_game_ids(category)
    indexed = defaultdict(list)
    nrows = []
    for r in native:
        source = Path(r["path"])
        check_file(source, r["sha"])
        identity = pixel_identity(source)
        r = {**r, "pixel": identity[2], "width": identity[0], "height": identity[1]}
        indexed[identity].append(r)
        nrows.append(r)

    results = []
    used_native = set()
    for ref in refs:
        ref_id = ref["sprite_id"]
        ref_file = ROOT / ref["icon_path"]
        check_file(ref_file, ref["sha256"])
        identity = pixel_identity(ref_file)
        found = indexed.get(identity, [])
        status = ("PIXEL_EXACT_UNIQUE" if len(found) == 1 else
                  "PIXEL_EXACT_MULTIPLE_SOURCES" if found else "NO_PIXEL_EXACT_NATIVE")
        targets = found if found else [None]
        for native_row in targets:
            export_path = ""
            if native_row:
                used_native.add(native_row["path"])
                if copy_native:
                    export_file = dest / "Icons" / Path(native_row["path"]).name
                    export_file.parent.mkdir(parents=True, exist_ok=True)
                    if not export_file.exists() or hashlib.sha256(export_file.read_bytes()).hexdigest() != native_row["sha"]:
                        shutil.copyfile(native_row["path"], export_file)
                    export_path = export_file.as_posix()
            results.append({
                "reference_sprite_id": ref_id,
                "reference_png": str((ROOT / ref["icon_path"]).as_posix()),
                "reference_png_sha256": ref["sha256"],
                "reference_game_ids_from_pokohex": ";".join(ids.get(ref_id, [])),
                "status": status,
                "match_count": str(len(found)),
                "native_texture_name": native_row["name"] if native_row else "",
                "native_png": native_row["path"] if native_row else "",
                "native_export_png": export_path,
                "native_png_sha256": native_row["sha"] if native_row else "",
                "native_texinfo_path": native_row["texinfo"] if native_row else "",
                "native_g1t_path": native_row["g1t"] if native_row else "",
                "native_texinfo_hash": native_row["thash"] if native_row else "",
                "native_g1t_hash": native_row["ghash"] if native_row else "",
                "native_record_index": native_row["record"] if native_row else "",
                "native_layer": native_row["layer"] if native_row else "",
                "native_source_kind": native_row["kind"] if native_row else "",
                "pixel_rgba_sha256": native_row["pixel"] if native_row else "",
            })

    # Every sprite with a native source is retained as a native sprite, even if
    # PokoHex has no ID for it. For Villagers use already existing Pokémon
    # candidates rather than duplicating all 609 source images.
    if category != "Villagers":
        for r in nrows:
            file = dest / "Icons" / Path(r["path"]).name
            file.parent.mkdir(parents=True, exist_ok=True)
            if not file.exists() or hashlib.sha256(file.read_bytes()).hexdigest() != r["sha"]:
                shutil.copyfile(r["path"], file)

    refs_matched = {r["reference_sprite_id"] for r in results if r["match_count"] != "0"}
    statuses = dict(Counter({r["reference_sprite_id"]: r["status"] for r in results}.values()))
    write_csv(dest / "native_icon_crosswalk.csv", results)
    summary = {
        "version": "2.0.1", "category": category,
        "pokohex_reference_count": len(refs),
        "native_texinfo_png_candidates": len(native),
        "pixel_exact_matched_reference_icons": len(refs_matched),
        "unmatched_reference_icons": len(refs) - len(refs_matched),
        "native_pngs_used_by_exact_matches": len(used_native),
        "reference_status_counts": statuses,
        "evidence": "RGBA visible-pixel SHA256 identity, sourced from verified native TEXINFO/G1T PNG manifests",
        "id_provenance": "Game-ID and portrait-ID columns, when present, originate in pinned PokoHex; no native runtime ID binding is implied.",
        "limitations": "Pixel identity is not proof of original native species/villager ID; visual-only or fuzzy candidates are intentionally never joined.",
    }
    (dest / "native_icon_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", choices=["Reactions", "Skills", "Villagers", "all"], default="all")
    args = parser.parse_args()
    categories = ("Reactions", "Skills", "Villagers") if args.category == "all" else (args.category,)
    summaries = {}
    for category in categories:
        native = collect_pokemon() if category == "Villagers" else collect_misc(category)
        summaries[category] = export_category(category, native, copy_native=True)
    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
