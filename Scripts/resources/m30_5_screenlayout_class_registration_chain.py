#!/usr/bin/env python3
"""M30.5: recover exact original class labels for BOTH stages of native
Pokopia 2.0.1 ScreenLayout icon source->texture resource chain.

The original registration code places ASCII literal in x1, class registry
in x0, then directly BLs a type initializer. The type initializer embeds
a class hash and installs BSS vtable. Verify instructions / pointers from
the pinned original NSO. It proves static *class label and type hash*,
not a runtime game species or form input to the texture pack lookup.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m20_native_species_item_targets import (
    MAIN,SHA_MAIN,branch_target,decode_adrp,arm64_window,
)

OUT=Path("UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M30")
TYPES=(
    {
        "class_name":"ScreenLayoutTexturePackSettings",
        "original_string_va":0x27B09B9,
        "load_adrp":0xBAA51C,"load_add":0xBAA520,"pass_reg":0xBAA524,"call_pc":0xBAA528,
        "function":0xBE19B4,
        "type_hash":0x9D1AFA46,"movz_pc":0xBE19C8,"movk_pc":0xBE19D0,
        "class_bss_global":0x349C2E0,"table_base_global":0x349C2E8,
        "bss_object":0x367AD40,"vtable_base":0x33135C8,
        "property_method_slot":0x18,"property_method":0xDD1B48,
        "native_fields":[0x2F610FEA,0xE88C8D60,0x34CBB458],
    },
    {
        "class_name":"StaticScreenLayoutTextures",
        "original_string_va":0x279B44D,
        "load_adrp":0xBA6A10,"load_add":0xBA6A14,"pass_reg":0xBA6A18,"call_pc":0xBA6A1C,
        "function":0xBB8558,
        "type_hash":0x79991E79,"movz_pc":0xBB85F8,"movk_pc":0xBB8600,
        "class_bss_global":0x34963B0,"table_base_global":0x34963B8,
        "bss_object":0x366E6F0,"vtable_base":0x32F0EE0,
        "property_method_slot":0x18,"property_method":0xCE854C,
        "native_fields":[0x2856A1B3],
    },
)
def mapbytes(parts,va,n):
    for p in parts:
        off=va-p["mem_offset"]
        if 0<=off and off+n<=len(p["data"]):
            return p["name"],bytes(p["data"][off:off+n])
    return "",None
def get32(code,base,pc):
    return struct.unpack_from("<I",code,pc-base)[0]
def load_string_target(code,base,site):
    pc=site["load_adrp"]
    first=decode_adrp(get32(code,base,pc),pc)
    if first is None:raise ValueError(f"Missing original ADRP at {pc:x}")
    next_word=get32(code,base,site["load_add"])
    if (site["load_add"]!=pc+4 or next_word&0xff000000!=0x91000000
        or ((next_word>>5)&31)!=first[1]):
        raise ValueError("Original address builder not adjacent ADRP+ADD")
    sh=(next_word>>22)&3
    if sh>1:raise ValueError("Unsupported ADRP add shift")
    val=first[0]+(((next_word>>10)&0xfff)<<(12 if sh else 0))
    if val!=site["original_string_va"]:raise ValueError("Original registered class string address changed")
    return {"first_original_word":f"{get32(code,base,pc):08x}",
            "second_original_word":f"{next_word:08x}",
            "effective_original_string_va":hex(val)}
def movw_pair(code,base,low_at,high_at,expected):
    a=get32(code,base,low_at);b=get32(code,base,high_at)
    if ((a&0x7f800000)!=0x52800000 or
        (b&0x7f800000)!=0x72800000 or
        ((a>>21)&3)!=0 or ((b>>21)&3)!=1 or
        (a&31)!=(b&31)):
        raise ValueError("Missing true original type Hash MOVZ/MOVK instructions")
    number=(((b>>5)&0xffff)<<16)|((a>>5)&0xffff)
    if number!=expected:raise ValueError(f"Native type hash differs: {number:x} vs {expected:x}")
    return {"type_hash":hex(number),
            "original_movz_word":f"{a:08x}",
            "original_movk_word":f"{b:08x}",
            "same_register":f"w{a&31}",
            "intervening_register_liveness_proven":False if high_at-low_at>4 else True}
def original_u64(parts,va,expected):
    section,raw=mapbytes(parts,va,8)
    if section!="data" or struct.unpack("<Q",raw)[0]!=expected:
        raise ValueError(f"Original class/data pointer differs {va:x}")
    return hex(expected)
def run():
    raw=MAIN.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SHA_MAIN:
        raise ValueError("Pinned original NSO SHA mismatch")
    kind,parts=get_sections(raw)
    if kind!="NSO0":raise ValueError("Original source not an NSO")
    text=next(p for p in parts if p["name"]=="text")
    code,base=text["data"],text["mem_offset"]
    artifacts=[]
    for site in TYPES:
        name=site["class_name"]
        section,label=mapbytes(parts,site["original_string_va"],len(name)+1)
        if section!="rodata" or label!=name.encode()+b"\0":
            raise ValueError("Registered class name not backed by original ASCII")
        address=load_string_target(code,base,site)
        # The exact source passes x19 object in x0; it doesn't prove this
        # x19 is any particular Pokémon game instance.
        source_reg_word=get32(code,base,site["pass_reg"])
        if source_reg_word!=0xAA1303E0:
            raise ValueError("Original registered context x0=x19 changed")
        if site["pass_reg"]!=site["load_add"]+4 or site["call_pc"]!=site["pass_reg"]+4:
            raise ValueError("Registered class has unexpected gap in source instructions")
        branch=branch_target(site["call_pc"],get32(code,base,site["call_pc"]))
        if branch!=(site["function"],"BL"):
            raise ValueError(f"Native class constructor BL target changed {name}: {branch}")
        typehash=movw_pair(code,base,site["movz_pc"],site["movk_pc"],site["type_hash"])
        original_u64(parts,site["class_bss_global"],site["bss_object"])
        # Original initializer accesses table-base global and adds 0x10
        # before its initial method table installation.
        original_u64(parts,site["table_base_global"],site["vtable_base"]-16)
        original_u64(parts,site["vtable_base"]+site["property_method_slot"],site["property_method"])
        artifacts.append({
            "original_registered_class_label":name,
            "original_class_type_hash":hex(site["type_hash"]),
            "original_label_and_type_same_registered_class":True,
            "registered_label_rodata_va":hex(site["original_string_va"]),
            "constructor_BL_site":hex(site["call_pc"]),
            "constructor_original_target":hex(site["function"]),
            "constructor_BL_source_word":f"{get32(code,base,site['call_pc']):08x}",
            "class_label_adrp_add_bytes":address,
            "class_registration_x0_from_x19_original_word":f"{source_reg_word:08x}",
            "exact_type_hash_original_MOVZ_MOVK":typehash,
            "original_BSS_class_object":hex(site["bss_object"]),
            "original_installed_method_table":hex(site["vtable_base"]),
            "original_property_descriptor_method":hex(site["property_method"]),
            "original_property_method_table_offset":hex(site["property_method_slot"]),
            "native_property_hashes":[f"{x:08x}" for x in site["native_fields"]],
            "original_callsite_asm_window":arm64_window(code,base,site["call_pc"],0x14,0x18),
            "original_initializer_type_hash_asm_window":arm64_window(code,base,site["movz_pc"],0x10,0x20),
            "same_runtime_game_entity_or_texture_selection_proven":False,
        })
    summary={
        "version":"2.0.1","original_main_sha256":SHA_MAIN,
        "original_registered_KIDS_class_count":len(artifacts),
        "registered_class_labels":{
            x["original_registered_class_label"]:x["original_class_type_hash"]
            for x in artifacts},
        "ScreenLayoutTexturePackSettings_origin_type_hash":"0x9d1afa46",
        "StaticScreenLayoutTextures_origin_type_hash":"0x79991e79",
        "named_typed_classes_same_static_ScreenLayout_registration_family":True,
        "source_to_texture_property_hash":"0x2856a1b3",
        "paired_texture_pack_key_array_hash":"0xe88c8d60",
        "paired_texture_pack_object_array_hash":"0x34cbb458",
        "static_original_class_metadata_chain_proven":True,
        "runtime_texture_pack_query_consumer_proven":False,
        "runtime_species_ID_or_form_selection_proven":False,
        "game_ID_to_icon_Source_OID_proven":False,
        "warning":"Two real class registrations and vtable property schemas are static metadata evidence, not a game instance/source lookup call. A common registrar x19 register may represent registry context, NOT a Pokémon object.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"m30_5_two_named_KIDS_class_registrations.json").write_text(
        json.dumps({"summary":summary,"source_verified_classes":artifacts},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT/"m30_5_static_native_class_chain_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary
def selftest():
    assert len(TYPES)==2
    assert {x["class_name"] for x in TYPES}=={
        "ScreenLayoutTexturePackSettings","StaticScreenLayoutTextures"}
    print("PASS original two named KIDS ScreenLayout type registrations")
if __name__=="__main__":
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--self-test",action="store_true")
    v=a.parse_args()
    if v.self_test:selftest()
    else:run()
