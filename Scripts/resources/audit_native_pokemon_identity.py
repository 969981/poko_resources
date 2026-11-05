#!/usr/bin/env python3
"""Source-trace 2.0.1 Pokémon icon sprites without inventing Pokédex IDs.

Cross-check the texture index, the decoded PNG manifest and KIDSOBJDB layout
index; keep every source-qualified duplicate.  A numeric icon_poke_ suffix is
NOT evidence of a native species ID, so verified_species_id stays empty.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("UnPack/2.0.1/Resources")
FIELDS = [
    "texture_name", "texture_category", "texture_number_candidate",
    "texture_form_suffix", "native_species_id_verified", "species_identity_status",
    "texinfo_hash", "g1t_hash", "texinfo_filename", "g1t_filename",
    "texinfo_record_index", "texture_layer", "object_hash", "objdb_file",
    "reference_evidence", "source_kind", "swizzle_layout",
    "png_path", "png_sha256", "png_decode_status", "link_status",
]
NAME = re.compile(r"^icon_poke(?:_uni)?_(\d{4})_(\d{2})_(\d{2})_(\d{2})(?:_(.*))?$")


def rows(path, delimiter=","):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def build(index, manifest, layouts):
    edges = defaultdict(list)
    for e in layouts:
        edges[(e["texinfo_hash"].lower(), e["g1t_hash"].lower())].append(e)
    pngs = defaultdict(list)
    for p in manifest:
        pngs[(p["texture_name"], p["texinfo_hash"], p["g1t_hash"])].append(p)

    result = []
    for sprite in index:
        key = (sprite["texture_name"], sprite["texinfo_hash"], sprite["g1t_hash"])
        pair = (sprite["texinfo_hash"].lower(), sprite["g1t_hash"].lower())
        mapped, evidence = pngs.get(key, []), edges.get(pair, [])
        match = NAME.match(sprite["texture_name"])
        number = match.group(1) if match else ""
        suffix = "_".join(match.groups()[1:4]) if match else ""
        if match and match.group(5):
            suffix += "_" + match.group(5)
        if len(mapped) != 1:
            status = "MISSING_OR_AMBIGUOUS_PNG_MANIFEST"
        elif len(evidence) != 1:
            status = "MISSING_OR_AMBIGUOUS_KIDSOBJDB_INDEX_EDGE"
        elif not mapped[0]["png_path"] or not mapped[0]["png_sha256"]:
            status = "PNG_NOT_EXPORTED"
        elif sprite["status"] != "PHYSICAL_G1T_PRESENT":
            status = "PHYSICAL_G1T_NOT_CONFIRMED"
        else:
            status = "INDEX_PNG_AND_HASH_EDGE_LINKED"
        row = mapped[0] if len(mapped) == 1 else {}
        edge = evidence[0] if len(evidence) == 1 else {}
        result.append({
            "texture_name": sprite["texture_name"],
            "texture_category": sprite["category"],
            "texture_number_candidate": number or sprite["texture_number_candidate"],
            "texture_form_suffix": suffix,
            "native_species_id_verified": "",
            "species_identity_status": "TEXTURE_NUMBER_ONLY__NATIVE_SPECIES_REFERENCE_UNVERIFIED",
            "texinfo_hash": sprite["texinfo_hash"], "g1t_hash": sprite["g1t_hash"],
            "texinfo_filename": sprite["texinfo_filename"],
            "g1t_filename": sprite["g1t_filename"],
            "texinfo_record_index": sprite["texinfo_record_index"],
            "texture_layer": sprite["texture_layer"],
            "object_hash": edge.get("object_hash", ""),
            "objdb_file": edge.get("objdb_file", ""),
            "reference_evidence": "EXTRACTED_TEXINFO_NAME_UV_G1T_SHA_AND_KIDSOBJDB_INDEX" if status == "INDEX_PNG_AND_HASH_EDGE_LINKED" else "INCOMPLETE_INDEX",
            "source_kind": sprite["native_source_kind"],
            "swizzle_layout": row.get("swizzle_layout", ""),
            "png_path": row.get("png_path", ""),
            "png_sha256": row.get("png_sha256", ""),
            "png_decode_status": row.get("status", "MISSING"),
            "link_status": status,
        })
    return result


def main():
    root = ROOT / "Pokemon"
    original = rows(root / "pokemon_texture_index.csv")
    decoded = rows(root / "NativeCandidates/pokemon_native_manifest.csv")
    native_edges = rows(ROOT / "Textures/Indexes/layout-textures.tsv", "\t")
    audit = build(original, decoded, native_edges)
    if len(original) != 609 or len(decoded) != 609 or len(audit) != 609:
        raise ValueError("source/manifest row count mismatch")
    if len(set((r["texture_name"],r["texinfo_hash"],r["g1t_hash"]) for r in audit)) != 609:
        raise ValueError("duplicate source-qualified row")
    output = root / "pokemon_identity_crosswalk.csv"
    with output.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(audit)
    statuses = dict(Counter(row["link_status"] for row in audit))
    summary = {
        "game_version":"2.0.1", "native_texture_rows":len(audit),
        "distinct_texture_names":len(set(row["texture_name"] for row in audit)),
        "linked_png_and_kidsobjdb_index":statuses.get("INDEX_PNG_AND_HASH_EDGE_LINKED",0),
        "status_counts":statuses,
        "species_id_verified_count":0,
        "source_kinds":dict(Counter(x["source_kind"] for x in audit)),
        "texture_number_field_is_species_id":False,
        "next_required_evidence":"Original native species/villager lookup table or a runtime sprite-binding consumer pointing to the same texture resource hash, plus visual cross-check",
        "note":"609 rows are native source-qualified TEXINFO records, not 609 confirmed species. Numeric texture names are retained as unverified candidates."
    }
    (root / "pokemon_identity_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if summary["linked_png_and_kidsobjdb_index"] != 609:
        raise ValueError(f"unresolved texture/source links: {statuses}")
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
