#!/usr/bin/env python3
"""Reconcile original 2.0.1 native icon sources into 1615 distinct item IDs.

No PNG copies, no overwrites and no inferred material categories.
Four duplicated native IDs preserve separate original pack variants, with the
primary atlas as deterministic canonical source and both variants in catalog.
Every referenced PNG is checked against its per-source SHA and 72x72 RGBA data.
"""
from __future__ import annotations
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image
from Scripts.resources.score_atlas_candidates import distance

RESOURCES = Path("UnPack/2.0.1/Resources")
NATIVE = RESOURCES / "Items/Native_2.0.1"
LANGUAGES = ("en", "jp", "de", "es", "fr", "it", "ko", "zhs", "zht")
HEADERS = [
    "item_id", "native_png", "native_source_group", "primary_atlas_png",
    "extra272_png", "extra14_png", "native_variant_count", "source_g1t_hash",
    "source_texinfo_hash", "native_png_sha256", "pokohex_reference_png",
    "source_evidence_status", "en", "jp", "de", "es", "fr", "it", "ko", "zhs", "zht",
]

def read_csv(path, delimiter=","):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=delimiter))

def validated_image(path, sha):
    if not path.is_file():
        raise ValueError(f"native PNG missing: {path}")
    if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
        raise ValueError(f"native image SHA mismatch: {path}")
    with Image.open(path) as im:
        if im.size != (72,72) or im.format != "PNG":
            raise ValueError(f"native image format/dimensions incorrect: {path}")
        im.verify()

def main():
    primary = read_csv(NATIVE / "native_icon_manifest.csv")
    extra272 = read_csv(NATIVE / "Extra272Candidates/manifest.csv")
    extra14 = read_csv(NATIVE / "Extra14Candidates/manifest.csv")
    inventory = read_csv(RESOURCES / "Textures/Indexes/item-id-inventory.tsv", "\t")
    names = read_csv(NATIVE / "native_item_catalog.csv")
    names_by_id = {int(x["item_id"]): x for x in names}
    expected = {int(x["item_id"]) for x in inventory}
    if len(primary) != 1333 or len(extra272) != 272 or len(extra14) != 14:
        raise ValueError("source atlas row coverage unexpectedly changed")
    if len(expected) != 1615 or len(names_by_id) != 4600:
        raise ValueError("native item ID inventory changed")
    groups = defaultdict(dict)
    for record in primary:
        item = int(record["item_id"])
        if "primary" in groups[item]:
            raise ValueError(f"duplicate primary atlas record {item}")
        groups[item]["primary"] = (Path(record["png_path"]), record["png_sha256"],
                                   "a0ce9914", "b4b1fe49")
    for record in extra272:
        item = int(record["item_id"])
        if "extra272" in groups[item]:
            raise ValueError(f"duplicate second atlas record {item}")
        groups[item]["extra272"] = (Path(record["png"]), record["png_sha256"],
                                    record["g1t_hash"], record["texinfo_hash"])
    for record in extra14:
        item = int(record["id"])
        if "extra14" in groups[item]:
            raise ValueError(f"duplicate 14 atlas record {item}")
        groups[item]["extra14"] = (Path(record["path"]), record["sha256"],
                                   record["g1t_hash"], record["texinfo_hash"])
    if set(groups) != expected:
        missing, surplus = sorted(expected - set(groups)), sorted(set(groups) - expected)
        raise ValueError(f"native source coverage mismatch; missing={missing[:30]}, surplus={surplus[:30]}")

    rows, duplicate_rows = [], []
    count = Counter()
    for item in sorted(groups):
        variants = groups[item]
        for path, digest, _, _ in variants.values():
            validated_image(path, digest)
        chosen = next((group for group in ("primary", "extra272", "extra14") if group in variants), None)
        path, digest, g1t, texinfo = variants[chosen]
        extra_paths = {group: str(variants[group][0]) if group in variants else "" for group in ("primary", "extra272", "extra14")}
        ref = RESOURCES / "Items/Icons" / f"item_{item:04d}.png"
        if not ref.is_file():
            raise ValueError(f"reference image missing for mapped item {item}")
        if len(variants) > 1:
            groups_sorted = sorted(variants.keys())
            if groups_sorted != ["extra272", "primary"]:
                raise ValueError(f"unexpected icon source overlap: item {item}: {groups_sorted}")
            altpath = variants["extra272"][0]
            duplicate_rows.append({
                "item_id": item, "primary_png": str(variants["primary"][0]),
                "alternate_png": str(altpath),
                "primary_vs_secondary_distance": distance(variants["primary"][0], altpath),
                "primary_vs_pokohex_distance": distance(variants["primary"][0], ref),
                "secondary_vs_pokohex_distance": distance(altpath, ref),
                "decision": "PRESERVE_BOTH_PRIMARY_CANONICAL_UNTIL_MANUAL_REVIEW",
            })
        count[chosen] += 1
        name = names_by_id[item]
        rows.append({
            "item_id": item, "native_png": str(path), "native_source_group": chosen,
            "primary_atlas_png": extra_paths["primary"],
            "extra272_png": extra_paths["extra272"],
            "extra14_png": extra_paths["extra14"],
            "native_variant_count": len(variants),
            "source_g1t_hash": g1t, "source_texinfo_hash": texinfo,
            "native_png_sha256": digest, "pokohex_reference_png": str(ref),
            "source_evidence_status": "ORIGINAL_SOURCE_UV_AND_PNG_CHECKED_REFERENCE_HEURISTIC",
            **{lang: name.get(lang, "") for lang in LANGUAGES},
        })
    if dict(count) != {"primary":1333,"extra272":268,"extra14":14}:
        raise ValueError(f"unexpected canonical source distribution {dict(count)}")
    if sorted(x["item_id"] for x in duplicate_rows) != [1677,1764,1765,2742]:
        raise ValueError("unexpected duplicate variant IDs")
    with (NATIVE / "native_icon_complete_catalog.csv").open("w", encoding="utf-8", newline="") as f:
        w=csv.DictWriter(f, fieldnames=HEADERS)
        w.writeheader();w.writerows(rows)
    dupfields = ["item_id", "primary_png", "alternate_png", "primary_vs_secondary_distance",
                 "primary_vs_pokohex_distance", "secondary_vs_pokohex_distance", "decision"]
    with (NATIVE / "native_icon_variant_review.csv").open("w", encoding="utf-8", newline="") as f:
        w=csv.DictWriter(f, fieldnames=dupfields)
        w.writeheader();w.writerows(duplicate_rows)
    summary={
        "game_version":"2.0.1",
        "original_native_png_records":1619,
        "unique_item_ids":1615,
        "primary_atlas":1333,"secondary_atlas":272,"mixed_special_atlas":14,
        "canonical_source_counts":dict(count),
        "duplicate_item_ids":[1677,1764,1765,2742],
        "images_checked_for_existence_size_and_sha256":1619,
        "language_columns":list(LANGUAGES),
        "warnings":[
            "The 1615 icon IDs have source-linked PNGs, but 3586 items have nonempty names; an icon is not proven present for every named ID.",
            "Reference differences are heuristic; neither perfect native pixels nor object identity is established by a similarity score.",
            "Four overlapping item IDs preserve all native atlas variants without overwriting earlier PNGs.",
            "Do not classify material vs other items by name alone."
        ],
    }
    (NATIVE / "native_icon_coverage.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
