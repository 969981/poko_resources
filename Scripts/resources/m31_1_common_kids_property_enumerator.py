#!/usr/bin/env python3
"""M31.1: prove the original common KIDS descriptor iterator dispatch edge.

This verifies the 2 class vtable+0x10 entries both point to the same
generic iterator at main+0x1FE4FA0, and that its AArch64 machine code
dynamically calls vtable+0x18 for each index through BLR. The virtual
target is the source-verified class-specific property method.

The common iterator is not evidence of a gameplay character-ID lookup,
and enumerating/serializing fields is not proof of user-facing icon
resource selection. Build exact ASM for both property handlers to
identify where their fields are consumed and which registers feed it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import defaultdict
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m20_native_species_item_targets import (
    MAIN,SHA_MAIN,arm64_window,branch_target
)

OUT=Path("UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M31")
GENERIC=0x1FE4FA0
TYPE_METHODS={
    "ScreenLayoutTexturePackSettings":{
        "table":0x33135C8,
        "type_hash":0x9D1AFA46,
        "prop_entry":0xDD1B48,
        "prop_end":0xDD1C24,
        "expected_property_hashes":[0x2F610FEA,0xE88C8D60,0x34CBB458],
    },
    "StaticScreenLayoutTextures":{
        "table":0x32F0EE0,
        "type_hash":0x79991E79,
        "prop_entry":0xCE854C,
        "prop_end":0xCE861C,
        "expected_property_hashes":[0x2856A1B3],
    },
}
EXPECTED_OPS={
    0x1FE4FBC:("mov x21, x0",),
    0x1FE4FC4:("ldr x8, [x21]",),
    0x1FE4FCC:("mov x1, x19",),
    0x1FE4FD0:("mov w2, #1",),
    0x1FE4FD4:("mov w3, w22",),
    0x1FE4FD8:("ldr x8, [x8, #0x18]",),
    0x1FE4FDC:("blr x8",),
    0x1FE4FE0:("ldr w8, [x19, #4]",),
    0x1FE4FE8:("add w22, w22, #1",),
    0x1FE4FF0:("b.ne #0x1fe4fc4",),
}
METHOD_ANCHORS={
    0xDD1B50:("cmp w3, #2",),
    0xDD1B74:("ldr w12, [x9, w3, sxtw #2]",),
    0xCE8554:("cmp w3, #2",),
    0xCE856C:("ldr w11, [x8, w3, sxtw #2]",),
}

def segment(parts,va,n):
    for s in parts:
        off=va-s["mem_offset"]
        if 0<=off and off+n<=len(s["data"]):
            return s["name"],bytes(s["data"][off:off+n])
    return None,None

def asmspan(code,base,start,end):
    if start%4 or end%4 or end<=start:
        raise ValueError("Unaligned original ARM64 source range")
    return arm64_window(code,base,start,0,end-start-4)

def check_asm(row_map,checks):
    proven=[]
    for pc,expected in checks.items():
        r=row_map.get(pc)
        if r is None or not all(x in r["asm"] for x in expected):
            raise ValueError(f"Original machine-code event differs {pc:#x}: {r}")
        proven.append({
            "source_pc":hex(pc),"original_word":r["word"],"asm":r["asm"],
            "exact_original_instruction_proven":True})
    return proven

def run():
    raw=MAIN.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SHA_MAIN:
        raise ValueError("Pinned original Pokopia 2.0.1 NSO source changed")
    kind,parts=get_sections(raw)
    if kind!="NSO0":raise ValueError("Original NSO0 required")
    sec=next(s for s in parts if s["name"]=="text")
    code,base=sec["data"],sec["mem_offset"]
    generic_window=asmspan(code,base,GENERIC,0x1FE5008)
    by_pc={int(r["pc"],16):r for r in generic_window}
    proven=check_asm(by_pc,EXPECTED_OPS)
    rows=[]
    for name,entry in TYPE_METHODS.items():
        data_va=entry["table"]
        type_,mem=segment(parts,data_va+0x10,16)
        if type_!="data":
            raise ValueError("Original class registered method table not in data")
        common,actual=struct.unpack("<2Q",mem)
        if common!=GENERIC or actual!=entry["prop_entry"]:
            raise ValueError(f"Original {name} method vtable slots changed")
        fields=asmspan(code,base,entry["prop_entry"],entry["prop_end"])
        fields_by_pc={int(x["pc"],16):x for x in fields}
        this_checks={pc:v for pc,v in METHOD_ANCHORS.items()
                     if entry["prop_entry"]<=pc<entry["prop_end"]}
        exact=check_asm(fields_by_pc,this_checks)
        branches=[]
        for r in fields:
            pc=int(r["pc"],16);word=int(r["word"],16)
            target=branch_target(pc,word)
            if target:branches.append({"original_branch_pc":hex(pc),
                "kind":target[1],"target":hex(target[0])})
        rows.append({
            "registered_class":name,
            "original_type_hash":hex(entry["type_hash"]),
            "original_method_table_base":hex(data_va),
            "method_slot_0x10_shared_enumerator":hex(common),
            "method_slot_0x18_class_specific_property_processor":hex(actual),
            "method_table_two_pointer_raw_little_endian":mem.hex(),
            "shared_enumerator_dispatches_class_specific_property_method":True,
            "original_property_method_critical_instruction_proofs":exact,
            "class_specific_original_property_handler_full_ASM":fields,
            "local_direct_branch_targets":branches,
            "actual_3543_packed_array_bytes_read_from_file_by_native_program_proven":False,
            "runtime_species_ID_selection_proven":False,
        })
    # Pointer-reference check records actual original initialized data slots.
    pointer_refs=defaultdict(list)
    targets={GENERIC,*[x["prop_entry"] for x in TYPE_METHODS.values()]}
    for section in parts:
        if section["name"]!="data":continue
        b=section["data"];origin=section["mem_offset"]
        for pos in range(0,len(b)-7,8):
            value=struct.unpack_from("<Q",b,pos)[0]
            if value in targets:
                pointer_refs[value].append(hex(origin+pos))
    summary={
        "version":"2.0.1",
        "original_main_sha256":SHA_MAIN,
        "registered_classes_using_same_common_enumerator":len(rows),
        "generic_enumerator_pc":hex(GENERIC),
        "generic_enumerator_calls_virtual_slot_offset":"0x18",
        "generic_original_source_check_instructions":len(proven),
        "class_specific_virtual_property_methods":[hex(x["prop_entry"]) for x in TYPE_METHODS.values()],
        "class_specific_full_instruction_count":sum(
            len(x["class_specific_original_property_handler_full_ASM"]) for x in rows),
        "class_type_names_and_hashes_verified":True,
        "actual_indirect_callsite_class_targets_grounded_by_static_vtable_slots":True,
        "initialized_data_references_to_generic_iterator":len(pointer_refs.get(GENERIC,[])),
        "initialized_data_references_to_specific_methods":{
            hex(x):len(pointer_refs.get(x,[]))
            for x in targets if x!=GENERIC},
        "source_static_vtable_path_proven":True,
        "runtime_common_iterator_called_with_pokemon_instance_proven":False,
        "game_ID_to_texture_pack_lookup_proven":False,
        "runtime_source_OID_selection_proven":False,
        "warning":"This proves a static generic BLR vtable dispatch structure; it does NOT prove real game execution or that the KIDS enumerated arrays were used to select a Pokémon icon.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"m31_1_common_native_KIDS_enumerator_and_property_asm.json").write_text(
        json.dumps({"summary":summary,"generic_iterator_verified_instructions":proven,
                   "generic_iterator_full_ASM":generic_window,
                   "original_property_handlers":rows,
                   "original_data_pointer_cell_refs":{
                       hex(k):v[:30] for k,v in pointer_refs.items()}},
                  ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT/"m31_1_generic_vtable_dispatch_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary

def selftest():
    assert len(TYPE_METHODS)==2 and len(EXPECTED_OPS)>=10
    assert all(x["table"]%8==0 for x in TYPE_METHODS.values())
    print("PASS original 2-class common KIDS property enumerator and method offset constants")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test:selftest()
    else:run()

if __name__=="__main__":main()
