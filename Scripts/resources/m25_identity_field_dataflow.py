#!/usr/bin/env python3
"""M25: byte-check two native Pokemon identity anchors and their helper callees.

Targets exactly pokemon_dex_id (main+0x1136AA4) and m_mainPokemonList
(main+0x5FD168). Source/caller identity is not inferred from string name.
No path here proves a game species ID -> KIDS Source OID.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from pathlib import Path
from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m20_native_species_item_targets import (
    MAIN,SHA_MAIN,arm64_window,branch_target,scan_direct_callers,u32,
)

ROOT=Path("UnPack/2.0.1/Resources")
PRIOR=ROOT/"Villagers/Native_2.0.1/M24/m24_1_identity_anchors_summary.json"
OUT=ROOT/"Villagers/Native_2.0.1/M25"
ANCHORS={
    "pokemon_dex_id":{"site":0x1136AA4,"expected_helper":0x27470E0,"helper_call":0x1136AB0},
    "m_mainPokemonList":{"site":0x5FD168,"expected_helper":0x5A71E0,"helper_call":0x5FD174},
}
HELPERS=(0x27470E0,0x5A71E0,0x113AF80)
WANTED_INSTRUCTION_SITES=(
    0x1136A60,  # LDRH ID-like candidate x22+8
    0x1136A68,  # bound #1f3
    0x1136AA4, 0x1136AAC,0x1136AB0,
    0x5FD128,   # LDRB x19+26
    0x5FD168,0x5FD16C,0x5FD170,0x5FD174
)

def original_sections():
    b=MAIN.read_bytes()
    if hashlib.sha256(b).hexdigest()!=SHA_MAIN:
        raise ValueError("Original Pokopia NSO SHA mismatch")
    kind,s=get_sections(b)
    if kind!="NSO0":raise ValueError("Not original NSO")
    c=next(v for v in s if v["name"]=="text")
    return s,c["data"],c["mem_offset"]

def run():
    old=json.loads(PRIOR.read_text(encoding="utf-8"))
    if (old.get("original_main_sha256")!=SHA_MAIN or
            old["primary_identity_anchors"]!=[
                {"name":"RegisterPokemonNum","sites":["0x1135b44"]},
                {"name":"m_mainPokemonList","sites":["0x5fd168"]},
                {"name":"pokemon_dex_id","sites":["0x1136aa4"]}]):
        raise ValueError("Original M24.1 identity anchor baseline changed")
    sections,code,base=original_sections()
    read={}
    for name,src in ANCHORS.items():
        site=src["site"];call=src["helper_call"];target=src["expected_helper"]
        near=arm64_window(code,base,call,0x160,0xb0)
        this={int(x["pc"],16):x for x in near}
        if site not in this or call not in this:
            raise ValueError(f"Original identity anchor disappeared: {name}")
        decoded=branch_target(call,u32(code,call-base))
        if decoded!=(target,"BL"):
            raise ValueError(f"Original helper target changed: {name} {decoded}")
        # Only local syntax claims; the underlying record's semantic type is not
        # proven to be texture, species, villager, or KIDS OID.
        relevant=[]
        for pc in WANTED_INSTRUCTION_SITES:
            if pc in this:
                relevant.append({"pc":hex(pc),"original_word":this[pc]["word"],
                                 "original_asm":this[pc]["asm"]})
        read[name]={
            "original_literal_anchor":hex(site),
            "original_helper_call":hex(call),
            "original_helper_target":hex(target),
            "direct_call_verified_by_original_instruction":True,
            "selected_original_instructions":relevant,
            "source_asm_window":near,
            "upstream_record_runtime_semantics_proven":False,
            "native_KIDS_object_id_binding_proven":False,
        }

    helper_code={}
    for addr in HELPERS:
        bl,b=scan_direct_callers(code,base,addr)
        helper_code[hex(addr)]={
            "original_function_address":hex(addr),
            "direct_BL_count":len(bl),
            "direct_B_count":len(b),
            "BL_site_first":[hex(p) for p in bl[:70]],
            "B_site_first":[hex(p) for p in b[:70]],
            "original_disassembly":arm64_window(code,base,addr,0x10,0xD0),
            "function_role_verified":False,
        }
    # The two identity anchors are in separated code regions. Distinct helper
    # callees means the strings do not by themselves establish a shared ID path.
    report={
        "version":"2.0.1",
        "original_main_sha256":SHA_MAIN,
        "verified_anchor_count":len(read),
        "pokemon_dex_id_rodata_reference_site":hex(ANCHORS["pokemon_dex_id"]["site"]),
        "pokemon_dex_id_helper_call_verified":hex(ANCHORS["pokemon_dex_id"]["helper_call"]),
        "pokemon_dex_id_helper":hex(ANCHORS["pokemon_dex_id"]["expected_helper"]),
        "mainPokemonList_rodata_reference_site":hex(ANCHORS["m_mainPokemonList"]["site"]),
        "mainPokemonList_helper_call_verified":hex(ANCHORS["m_mainPokemonList"]["helper_call"]),
        "mainPokemonList_helper":hex(ANCHORS["m_mainPokemonList"]["expected_helper"]),
        "shared_helper_between_two_anchors":False,
        "native_species_id_to_KIDS_source_OID_verified":False,
        "runtime_villager_id_link_verified":False,
        "new_9_ambiguous_portraits_resolved":0,
        "new_79_missing_portraits_resolved":0,
        "next_required_proof":"Recover actual record/ID in x21 at main+0x1136AB0 and x19/x21 at main+0x5FD174, then show a same-instance native KIDS source OID property read.",
        "warning":"Native helper calls and nearby ID-like offsets are code-flow evidence, NOT a species-ID mapping.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"m25_identity_caller_rodata_code.json").write_text(
        json.dumps({"anchor_records":read,"helpers":helper_code},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT/"m25_identity_caller_summary.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return report

def self_test():
    assert len(ANCHORS)==2
    assert len(set(x["expected_helper"] for x in ANCHORS.values()))==2
    assert branch_target(0x1000,0x94000400)==(0x2000,"BL")
    print("PASS original identity helper direct branch tests")

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test",action="store_true")
    args=parser.parse_args()
    if args.self_test:self_test()
    else:run()

if __name__=="__main__":main()
