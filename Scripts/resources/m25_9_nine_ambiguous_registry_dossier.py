#!/usr/bin/env python3
"""M25.9: join nine PokoHex ambiguous visual candidates to exact KIDS slots.

The native source->texture relationship and array position is now original
byte-verified. Neither a source slot nor the closest thumbnail proves which
native variant a runtime village NPC uses for a specific PokoHex ID.
"""
from __future__ import annotations
import csv
import json
from collections import Counter,defaultdict
from pathlib import Path

ROOT=Path("UnPack/2.0.1/Resources")
OLD=ROOT/"Villagers/Native_2.0.1/M22/m22_nine_ambiguous_native_object_refs.csv"
NATIVE=ROOT/"Pokemon/NativeRecoveryM25/m25_8_complete_native_629_kids_icon_source_index.csv"
OUT=ROOT/"Villagers/Native_2.0.1/M25"
COLS=(
    "reference_pokohex_portrait_id","pokohex_villager_game_ids_unverified",
    "reference_name","native_texture_name","visual_mae_32px",
    "original_icon_array_owner_oid","original_icon_array_index",
    "source_oid","target_texture_oid","native_texinfo_hash","native_g1t_hash",
    "original_source_to_texture_u32_byte_offset",
    "native_source_png","native_identity_binding_verified",
)

def csvread(p):
    with p.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def run():
    raw=csvread(OLD)
    current=csvread(NATIVE)
    if len(raw)!=54 or len(current)!=629:raise ValueError("Input native evidence does not have expected coverage")
    by_target={x["target_texture_oid"]:x for x in current}
    if len(by_target)!=629:raise ValueError("Original registered texture OID collision")
    result=[]
    for r in raw:
        t=by_target.get(r["native_object_hash"])
        if not t:raise ValueError(f"Original native texture OID missing {r['native_object_hash']}")
        if (t["source_oid"]!=r["native_source_oid"]
                or t["g1t_hash"]!=r["g1t_hash"]
                or t["texinfo_hash"]!=r["texinfo_hash"]):
            raise ValueError(f"Cross-layer source→texture data inconsistent for {r['portrait_id_pokohex']}")
        if r["native_villager_portrait_id_verified"]:
            raise ValueError("M22 unproved game ID promoted")
        result.append({
            "reference_pokohex_portrait_id":r["portrait_id_pokohex"],
            "pokohex_villager_game_ids_unverified":r["pokohex_game_ids"],
            "reference_name":r["pokohex_en"],
            "native_texture_name":r["native_texture_name"],
            "visual_mae_32px":r["thumbnail_mae"],
            "original_icon_array_owner_oid":t["original_owner_oid"],
            "original_icon_array_index":t["original_array_index"],
            "source_oid":t["source_oid"],"target_texture_oid":t["target_texture_oid"],
            "native_texinfo_hash":t["texinfo_hash"],"native_g1t_hash":t["g1t_hash"],
            "original_source_to_texture_u32_byte_offset":r["native_source_property_byte_offset"],
            "native_source_png":r["native_png_path"],
            "native_identity_binding_verified":"",
        })
    by_id=defaultdict(list)
    for x in result:by_id[x["reference_pokohex_portrait_id"]].append(x)
    if len(by_id)!=9:raise ValueError("Nine ambiguous groups not represented")
    summary={
        "version":"2.0.1",
        "unresolved_ambiguous_pokohex_portrait_ids":sorted([int(k) for k in by_id]),
        "original_native_source_to_texture_candidate_rows":len(result),
        "source_oid_to_original_array_slot_links_verified":len(result),
        "groups_with_multisource_visual_candidates":len(by_id),
        "rows_per_reference":{str(k):len(v) for k,v in sorted(by_id.items(),key=lambda x:int(x[0]))},
        "native_runtime_villager_id_bindings_verified":0,
        "native_runtime_species_id_bindings_verified":0,
        "warning":"Array position provenance does not disambiguate PokoHex portrait IDs; runtime per-NPC ID/variant consumer still required.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/"m25_9_nine_ambiguous_native_array_slot_dossier.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=COLS);w.writeheader();w.writerows(result)
    (OUT/"m25_9_ambiguous_slot_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary

if __name__=="__main__":run()
