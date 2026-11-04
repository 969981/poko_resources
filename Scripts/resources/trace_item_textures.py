#!/usr/bin/env python3
"""M5 source-traceable sprite index: three TSVs -> native TEXINFO/G1T -> PNG candidates.

Trust levels:
TABLE_MATCH: TSV cross-join only;
NATIVE_MATCH: real TEXINFO name, G1T bytes and source pack match;
PNG_CANDIDATE: image decoded; layout/appearance not established;
ATLAS_UNCROPPED: shared texture, not an individual item PNG.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from g1t_to_png import parse_g1t, decode_png

COLUMNS = ["item_id", "sprite_name", "variant", "texinfo_hash", "g1t_hash",
           "g1t_pack", "g1t_bytes", "object_hash", "objdb_file",
           "texinfo_path", "g1t_path", "objdb_path", "name_matches",
           "g1t_size_matches", "object_found", "status"]


def table(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def build_files(root, suffix):
    found = defaultdict(list)
    for path in root.rglob("*." + suffix):
        hash_value = path.stem.rsplit("_", 1)[-1].lower()
        if len(hash_value) == 8 and all(c in "0123456789abcdef" for c in hash_value):
            found[hash_value].append(path)
    return found


def pack_of(path):
    p = path.parent.parent
    if p.parent.name.startswith("MountPoint_"):
        return p.parent.name + "/" + p.name
    return p.name


def choose(paths, pack=None):
    if pack:
        pack = pack.replace("\\", "/").lower()
        paths = [p for p in paths if pack_of(p).lower() == pack]
    return paths[0] if len(paths) == 1 else None


def texinfo_name(path):
    data = path.read_bytes()
    if len(data) < 68 or int.from_bytes(data[:4], "little") != 1:
        return ""
    try:
        return data[4:68].split(b"\0", 1)[0].decode("ascii")
    except UnicodeDecodeError:
        return ""


def main():
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--root", type=Path, default=Path("UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE"))
    a.add_argument("--indexes", type=Path, default=Path("UnPack/2.0.1/Resources/Textures/Indexes"))
    a.add_argument("--output", type=Path, default=Path("UnPack/2.0.1/Resources"))
    a.add_argument("--ids", help="comma-separated item IDs to export preview candidates")
    a.add_argument("--max-preview", type=int, default=10)
    a.add_argument("--layouts", default="linear,gob1,gob2,gob4,gob8")
    args = a.parse_args()

    links = table(args.indexes / "layout-textures.tsv")
    mapped = table(args.indexes / "item-texture-map.tsv")
    inventories = table(args.indexes / "item-id-inventory.tsv")
    pairs = defaultdict(list)
    for row in links:
        pairs[(row["texinfo_hash"].lower(), row["g1t_hash"].lower())].append(row)
    alltex = build_files(args.root, "texinfo")
    allg1t = build_files(args.root, "g1t")
    allobj = build_files(args.root, "kidsobjdb")
    chosen_ids = {str(int(x)) for x in args.ids.split(",")} if args.ids else None
    layouts = args.layouts.split(",")

    rows = []
    count = Counter()
    for item in mapped:
        pair = (item["texinfo_hash"].lower(), item["g1t_hash"].lower())
        matching_links = pairs.get(pair, [])
        # Never claim exact linkage without unambiguous matching KIDSOBJDB row.
        link = matching_links[0] if len(matching_links) == 1 else None
        if link:
            native_pack = item["g1t_pack"]
            db_pack = link["objdb_file"].split("__", 1)[0] + ".fdata"
            obj_hash = link["objdb_file"].split("__", 1)[-1].split(".", 1)[0]
            tex = choose(alltex[pair[0]], native_pack)
            g1t = choose(allg1t[pair[1]], native_pack)
            obj = choose(allobj[obj_hash], db_pack)
        else:
            tex = g1t = obj = None
        expected_name = item["sprite_name"]
        name_ok = bool(tex and texinfo_name(tex) == expected_name)
        size_ok = bool(g1t and g1t.stat().st_size == int(item["g1t_bytes"]))
        obj_ok = bool(obj)
        if not link:
            status = "AMBIGUOUS_OR_MISSING_LAYOUT"
        elif name_ok and size_ok and obj_ok:
            status = "NATIVE_MATCH"
        else:
            status = "NATIVE_MISMATCH"
        count[status] += 1
        rows.append({**{k: item.get(k, "") for k in COLUMNS},
                     "object_hash": link["object_hash"] if link else "",
                     "objdb_file": link["objdb_file"] if link else "",
                     "texinfo_path": tex.as_posix() if tex else "",
                     "g1t_path": g1t.as_posix() if g1t else "",
                     "objdb_path": obj.as_posix() if obj else "",
                     "name_matches": str(name_ok),
                     "g1t_size_matches": str(size_ok),
                     "object_found": str(obj_ok),
                     "status": status})

    out = args.output / "Textures"
    out.mkdir(parents=True, exist_ok=True)
    with (out / "item_native_link_audit.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)

    ids = {r["item_id"] for r in rows}
    if ids != {r["item_id"] for r in inventories}:
        raise ValueError("inventory item IDs disagree with texture map")
    if len(rows) != len(mapped) or not rows:
        raise ValueError("index mismatch")
    # Avoid falsely duplicating atlas texture for every item.
    preview = args.output / "Items" / "NativeCandidates"
    preview.mkdir(parents=True, exist_ok=True)
    exported = 0
    preview_status = []
    for r in rows:
        if r["status"] != "NATIVE_MATCH" or not r["variant"]:
            continue
        if chosen_ids is not None and r["item_id"] not in chosen_ids:
            continue
        if exported >= args.max_preview:
            break
        source = Path(r["g1t_path"])
        try:
            platform, textures = parse_g1t(source.read_bytes())
        except ValueError as e:
            preview_status.append({"sprite": r["sprite_name"], "status": "FAILED_G1T", "reason": str(e)})
            continue
        for ti, tex in enumerate(textures):
            for layout in layouts:
                try:
                    png = decode_png(tex["payload"], tex["width"], tex["height"], layout, tex["format"])
                except Exception as e:
                    preview_status.append({"sprite": r["sprite_name"], "layout": layout,
                                           "status": "FAILED_PNG", "reason": str(e)})
                    continue
                target = preview / (r["sprite_name"] + "__" + r["g1t_hash"] + "__t" +
                                    str(ti) + "__" + layout + ".png")
                target.write_bytes(png)
                preview_status.append({"sprite": r["sprite_name"], "layout": layout,
                                       "source": source.as_posix(), "sha256": hashlib.sha256(png).hexdigest(),
                                       "png": target.as_posix(), "status": "PNG_CANDIDATE_UNVERIFIED"})
        exported += 1

    counts = Counter(x["status"] for x in preview_status)
    summary = {"layout_rows": len(links), "mapping_rows": len(mapped),
               "inventory_items": len(inventories), "layout_zero_rows":
               sum(x["texinfo_hash"] == "00000000" for x in links),
               "link_status": dict(count), "g1t_scanned": sum(map(len, allg1t.values())),
               "texinfo_scanned": sum(map(len, alltex.values())),
               "previews": dict(counts),
               "warning": "User-supplied TSV provenance is not independently proven; NATIVE_MATCH means name, bytes, pack and object path checked. PNG layout is not yet validated; atlas cropping is not supported."}
    (out / "item_native_link_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (out / "item_native_preview_manifest.csv").open("w", encoding="utf-8", newline="") as f:
        fields = ["sprite", "layout", "source", "sha256", "png", "status", "reason"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(preview_status)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
