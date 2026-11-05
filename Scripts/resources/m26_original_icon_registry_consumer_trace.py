#!/usr/bin/env python3
"""M26: scoped NSO source-byte trace of icon registry type 0x9D1AFA46.

Anchors: 0xBE19C8/0xBE1A54 registrations; 0xDD1C30 type hash getter;
0x283883C original 0x34CBB458 property descriptor; 0x1136AA4
pokemon_dex_id; 0x5FD168 m_mainPokemonList.

No claim of a native game-ID consumer without source-byte code and a proven
same-instance KIDS source OID connection. Never infer from filename numbers.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m20_native_species_item_targets import (
    MAIN,SHA_MAIN,arm64_window,branch_target,decode_adrp,scan_direct_callers,u32,
)

ROOT=Path("UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M26")
HASH=0x34CBB458
CLASS=0x9D1AFA46
HASH_VA=0x283883C
CLASS_GETTER=0xDD1C30
GLOBAL_CELLS=(0x349C2D8,0x349C2E0,0x349C2E8)
DUMP_SITES=(
    ("type_registration_conditional_1",0xBE19C8,0x40,0x54),
    ("type_registration_conditional_2",0xBE1A54,0x48,0x60),
    ("return_type_hash",CLASS_GETTER,0x10,0x38),
    ("dex_field_observation",0x1136AA4,0x180,0x90),
    ("main_pokemon_list_label",0x5FD168,0x80,0x70),
)
RODATA_RADIUS=0x80

def mapped(parts,va,n):
    for p in parts:
        at=va-p["mem_offset"]
        if 0<=at and at+n<=len(p["data"]):
            return p["name"],p["data"][at:at+n]
    return "",None

def read_native_pointer(bits):
    return struct.unpack("<Q",bits)[0]

def pointer_sites(parts,aim,radius=0):
    matches=[]
    for section in parts:
        if section["name"] not in ("rodata","data"):continue
        b=section["data"];base=section["mem_offset"]
        for off in range(0,len(b)-7,8):
            val=struct.unpack_from("<Q",b,off)[0]
            if aim-radius<=val<=aim+radius:
                matches.append({"source_section":section["name"],
                                "original_cell_rva":hex(base+off),
                                "original_pointer_rva":hex(val),
                                "relative_delta":val-aim,
                                "unaligned_variants_not_searched":True})
    return matches

def page_refs(text,base,target,radius=0x80):
    """Only bounded ADRP + register-consistent ADD/LDR candidates.

    Such address construction does NOT guarantee a typed property consumer.
    Nonadjacent instructions may redefine the ADRP register; report as
    a search lead, never a proven effective address.
    """
    results=[]
    page=target&~4095
    for at in range(0,len(text)-4,4):
        pc=base+at
        d=decode_adrp(u32(text,at),pc)
        if d is None or d[0]!=page:continue
        base_reg=d[1]
        for steps in range(1,13):
            look=at+4*steps
            if look+4>len(text):break
            word=u32(text,look)
            op=None
            if (word&0xFF000000)==0x91000000 and ((word>>5)&31)==base_reg:
                sh=(word>>22)&3
                if sh in (0,1):
                    imm=((word>>10)&4095)<<(12 if sh==1 else 0)
                    op="ADD_ADDR"
            elif (word&0xFFC00000)==0xB9400000 and ((word>>5)&31)==base_reg:
                imm=((word>>10)&4095)*4;op="LDR_W"
            elif (word&0xFFC00000)==0xF9400000 and ((word>>5)&31)==base_reg:
                imm=((word>>10)&4095)*8;op="LDR_X"
            if op is None:continue
            value=page+imm
            if abs(value-target)>radius:continue
            results.append({
                "adrp_pc":hex(pc),"candidate_pc":hex(base+look),
                "target_nearby_rodata_va":hex(value),
                "signed_byte_difference_from_property_hash":value-target,
                "kind":op,"instructions_apart":steps,
                "grade":"ADJACENT_EFFECTIVE_ADDRESS_SYNTAX_ONLY" if steps==1
                    else "NONADJACENT_REGISTER_LIVENESS_UNVERIFIED",
                "property_consumer_identity_verified":False,
            })
    return results

def inspect():
    binary=MAIN.read_bytes()
    if hashlib.sha256(binary).hexdigest()!=SHA_MAIN:
        raise ValueError("M26 cannot operate on unpinned original NSO")
    kind,parts=get_sections(binary)
    if kind!="NSO0":raise ValueError("Expected original mapped NSO")
    code=next(p for p in parts if p["name"]=="text")
    text,base=code["data"],code["mem_offset"]
    typ,word=mapped(parts,HASH_VA,4)
    if typ!="rodata" or struct.unpack("<I",word)[0]!=HASH:
        raise ValueError("Native 0x34CBB458 property hash lost its original rodata byte location")
    # Byte-verify original exact MOVZ/MOVK/RET getter of KIDS class hash.
    expected=(0x529F48C0,0x72B3A340,0xD65F03C0)
    words=tuple(u32(text,CLASS_GETTER-base+4*i) for i in range(3))
    if words!=expected:
        raise ValueError(f"Original KIDS type getter instructions changed: {words!r}")
    # Two native constructor/registration callsites use exact class hash,
    # but this does not link them to the sprite table 0x34cbb458.
    type_pairs=[]
    for start,end in ((0xBE19C8,0xBE19D0),(0xBE1A54,0xBE1A5C)):
        low=u32(text,start-base);high=u32(text,end-base)
        if low!=0x529F48C1 or high!=0x72B3A341:
            raise ValueError("Original type initialization hash constants changed")
        branch=branch_target(end+4,u32(text,end+4-base))
        if branch!=(0x1FDC1E0,"B"):
            raise ValueError("Type initialization helper branch changed")
        type_pairs.append({"MOVZ_PC":hex(start),"MOVK_PC":hex(end),
                           "type_hash":hex(CLASS),
                           "tail_branch_target":hex(branch[0]),
                           "dynamic_class_instance_verified":False})
    global_info=[]
    for va in GLOBAL_CELLS:
        sec,ptr=mapped(parts,va,8)
        if sec!="data" or ptr is None:
            raise ValueError("Original static type registration pointer not in data")
        value=read_native_pointer(ptr)
        global_info.append({
            "global_pointer_cell_rva":hex(va),"initialized_u64_pointer_rva":hex(value),
            "target_original_section":mapped(parts,value,1)[0] or "UNMAPPED_OR_BSS",
            "pointer_in_dynamic_session_verified":False,
        })
    table_asm={name:arm64_window(text,base,addr,before,after)
               for name,addr,before,after in DUMP_SITES}
    base_seg=next(p for p in parts if p["name"]=="rodata")
    dump_start=HASH_VA-RODATA_RADIUS
    sec,raw=mapped(parts,dump_start,2*RODATA_RADIUS)
    if sec!="rodata":raise ValueError("Native descriptor neighborhood not mapped")
    descriptor=[]
    for i in range(0,len(raw),4):
        va=dump_start+i
        v=struct.unpack_from("<I",raw,i)[0]
        descriptor.append({"va":hex(va),"raw_u32":f"{v:08x}",
                           "is_target_property_hash":va==HASH_VA})
    descriptor_pointers=pointer_sites(parts,HASH_VA,0x100)
    typegetter_ptrs=pointer_sites(parts,CLASS_GETTER,0)
    property_addr_refs=page_refs(text,base,HASH_VA,0x100)
    callee_bl,callee_b=scan_direct_callers(text,base,CLASS_GETTER)
    # M25's two field-name consumers are separately traced in
    # m25_identity_caller_rodata_code.json. These are observed calling
    # different helpers and not the original class array descriptor.
    summary={
        "version":"2.0.1","original_nso_sha256":SHA_MAIN,
        "original_kids_array_type_hash":hex(CLASS),
        "original_kids_property_hash":hex(HASH),
        "verified_original_rodata_property_hash_va":hex(HASH_VA),
        "class_typehash_getter_verified":hex(CLASS_GETTER),
        "exact_typehash_getter_machine_words":[f"{x:08x}" for x in words],
        "type_registration_tailcall_sites":[x["MOVK_PC"] for x in type_pairs],
        "type_registration_original_global_cells":global_info,
        "original_typegetter_function_pointer_cells":len(typegetter_ptrs),
        "original_property_neighborhood_pointer_cells":len(descriptor_pointers),
        "bounded_property_neighborhood_adrp_candidates":len(property_addr_refs),
        "property_adrp_adjacent_candidate_count":sum(x["instructions_apart"]==1 for x in property_addr_refs),
        "original_direct_callers_of_typehash_getter":{
            "BL":len(callee_bl),"B":len(callee_b)},
        "gameplay_ID_to_icon_array_slot_verified":False,
        "runtime_object_instance_to_source_oid_verified":False,
        "game_native_villager_id_verified":False,
        "warning":"Unrelated native field name consumer/rodata hash and a typehash getter are not proof of the index expression or in-game species identity.",
    }
    ROOT.mkdir(parents=True,exist_ok=True)
    (ROOT/"m26_original_rodata_class_source_trace.json").write_text(
        json.dumps({
            "type_registration_bytes":type_pairs,
            "typehash_getter_pointer_references":typegetter_ptrs,
            "property_hash_rodata_neighbor_u32":descriptor,
            "property_neighborhood_aligned_pointer_references":descriptor_pointers[:120],
            "property_neighborhood_bounded_ADRP_candidates":property_addr_refs[:300],
            "original_candidate_code_windows":table_asm,
            "getter_BL_callers":[hex(x) for x in callee_bl[:100]],
            "getter_B_callers":[hex(x) for x in callee_b[:100]],
        },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (ROOT/"m26_original_class_consumer_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary

def selftest():
    assert CLASS==0x9D1AFA46 and HASH==0x34CBB458
    assert len(GLOBAL_CELLS)==3
    print("PASS original class hash and original rodata property anchor invariant")
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:selftest()
    else:inspect()
if __name__=="__main__":main()
