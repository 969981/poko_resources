#!/usr/bin/env python3
"""M26.2: recover KIDS 0x9D1AFA46 class method-table installation and
0x34CBB458 source-array property descriptor's original read-only metadata.

This closes *static native type/metadata ownership* of the 3543-entry
resource array, not species ID->slot runtime dataflow.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m20_native_species_item_targets import (
    MAIN,SHA_MAIN,arm64_window,decode_adrp,scan_direct_callers,u32,
)

OUT=Path("UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M26")
TYPE_HASH=0x9D1AFA46
PROP_HASH=0x34CBB458
OWNER_GLOBAL=0x349C2E0
METHOD_GLOBAL=0x349C2E8
ORIGINAL_OWNER=0x367AD40
ORIGINAL_METHOD_BASE=0x33135B8
VTABLE=ORIGINAL_METHOD_BASE+0x10 # original instruction: add x8,x8,#0x10
VTABLE_STORE=0xBE1A28
TYPEGET=0xDD1C30
GETTER_SLOT=0x33135F0
RODATA_DESCRIPTOR=0x2838834
RODATA_PROPERTY=RODATA_DESCRIPTOR+8

def section(parts,va,n):
    for p in parts:
        at=va-p["mem_offset"]
        if 0<=at and at+n<=len(p["data"]):
            return p["name"],p["data"][at:at+n]
    return "",None

def original_u64(parts,va,expected=None):
    k,b=section(parts,va,8)
    if k!="data" or b is None:raise ValueError(f"Original static data unavailable at {va:#x}")
    val=struct.unpack("<Q",b)[0]
    if expected is not None and val!=expected:
        raise ValueError(f"Original initialized pointer differs at {va:#x}: {val:#x} != {expected:#x}")
    return val

def actual_adrp_add(text,base,adrp,add,expected):
    a=u32(text,adrp-base);b=u32(text,add-base)
    first=decode_adrp(a,adrp)
    if first is None:
        raise ValueError("Original class descriptor ADRP instruction lost")
    if (b&0xFF000000)!=0x91000000:
        raise ValueError("Original class descriptor ADD missing")
    if ((b>>5)&31)!=first[1]:
        raise ValueError("Original descriptor ADD no longer consumes ADRP register")
    shift=(b>>22)&3
    if shift>1:raise ValueError("Unexpected original ADD shift")
    value=first[0]+(((b>>10)&4095)<<(12 if shift else 0))
    if value!=expected:
        raise ValueError(f"Class property metadata pointer changed {value:#x} != {expected:#x}")
    return {"adrp_pc":hex(adrp),"add_pc":hex(add),
            "adrp_original_word":f"{a:08x}","add_original_word":f"{b:08x}",
            "reconstructed_original_descriptor_va":hex(value),
            "register_preservation":"EXACT_ADJACENT_ADRP_ADD",
            "runtime_property_consumer_verified":False}

def run():
    source=MAIN.read_bytes()
    if hashlib.sha256(source).hexdigest()!=SHA_MAIN:
        raise ValueError("Original NSO0 SHA256 required")
    kind,parts=get_sections(source)
    if kind!="NSO0":raise ValueError("Expected original mapped NSO0")
    sec=next(x for x in parts if x["name"]=="text")
    txt,base=sec["data"],sec["mem_offset"]
    if original_u64(parts,OWNER_GLOBAL,ORIGINAL_OWNER)!=ORIGINAL_OWNER:
        raise ValueError("Wrong static owner")
    original_u64(parts,METHOD_GLOBAL,ORIGINAL_METHOD_BASE)
    original_u64(parts,GETTER_SLOT,TYPEGET)
    # Original constructor source bytes must load both class cells and apply
    # +0x10 before the write; no runtime execution proof is assumed.
    asm=arm64_window(txt,base,VTABLE_STORE,0x34,0x28)
    by_addr={int(x["pc"],16):x["asm"] for x in asm}
    for site,mnemonics in {
        0xBE1A10:("ldr x1,","[x1, #0x2e0]"),
        0xBE1A14:("ldr x8,","[x8, #0x2e8]"),
        0xBE1A24:("add x8, x8, #0x10",),
        VTABLE_STORE:("stp x8, x9, [x1]",),
    }.items():
        if not all(fragment in by_addr.get(site,"") for fragment in mnemonics):
            raise ValueError(f"Original static class method-table install changed: {site:x} {by_addr.get(site)}")
    if original_u64(parts,VTABLE+0x28,TYPEGET)!=TYPEGET:
        raise ValueError("Typehash getter method slot diverged")
    typ,r=section(parts,RODATA_PROPERTY,4)
    if typ!="rodata" or struct.unpack("<I",r)[0]!=PROP_HASH:
        raise ValueError("Original 0x34CBB458 descriptor lost at +8")
    descriptor=actual_adrp_add(txt,base,0xDD1B60,0xDD1B64,RODATA_DESCRIPTOR)
    _,raw=section(parts,RODATA_DESCRIPTOR-0x30,0x90)
    words=[{"original_va":hex(RODATA_DESCRIPTOR-0x30+i),
            "u32":f"{struct.unpack_from('<I',raw,i)[0]:08x}",
            "description":"KIDS_SOURCE_ICON_ARRAY_PROPERTY_HASH" if
              RODATA_DESCRIPTOR-0x30+i==RODATA_PROPERTY else
              "UNINTERPRETED_DESCRIPTOR_BYTES"}
           for i in range(0,len(raw),4)]
    table=[]
    for off in range(0,0x80,8):
        val=original_u64(parts,VTABLE+off)
        table.append({
            "vtable_offset":hex(off),
            "original_function_rva":hex(val),
            "is_typehash_getter":val==TYPEGET,
            "value_in_original_text":base<=val<base+len(txt),
            "method_semantics_verified":False,
        })
    functions={}
    for label,pc,before,after in (
        ("class_type_registration",0xBE1A10,0x14,0x64),
        ("class_property_descriptor",0xDD1B60,0x60,0xB0),
        ("typehash_getter_and_following_virtual_calls",TYPEGET,0x44,0x60),
    ):
        functions[label]=arm64_window(txt,base,pc,before,after)
    # Class table positions are code-pointer source evidence. The descriptor
    # property list may be returned by several getters; do not assert which
    # virtual method directly returns the 3543-entry field without a consumer.
    result={
        "version":"2.0.1","original_main_sha256":SHA_MAIN,
        "original_class_type_hash":hex(TYPE_HASH),
        "original_class_global_owner_cell":hex(OWNER_GLOBAL),
        "original_class_global_table_cell":hex(METHOD_GLOBAL),
        "original_class_bss_owner_initial_va":hex(ORIGINAL_OWNER),
        "original_class_method_table_installed_at":hex(VTABLE),
        "original_class_store_instruction":hex(VTABLE_STORE),
        "original_class_typehash_getter_method_slot_offset":hex(GETTER_SLOT-VTABLE),
        "original_class_typehash_getter":hex(TYPEGET),
        "original_3543_icon_source_property_hash":hex(PROP_HASH),
        "original_property_descriptor_address":hex(RODATA_DESCRIPTOR),
        "property_hash_byte_offset_in_descriptor":8,
        "original_descriptor_adrp_add_verified":True,
        "original_vtable_first_16_code_pointer_entries":len(table),
        "original_vtable_first_16_values_in_text":sum(x["value_in_original_text"] for x in table),
        "type_hash_and_descriptor_metadata_source_proven":True,
        "descriptor_native_game_ID_consumer_proven":False,
        "game_species_ID_to_3543_array_index_proven":False,
        "native_villager_ID_to_icon_source_OID_proven":False,
        "warning":"Verified original BSS class, installed method table, descriptor address/hash; not a caller-level or runtime assignment of a native species ID.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"m26_2_class_methodtable_descriptor_evidence.json").write_text(
        json.dumps({"descriptor_pointer_instruction":descriptor,
                    "property_descriptor_original_u32_neighborhood":words,
                    "original_static_vtable":table,
                    "original_class_related_code_windows":functions},
                   ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT/"m26_2_class_methodtable_descriptor_summary.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result
def self_test():
    assert GETTER_SLOT-VTABLE==0x28
    assert RODATA_DESCRIPTOR+8==0x283883C
    print("PASS native type method table and property descriptor geometry")
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:self_test()
    else:run()
if __name__=="__main__":main()
