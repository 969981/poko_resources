#!/usr/bin/env python3
"""M30.2: recover original string *pointers* in KIDS type 0x9D1AFA46
3-field descriptor property array.

M26.3 established that main+0x3331810/+0x3331818/+0x3331820 are
initialized 64-bit pointers into .rodata, NOT function pointers in .text.
Read their exact ASCII/UTF8 NUL-terminated data to understand the actual
descriptors and original source field name semantics. No species ID guess.
"""
from __future__ import annotations
import hashlib
import json
import struct
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m20_native_species_item_targets import MAIN,SHA_MAIN

OUT=Path("UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M30")
VTABLE_DESCRIPTORS=(0x3331810,0x3331818,0x3331820)
EXPECTED_POINTERS=(0x27FB2C7,0x27B13C1,0x27CFED6)
HASH_ARRAY=0x2838834
EXPECTED_HASHES=(0x2F610FEA,0xE88C8D60,0x34CBB458)
MAX_LENGTH=512

def exact(parts,address,length):
    for p in parts:
        pos=address-p["mem_offset"]
        if 0<=pos and pos+length<=len(p["data"]):
            return p["name"],bytes(p["data"][pos:pos+length])
    return None,None

def read_nul(parts,address):
    kind,blob=exact(parts,address,MAX_LENGTH)
    if kind!="rodata":
        raise ValueError(f"Original descriptor pointer target {address:#x} not in rodata")
    end=blob.find(b"\0")
    if end<0:
        raise ValueError("Property descriptor ASCII string exceeds bound or lacks NUL")
    data=blob[:end]
    if not 1<=len(data)<=255:
        raise ValueError("Original descriptor text length outside expected bound")
    try:content=data.decode("utf-8")
    except UnicodeDecodeError:content=None
    return {"literal_utf8":content,"literal_hex":data.hex(),
            "nul_terminated":True,"byte_length":len(data),
            "source_section":kind,"read_max_length":MAX_LENGTH}

def run():
    raw=MAIN.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SHA_MAIN:raise ValueError("Original Pokopia NSO SHA256 mismatch")
    kind,parts=get_sections(raw)
    if kind!="NSO0":raise ValueError("Expected source-qualified original NSO0")
    metadata,hashes=exact(parts,HASH_ARRAY,12)
    if metadata!="rodata" or struct.unpack("<3I",hashes)!=EXPECTED_HASHES:
        raise ValueError("Original KIDS property hashes changed")
    rows=[]
    for i,(cell,expected) in enumerate(zip(VTABLE_DESCRIPTORS,EXPECTED_POINTERS)):
        section,rawptr=exact(parts,cell,8)
        if section!="data" or struct.unpack("<Q",rawptr)[0]!=expected:
            raise ValueError("Original type field string pointer moved")
        string=read_nul(parts,expected)
        rows.append({
            "descriptor_index":i,"source_cell":hex(cell),
            "source_cell_raw_u64_le":rawptr.hex(),
            "static_pointer_target":hex(expected),
            "property_hash_u32":f"{EXPECTED_HASHES[i]:08x}",
            "original_target_type":"RODATA_NUL_TERMINATED_TEXT_NOT_CODE",
            **string,
            "property_runtime_game_ID_field_verified":False,
        })
    summary={
        "game_version":"2.0.1",
        "original_main_sha256":SHA_MAIN,
        "original_KIDS_type_hash":"0x9d1afa46",
        "original_property_descriptor_string_pointer_cells":len(rows),
        "original_KIDS_property_hashes":[f"{x:08x}" for x in EXPECTED_HASHES],
        "all_pointer_targets_are_rodata_text":True,
        "original_field_2_3543_entry_key_array_hash":"e88c8d60",
        "original_field_3_3543_entry_source_array_hash":"34cbb458",
        "property_strings_are_not_function_pointers":True,
        "native_species_ID_to_KIDS_source_OID_proven":False,
        "game_villager_ID_to_texture_proven":False,
        "warning":"The 3 data pointers are property descriptor label strings, NOT virtual getter functions. Original hashes and names may illuminate structure; game entity ID->array key still needs dynamic or native code consumer evidence.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"m30_2_original_KIDS_field_descriptor_labels.json").write_text(
        json.dumps({"summary":summary,"original_descriptor_rows":rows},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT/"m30_2_original_KIDS_field_labels_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"summary":summary,"original_descriptor_rows":rows},ensure_ascii=False,indent=2))
    return summary

def selftest():
    assert len(VTABLE_DESCRIPTORS)==len(EXPECTED_POINTERS)==len(EXPECTED_HASHES)==3
    assert VTABLE_DESCRIPTORS[-1]-VTABLE_DESCRIPTORS[0]==16
    print("PASS original property descriptor text-target pointer layout")

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test:selftest()
    else:run()
