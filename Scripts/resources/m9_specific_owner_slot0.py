#!/usr/bin/env python3
"""M9.17: prove a concrete indirect call through the *specific* owner field.

Constructor:
  x19 <- x3 @ 0xD590FC, object <- x0 @ 0xD591B0, vptr store,
  owner[0x28] <- x23 @ 0xD59274.
Local cleanup path:
  x19 <- x3 @ 0xD58E54, x23 <- owner[0x28] @ 0xD58EB8,
  x8 <- [x23] -> x8 <- [x8,#0] -> BLR x8 @ 0xD58F10,
  owner[0x28] <- NULL @ 0xD58F28.

This is a byte-proven static *method dispatch pattern* for a member loaded
from the same offset and argument position; no proof both functions
receive the same runtime owner instance. When that member retains
vptr 0x32FDFA0, the slot-0 callback is the original pointer 0xD593CC.
Do not confuse the slot-0 call with slot-0x38 descriptor enumeration.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m9_verified_vptr_assignments import read_pointer
from Scripts.resources.m9_owner_local_callgraph import local_context

SHA="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
CONSTRUCTOR_OWNER_ARG=0xD590FC
CONSTRUCTOR_OBJECT_SAVE=0xD591B0
CONSTRUCTOR_OWNER_STORE=0xD59274
RELEASER_OWNER_ARG=0xD58E54
RELEASER_OBJECT_LOAD=0xD58EB8
RELEASER_VPTR_LOAD=0xD58F04
RELEASER_PASS_THIS=0xD58F08
RELEASER_VFUNC_LOAD=0xD58F0C
RELEASER_BLR=0xD58F10
RELEASER_CLEAR=0xD58F28
KNOWN_VPTR=0x32FDFA0
EXPECTED_VFUNC0=0xD593CC
KNOWN_DESCRIPTOR=0xD59420


def instructions_match(ins,required):
    bypc={x["pc"]:x for x in ins}
    for pc,(m,ops) in required.items():
        if pc not in bypc or bypc[pc]["mnemonic"]!=m or bypc[pc]["operands"]!=ops:
            raise ValueError(f"Original ARM64 bytes mismatch at {pc:#x}: {bypc.get(pc)}")
    return bypc


def assert_callee_saved_not_modified(ins,reg,start,end):
    """Capstone may mark CMP's source as written; it is actually flag-only."""
    write_like={"mov","ldr","ldur","ldp","add","sub","and","orr","eor","adr","adrp",
                "csel","csinc","mul","madd","sxtw","uxtw","ldrb","ldrh","ldrsh","ldrsw",
                "ldaxr","ldxr","ldar","ldaxp","ldxp"}
    bad=[x for x in ins if start<x["pc"]<end
         and x["mnemonic"] in write_like
         and reg in x["writes"]]
    if bad:
        raise ValueError(f"Native {reg} clobbered between provenance edges: {bad}")
    return True


