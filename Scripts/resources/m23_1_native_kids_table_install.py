#!/usr/bin/env python3
"""M23.1: verify source-byte AArch64 method-table installation at main+0xBB85AC.

Recovers a concrete original NSO dataflow:
global[0x34963B8] (0x32F0ED0) + 0x10 -> register x8
and stores x8 at [x1] after loading x1 from global[0x34963B0].
The method 0xCE854C then sits at offset +0x18 from that installed table
address. Nearby original instructions construct 0x79991E79, which matches
the *native object type hash*, not a verified species or villager ID.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m20_native_species_item_targets import (
    SHA_MAIN, MAIN, arm64_window, scan_direct_callers, branch_target,
)

OUT=Path("UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M23")
SOURCE=Path("UnPack/2.0.1/Resources/Pokemon/NativeCallers/M19/m19_texture_object_edge_summary.json")
PRIOR=OUT/"m23_original_property_consumer_triage.json"

GLOBALS={
    0x34963B0:"OBJECT_OWNER_POINTER_CELL",
    0x34963B8:"METHOD_TABLE_BASE_POINTER_CELL",
    0x34963C0:"RELATED_GLOBAL_POINTER_CELL",
}
METHOD_PTR_CELL=0x32F0EF8
REGISTERED_BASE=0x32F0EE0
METHOD=0xCE854C
TYPEHASH=0x79991E79
INSTALL=0xBB85CC
DISPATCH=0xBB85F4
CALL_TARGET=0x1FDC1E0
# PC and exact little-endian AArch64 instruction words from original 2.0.1.
WORDS={
    0xBB85AC:0xD00146E1, # adrp x1, 0x3496000
    0xBB85B0:0xD00146E8, # adrp x8, 0x3496000
    0xBB85B4:0xF941D821, # ldr x1, [x1,#0x3b0]
    0xBB85B8:0xF941DD08, # ldr x8, [x8,#0x3b8]
    0xBB85C8:0x91004108, # add x8,x8,#0x10
    0xBB85CC:0xA9002428, # stp x8,x9,[x1]
    0xBB85F4:0xD00146E2, # adrp x2,0x3496000
    0xBB85F8:0x5283CF21, # movz w1,#0x1e79
    0xBB85FC:0xF941D842, # ldr x2,[x2,#0x3b0]
    0xBB8600:0x72AF3321, # movk w1,#0x7999,lsl 16
    0xBB8604:0x14508EF7, # b 0x1fdc1e0
}

def mapped(parts,addr,length):
    for p in parts:
        offset=addr-p["mem_offset"]
        if 0<=offset and offset+length<=len(p["data"]):
            return p["name"],p["data"][offset:offset+length]
    return "",None

def inspect():
    src=MAIN.read_bytes()
    if hashlib.sha256(src).hexdigest()!=SHA_MAIN:
        raise ValueError("M23.1 original main hash mismatch")
    prev=json.loads(PRIOR.read_text(encoding="utf-8"))
    if prev["original_main_sha256"]!=SHA_MAIN or not prev["pointer_chain_bytes_verified"]:
        raise ValueError("M23 prerequisite pointer cell not verified")
    m19=json.loads(SOURCE.read_text(encoding="utf-8"))
    if m19.get("verified_distinct_object_edges")!=603:
        raise ValueError("M19 native byte-verified object baseline changed")
    kind,parts=get_sections(src)
    if kind!="NSO0":raise ValueError("Expected original NSO0")
    code=next(x for x in parts if x["name"]=="text")
    textbuf,base=code["data"],code["mem_offset"]
    for pc,expected in WORDS.items():
        if not 0<=pc-base<len(textbuf)-3:
            raise ValueError(f"Original instruction unmapped: {pc:x}")
        got=struct.unpack_from("<I",textbuf,pc-base)[0]
        if got!=expected:
            raise ValueError(f"Source instruction changed: {pc:x} {got:08x}!={expected:08x}")
    decoded=arm64_window(textbuf,base,INSTALL,0x30,0x48)
    asm={int(x["pc"],16):x["asm"] for x in decoded}
    required={
        0xBB85B4:("ldr x1,","[x1, #0x3b0]"),
        0xBB85B8:("ldr x8,","[x8, #0x3b8]"),
        0xBB85C8:("add x8, x8, #0x10",),
        INSTALL:("stp x8, x9, [x1]",),
    }
    for pc,frags in required.items():
        if not all(f in asm.get(pc,"") for f in frags):
            raise ValueError(f"Original AArch64 register-flow changed: {pc:x} {asm.get(pc)}")
    typ=arm64_window(textbuf,base,0xBB85FC,0x20,0x24)
    type_asm={int(x["pc"],16):x["asm"] for x in typ}
    if not ("mov w1, #0x1e79" in type_asm[0xBB85F8] and
            "movk w1, #0x7999, lsl #16" in type_asm[0xBB8600]):
        raise ValueError("Type-hash assembly changed")
    target,branch=branch_target(0xBB8604,WORDS[0xBB8604])
    if branch!="B" or target!=CALL_TARGET:raise ValueError("Typehash tail-call target changed")
    glob={}
    for addr,label in GLOBALS.items():
        sec,b=mapped(parts,addr,8)
        if sec!="data" or b is None:raise ValueError(f"Global cell unmapped {addr:x}")
        glob[label]={"virtual_address":f"0x{addr:x}","source_section":sec,
                     "initial_raw_pointer_value":f"0x{struct.unpack('<Q',b)[0]:x}"}
    owner_target=int(glob["OBJECT_OWNER_POINTER_CELL"]["initial_raw_pointer_value"],16)
    data_section=next(x for x in parts if x["name"]=="data")
    data_end=data_section["mem_offset"]+len(data_section["data"])
    original_nso_bss_size=struct.unpack_from("<I",src,0x3c)[0]
    bss_start=data_end
    bss_end=bss_start+original_nso_bss_size
    owner_in_original_bss=bss_start <= owner_target < bss_end
    if int(glob["METHOD_TABLE_BASE_POINTER_CELL"]["initial_raw_pointer_value"],16)!=REGISTERED_BASE-0x10:
        raise ValueError("Method table registration base differs")
    sec,b=mapped(parts,METHOD_PTR_CELL,8)
    if sec!="data" or not b or struct.unpack("<Q",b)[0]!=METHOD:
        raise ValueError("Registered method slot differs")
    # M19 exposes native typed-object hash 0x79991e79, not original species ID.
    first_path=Path("UnPack/2.0.1/Resources/Pokemon/NativeCallers/M19/m19_verified_texture_object_edges.csv")
    import csv
    with first_path.open(encoding="utf-8",newline="") as f:
        for row in csv.DictReader(f):
            if int(row["source_type_hash"],16)!=TYPEHASH or int(row["target_type_hash"],16)!=TYPEHASH:
                raise ValueError("M19 original KIDS typed source hashes contradict assembly")
    callers,b_tail=scan_direct_callers(textbuf,base,DISPATCH)
    out={
        "version":"2.0.1","main_sha256":SHA_MAIN,
        "original_install_instruction_verified":True,
        "original_install_pc":hex(INSTALL),
        "stp_destination_pointer_source_global":hex(0x34963B0),
        "stp_installed_table_pointer_source_global":hex(0x34963B8),
        "registered_method_table_pointer":hex(REGISTERED_BASE),
        "static_owner_address_from_initialized_global":hex(owner_target),
        "owner_in_original_nso_bss_range":owner_in_original_bss,
        "original_nso_data_end_rva":hex(data_end),
        "original_nso_bss_start_rva":hex(bss_start),
        "original_nso_bss_end_rva":hex(bss_end),
        "owner_pointer_liveness_at_runtime_verified":False,
        "registered_method_pointer_offset":hex(METHOD_PTR_CELL-REGISTERED_BASE),
        "original_code_pointer_at_vtable_offset":hex(METHOD),
        "original_data_global_cells":glob,
        "byte_verified_instruction_words":{f"0x{pc:x}":f"0x{w:08x}" for pc,w in WORDS.items()},
        "original_install_asm_window":decoded,
        "original_typehash_asm_window":typ,
        "nearby_type_hash_value":hex(TYPEHASH),
        "native_typed_KIDSOBJDB_source_target_hash_matches":True,
        "nearby_type_hash_tail_branch_target":hex(CALL_TARGET),
        "direct_bl_callers_to_typehash_site":[hex(x) for x in callers[:50]],
        "direct_b_callers_to_typehash_site":[hex(x) for x in b_tail[:50]],
        "typehash_site_callers_total":len(callers)+len(b_tail),
        "dynamic_pointer_global_owner_verified":False,
        "runtime_registration_execution_verified":False,
        "typehash_call_semantic_role_verified":False,
        "game_villager_id_to_native_object_verified":False,
        "native_species_id_verified":False,
        "next_proof":"Trace the initialization and dynamic pointed-to object of [main+0x34963b0], identify callsite and runtime owner of the installed method table, and recover the game villager ID field consumer.",
        "warning":"This verifies a static original pointer installation, not the dynamic class identity or species-ID semantics.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"m23_1_original_kids_table_install.json").write_text(
        json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in out.items() if not isinstance(v,(dict,list))},ensure_ascii=False,indent=2))
    return out

def selftest():
    assert METHOD_PTR_CELL-REGISTERED_BASE==0x18
    assert (0x1e79|(0x7999<<16))==TYPEHASH
    x=branch_target(0xBB8604,WORDS[0xBB8604])
    assert x==(CALL_TARGET,"B")
    print("PASS native method offset and type hash assembly tests")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test:selftest()
    else:inspect()

if __name__=="__main__":main()
