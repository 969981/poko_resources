#!/usr/bin/env python3
"""M9.22: disambiguate the +0x38 call in constructor vs new inner object.

Original AArch64 2.0.1:
 - x22 = incoming x0 at D591A0 (source object; vcall +0x30 D591AC)
 - x23 = x0 at D591B0 (returned by the preceding BLR)
 - x23.vptr = 0x32FDFA0 at D591C8 (M9.12)
 - +0x38 indirect method at D59250 uses x22, NOT x23
 - x23 escapes to owner[x19+0x28] at D59274
The two register value definitions are source-distinct. They are NOT
necessarily unequal pointer values at runtime; do not infer their semantic
class identity or assert a descriptor callback was actually invoked.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m9_owner_local_callgraph import local_context
from Scripts.resources.m9_owner_object_escape import ldrx,is_blr_reg

SHA="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
PC={
    "incoming_owner_alias":0xD590FC,
    "source_x22_alias":0xD591A0,
    "source_vptr":0xD591A4,
    "source_method_slot0x30":0xD591A8,
    "source_call":0xD591AC,
    "created_x23_alias":0xD591B0,
    "created_vptr_write":0xD591C8,
    "source_this_arg":0xD59240,
    "source_obj_vptr":0xD59244,
    "source_method_slot0x38":0xD5924C,
    "source_method_blr":0xD59250,
    "created_owner_store":0xD59274,
}

REQUIRED={
    "incoming_owner_alias":("mov","x19, x3"),
    "source_x22_alias":("mov","x22, x0"),
    "source_vptr":("ldr","x8, [x0]"),
    "source_method_slot0x30":("ldr","x8, [x8, #0x30]"),
    "source_call":("blr","x8"),
    "created_x23_alias":("mov","x23, x0"),
    "created_vptr_write":("stp","x8, xzr, [x23]"),
    "source_this_arg":("mov","x0, x22"),
    "source_obj_vptr":("ldr","x8, [x22]"),
    "source_method_slot0x38":("ldr","x8, [x8, #0x38]"),
    "source_method_blr":("blr","x8"),
    "created_owner_store":("str","x23, [x19, #0x28]"),
}


def verify_words(instructions):
    bypc={x["pc"]:x for x in instructions}
    for name,(mnemonic,operand) in REQUIRED.items():
        pc=PC[name]
        row=bypc.get(pc)
        if not row or (row["mnemonic"],row["operands"])!=(mnemonic,operand):
            raise ValueError(f"Original raw register flow changed at {name}, {pc:#x}, {row}")
    writes={"x22":[],"x23":[]}
    for reg in writes:
        writes[reg]=[x for x in instructions
                     if reg in x["writes"] or ("w"+reg[1:]) in x["writes"]]
    for reg,start,end in (
        ("x22",PC["source_x22_alias"],PC["source_method_blr"]),
        ("x23",PC["created_x23_alias"],PC["created_owner_store"]),
    ):
        bad=[row for row in writes[reg] if start<row["pc"]<end]
        if bad:raise ValueError(f"Original {reg} clobbered: {bad}")
    return writes


def analyze(blob,previous):
    sha=hashlib.sha256(blob).hexdigest()
    if sha!=SHA or previous["report"]["source_exefs_sha256"]!=sha:
        raise ValueError("Incorrect original NSO or M9.21 input")
    expected=next(x for x in previous["methods"] if x["name"]=="constructor")
    if (expected["entry_pc"]!=0xd590e0 or expected["end_exclusive_pc"]!=0xd592b4 or
        not expected["complete_original_linear_instructions_verified"]):
        raise ValueError("M9.21 function boundaries changed")
    fmt,parts=get_sections(blob)
    if fmt!="NSO0":raise ValueError("Expected original NSO0")
    text=next(x for x in parts if x["name"]=="text")
    rows=local_context(text["data"],text["mem_offset"],0xd590e0,0xd592b4)
    writes=verify_words(rows)
    expected_by_pc={x["pc"]:x for x in expected["native_instructions"]}
    for name,pc in PC.items():
        old=expected_by_pc.get(pc)
        current=next(x for x in rows if x["pc"]==pc)
        if not old or old["word"]!=current["u32"]:
            raise ValueError(f"Previous byte-proven original M9.21 word mismatch {name}")
    report={
        "status":"M9_NATIVE_CONSTRUCTOR_SLOT38_RECEIVER_DISAMBIGUATED",
        "original_main_sha256":sha,
        "specific_virtual_slot0x38_call_pc":PC["source_method_blr"],
        "source_object_receiver_register":"x22",
        "x22_source_pc":PC["source_x22_alias"],
        "source_vptr_slot0x30_call_pc":PC["source_call"],
        "inner_created_object_register":"x23",
        "x23_source_pc":PC["created_x23_alias"],
        "inner_object_vptr_assignment_pc":PC["created_vptr_write"],
        "inner_object_owner_escape_pc":PC["created_owner_store"],
        "same_register_instance_at_slot38_and_created_inner_object":False,
        "runtime_source_and_created_object_pointer_inequality_verified":False,
        "specific_inner_class_slot38_callback_invocation_verified":False,
        "specific_callback_main_d59420_called_at_d59250_verified":False,
        "runtime_method_execution_observed":False,
        "KIDSOBJDB_native_getter_verified":False,
        "new_M7_foreign_keys":0,
        "warnings":[
            "The slot+0x38 BLR at D59250 dereferences x22, which was saved from original x0 before D591AC.",
            "The inner x23 object comes from x0 after D591AC; the native dataflow sources differ.",
            "Distinct register definitions do not exclude coincident pointer values at runtime.",
            "No evidence here shows inner x23.vptr+0x38 calls D59420; original callback slot membership alone does not prove dispatch.",
        ],
    }
    return {
        "report":report,
        "register_x22_source_and_overwrites":writes["x22"],
        "register_x23_source_and_overwrites":writes["x23"],
        "exact_original_instruction_evidence":[
            {"name":name,**next(x for x in rows if x["pc"]==pc)}
            for name,pc in PC.items()
        ],
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--main",type=Path,required=True)
    p.add_argument("--m9-21",type=Path,required=True)
    p.add_argument("--dest",type=Path,required=True)
    args=p.parse_args()
    r=analyze(args.main.read_bytes(),json.loads(args.m9_21.read_text(encoding="utf-8")))
    args.dest.mkdir(parents=True,exist_ok=True)
    (args.dest/"exefs_constructor_slot38_receiver_provenance.json").write_text(
        json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(r["report"],ensure_ascii=False,indent=2))


if __name__=="__main__":main()