def verify(main,prior):
    sha=hashlib.sha256(main).hexdigest()
    if sha!=SHA or prior["report"]["native_sha256"]!=sha:
        raise ValueError("Original NSO or M9.16 evidence mismatch")
    if prior["report"]["verified_member_store_pc"]!=CONSTRUCTOR_OWNER_STORE:
        raise ValueError("Original owner field store evidence changed")
    kind,sections=get_sections(main)
    if kind!="NSO0":raise ValueError("NSO0 input required")
    text=next(x for x in sections if x["name"]=="text")
    data=next(x for x in sections if x["name"]=="data")
    base,code=text["mem_offset"],text["data"]
    c=local_context(code,base,CONSTRUCTOR_OWNER_ARG,CONSTRUCTOR_OWNER_STORE+4)
    d=local_context(code,base,RELEASER_OWNER_ARG,RELEASER_CLEAR+4)
    instructions_match(c,{
        CONSTRUCTOR_OWNER_ARG:("mov","x19, x3"),
        CONSTRUCTOR_OBJECT_SAVE:("mov","x23, x0"),
        CONSTRUCTOR_OWNER_STORE:("str","x23, [x19, #0x28]"),
    })
    instructions_match(d,{
        RELEASER_OWNER_ARG:("mov","x19, x3"),
        RELEASER_OBJECT_LOAD:("ldr","x23, [x19, #0x28]"),
        RELEASER_VPTR_LOAD:("ldr","x8, [x23]"),
        RELEASER_PASS_THIS:("mov","x0, x23"),
        RELEASER_VFUNC_LOAD:("ldr","x8, [x8]"),
        RELEASER_BLR:("blr","x8"),
        RELEASER_CLEAR:("str","xzr, [x19, #0x28]"),
    })
    assert_callee_saved_not_modified(c,"x19",CONSTRUCTOR_OWNER_ARG,CONSTRUCTOR_OWNER_STORE)
    assert_callee_saved_not_modified(d,"x19",RELEASER_OWNER_ARG,RELEASER_CLEAR)
    assert_callee_saved_not_modified(d,"x23",RELEASER_OBJECT_LOAD,RELEASER_BLR)
    # Capstone-revalidated object vptr proof from M9.12, via M9.16 local report.
    present=[p for p in prior["original_disassembly_context"]
             if p["pc"] in (CONSTRUCTOR_OWNER_ARG,CONSTRUCTOR_OWNER_STORE,
                             RELEASER_OWNER_ARG,RELEASER_OBJECT_LOAD)]
    if len(present)!=4:
        raise ValueError("M9.16 local byte context missing expected evidence")
    raw_slot0=read_pointer(data,KNOWN_VPTR)
    raw_slot38=read_pointer(data,KNOWN_VPTR+0x38)
    if raw_slot0!=EXPECTED_VFUNC0 or raw_slot38!=KNOWN_DESCRIPTOR:
        raise ValueError("Original vtable callback slots changed")
    target_body=local_context(code,base,EXPECTED_VFUNC0,KNOWN_DESCRIPTOR)
    result={
        "report":{
            "status":"M9_NATIVE_OWNER_MEMBER_VIRTUAL_SLOT0_CALLSITE_PROVEN",
            "original_exefs_sha256":sha,
            "constructor_argument_x3_to_owner_x19_verified":True,
            "consumer_argument_x3_to_owner_x19_verified":True,
            "same_member_offset_write_and_read_verified":True,
            "callee_saved_x19_x23_provenance_checked":True,
            "actual_indirect_callsite_pc_verified":RELEASER_BLR,
            "indirect_slot_offset":0,
            "original_vptr":KNOWN_VPTR,
            "resolved_vtable_slot0_target_if_object_vptr_unmodified":raw_slot0,
            "separate_descriptor_slot0x38_callback":raw_slot38,
            "same_runtime_owner_instance_verified":False,
            "specific_runtime_method_invocation_observed":False,
            "specific_descriptor_slot0x38_dispatch_verified":False,
            "KIDSOBJDB_property_getter_verified":False,
            "new_script_scene_quest_building_M7_text_FKs":0,
            "limitations":[
                "Two native functions use the same x3 argument position and object+0x28 member, not a proven same runtime owner instance.",
                "Virtual slot zero is not the descriptor callback at offset 0x38.",
                "The actual target of BLR requires verifying the instance vptr at call time; native slot value is conditional on no vptr replacement.",
                "No dialogue/quest/building text field or getter is established.",
            ]},
        "constructor_native_evidence":[x for x in c if x["pc"] in
            (CONSTRUCTOR_OWNER_ARG,CONSTRUCTOR_OBJECT_SAVE,0xD591C8,CONSTRUCTOR_OWNER_STORE)],
        "consumer_native_evidence":[x for x in d if x["pc"] in
            (RELEASER_OWNER_ARG,RELEASER_OBJECT_LOAD,RELEASER_VPTR_LOAD,
             RELEASER_PASS_THIS,RELEASER_VFUNC_LOAD,RELEASER_BLR,RELEASER_CLEAR)],
        "slot0_target_function_instructions":target_body,
    }
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--main",type=Path,required=True)
    p.add_argument("--m9-16",type=Path,required=True)
    p.add_argument("--dest",type=Path,required=True)
    a=p.parse_args()
    result=verify(a.main.read_bytes(),json.loads(a.m9_16.read_text(encoding="utf-8")))
    a.dest.mkdir(parents=True,exist_ok=True)
    (a.dest/"exefs_owner_specific_virtual_slot0.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result["report"],ensure_ascii=False,indent=2))


if __name__=="__main__":main()
