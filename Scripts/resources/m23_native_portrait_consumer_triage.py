#!/usr/bin/env python3
"""M23: bounded original ARM64 xrefs for KIDS property-dispatch descriptor.

Source is the pinned original 2.0.1 NSO and existing M20/M22 byte evidence.
No static address, generic vtable, or r3 property-selector call is a native
villager-ID binding without the original producer/consumer dataflow.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m20_native_species_item_targets import (
    SHA_MAIN, MAIN, decode_adrp, arm64_window, scan_direct_callers, u32,
)

RES = Path("UnPack/2.0.1/Resources")
OUT = RES / "Villagers/Native_2.0.1/M23"
M20 = RES / "Pokemon/NativeCallers/M20/m20_3_schema_pointer_backrefs.json"
M22 = RES / "Villagers/Native_2.0.1/M22/m22_nine_ambiguous_native_object_refs.csv"
METHOD = 0xCE854C
METHOD_CELL = 0x32F0EF8
TABLE_ORIGIN = 0x32F0ED0
POINTER_TO_TABLE = 0x34963B8
PROPERTY_RODATA_CELL = 0x2830C98
PROPERTY = 0x2856A1B3
TARGETS=(POINTER_TO_TABLE,TABLE_ORIGIN,METHOD_CELL,PROPERTY_RODATA_CELL)
MAX_ROWS=120

def span(parts, address, size):
    for p in parts:
        at=address-p["mem_offset"]
        if 0<=at and at+size<=len(p["data"]):
            return p["name"], p["data"][at:at+size]
    return "",None

def word_mem_addr(word,page,base_reg):
    rn=(word>>5)&31
    if rn!=base_reg: return None
    if (word&0xff000000)==0x91000000: # ADD X, X, #imm
        shift=(word>>22)&3
        if shift<=1:
            return "ADD_ADDRESS",page+(((word>>10)&0xfff)<<(12 if shift==1 else 0))
    if (word&0xffc00000)==0xf9400000:
        return "LDR_X_CELL",page+(((word>>10)&0xfff)*8)
    if (word&0xffc00000)==0xf9000000:
        return "STR_X_CELL",page+(((word>>10)&0xfff)*8)
    if (word&0xffc00000)==0xb9400000:
        return "LDR_W_CELL",page+(((word>>10)&0xfff)*4)
    if (word&0xffc00000)==0xb9000000:
        return "STR_W_CELL",page+(((word>>10)&0xfff)*4)
    return None

def audit():
    blob=MAIN.read_bytes()
    if hashlib.sha256(blob).hexdigest()!=SHA_MAIN:
        raise ValueError("Original game NSO SHA256 changed")
    previous=json.loads(M20.read_text(encoding="utf-8"))
    if (previous["main_sha256"]!=SHA_MAIN or not previous["native_function_pointer_cell_exact_verified"]
            or previous["schema_function_pointer_cell"]!=hex(METHOD_CELL)
            or previous["native_raw_pointers_to_neighborhood_total"]!=1):
        raise ValueError("M20 original source pointer evidence missing")
    with M22.open(encoding="utf-8",newline="") as f: ambiguity=list(csv.DictReader(f))
    if len(ambiguity)!=54 or len({x["portrait_id_pokohex"] for x in ambiguity})!=9:
        raise ValueError("M22 typed original object evidence changed")
    if any(x["native_villager_portrait_id_verified"] or
           x["typed_object_link"]!="RAW_BYTES_CONFIRMED_SOURCE_PROPERTY_TO_TEXTURE_OID"
           for x in ambiguity):
        raise ValueError("M22 claims unproven villager identity")

    kind,sections=get_sections(blob)
    if kind!="NSO0": raise ValueError("Original ExeFS is not mapped NSO0")
    expected={
        METHOD_CELL: ("data",METHOD), POINTER_TO_TABLE:("data",TABLE_ORIGIN),
    }
    for addr,(section,pointer) in expected.items():
        name,p=span(sections,addr,8)
        if name!=section or not p or struct.unpack("<Q",p)[0]!=pointer:
            raise ValueError(f"Native pointer chain differs at {addr:#x}")
    name,p=span(sections,PROPERTY_RODATA_CELL,4)
    if name!="rodata" or not p or struct.unpack("<I",p)[0]!=PROPERTY:
        raise ValueError("Native KIDS property hash literal differs")
    code=next(x for x in sections if x["name"]=="text")
    data,base=code["data"],code["mem_offset"]
    bl,b=scan_direct_callers(data,base,METHOD)
    if bl or b: raise ValueError("M20 direct caller baseline changed")

    page_to_targets={}
    for t in TARGETS: page_to_targets.setdefault(t&~0xfff,set()).add(t)
    matches=[];page_hits={t:0 for t in TARGETS}
    for off in range(0,len(data)-3,4):
        pc=base+off
        dec=decode_adrp(u32(data,off),pc)
        if dec is None:continue
        page,reg=dec
        if page not in page_to_targets: continue
        for target in page_to_targets[page]:page_hits[target]+=1
        # Each plausible lookahead remains a *candidate* unless the
        # computed effective address is from the immediately adjacent op.
        for gap in range(4,49,4):
            if off+gap+4>len(data):break
            op=word_mem_addr(u32(data,off+gap),page,reg)
            if op is None or op[1] not in page_to_targets[page]:continue
            operation, target=op
            matches.append({
                "pointer_or_hash_cell":f"0x{target:x}",
                "source_adrp_rva":f"0x{pc:x}",
                "source_second_instruction_rva":f"0x{pc+gap:x}",
                "operation":operation,
                "gap_instructions":gap//4,
                "address_resolution_grade":("ADJACENT_EXACT_EFFECTIVE_ADDRESS" if gap==4
                                             else "LOOKAHEAD_REGISTER_LIVENESS_UNPROVEN"),
                "semantic_consumer_proven":"NO",
                "villager_id_to_object_proven":"NO",
            })

    if len(matches)>2000: raise ValueError("Suspicious cross-reference explosion")
    # Raw data-to-data backrefs to 3 table cells (never objects by themselves).
    raw_refs=[]
    for part in sections:
        if part["name"] not in ("rodata","data"): continue
        src=part["data"]; pbase=part["mem_offset"]
        for offset in range(0,len(src)-7,8):
            value=struct.unpack_from("<Q",src,offset)[0]
            if value in TARGETS:
                raw_refs.append({"pointer_cell":f"0x{pbase+offset:x}",
                                 "target_cell":f"0x{value:x}",
                                 "proven_constructor":False})
    rowsets={target:[x for x in matches if x["pointer_or_hash_cell"]==f"0x{target:x}"]
             for target in TARGETS}
    report={
        "version":"2.0.1",
        "original_main_sha256":SHA_MAIN,
        "m22_ambiguous_reference_count":9,
        "m22_typed_source_object_edge_rows_verified":54,
        "property_hash":f"0x{PROPERTY:x}",
        "property_hash_literal_rva":f"0x{PROPERTY_RODATA_CELL:x}",
        "indexed_property_dispatch_function":f"0x{METHOD:x}",
        "property_dispatch_indirect_method_cell":f"0x{METHOD_CELL:x}",
        "method_table_origin_candidate":f"0x{TABLE_ORIGIN:x}",
        "data_pointer_to_method_table":f"0x{POINTER_TO_TABLE:x}",
        "pointer_chain_bytes_verified":True,
        "direct_bl_or_b_to_property_dispatch":0,
        "adrp_page_hits_by_target":{f"0x{key:x}":value for key,value in page_hits.items()},
        "exact_adjacent_computed_addresses_by_target":{
            f"0x{k:x}":sum(x["address_resolution_grade"]=="ADJACENT_EXACT_EFFECTIVE_ADDRESS" for x in v)
            for k,v in rowsets.items()},
        "total_candidate_nearby_address_xrefs":len(matches),
        "raw_pointer_backrefs":raw_refs[:MAX_ROWS],
        "raw_pointer_backref_total":len(raw_refs),
        "first_candidate_code_windows":[
            {"computed_address":r["pointer_or_hash_cell"],
             "site":r["source_second_instruction_rva"],
             "instructions":arm64_window(data,base,int(r["source_second_instruction_rva"],16),0x34,0x54)}
            for r in matches[:min(20,len(matches))]
        ],
        "original_villager_id_producer_verified":False,
        "method_vptr_owner_verified":False,
        "original_species_id_to_texture_consumer_verified":False,
        "next_required_evidence":"Establish the owner of pointer cell 0x34963b8 / table 0x32f0ed0; trace indirect call and upstream game ID into KIDS source OID before declaring any identity.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"m23_original_property_consumer_triage.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with (OUT/"m23_property_pointer_code_xrefs.csv").open("w",encoding="utf-8",newline="") as f:
        field=["pointer_or_hash_cell","source_adrp_rva","source_second_instruction_rva",
               "operation","gap_instructions","address_resolution_grade",
               "semantic_consumer_proven","villager_id_to_object_proven"]
        w=csv.DictWriter(f,fieldnames=field);w.writeheader();w.writerows(matches)
    print(json.dumps({k:v for k,v in report.items() if k not in (
        "first_candidate_code_windows","raw_pointer_backrefs")},ensure_ascii=False,indent=2))
    return report

def selftest():
    word=0xf9400000 | (0x77<<10) | (8<<5) | 1
    assert word_mem_addr(word,0x3000,8)==("LDR_X_CELL",0x3000+0x77*8)
    assert word_mem_addr(word,0x3000,9) is None
    print("PASS AArch64 xref address decoding tests")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test: selftest()
    else: audit()

if __name__=="__main__":
    main()
