#!/usr/bin/env python3
"""M31.3 native StaticScreenLayoutTextures class field semantic re-audit.

Previous M16/M25 tables called hash 0x2856A1B3 "third_unknown" /
"target_texture_oid". Original ExeFS M31.2 has now established the
actual class property name WrapStaticScreenLayoutTexturesObjectHash.

Verify for all 628 *real original* Source OIDs:
  0xC8BB66DA = LayoutTexturesRenderStateObjectHash
  0x2276FC56 = LayoutTexturesInfoDataResourceHash
  0x2856A1B3 = WrapStaticScreenLayoutTexturesObjectHash

Check all raw u32s against M25 imported legacy names; retain legacy
columns ONLY for backward compatibility, never interpret the wrapped
object hash itself as the final G1T/TEXINFO object identity.

No game species IDs are implied. A target wrapper hash may refer to an
external KIDS object or resource: only claim local existence if present.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,struct
from collections import Counter
from pathlib import Path

from Scripts.resources.m16_verify_pokemon_texture_kidsobjdb import parse_kids

ROOT=Path("UnPack/2.0.1/Resources")
SRC=Path("UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0xacd220a8.fdata/native/root_019167_50ae86ef.kidsobjdb")
PIN="86f90b4c11da9bc2b3e28889a5090ff507f96ca713fe4fad1dd50f6f692d7541"
INDEX=ROOT/"Pokemon/NativeRecoveryM25/m25_8_complete_native_629_kids_icon_source_index.csv"
OUT=ROOT/"Villagers/Native_2.0.1/M31"
TYPE=0x79991E79
OWNER=0xB4A1803B
FIELDS={
    "LayoutTexturesRenderStateObjectHash":0xC8BB66DA,
    "LayoutTexturesInfoDataResourceHash":0x2276FC56,
    "WrapStaticScreenLayoutTexturesObjectHash":0x2856A1B3,
}
COLS=(
    "source_oid","source_type_hash","original_source_idok_node_offset",
    "original_texinfo_texture_name_aliases",
    "original_layout_textures_render_state_object_hash",
    "original_layout_textures_info_data_resource_hash",
    "original_wrap_static_screen_layout_textures_object_hash",
    "legacy_M25_g1t_hash_same_raw_u32",
    "legacy_M25_texinfo_hash_same_raw_u32",
    "legacy_M25_target_texture_oid_same_raw_u32",
    "original_wrapper_hash_locally_present_as_IDOK",
    "original_wrapper_target_node_type_if_present",
    "native_game_species_id_verified",
    "native_game_villager_id_verified",
)
def fmt(v):return f"{v:08x}"
def rows(path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))
def run():
    blob=SRC.read_bytes()
    if hashlib.sha256(blob).hexdigest()!=PIN:
        raise ValueError("Original 2.0.1 KIDSOBJDB SHA256 changed")
    header,nodes=parse_kids(blob)
    index=rows(INDEX)
    if len(index)!=629:raise ValueError("M25 original 629 source index changed")
    this=[x for x in index if x["original_owner_oid"]==fmt(OWNER)]
    if len(this)!=628:raise ValueError("Expected exactly 628 named main icon source OIDs")
    result=[]
    seen=set()
    errors=[]
    for r in this:
        oid=int(r["source_oid"],16)
        if oid in seen:raise ValueError("Duplicate original Source OID")
        seen.add(oid)
        node=nodes.get(oid)
        if node is None or node["type"]!=TYPE:
            raise ValueError(f"Original KIDS Source OID/type missing {fmt(oid)}")
        values={}
        for label,key in FIELDS.items():
            prop=node["fields"].get(key)
            if prop is None or prop["kind"]!=5 or prop["count"]!=1:
                raise ValueError(f"Source {fmt(oid)} missing typed original field {label}")
            values[label]=struct.unpack_from("<I",blob,prop["offset"])[0]
        render=values["LayoutTexturesRenderStateObjectHash"]
        info=values["LayoutTexturesInfoDataResourceHash"]
        wrap=values["WrapStaticScreenLayoutTexturesObjectHash"]
        if (fmt(render)!=r["g1t_hash"] or fmt(info)!=r["texinfo_hash"]
            or fmt(wrap)!=r["target_texture_oid"]):
            raise ValueError(f"M25 legacy field values mismatch original source bytes {fmt(oid)}")
        target=nodes.get(wrap)
        result.append({
            "source_oid":fmt(oid),
            "source_type_hash":fmt(TYPE),
            "original_source_idok_node_offset":node["offset"],
            "original_texinfo_texture_name_aliases":r["original_texture_name_variants"],
            "original_layout_textures_render_state_object_hash":fmt(render),
            "original_layout_textures_info_data_resource_hash":fmt(info),
            "original_wrap_static_screen_layout_textures_object_hash":fmt(wrap),
            "legacy_M25_g1t_hash_same_raw_u32":fmt(render),
            "legacy_M25_texinfo_hash_same_raw_u32":fmt(info),
            "legacy_M25_target_texture_oid_same_raw_u32":fmt(wrap),
            "original_wrapper_hash_locally_present_as_IDOK":int(target is not None),
            "original_wrapper_target_node_type_if_present":fmt(target["type"]) if target else "",
            "native_game_species_id_verified":"",
            "native_game_villager_id_verified":"",
        })
    for col in ("original_layout_textures_render_state_object_hash",
                "original_layout_textures_info_data_resource_hash",
                "original_wrap_static_screen_layout_textures_object_hash"):
        if len({x[col] for x in result})!=628:
            raise ValueError(f"Unexpected duplicate original field values {col}")
    result.sort(key=lambda x:x["source_oid"])
    n_local=sum(x["original_wrapper_hash_locally_present_as_IDOK"] for x in result)
    summary={
        "version":"2.0.1",
        "original_root_kids_sha256":PIN,
        "original_kids_node_count":len(nodes),
        "original_icon_source_OID_records_verified":len(result),
        "source_OID_records_three_typed_property_fields_verified":len(result),
        "original_native_type_name":"StaticScreenLayoutTextures",
        "original_native_type_hash":fmt(TYPE),
        "original_field_name_hashes":{k:fmt(v) for k,v in FIELDS.items()},
        "all_original_property_raw_values_match_M25_legacy_columns":True,
        "unique_original_wrap_object_hashes":len({
            x["original_wrap_static_screen_layout_textures_object_hash"] for x in result}),
        "wrapper_hashes_locally_present_as_IDOK":n_local,
        "wrapper_hashes_not_locally_present_as_IDOK":len(result)-n_local,
        "M25_column_target_texture_oid_is_original_wrap_static_screen_layout_textures_object_hash":True,
        "original_render_state_field_raw_value_equals_M25_g1t_hash":True,
        "original_info_data_field_raw_value_equals_M25_texinfo_hash":True,
        "raw_hash_equals_file_hash_is_not_a_proven_resource_consumer":True,
        "direct_source_to_final_texture_object_relation_proven":False,
        "native_species_id_to_icon_source_OID_proven":False,
        "game_villager_id_to_wrapper_hash_proven":False,
        "warning":"M25 target_texture_oid is the source byte value of property WrapStaticScreenLayoutTexturesObjectHash. Retain the old column only as a legacy alias; it is not automatically the final texture object ID. Matching G1T/TEXINFO hash values are numeric provenance, not an executed loader call.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/"m31_3_corrected_628_native_texture_object_fields.csv").open(
        "w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=COLS);w.writeheader();w.writerows(result)
    (OUT/"m31_3_original_628_source_field_semantics_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary

def selftest():
    assert FIELDS["WrapStaticScreenLayoutTexturesObjectHash"]==0x2856A1B3
    assert FIELDS["LayoutTexturesRenderStateObjectHash"]==0xC8BB66DA
    assert FIELDS["LayoutTexturesInfoDataResourceHash"]==0x2276FC56
    print("PASS original three named StaticScreenLayoutTextures property Hashes")
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:selftest()
    else:run()
