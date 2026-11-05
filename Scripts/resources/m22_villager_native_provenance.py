#!/usr/bin/env python3
"""M22: original-source audit of 79 unresolved villager portraits and 9 ambiguous icons.

Read-only investigation. Original KIDSOBJDB object references and physical
TEXINFO/G1T paths are evidence; a PokoHex portrait_id or visible sprite-name
number is NOT proven to be a native species/villager ID.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import struct
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

ROOT = Path("UnPack/2.0.1/Resources")
OUT = ROOT / "Villagers/Native_2.0.1/M22"
FIELD = 0x2856A1B3
EXPECTED_MISSING = 88
EXPECTED_AMBIG = 9
EXPECTED_FAR = 79
EXPECTED_M19_EDGES = 603
EXPECTED_MISC = 3930
EXPECTED_NATIVE = 609

def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def sprite_id(name):
    m = re.search(r"_(\d{4})\.png$", name)
    return int(m.group(1)) if m else None

def thumb(path, expected_sha=None):
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    if expected_sha and hashlib.sha256(source.read_bytes()).hexdigest() != expected_sha:
        raise ValueError(f"Original PNG SHA-256 changed: {source}")
    with Image.open(source) as im:
        pic = im.convert("RGBA")
        if pic.width < 16 or pic.height < 16:
            return None, (pic.width, pic.height)
        pic = Image.alpha_composite(Image.new("RGBA", pic.size), pic)
        return pic.resize((32, 32), Image.Resampling.LANCZOS), (pic.width, pic.height)

def distance(a, b):
    return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / (4 * 255.0)

def top_insert(heap, value, limit=5):
    heap.append(value)
    heap.sort(key=lambda p: (p[0], p[1]["texture_name"], p[1]["png_path"]))
    del heap[limit:]

def collect():
    m21 = read_csv(ROOT / "Villagers/Native_2.0.1/native_icon_crosswalk.csv")
    catalog = read_csv(ROOT / "Villagers/villager_catalog.csv")
    native = read_csv(ROOT / "Pokemon/pokemon_identity_crosswalk.csv")
    m19 = read_csv(ROOT / "Pokemon/NativeCallers/M19/m19_verified_texture_object_edges.csv")
    missing = [r for r in m21 if r["status"] == "NO_CONFIDENT_IMAGE_CANDIDATE"]
    ambiguous = [r for r in missing if float(r["nearest_normalized_mae"]) <= .015]
    far = [r for r in missing if float(r["nearest_normalized_mae"]) > .015]
    if (len(m21), len(native), len(m19), len(missing), len(ambiguous), len(far)) != (
        378, EXPECTED_NATIVE, EXPECTED_M19_EDGES, EXPECTED_MISSING, EXPECTED_AMBIG, EXPECTED_FAR):
        raise ValueError("M21/M19 input changed: update expected counts and rerun original evidence audit")
    grouped = defaultdict(list)
    for r in catalog:
        if r["has_any_name"] == "1" and r["portrait_id_raw_u16"]:
            grouped[int(r["portrait_id_raw_u16"])].append(r)
    return missing, ambiguous, far, native, m19, grouped

def refs_for(grouped, portrait):
    return grouped.get(int(portrait), [])

def list_missing(far, grouped):
    rows = []
    for r in sorted(far, key=lambda x: int(x["reference_sprite_id"])):
        rid = int(r["reference_sprite_id"])
        owners = refs_for(grouped, rid)
        rows.append({
            "portrait_id_pokohex": rid,
            "range_group": "CONSECUTIVE_317_378" if 317 <= rid <= 378 else "SCATTERED",
            "pokohex_game_ids": ";".join(x["villager_id"] for x in owners),
            "pokohex_name_en": ";".join(x["en"] for x in owners),
            "pokohex_name_zhs": ";".join(x["zhs"] for x in owners),
            "reference_png": r["reference_png"],
            "reference_sha256": r["reference_png_sha256"],
            "old_m21_nearest_sprite": r["nearest_native_candidate"],
            "old_m21_nearest_mae": r["nearest_normalized_mae"],
            "native_texture_id_proven": "NO",
            "native_portrait_id_proven": "NO",
            "source_status": "M21_609_NATIVE_POKEMON_PNG_SEARCH_NO_CONFIDENT_CANDIDATE",
        })
    return rows

def typed_edges_for_variants(ambiguous, native, m19, grouped):
    by_name = defaultdict(list)
    for r in native:
        m = re.match(r"icon_poke_(?:uni_)?(\d{4})_", r["texture_name"])
        if m:
            by_name[int(m.group(1))].append(r)
    target_edge = defaultdict(list)
    for r in m19:
        target_edge[r["target_object_hash"]].append(r)
    original_cache = {}
    # Raw-byte check of the exact typed u32 source field; M19 describes
    # link target but it cannot assign the PokoHex game ID to that source object.
    def original_blob(path, sha):
        if path not in original_cache:
            p = Path(path)
            blob = p.read_bytes()
            if hashlib.sha256(blob).hexdigest() != sha:
                raise ValueError(f"Original KIDSOBJDB digest changed: {path}")
            original_cache[path] = blob
        return original_cache[path]

    all_candidates = []
    report = []
    for ref in sorted(ambiguous, key=lambda x: int(x["reference_sprite_id"])):
        ident = int(ref["reference_sprite_id"])
        m = re.search(r"icon_poke_(?:uni_)?(\d{4})_", ref["nearest_native_candidate"])
        if not m:
            raise ValueError(f"M21 candidate does not have native-number feature: {ref}")
        number = int(m.group(1))
        variants = sorted(by_name[number], key=lambda x: (
            x["texture_name"], x["texinfo_hash"], x["g1t_hash"]))
        if len(variants) < 2:
            raise ValueError(f"Ambiguous portrait had fewer than two native variants: {number}")
        reference_thumb, size = thumb(ref["reference_png"], ref["reference_png_sha256"])
        if reference_thumb is None:
            raise ValueError("PokoHex reference is not a real portrait image")
        matches = []
        for candidate in variants:
            target = candidate["object_hash"]
            found_edges = target_edge.get(target, [])
            if len(found_edges) != 1:
                raise ValueError(f"Expected one M19 verified native source->target object edge: {target}")
            edge = found_edges[0]
            raw = original_blob(edge["original_source_file"], edge["source_file_sha256"])
            offset = int(edge["source_field_byte_offset"])
            if (int(edge["source_field_hash"], 16) != FIELD
                or offset < 0 or offset + 4 > len(raw)
                or struct.unpack_from("<I", raw, offset)[0] != int(target,16)):
                raise ValueError(f"Original native typed property bytes mismatch: {target}")
            icon_thumb, native_size = thumb(candidate["png_path"], candidate["png_sha256"])
            d = distance(reference_thumb, icon_thumb) if icon_thumb is not None else 1.0
            row = {
                "portrait_id_pokohex": ident,
                "pokohex_game_ids": ";".join(x["villager_id"] for x in refs_for(grouped, ident)),
                "pokohex_en": ";".join(x["en"] for x in refs_for(grouped, ident)),
                "source_texture_number_string": f"{number:04d}",
                "native_texture_name": candidate["texture_name"],
                "texinfo_hash": candidate["texinfo_hash"], "g1t_hash": candidate["g1t_hash"],
                "native_png_path": candidate["png_path"],
                "native_png_sha256": candidate["png_sha256"],
                "thumbnail_mae": f"{d:.8f}",
                "native_object_hash": target,
                "native_source_oid": edge["source_object_hash"],
                "native_source_type_hash": edge["source_type_hash"],
                "native_source_file": edge["original_source_file"],
                "native_source_sha256": edge["source_file_sha256"],
                "native_source_node_byte_offset": edge["source_original_node_offset"],
                "native_source_property_hash": edge["source_field_hash"],
                "native_source_property_byte_offset": edge["source_field_byte_offset"],
                "original_u32_at_offset": f"{struct.unpack_from('<I',raw,offset)[0]:08x}",
                "native_g1t_property_hash": edge["target_g1t_hash"],
                "native_texinfo_property_hash": edge["target_texinfo_hash"],
                "typed_object_link": "RAW_BYTES_CONFIRMED_SOURCE_PROPERTY_TO_TEXTURE_OID",
                "native_pokemon_species_id_verified": "",
                "native_villager_portrait_id_verified": "",
            }
            if (edge["target_g1t_hash"] != candidate["g1t_hash"]
                or edge["target_texinfo_hash"] != candidate["texinfo_hash"]):
                raise ValueError(f"Target native KIDSOBJDB resource properties contradict sprite: {target}")
            matches.append(row)
        matches.sort(key=lambda x: (float(x["thumbnail_mae"]), x["native_texture_name"], x["native_object_hash"]))
        # Explicitly retain all variants; no auto-selection by minor differences.
        all_candidates.extend(matches)
        report.append({
            "portrait_id": ident, "variants": len(matches),
            "source_typed_u32_links_byte_verified": len(matches),
            "best_resource_texture": matches[0]["native_texture_name"],
            "best_mae": matches[0]["thumbnail_mae"],
            "second_mae": matches[1]["thumbnail_mae"],
            "game_portrait_ID_semantic_link_verified": False,
        })
    return all_candidates, report, original_cache

def misc_sweep(far, base, max_batches=17):
    """Check all 3930 already PNG-exported non-Pokémon/native index sprites.

    Search is only an independent-image candidate check, not proof that an
    arbitrary UI texture is actually a villager portrait.
    """
    refs = {}
    for r in far:
        pic, dimensions = thumb(r["reference_png"], r["reference_png_sha256"])
        if pic is None: raise ValueError("Reference portrait was too small")
        refs[int(r["reference_sprite_id"])] = (pic, dimensions)
    scores = {k: [] for k in refs}
    seen = 0
    sampled_prefix = Counter()
    for batch_id in range(max_batches):
        batch = base / f"batch_{batch_id:02d}"
        rows = read_csv(batch / "misc_native_sample_manifest.csv")
        for r in rows:
            if not r["png_path"]:
                raise ValueError(f"M9 batch contains missing PNG: {r}")
            if r["status"] == "TRANSPARENT_CANDIDATE_REVIEW":
                seen += 1
                continue
            img, shape = thumb(r["png_path"], r["png_sha256"])
            if img is None:
                seen += 1
                continue
            seen += 1
            label = r["texture_name"]
            sampled_prefix[label.split("_")[0]] += 1
            item = {
                "texture_name": label, "png_path": r["png_path"], "png_sha256": r["png_sha256"],
                "texinfo_hash": r["texinfo_hash"], "g1t_hash": r["g1t_hash"],
                "texinfo_path": r["texinfo_path"], "g1t_path": r["g1t_path"],
                "record_index": r["record_index"], "texture_layer": r["layer"],
                "width": shape[0], "height": shape[1],
            }
            for portrait, (ref_img, ref_shape) in refs.items():
                # Square-ish face images only; wild scene stills cannot reliably
                # be compared as full square face sprites.
                ratio = shape[0] / shape[1]
                if not (0.8 <= ratio <= 1.25):
                    continue
                d = distance(ref_img, img)
                top_insert(scores[portrait], (d, item), 3)
    if max_batches == 17 and seen != EXPECTED_MISC:
        raise ValueError(f"Native misc PNG corpus incomplete: {seen} vs {EXPECTED_MISC}")
    results=[]
    for portrait, top in sorted(scores.items()):
        for rank, (d, c) in enumerate(top, 1):
            second = top[1][0] if len(top)>1 else None
            status=("STRONG_VISUAL_CANDIDATE_REVIEW_ONLY"
                    if rank == 1 and d <= .015 and (second is None or second-d>=.015)
                    else "NO_DEMONSTRATED_PORTRAIT_ID")
            results.append({
                "portrait_id_pokohex": portrait, "rank": rank, "name_heuristic_only": c["texture_name"],
                "normalized_mae_32px": f"{d:.8f}", "visual_candidate_status": status,
                "native_png": c["png_path"], "native_png_sha256": c["png_sha256"],
                "native_texinfo_path": c["texinfo_path"], "native_g1t_path": c["g1t_path"],
                "texinfo_hash": c["texinfo_hash"], "g1t_hash": c["g1t_hash"],
                "texinfo_record_index": c["record_index"], "layer": c["texture_layer"],
                "native_portrait_id_verified": "",
            })
    return results, {"other_original_pngs_swept": seen, "batch_count": max_batches,
                     "swept_prefixes": dict(sampled_prefix.most_common(15)),
                     "strong_cross_family_visual_candidate_count": sum(
                         r["visual_candidate_status"]=="STRONG_VISUAL_CANDIDATE_REVIEW_ONLY" for r in results),
                     "note": "No visual-only association can establish a native villager ID or a missing source version."}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--skip-misc", action="store_true", help="Skip 3930 non-Pokémon PNGs")
    p.add_argument("--self-test", action="store_true")
    args=p.parse_args()
    if args.self_test:
        heap=[]
        for i in range(9, -1, -1):
            top_insert(heap,(float(i),{"texture_name":str(i),"png_path":str(i)}),3)
        assert [a for a,_ in heap]==[0.,1.,2.]
        assert sprite_id("villager_0317.png")==317
        print("M22 pure helper self-test passed")
        return
    missing, ambiguous, far, native, m19, grouped=collect()
    OUT.mkdir(parents=True,exist_ok=True)
    missing_rows=list_missing(far,grouped)
    typed_rows, typed_summary, sources=typed_edges_for_variants(ambiguous,native,m19,grouped)
    fields_missing=list(missing_rows[0])
    fields_typed=list(typed_rows[0])
    write_csv(OUT/"m22_unresolved_79_source_targets.csv",missing_rows,fields_missing)
    write_csv(OUT/"m22_nine_ambiguous_native_object_refs.csv",typed_rows,fields_typed)
    if not args.skip_misc:
        misc_rows, misc_report=misc_sweep(far,ROOT/"Textures/MiscNativeBatches")
        write_csv(OUT/"m22_79_other_native_png_top3.csv", misc_rows, list(misc_rows[0]))
    else:
        misc_report={"skipped": True}
    coverage=json.loads(Path("UnPack/2.0.1/_reports/source_coverage.json").read_text(encoding="utf-8"))
    unavailable = read_csv(Path("UnPack/2.0.1/_reports/missing_input_records.csv"))
    input_types = Counter(x["type_hash"] for x in unavailable)
    # Type labels originate in Scripts/unpack/m3_types.py; RDB type hashes
    # are source metadata, not direct proof of a portrait's semantic identity.
    known_kinds = {"afbec60c": "g1t", "f20de437": "texinfo",
                   "8e39aa37": "ktid", "20a6a0bb": "kidsobjdb"}
    by_source = defaultdict(Counter)
    missing_texinfo_capacity = 0
    for item in unavailable:
        source = item["source_file"]
        kind = known_kinds.get(item["type_hash"], "other")
        by_source[source][kind] += 1
        if kind == "texinfo":
            size = int(item["unpacked_size"])
            if size < 108 or (size-4) % 104 != 0:
                raise ValueError(f"Unexpected missing TEXINFO expected uncompressed size: {source}/{item}")
            missing_texinfo_capacity += (size-4)//104
    focused = []
    for name, counts in sorted(by_source.items()):
        if counts["g1t"] or counts["texinfo"] or counts["ktid"]:
            focused.append({
                "original_missing_container": name,
                "missing_g1t_records_in_root_rdb": counts["g1t"],
                "missing_texinfo_files_in_root_rdb": counts["texinfo"],
                "missing_texinfo_sprite_slots_upper_bound": sum(
                    (int(x["unpacked_size"])-4)//104 for x in unavailable
                    if x["source_file"]==name and x["type_hash"]=="f20de437"),
                "missing_ktid_files_in_root_rdb": counts["ktid"],
                "missing_kidsobjdb_files_in_root_rdb": counts["kidsobjdb"],
                "portrait_identity_proven": "NO",
            })
    write_csv(OUT/"m22_missing_texture_containers.csv", focused, list(focused[0]))
    source_report={
        "version":"2.0.1", "original_missing_input_files":coverage["coverage"]["remaining_missing_physical_inputs"],
        "original_unavailable_index_records":coverage["overall"]["missing_source_records"],
        "missing_index_rows_loaded":len(unavailable),
        "missing_original_file_type_hash_counts":dict(input_types.most_common()),
        "type_hash_is_only_an_index_label":True,
        "type_hash_labels_from_m3_types":known_kinds,
        "missing_g1t_original_records":input_types["afbec60c"],
        "missing_texinfo_original_files":input_types["f20de437"],
        "missing_texinfo_sprite_slots_upper_bound":missing_texinfo_capacity,
        "missing_ktid_original_records":input_types["8e39aa37"],
        "missing_kidsobjdb_original_records":input_types["20a6a0bb"],
        "original_missing_texture_container_count":len(focused),
        "missing_image_identity_attributed_to_missing_fdata_count":0,
        "caveat":"No direct per-portrait source path exists for the 79 missing reference PNGs, so 27 absent FDATA cannot be asserted to contain any of them.",
    }
    summary={
        "version":"2.0.1",
        "reference_count_m21":378,
        "unresolved":len(missing),"ambiguous_visual":len(ambiguous),"far_visual":len(far),
        "far_consecutive_317_378":sum(317<=int(x["portrait_id_pokohex"])<=378 for x in missing_rows),
        "far_scattered":sum(x["range_group"]=="SCATTERED" for x in missing_rows),
        "native_variant_rows_original_u32_verified":len(typed_rows),
        "ambiguous_portrait_ids":[int(x["reference_sprite_id"]) for x in ambiguous],
        "typed_link_unique_original_files":len(sources),
        "typed_link_hash":f"{FIELD:08x}",
        "native_villager_id_semantic_bindings_verified":0,
        "native_species_id_semantic_bindings_verified":0,
        "original_fdata_coverage":source_report,
        "other_original_png_sweep":misc_report,
        "caveat":"PokoHex IDs and M19 native sprite OIDs remain separate ID domains; typed source->target edges do not prove game ID binding.",
    }
    save_json(OUT/"m22_source_coverage_summary.json",source_report)
    save_json(OUT/"m22_nine_typed_reference_summary.json",typed_summary)
    save_json(OUT/"m22_summary.json",summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
