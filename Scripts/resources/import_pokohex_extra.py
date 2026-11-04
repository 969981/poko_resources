#!/usr/bin/env python3
"""Import reference sprites and 9-language tables from pinned PokoHex (not verified native 2.0.1)."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import shutil
import struct
from pathlib import Path

LANGS = ("en", "jp", "de", "es", "fr", "it", "ko", "zhs", "zht")
COMMIT = "c71d2b73fb9d8cfe99c1067e6bfadfd19f60bf78"
KINDS = (
    ("Villagers", "Villager", "villager", 378),
    ("Reactions", "Reaction", "reaction", 47),
    ("Skills", "Skill", "skill", 10),
)

def write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(rows)

def load_text(source, dest, category, stem):
    names = {}
    for language in LANGS:
        file = source / "PokoHex.Core/Resources/text" / language / f"text_{stem}_{language}.txt"
        lines = file.read_text(encoding="utf-8-sig").replace("\r\n", "\n").splitlines()
        names[language] = lines
        target = dest / category / "Text" / file.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if len({len(rows) for rows in names.values()}) != 1:
        raise ValueError(f"Language ID slots disagree: {category}")
    return names

def load_images(source, dest, category, upstream, stem, expected):
    paths = {}
    provenance = []
    for file in sorted((source / "PokoHex/Resources" / upstream).iterdir()):
        match = re.fullmatch(rf"{stem}_(\d{{4}})\.png", file.name)
        if not file.is_file() or match is None:
            raise ValueError(f"Unexpected source icon: {file}")
        sprite_id = int(match.group(1))
        data = file.read_bytes()
        if not data.startswith(b"\x89PNG\r\n\x1a\n") or sprite_id in paths:
            raise ValueError(f"Bad or duplicated PNG: {file}")
        target = dest / category / "Icons" / file.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file, target)
        relative = target.relative_to(dest).as_posix()
        paths[sprite_id] = relative
        provenance.append([sprite_id, relative, file.relative_to(source).as_posix(),
                           hashlib.sha256(data).hexdigest()])
    if len(paths) != expected:
        raise ValueError(f"Unexpected {category} image count: {len(paths)} != {expected}")
    write_csv(dest / category / "pokohex_icon_sources.csv",
              ["sprite_id", "icon_path", "pokohex_source_path", "sha256"], provenance)
    return paths

def import_kind(source, dest, kind):
    category, upstream, stem, expected = kind
    names = load_text(source, dest, category, stem)
    count = len(names["en"])
    images = load_images(source, dest, category, upstream, stem, expected)
    if category == "Villagers":
        raw = (source / "PokoHex.Core/Resources/byte/villager_portrait.bin").read_bytes()
        if len(raw) != 2 * count:
            raise ValueError(f"Villager portrait map byte count {len(raw)} != {count * 2}")
        portraits = struct.unpack(f"<{count}H", raw)
        columns = ["portrait_id_raw_u16", "is_public"]
    elif category == "Skills":
        portraits = ()
        columns = ["is_public", "can_use_wheel"]
    else:
        portraits = ()
        columns = ["is_public"]
    header = [stem + "_id", *LANGS, *columns, "icon_path", "has_pokohex_icon", "has_any_name"]
    rows, missing, linked = [], [], set()
    for game_id in range(count):
        values = [names[language][game_id] for language in LANGS]
        named = int(any(values))
        if category == "Villagers":
            sprite_id = portraits[game_id]
            public = named
            extra = [sprite_id, public]
        elif category == "Reactions":
            sprite_id = game_id
            public = int(1 <= game_id <= 100 and bool(names["en"][game_id]))
            extra = [public]
        else:
            sprite_id = game_id
            public = int(game_id in (*range(1, 7), *range(10, 14)))
            extra = [public, int(game_id in (*range(1, 7), 12, 13))]
        icon = images.get(sprite_id, "") if (category != "Villagers" or sprite_id != 0) else ""
        if icon:
            linked.add(sprite_id)
        if public and not icon:
            missing.append([game_id, names["zhs"][game_id], names["en"][game_id], sprite_id])
        rows.append([game_id, *values, *extra, icon, int(bool(icon)), named])
    write_csv(dest / category / f"{stem}_catalog.csv", header, rows)
    write_csv(dest / category / "missing_pokohex_icons.csv",
              [stem + "_id", "zhs", "en", "required_sprite_id"], missing)
    return {
        "game_id_slots": count, "named_slots": sum(any(row[1:1+len(LANGS)]) for row in rows),
        "pokohex_png_files": len(images), "linked_sprite_ids": len(linked),
        "unreferenced_sprite_ids": sorted(set(images) - linked),
        "missing_public_or_named_icons": len(missing),
        "sprite_id_rule": "portrait_map: villager ID -> portrait ID" if portraits else "direct",
        "native_2_0_1_verified": False, "pokohex_source_commit": COMMIT,
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--dest", type=Path, default=Path("UnPack/2.0.1/Resources"))
    args = parser.parse_args()
    results = {kind[0]: import_kind(args.source, args.dest, kind) for kind in KINDS}
    report = args.dest / "SOURCE_AND_COVERAGE.json"
    existing = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
    existing["additional_pokohex_categories"] = results
    existing["additional_pokohex_source"] = {
        "repo": "https://github.com/969981/PokoHex", "commit": COMMIT,
        "images": "PokoHex/Resources/{Villager,Reaction,Skill}",
        "names": "PokoHex.Core/Resources/text/<lang>/text_{villager,reaction,skill}_<lang>.txt",
        "portrait_map": "PokoHex.Core/Resources/byte/villager_portrait.bin",
    }
    existing.setdefault("warnings", [])
    note = "PokoHex sprite resources are third-party references, not verified native 2.0.1 game extraction."
    if note not in existing["warnings"]:
        existing["warnings"].append(note)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
