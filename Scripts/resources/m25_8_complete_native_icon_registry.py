#!/usr/bin/env python3
"""M25.8: build the COMPLETE original KIDS Pokémon icon array source graph.

629 KIDS source OIDs: 628 original main registry slots (314 normal + 314
uni), plus one original icon_poke_at_home from a separate 15-entry table.
Every row is traceable to original source-node and texture-node OIDs,
G1T and TEXINFO hashes, and a decoded original PNG candidate.
Neither the filename number nor array index proves a gameplay species ID.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from collections import Counter,defaultdict
from pathlib import Path

R=Path("UnPack/2.0.1/Resources")
M=R/"Villagers/Native_2.0.1/M25"
P=R/"Pokemon"
OLD=M/"m25_original_second_hop_kids_source_oid_backrefs.csv"
GAPS=M/"m25_3_26_original_source_to_texture_objects.csv"
REGISTRY=M/"m25_2_full_628_native_icon_registry.csv"
EXISTING=P/"pokemon_identity_crosswalk.csv"
RECOVER=P/"NativeRecoveryM25/m25_5_native_icon_export_manifest.csv"
OUT=P/"NativeRecoveryM25"
COLS=("original_owner_oid","original_owner_type_hash","original_array_property_hash",
      "original_array_index","original_u32_field_byte_offset","source_oid","target_texture_oid",
      "original_texture_name_variants","texture_name_entry_count","texinfo_hash","g1t_hash",
      "original_png_candidates","source_kind","game_species_id_verified",
      "native_villager_id_verified","original_link_evidence")

def read(path):
    with path.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def run():
    original=read(OLD)
    gap=read(GAPS)
    registry=read(REGISTRY)
    oldtex=read(EXISTING)
    native=read(RECOVER)
    if (len(original),len(gap),len(registry),len(oldtex),len(native))!=(603,26,628,609,26):
        raise ValueError("M25 canonical original inputs changed")
    by_target=defaultdict(list)
    for r in oldtex:by_target[r["object_hash"]].append(r)
    if len(by_target)!=603:raise ValueError("Original icon source/target aliases changed")
    gap_by_slot={int(x["original_array_slot"]):x for x in gap}
    new_by_slot={int(x["original_array_slot"]):x for x in native}
    reg_by_slot={int(x["native_array_index"]):x for x in registry}
    if len(gap_by_slot)!=26 or len(new_by_slot)!=26 or len(reg_by_slot)!=628:
        raise ValueError("Original slot values duplicated")
    records=[]
    for old in original:
        target=old["matched_M19_target_icon_oid"]
        matches=by_target.get(target)
        if not matches:raise ValueError(f"No verified texture record for {target}")
        th={x["texinfo_hash"] for x in matches}
        gh={x["g1t_hash"] for x in matches}
        if len(th)!=1 or len(gh)!=1:raise ValueError("Conflicting source texture hashes for one exact target")
        idx=int(old["native_property_value_index"])
        owner=old["backref_source_node_oid"]
        if owner=="b4a1803b":
            a=reg_by_slot.get(idx)
            if not a or a["original_u32"]!=old["matched_M19_source_oid"]:
                raise ValueError("Source OID and original array bytes disagree")
            block=a["index_block"]
        elif owner=="15adf4b3":
            if idx!=10 or target not in by_target:raise ValueError("Unexpected special root table")
            block="icon_poke_at_home_external_root_15_entry_table"
        else:raise ValueError("Unrecognized original KIDS owner")
        rec={
            "original_owner_oid":owner,
            "original_owner_type_hash":old["backref_source_node_type_hash"],
            "original_array_property_hash":old["native_property_hash"],
            "original_array_index":idx,
            "original_u32_field_byte_offset":old["native_property_absolute_byte_offset"],
            "source_oid":old["matched_M19_source_oid"],
            "target_texture_oid":target,
            "original_texture_name_variants":";".join(sorted({x["texture_name"] for x in matches})),
            "texture_name_entry_count":len(matches),
            "texinfo_hash":next(iter(th)),
            "g1t_hash":next(iter(gh)),
            "original_png_candidates":";".join(sorted({x["png_path"] for x in matches if x["png_path"]})),
            "source_kind":block,
            "game_species_id_verified":"",
            "native_villager_id_verified":"",
            "original_link_evidence":"ORIGINAL_ARRAY_BYTE_TO_SOURCE_OID_TO_TYPED_TEXTURE_OID",
        }
        records.append(rec)
    for slot,src in sorted(gap_by_slot.items()):
        pic=new_by_slot[slot]
        a=reg_by_slot[slot]
        if a["original_u32"]!=src["native_source_oid"]:
            raise ValueError("New slot original source ID not matched")
        if (pic["original_source_oid"]!=src["native_source_oid"]
                or pic["original_texture_oid"]!=src["native_target_oid"]
                or pic["texinfo_hash"]!=src["target_texinfo_hash"]
                or pic["g1t_hash"]!=src["target_g1t_hash"]
                or not pic["png_file"] or pic["status"]!="ORIGINAL_NATIVE_SOURCE_PNG_CANDIDATE"):
            raise ValueError("New sprite original type/PNG proof mismatch")
        p=Path(pic["png_file"])
        if hashlib.sha256(p.read_bytes()).hexdigest()!=pic["png_sha256"]:
            raise ValueError("Native recovered PNG SHA256 changed")
        records.append({
            "original_owner_oid":"b4a1803b",
            "original_owner_type_hash":"9d1afa46",
            "original_array_property_hash":"34cbb458",
            "original_array_index":slot,
            "original_u32_field_byte_offset":a["original_u32_byte_offset"],
            "source_oid":src["native_source_oid"],
            "target_texture_oid":src["native_target_oid"],
            "original_texture_name_variants":pic["texture_name_original_texinfo"],
            "texture_name_entry_count":1,
            "texinfo_hash":pic["texinfo_hash"],
            "g1t_hash":pic["g1t_hash"],
            "original_png_candidates":pic["png_file"],
            "source_kind":a["index_block"],
            "game_species_id_verified":"",
            "native_villager_id_verified":"",
            "original_link_evidence":"M25_ORIGINAL_DECODED_TEXINFO_AND_NATIVE_G1T_TO_PNG",
        })
    records.sort(key=lambda r:(r["original_owner_oid"]!="b4a1803b",int(r["original_array_index"])))
    by_kind=Counter(x["source_kind"] for x in records)
    if by_kind!={"original_icon_poke_block":314,
                 "original_icon_poke_uni_block":314,
                 "icon_poke_at_home_external_root_15_entry_table":1}:
        raise ValueError(f"Native array source coverage incomplete: {by_kind}")
    if (len(records)!=629 or len({x["source_oid"] for x in records})!=629 or
            len({x["target_texture_oid"] for x in records})!=629):
        raise ValueError("Original source or texture OID collision")
    if any(x["game_species_id_verified"] or x["native_villager_id_verified"] for x in records):
        raise ValueError("No promoted species-ID evidence allowed")
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/"m25_8_complete_native_629_kids_icon_source_index.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=COLS);w.writeheader();w.writerows(records)
    summary={
        "version":"2.0.1","original_registry_source_oid_nodes":629,
        "main_kids_source_array_count":3543,
        "main_kids_icon_source_normal":314,
        "main_kids_icon_source_uni":314,
        "other_icon_at_home_source":1,
        "m25_existing_original_source_links":603,
        "m25_new_original_native_g1t_texinfo_pngs":26,
        "all_629_source_OIDs_unique":True,
        "all_629_target_OIDs_unique":True,
        "original_sprites_with_current_source_png_path":sum(bool(x["original_png_candidates"]) for x in records),
        "native_gameplay_species_ID_to_array_slot_proven":False,
        "native_gameplay_villager_ID_to_source_OID_proven":False,
        "warning":"This source-qualified registry contains all 628 discovered icon-array entries and one additional icon-at-home OID; it is not a verified gameplay species-ID table. Other original asset families may exist elsewhere.",
    }
    (OUT/"m25_8_complete_native_registry_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary

def selftest():
    assert 314+314+1==629
    assert 603+26==629
    print("PASS native registry graph cardinality invariants")
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:selftest()
    else:run()
if __name__=="__main__":main()
