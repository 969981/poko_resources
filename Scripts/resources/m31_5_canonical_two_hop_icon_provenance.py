#!/usr/bin/env python3
"""M31.5: authoritative 628 icon two-hop original KIDS source provenance.

Source: Pokopia 2.0.1 original KIDSOBJDB SHA pinned. For each of the
628 icon entries from M25's original 3543-value source array:

 TexturePackObjectHashArray[index] -> Source IDOK (0x79991E79):
    LayoutTexturesRenderStateObjectHash  = 0
    LayoutTexturesInfoDataResourceHash   = 0
    WrapStaticScreenLayoutTexturesObjectHash -> Wrapper IDOK (0x79991E79):
       LayoutTexturesRenderStateObjectHash -> M25 G1T file hash
       LayoutTexturesInfoDataResourceHash -> M25 TEXINFO file hash
       WrapStaticScreenLayoutTexturesObjectHash = 0

All object IDs, types, numeric values, byte offsets from original KIDS
bytes. The prior M25 "target_texture_oid" was the WRAPPER object OID,
not the final G1T hash nor TEXINFO hash.

This is source-asset provenance, NOT an executed loader or proof of a
gameplay species/form ID. Never infer any native game ID from icon digits.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,struct
from collections import Counter
from pathlib import Path
from Scripts.resources.m16_verify_pokemon_texture_kidsobjdb import parse_kids

ROOT=Path("UnPack/2.0.1/Resources")
KIDS=Path("UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0xacd220a8.fdata/native/root_019167_50ae86ef.kidsobjdb")
ORIGINAL_SHA="86f90b4c11da9bc2b3e28889a5090ff507f96ca713fe4fad1dd50f6f692d7541"
INDEX=ROOT/"Pokemon/NativeRecoveryM25/m25_8_complete_native_629_kids_icon_source_index.csv"
OUT=ROOT/"Villagers/Native_2.0.1/M31"
TYPE=0x79991E79
OWNER=0xB4A1803B
RENDER=0xC8BB66DA
INFO=0x2276FC56
WRAP=0x2856A1B3
FKEY=0x34CBB458
COUNT=628
FIELDS=(
    "original_3543_array_index",
    "original_texture_name_aliases",
    "original_texture_pack_owner_oid",
    "original_texture_pack_object_array_field_hash",
    "first_hop_static_texture_source_oid",
    "first_hop_static_texture_type_hash",
    "first_hop_IDOK_byte_offset",
    "first_hop_render_state_raw_u32",
    "first_hop_info_data_raw_u32",
    "first_hop_wrap_object_OID",
    "first_hop_wrap_field_byte_offset",
    "second_hop_wrapped_IDOK_type_hash",
    "second_hop_wrapped_IDOK_byte_offset",
    "second_hop_render_state_object_hash",
    "second_hop_render_state_field_byte_offset",
    "second_hop_info_data_resource_hash",
    "second_hop_info_data_field_byte_offset",
    "second_hop_wrap_field_raw_u32",
    "verified_prior_M25_g1t_resource_file_hash",
    "verified_prior_M25_texinfo_resource_file_hash",
    "original_M25_png_path_candidate",
    "two_hop_source_byte_provenance_verified",
    "native_species_ID_verified",
    "native_villager_ID_verified",
)
def hx(x):return f"{x:08x}"
def rows(file):
    with file.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))
def scalar(node,prop,binary):
    f=node["fields"].get(prop)
    if not f or f["kind"]!=5 or f["count"]!=1:
        raise ValueError(f"Native typed u32 property missing {hx(prop)}")
    return struct.unpack_from("<I",binary,f["offset"])[0],f["offset"]
def run():
    original=KIDS.read_bytes()
    if hashlib.sha256(original).hexdigest()!=ORIGINAL_SHA:
        raise ValueError("Original Pokopia 2.0.1 KIDSOBJDB SHA mismatch")
    _,nodes=parse_kids(original)
    entries=rows(INDEX)
    subset=[x for x in entries if x["original_owner_oid"]==hx(OWNER)]
    if len(entries)!=629 or len(subset)!=COUNT:
        raise ValueError("M25 original source index and coverage changed")
    trace=[]
    seen_source=set();seen_wrap=set()
    for x in subset:
        src=int(x["source_oid"],16);old_wrapper=int(x["target_texture_oid"],16)
        slot=int(x["original_array_index"])
        if slot not in range(429,1057):
            raise ValueError(f"Unexpected 2.0.1 original icon slot {slot}")
        if src in seen_source or old_wrapper in seen_wrap:
            raise ValueError("Original icon Source and Wrapper OID should be unique")
        seen_source.add(src);seen_wrap.add(old_wrapper)
        outer=nodes.get(src)
        if outer is None or outer["type"]!=TYPE:
            raise ValueError("Original source IDOK missing or wrong class")
        a,_=scalar(outer,RENDER,original)
        b,_=scalar(outer,INFO,original)
        wrap,wrap_offset=scalar(outer,WRAP,original)
        if wrap!=old_wrapper:
            raise ValueError("M25 legacy target OID is not original wrapper object OID")
        child=nodes.get(wrap)
        if child is None or child["type"]!=TYPE:
            raise ValueError("Second-hop original wrapper IDOK missing or has wrong class type")
        g1t,g1t_at=scalar(child,RENDER,original)
        texinfo,info_at=scalar(child,INFO,original)
        extra,_=scalar(child,WRAP,original)
        if hx(g1t)!=x["g1t_hash"] or hx(texinfo)!=x["texinfo_hash"]:
            raise ValueError(f"Actual original wrapper file hashes disagree M25 source index at {slot}")
        trace.append({
            "original_3543_array_index":slot,
            "original_texture_name_aliases":x["original_texture_name_variants"],
            "original_texture_pack_owner_oid":hx(OWNER),
            "original_texture_pack_object_array_field_hash":hx(FKEY),
            "first_hop_static_texture_source_oid":hx(src),
            "first_hop_static_texture_type_hash":hx(TYPE),
            "first_hop_IDOK_byte_offset":outer["offset"],
            "first_hop_render_state_raw_u32":hx(a),
            "first_hop_info_data_raw_u32":hx(b),
            "first_hop_wrap_object_OID":hx(wrap),
            "first_hop_wrap_field_byte_offset":wrap_offset,
            "second_hop_wrapped_IDOK_type_hash":hx(child["type"]),
            "second_hop_wrapped_IDOK_byte_offset":child["offset"],
            "second_hop_render_state_object_hash":hx(g1t),
            "second_hop_render_state_field_byte_offset":g1t_at,
            "second_hop_info_data_resource_hash":hx(texinfo),
            "second_hop_info_data_field_byte_offset":info_at,
            "second_hop_wrap_field_raw_u32":hx(extra),
            "verified_prior_M25_g1t_resource_file_hash":x["g1t_hash"],
            "verified_prior_M25_texinfo_resource_file_hash":x["texinfo_hash"],
            "original_M25_png_path_candidate":x["original_png_candidates"],
            "two_hop_source_byte_provenance_verified":1,
            "native_species_ID_verified":"",
            "native_villager_ID_verified":"",
        })
    if len(trace)!=COUNT or len(seen_source)!=COUNT or len(seen_wrap)!=COUNT:
        raise ValueError("M31.5 628 original graph edges incomplete")
    trace.sort(key=lambda x:int(x["original_3543_array_index"]))
    parent_first=Counter((x["first_hop_render_state_raw_u32"],x["first_hop_info_data_raw_u32"]) for x in trace)
    child_third=Counter(x["second_hop_wrap_field_raw_u32"] for x in trace)
    if set(parent_first)!={("00000000","00000000")}:
        raise ValueError("Original parent render/info field values are not zero as previously evidenced")
    if set(child_third)!={"00000000"}:
        raise ValueError("Original wrapped child third scalar not the expected terminal 0")
    stats={
        "version":"2.0.1",
        "original_KIDSOBJDB_sha256":ORIGINAL_SHA,
        "original_source_IDOK_nodes_in_database":len(nodes),
        "two_hop_source_wrapper_G1T_TEXINFO_entries_verified":COUNT,
        "unique_original_source_OIDs":len(seen_source),
        "unique_original_wrapper_IDOK_OIDs":len(seen_wrap),
        "source_and_wrapper_both_class_StaticScreenLayoutTextures":True,
        "native_class_hash":hx(TYPE),
        "original_typed_field_labels":{
            hx(RENDER):"LayoutTexturesRenderStateObjectHash",
            hx(INFO):"LayoutTexturesInfoDataResourceHash",
            hx(WRAP):"WrapStaticScreenLayoutTexturesObjectHash"},
        "parent_source_render_info_u32_both_zero_count":parent_first[("00000000","00000000")],
        "wrapper_child_3rd_wrap_property_zero_count":child_third["00000000"],
        "second_hop_wrapper_render_field_equals_M25_G1T_hash_count":COUNT,
        "second_hop_wrapper_info_field_equals_M25_TEXINFO_hash_count":COUNT,
        "old_target_texture_oid_column_semantics":"FIRST_HOP_WRAP_STATIC_SCREEN_LAYOUT_TEXTURES_OBJECT_HASH",
        "existing_M25_extra_non_owner_icon_outside_628":len(entries)-COUNT,
        "source_file_hash_matches_original_schema_and_M25_index":True,
        "native_Executed_texture_resource_loader_verified":False,
        "native_species_form_ID_to_original_KIDS_OID_verified":False,
        "native_villager_ID_to_picture_verified":False,
        "note":"Original source bytes now directly prove every 628 two-hop object chain and child G1T/TEXINFO file hash values. This is asset provenance, not runtime source selection by game species or forms.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/"m31_5_canonical_628_two_hop_KIDS_asset_provenance.csv").open(
        "w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(trace)
    (OUT/"m31_5_full_two_hop_source_asset_report.json").write_text(
        json.dumps(stats,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(stats,ensure_ascii=False,indent=2))
    return stats
def selftest():
    assert COUNT==628 and FKEY==0x34CBB458
    assert WRAP==0x2856A1B3
    print("PASS M31.5 original two-hop KIDS source->wrapper->file hash field schema")
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:selftest()
    else:run()
