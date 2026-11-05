#!/usr/bin/env python3
"""M9.23: validate a real read-only GDB JSONL trace without inventing hits.

A verified callback-entry breakpoint plus the matching native inner-vptr
word and vtable+0x38 pointer is runtime *entry identity* evidence. This
still does not independently prove the entry was reached via an indirect
call from that vtable slot, which requires observing caller LR/BLR and
register dataflow. Input JSONL is supplied by the debugger user; report
is graded as an observed trace, not independently attested by CI.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path

SHA="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
OFFSETS={
    "owner_constructor_entry":0xd590e0,
    "owner_constructor_x23_vptr_write":0xd591c8,
    "owner_constructor_before_store":0xd59274,
    "owner_cleanup_entry":0xd58e34,
    "owner_slot0_blr":0xd58f10,
    "owner_constructor_sibling_entry":0xd592b4,
    "source_x22_slot38_blr":0xd59250,
    "actual_inner_descriptor_callback_entry":0xd59420,
}
VPTR=0x32fdfa0
SLOT38=0xd59420


def parse_hex(value):
    if value is None:return None
    if not isinstance(value,str):
        raise ValueError("GDB record address is not hexadecimal string")
    return int(value,16)


def validate(lines):
    sessions=[]
    events=[]
    for i,source in enumerate(lines,1):
        if not source.strip():continue
        record=json.loads(source)
        if record.get("kind")=="m9_23_capture_session":
            b=parse_hex(record.get("main_base"))
            if b is None or b<0x10000 or b%0x1000:
                raise ValueError("Invalid main base in session header")
            if record.get("expected_unrelocated_original_main_sha256")!=SHA:
                raise ValueError("Original ExeFS fingerprint mismatch")
            sessions.append((i,b))
            continue
        if record.get("kind")!="m9_23_native_runtime_breakpoint_hit":
            raise ValueError(f"Unknown M9.23 record kind at line {i}")
        if len(sessions)!=1:
            raise ValueError("Ambiguous/missing capture session")
        b=sessions[0][1]
        target=record.get("target")
        if target not in OFFSETS:
            raise ValueError("Unknown M9.23 breakpoint target")
        pc=parse_hex(record.get("breakpoint_pc"))
        off=parse_hex(record.get("main_offset"))
        if off!=OFFSETS[target] or pc is not None and pc!=b+off:
            raise ValueError("GDB breakpoint PC does not match known NSO offset")
        reg=record.get("registers")
        if not isinstance(reg,dict):
            raise ValueError("GDB record lacks registers")
        observed_vptr=parse_hex(record.get("object_x0_vptr"))
        observed_method=parse_hex(record.get("object_x0_vptr_plus_0x38_callback"))
        inner=(target=="actual_inner_descriptor_callback_entry" and
               observed_vptr==b+VPTR and observed_method==b+SLOT38)
        events.append({
            "source_line":i,"target":target,"pc":pc,"base":b,
            "x0":parse_hex(reg.get("x0")),
            "x3":parse_hex(reg.get("x3")),
            "x19":parse_hex(reg.get("x19")),
            "x23":parse_hex(reg.get("x23")),
            "owner_member_x3":parse_hex(record.get("owner_x3_plus_0x28")),
            "owner_member_x19":parse_hex(record.get("owner_x19_plus_0x28")),
            "hit_known_inner_descriptor_entry_with_matching_vptr_and_slot":inner,
            "candidate_blr_caller_at_link_register_minus4":bool(record.get("caller_instruction_is_arm64_blr")) if target=="actual_inner_descriptor_callback_entry" else False,
        })
    if len(sessions)!=1:
        raise ValueError("Require exactly one GDB capture session per JSONL")
    counts=Counter(x["target"] for x in events)
    hit=[r for r in events if r["hit_known_inner_descriptor_entry_with_matching_vptr_and_slot"]]
    with_blr=[r for r in hit if r["candidate_blr_caller_at_link_register_minus4"]]
    owner_stores=[r for r in events if r["target"]=="owner_constructor_before_store"
                  and r["x19"] is not None and r["x23"] is not None]
    matching_owners=[
        {"constructor_source_line":a["source_line"],
         "followup_line":b["source_line"],
         "owner":hex(a["x19"]),
         "prior_object":hex(a["x23"])}
        for a in owner_stores
        for b in events
        if b["source_line"]>a["source_line"] and b["target"] in
        ("owner_cleanup_entry","owner_constructor_sibling_entry")
        and b["x3"]==a["x19"]
    ]
    return {
        "status":"M9_USER_RUNTIME_TRACE_VALIDATED" if events else "M9_CAPTURE_HAS_NO_BREAKPOINT_HITS",
        "source":"USER_PROVIDED_GDB_JSONL_READ_ONLY_BREAKPOINTS",
        "original_exefs_sha256_expected":SHA,
        "main_base":hex(sessions[0][1]),
        "breakpoint_hits":len(events),
        "counts_by_site":dict(counts),
        "inner_descriptor_entry_hits_with_expected_vptr_and_slot_bytes":len(hit),
        "inner_descriptor_entry_hits_with_expected_vptr_and_blr_at_LR_minus4":len(with_blr),
        "matching_user_observed_constructor_owner_and_later_x3_event_pairs":matching_owners[:100],
        "evidence_grade":"USER_GDB_RUNTIME_ENTRY_WITH_NATIVE_VPTR_BYTE_MATCH" if hit
                     else "NO_SPECIFIC_INNER_CALLBACK_RUNTIME_ENTRY_EVIDENCE",
        "specific_vptr_slot0x38_indirect_call_path_proven":False,
        "M7_script_text_foreign_keys_proven":0,
        "limitations":[
            "A missing hit is not proof the callback is unreachable; code path and breakpoint coverage matter.",
            "The x3 owner correlation does not guarantee the lifetime has not ended or the owner memory address has not been reused.",
            "Entry breakpoint + correct receiver vptr proves an observed entry identity, not that the caller used vptr+0x38.",
            "A BLR word at LR-4 gives a candidate indirect caller address but still requires tracing the object-vptr slot load in that caller.",
            "Runtime dump remains user-provided, not independently attested by CI.",
        ],
    }


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    result=validate(args.input.read_text(encoding="utf-8").splitlines())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
