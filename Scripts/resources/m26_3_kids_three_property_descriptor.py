#!/usr/bin/env python3
"""M26.3: identify native KIDS type 0x9D1AFA46's THREE property descriptors
from its ORIGINAL installed vtable, metadata, code, and raw KIDSOBJDB node.

Fully source-check:
main+0x33135C8 vtable +0x18 -> main+0xDD1B48
properties 0..2 live in rodata main+0x2838828 and 0x2838834
descriptor consumers main+0xDD1B70/+74/+78
original KIDS object B4A1803B has field 0x34CBB458, kind 5, 3543 u32s.

Do not pretend a property index w3=2 is a game species/dex ID.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m20_native_species_item_targets import MAIN,SHA_MAIN,arm64_window,u32
from Scripts.resources.m16_verify_pokemon_texture_kidsobjdb import parse_kids

BASE=Path("UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M26")
KIDS_FILE=Path("UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0xacd220a8.fdata/native/root_019167_50ae86ef.kidsobjdb")
KIDS_SHA="86f90b4c11da9bc2b3e28889a5090ff507f96ca713fe4fad1dd50f6f692d7541"
OWNER=0xB4A1803B
TYPE=0x9D1AFA46
VTABLE=0x33135C8
METHOD=0xDD1B48
METHOD_SLOT=VTABLE+0x18
METATABLE=0x2838828
HASHTABLE=0x2838834
POINTERTABLE=0x3331810
HASHES=(0x2F610FEA,0xE88C8D60,0x34CBB458)
METAS=(0x05000001,0x05000000,0x05000000)
REGISTRY_HASH=HASHES[2]
REGISTRY_FIELD_COUNT=3543

def mapped(parts,addr,length):
    for p in parts:
        k=addr-p["mem_offset"]
        if 0<=k and k+length<=len(p["data"]):
            return p["name"],p["data"][k:k+length]
    return "",None

def u32block(parts,va,n,sec):
    got,dat=mapped(parts,va,n*4)
    if got!=sec:raise ValueError(f"Original raw table missing from {sec}:{va:#x}")
    return struct.unpack("<"+"I"*n,dat)

def u64block(parts,va,n,sec):
    got,dat=mapped(parts,va,n*8)
    if got!=sec:raise ValueError(f"Original raw pointer list missing from {sec}:{va:#x}")
    return struct.unpack("<"+"Q"*n,dat)

def run():
    raw=MAIN.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SHA_MAIN:raise ValueError("Original NSO SHA256 differs")
    kind,parts=get_sections(raw)
    if kind!="NSO0":raise ValueError("Expected native 2.0.1 NSO")
    c=next(p for p in parts if p["name"]=="text")
    text,base=c["data"],c["mem_offset"]
    getter=u64block(parts,METHOD_SLOT,1,"data")[0]
    if getter!=METHOD:raise ValueError("KIDS vtable +0x18 property method changed")
    metadata=u32block(parts,METATABLE,3,"rodata")
    field_hashes=u32block(parts,HASHTABLE,3,"rodata")
    pointercells=u64block(parts,POINTERTABLE,3,"data")
    if metadata!=METAS or field_hashes!=HASHES:
        raise ValueError("Original class 3-field descriptor metadata differs")
    asm=arm64_window(text,base,METHOD,0,0xE0)
    bypc={int(r["pc"],16):r["asm"] for r in asm}
    required={
        0xDD1B50:("cmp w3, #2",),
        0xDD1B58:("adrp x8,","0x2838000"),
        0xDD1B5C:("add x8, x8, #0x828",),
        0xDD1B60:("adrp x9,","0x2838000"),
        0xDD1B64:("add x9, x9, #0x834",),
        0xDD1B68:("adrp x10,","0x3331000"),
        0xDD1B6C:("add x10, x10, #0x810",),
        0xDD1B70:("ldr w11, [x8, w3, sxtw #2]",),
        0xDD1B74:("ldr w12, [x9, w3, sxtw #2]",),
        0xDD1B78:("ldr x13, [x10, w3, sxtw #3]",),
        0xDD1B7C:("stp w11, w12, [x1]",),
        0xDD1B88:("stp x13, x11, [x1, #8]",),
    }
    for pc,frags in required.items():
        if not all(f in bypc.get(pc,"") for f in frags):
            raise ValueError(f"Original native descriptor enumerator code diverges at {pc:x}: {bypc.get(pc)}")
    original_kids=KIDS_FILE.read_bytes()
    if hashlib.sha256(original_kids).hexdigest()!=KIDS_SHA:
        raise ValueError("Original KIDS raw database SHA256 changed")
    header,objects=parse_kids(original_kids)
    node=objects.get(OWNER)
    if not node or node["type"]!=TYPE:
        raise ValueError("Original 3-field KIDS registered type/object differs")
    last=node["fields"].get(REGISTRY_HASH)
    if not last or last["kind"] not in (4,5) or last["count"]!=REGISTRY_FIELD_COUNT:
        raise ValueError("Original 3543-element icon registry typed property missing")
    from_native=[]
    for i,field_hash in enumerate(HASHES):
        found=node["fields"].get(field_hash)
        from_native.append({
            "descriptor_index":i,
            "original_descriptor_meta":f"{metadata[i]:08x}",
            "original_descriptor_hash":f"{field_hash:08x}",
            "original_descriptor_pointer_cell_va":hex(POINTERTABLE+8*i),
            "original_descriptor_function_pointer_rva":hex(pointercells[i]),
            "pointer_in_original_text":base<=pointercells[i]<base+len(text),
            "original_kids_node_has_descriptor_field":bool(found),
            "native_property_kind":found["kind"] if found else None,
            "native_property_count":found["count"] if found else None,
            "native_property_data_byte_offset":found["offset"] if found else None,
            "is_3543_icon_registry_array":i==2,
            "game_species_id_field_verified":False,
        })
    if from_native[-1]["native_property_data_byte_offset"]!=378728:
        raise ValueError("Original KIDS 3543 source array byte offset changed")
    result={
        "game_version":"2.0.1",
        "original_main_sha256":SHA_MAIN,
        "original_kids_objdb_sha256":KIDS_SHA,
        "original_class_type_hash":hex(TYPE),
        "original_class_source_object_oid":f"{OWNER:08x}",
        "original_type_vtable_method_slot":hex(METHOD_SLOT),
        "original_property_descriptor_method":hex(METHOD),
        "original_property_descriptor_table":hex(HASHTABLE),
        "original_property_metadata_table":hex(METATABLE),
        "original_property_pointer_table":hex(POINTERTABLE),
        "native_property_descriptors":3,
        "original_icon_source_array_descriptor_index":2,
        "original_icon_array_field_hash":hex(REGISTRY_HASH),
        "original_icon_array_elements":REGISTRY_FIELD_COUNT,
        "original_icon_array_data_byte_offset":last["offset"],
        "original_method_reads_native_property_hash_by_index":True,
        "original_type_schema_and_data_field_connected":True,
        "original_game_species_id_to_array_index_verified":False,
        "original_game_villager_id_to_source_OID_verified":False,
        "warning":"Class vtable+0x18 reads exactly three native property descriptors. The third matches a 3543-u32 original KIDS field. This does not prove the gameplay's species-ID indexing of that field.",
    }
    BASE.mkdir(parents=True,exist_ok=True)
    (BASE/"m26_3_three_original_property_descriptors.json").write_text(
        json.dumps({"original_native_descriptor_rows":from_native,
                    "original_method_disassembly":asm},
                   ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (BASE/"m26_3_native_property_schema_summary.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result
def selftest():
    assert HASHES[2]==REGISTRY_HASH
    assert HASHTABLE==METATABLE+12
    assert METHOD_SLOT==0x33135E0
    print("PASS three original property descriptors geometry")
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:selftest()
    else:run()
if __name__=="__main__":main()
