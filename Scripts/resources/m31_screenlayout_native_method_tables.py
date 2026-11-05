#!/usr/bin/env python3
"""M31: bounded original 2.0.1 NSO ScreenLayout method-table survey.

ScreenLayoutTexturePackSettings = native class hash 0x9D1AFA46,
method table main+0x33135C8, confirmed method +0x18=>main+0xDD1B48.

StaticScreenLayoutTextures = native class hash 0x79991E79,
method table main+0x32F0EE0, confirmed method +0x18=>main+0xCE854C.

Inspect at most 16 consecutive u64 entries, and DO NOT claim those
16 entries form a complete vtable. The registered pointer is confirmed;
other slots are CANDIDATES until referenced by real class consumers.
For code targets, decode a bounded original machine-code window and
count direct BL and B xrefs. Indirect BLR callers remain unobserved.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import Counter,defaultdict
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m20_native_species_item_targets import MAIN,SHA_MAIN,arm64_window,branch_target

OUT=Path("UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M31")
TABLES={
  "ScreenLayoutTexturePackSettings":{
    "type_hash":0x9D1AFA46,"table":0x33135C8,
    "confirmed_method_offset":0x18,"confirmed_method_pc":0xDD1B48,
  },
  "StaticScreenLayoutTextures":{
    "type_hash":0x79991E79,"table":0x32F0EE0,
    "confirmed_method_offset":0x18,"confirmed_method_pc":0xCE854C,
  },
}
MAX_SLOTS=16
WINDOW_BYTES=0x90

def mapped(parts,at,n):
    for p in parts:
        off=at-p["mem_offset"]
        if 0<=off and off+n<=len(p["data"]):
            return p["name"],bytes(p["data"][off:off+n])
    return None,None

def original_code_pc(parts,pc):
    kind,_=mapped(parts,pc,4)
    return kind=="text" and pc%4==0

def run():
    raw=MAIN.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SHA_MAIN:
        raise ValueError("Original ExeFS NSO differs from 2.0.1 pinned source")
    kind,parts=get_sections(raw)
    if kind!="NSO0":raise ValueError("Expected original NSO0")
    text=next(p for p in parts if p["name"]=="text")
    buf,base=text["data"],text["mem_offset"]
    tables={}
    targets=set()
    for name,known in TABLES.items():
        p=known["table"]
        section,data=mapped(parts,p,MAX_SLOTS*8)
        if section!="data":raise ValueError("Native table pointer not in original data")
        words=struct.unpack("<"+("Q"*MAX_SLOTS),data)
        if words[known["confirmed_method_offset"]//8]!=known["confirmed_method_pc"]:
            raise ValueError(f"Original {name} confirmed method+0x18 changed")
        rows=[]
        for n,addr in enumerate(words):
            off=n*8
            target_section,_=mapped(parts,addr,4) if addr else (None,None)
            code=original_code_pc(parts,addr)
            if code:targets.add(addr)
            rows.append({
                "possible_method_table_slot":n,
                "slot_offset":hex(off),
                "raw_original_u64_hex":f"{addr:016x}",
                "target_original_section":target_section,
                "pointer_within_source_text_and_aligned":code,
                "prior_verified_class_property_method":(
                    off==known["confirmed_method_offset"] and
                    addr==known["confirmed_method_pc"]),
                "method_role_confirmed_only_for_prior_verified_slot":(
                    off==known["confirmed_method_offset"] and
                    addr==known["confirmed_method_pc"]),
                "original_target_asm_first_bytes":(
                    arm64_window(buf,base,addr,0,WINDOW_BYTES)
                    if code else []),
                "direct_callers_BL_total":0,
                "direct_callers_B_total":0,
                "direct_caller_samples":[],
                "indirect_BLR_callers_exhaustively_traced":False,
                "native_key_to_object_runtime_lookup_proven":False,
                "game_species_ID_consumer_proven":False,
            })
        tables[name]={
            "original_registered_type_hash":f"{known['type_hash']:08x}",
            "original_method_table_base":hex(p),
            "bounded_inspection_slot_count":MAX_SLOTS,
            "bounded_inspection_is_complete_vtable_proof":False,
            "original_raw_u64_entries":rows,
        }
    incoming=defaultdict(list)
    # One linear sweep of original code for known target addresses.
    for off in range(0,len(buf)-3,4):
        pc=base+off
        word=struct.unpack_from("<I",buf,off)[0]
        br=branch_target(pc,word)
        if br and br[0] in targets:
            incoming[br[0]].append((pc,br[1]))
    for row in tables.values():
        for slot in row["original_raw_u64_entries"]:
            addr=int(slot["raw_original_u64_hex"],16)
            sites=incoming.get(addr,[])
            slot["direct_callers_BL_total"]=sum(kind=="BL" for _,kind in sites)
            slot["direct_callers_B_total"]=sum(kind=="B" for _,kind in sites)
            slot["direct_caller_samples"]=[
                {"pc":hex(pc),"branch_type":kind} for pc,kind in sites[:35]]
    summary={
        "game_version":"2.0.1",
        "original_main_sha256":SHA_MAIN,
        "registered_classes_examined":len(tables),
        "bounded_u64_slots_examined_per_class":MAX_SLOTS,
        "total_u64_cells_read":MAX_SLOTS*len(tables),
        "within_original_text_code_pointer_cells":sum(
            r["pointer_within_source_text_and_aligned"]
            for t in tables.values() for r in t["original_raw_u64_entries"]),
        "unique_original_text_targets":len(targets),
        "confirmed_property_method_slots":2,
        "combined_direct_BL_to_scanned_method_code_targets":sum(
            r["direct_callers_BL_total"]
            for t in tables.values() for r in t["original_raw_u64_entries"]),
        "combined_direct_B_to_scanned_method_code_targets":sum(
            r["direct_callers_B_total"]
            for t in tables.values() for r in t["original_raw_u64_entries"]),
        "entire_vtable_size_verified":False,
        "consumer_of_3543_texture_pack_key_array_proven":False,
        "runtime_entity_species_form_to_icon_key_proven":False,
        "native_game_ID_binding_proven":False,
        "caveat":"A pointer in the bounded table region and even code xrefs do not prove specific method semantics; direct BL/B excludes virtual BLR and PAC dispatch. Only +0x18 methods had prior KIDS property evidence.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"m31_original_screen_layout_method_table_bounded_scan.json").write_text(
        json.dumps({"summary":summary,"original_class_method_table_candidates":tables},
                   ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT/"m31_original_method_table_consumer_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary

def selftest():
    assert len(TABLES)==2
    assert MAX_SLOTS==16
    assert all(x["confirmed_method_offset"]==0x18 for x in TABLES.values())
    print("M31 original ScreenLayout bounded table source address tests passed")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:selftest()
    else:run()

if __name__=="__main__":main()
