#!/usr/bin/env python3
"""M24: scoped source-byte consumer trace around the KIDS 0x79991E79 registration.

Proof tiers are intentionally separate:
 (1) RDB KIDS typed Hash -> object Hash 0x2856a1b3 -> texture object (M19/M22)
 (2) original NSO pointer install and KIDS type dispatcher (M23.1)
 (3) game villager ID -> KIDS source object consumer (still NOT established)

This script never writes to the original NSO, game data, or formal ID mappings.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path
from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m20_native_species_item_targets import (
    MAIN, SHA_MAIN, arm64_window, scan_direct_callers, decode_adrp, u32,
)

BASE = Path("UnPack/2.0.1/Resources")
M23 = BASE / "Villagers/Native_2.0.1/M23/m23_1_original_kids_table_install.json"
M22 = BASE / "Villagers/Native_2.0.1/M22/m22_nine_ambiguous_native_object_refs.csv"
OUT = BASE / "Villagers/Native_2.0.1/M24"
INSTALL = 0xBB85CC
REGISTER_TYPE = 0xBB85F4
REGISTRY_ROUTINE = 0x1FDC1E0
METHOD = 0xCE854C
OWNER_GLOBAL = 0x34963B0
TABLE_GLOBAL = 0x34963B8
RELATED_GLOBAL = 0x34963C0
BSS_OWNER = 0x366E6F0
METHOD_TABLE = 0x32F0EE0
KIDS_TYPE = 0x79991E79
HASH_METHOD = 0x2856A1B3

def view(parts, addr, length):
    for part in parts:
        off=addr-part["mem_offset"]
        if 0<=off and off+length<=len(part["data"]):
            return part["name"],part["data"][off:off+length]
    return "", None

def extract_load(word, r):
    """ADRP register + LDR/STR with unsigned scaled immediate."""
    rn=(word>>5)&31
    if rn!=r:
        return None
    for op, tag, scale in (
        (0xF9400000, "LDR_X",8), (0xF9000000,"STR_X",8),
        (0xB9400000,"LDR_W",4), (0xB9000000,"STR_W",4),
        (0x79400000,"LDR_H",2), (0x79000000,"STR_H",2),
        (0x39400000,"LDR_B",1), (0x39000000,"STR_B",1)
    ):
        if word&0xFFC00000==op:
            return tag,((word>>10)&4095)*scale
    if word&0xFF000000==0x91000000:
        shift=(word>>22)&3
        if shift<=1:
            return "ADD_ADDR", ((word>>10)&4095)<<(12 if shift else 0)
    return None

def source_adrp_refs(text, base, cells):
    """Adjacent original ADRP -> original LDR/STR/ADD only; no liveness claims."""
    by_page={}
    for addr in cells:by_page.setdefault(addr&~4095,set()).add(addr)
    rows=[]
    for off in range(0,len(text)-7,4):
        pc=base+off
        d=decode_adrp(u32(text,off),pc)
        if d is None or d[0] not in by_page:continue
        page,reg=d
        v=extract_load(u32(text,off+4),reg)
        if v is None:continue
        op,imm=v
        addr=page+imm
        if addr not in by_page[page]:continue
        rows.append({
            "pc_adrp":hex(pc),"pc_following":hex(pc+4),
            "global_cell_rva":hex(addr),
            "operation":op,"original_adrp_word":f"{u32(text,off):08x}",
            "original_second_word":f"{u32(text,off+4):08x}",
            "grade":"ADJACENT_ORIGINAL_EFFECTIVE_ADDRESS",
            "dynamic_object_semantics_proven":False})
    return rows

def run():
    original=MAIN.read_bytes()
    if hashlib.sha256(original).hexdigest()!=SHA_MAIN:raise ValueError("Wrong original NSO SHA")
    prior=json.loads(M23.read_text(encoding="utf-8"))
    if not (prior["original_install_instruction_verified"] and
            prior["static_owner_address_from_initialized_global"]==hex(BSS_OWNER) and
            prior["nearby_type_hash_value"]==hex(KIDS_TYPE) and
            prior["registered_method_table_pointer"]==hex(METHOD_TABLE)):
        raise ValueError("M23.1 original proof dependency changed")
    with M22.open(encoding="utf-8",newline="") as f:
        variants=list(csv.DictReader(f))
    if len(variants)!=54 or len({x["portrait_id_pokohex"] for x in variants})!=9:
        raise ValueError("M22 original link input changed")
    if any(x["native_villager_portrait_id_verified"] or
           x["typed_object_link"]!="RAW_BYTES_CONFIRMED_SOURCE_PROPERTY_TO_TEXTURE_OID"
           for x in variants):
        raise ValueError("M22 contains an unproven ID promotion")
    kind, parts=get_sections(original)
    if kind!="NSO0":raise ValueError("Original executable not mapped NSO")
    sec=next(x for x in parts if x["name"]=="text")
    text,base=sec["data"],sec["mem_offset"]
    if not 0<=REGISTRY_ROUTINE-base<len(text):
        raise ValueError("Original callee not in .text")
    sec_name,arr=view(parts,TABLE_GLOBAL,8)
    if sec_name!="data" or struct.unpack("<Q",arr)[0]!=METHOD_TABLE-16:
        raise ValueError("Original method table data pointer changed")
    sec_name,arr=view(parts,METHOD_TABLE+24,8)
    if sec_name!="data" or struct.unpack("<Q",arr)[0]!=METHOD:
        raise ValueError("Original method slot changed")
    cells=(OWNER_GLOBAL,TABLE_GLOBAL,RELATED_GLOBAL,BSS_OWNER)
    adjacent=source_adrp_refs(text,base,cells)
    direct={}
    for key,target in [
        ("native_type_registration_helper",REGISTRY_ROUTINE),
        ("schema_property_method",METHOD),
        ("type_registration_tail_site",REGISTER_TYPE),
        ("installed_table_store_site",INSTALL),
    ]:
        bl,b=scan_direct_callers(text,base,target)
        direct[key]={
            "target_va":hex(target),"direct_BL_total":len(bl),"direct_B_total":len(b),
            "direct_BL_first":[hex(x) for x in bl[:120]],
            "direct_B_first":[hex(x) for x in b[:120]],
            "anchor_windows":[{
                "caller_pc":hex(x),"kind":calltype,
                "original_instructions":arm64_window(text,base,x,0x24,0x30)}
                for calltype, vals in (("BL",bl[:18]),("B",b[:18])) for x in vals],
        }
    # Preserve bounded disassembly around exact instruction anchors.  We do not
    # equate this generic type-registration function with a villager lookup.
    windows={}
    for label,pc,before,after in (
        ("native_KIDS_type_registration_0x1fdc1e0",REGISTRY_ROUTINE,0x30,0x110),
        ("native_schema_method_0xce854c",METHOD,0x20,0xB0),
        ("native_install_and_type_setup_0xbb85cc",INSTALL,0x50,0xA0),
    ):
        windows[label]=arm64_window(text,base,pc,before,after)
    # Original initialized method table entries anchored to +0x32f0ee0:
    methods=[]
    for slot in range(0,0x80,8):
        section,pointer=view(parts,METHOD_TABLE+slot,8)
        if section!="data":break
        target=struct.unpack("<Q",pointer)[0]
        in_text=base<=target<base+len(text) and target%4==0
        methods.append({
            "slot_offset":hex(slot),"source_cell_rva":hex(METHOD_TABLE+slot),
            "raw_function_rva":hex(target),
            "in_original_text":in_text,
            "is_hash_method":target==METHOD,
            "class_semantic_identity_verified":False,
        })
    ids=Counter(x["portrait_id_pokohex"] for x in variants)
    summary={
        "version":"2.0.1","original_main_sha256":SHA_MAIN,
        "original_main_bytes_sha_verified":True,
        "m22_ambiguous_portrait_ids":sorted(ids,key=int),
        "m22_typed_native_edge_rows":len(variants),
        "m23_1_static_initialization_rechecked":True,
        "scope":"ORIGINAL_NSO_DIRECT_BRANCH_AND_ADJACENT_GLOBAL_REFERENCES_ONLY",
        "original_owner_bss_va":hex(BSS_OWNER),
        "registry_type_hash":hex(KIDS_TYPE),
        "texture_pointer_property_hash":hex(HASH_METHOD),
        "method_table_verified_entries":len(methods),
        "method_table_entries_in_original_text":sum(m["in_original_text"] for m in methods),
        "global_adjacent_source_xrefs_total":len(adjacent),
        "global_adjacent_source_xrefs_by_cell":dict(Counter(x["global_cell_rva"] for x in adjacent)),
        "registry_typehelper_direct_B_or_BL": direct["native_type_registration_helper"]["direct_B_total"]+direct["native_type_registration_helper"]["direct_BL_total"],
        "original_method_class_owner_verified":False,
        "game_villager_id_field_consumer_verified":False,
        "native_species_id_bindings_verified":0,
        "native_villager_id_bindings_verified":0,
        "warning":"No direct branch/ADRP read proves the caller passes a game villager ID. BSS owner and source->texture linkage remain independent evidence layers.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"m24_original_consumer_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT/"m24_direct_calls_and_asm.json").write_text(
        json.dumps({"calls":direct,"windows":windows,"method_table":methods},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with (OUT/"m24_owner_global_adjacent_xrefs.csv").open("w",newline="",encoding="utf-8") as f:
        cols=["pc_adrp","pc_following","global_cell_rva","operation","original_adrp_word","original_second_word","grade","dynamic_object_semantics_proven"]
        w=csv.DictWriter(f,fieldnames=cols)
        w.writeheader();w.writerows(adjacent)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary

def selftest():
    adr=0xf9400000|(0x3b0//8<<10)|(8<<5)|1
    assert extract_load(adr,8)==("LDR_X",0x3b0)
    assert extract_load(adr,9) is None
    assert extract_load(0x91004108,8)==("ADD_ADDR",0x10)
    print("PASS original register-effective-address decoder")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test:selftest()
    else:run()

if __name__=="__main__":main()
