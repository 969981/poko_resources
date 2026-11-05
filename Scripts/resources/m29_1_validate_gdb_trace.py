#!/usr/bin/env python3
"""M29.1: validate user-collected GDB JSONL from the four M28 original
native 2.0.1 sites, *without* assigning a villager/species ID by inference.

Only four original PC offsets and raw registers are accepted. This tool
checks version/offset/base/PC consistency, builds a per-site LR-x30 caller
inventory and bounded trace counts. Co-occurrence does NOT demonstrate
that a KIDS caller is selecting a species graphic.

Run:
  python -m Scripts.resources.m29_1_validate_gdb_trace --self-test
  python -m Scripts.resources.m29_1_validate_gdb_trace --input m28_runtime_trace.jsonl --out /tmp/m29
"""
from __future__ import annotations
import argparse
import csv
import json
import tempfile
from collections import Counter,defaultdict
from pathlib import Path

SHA="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
EVENTS={
    "kids_property_descriptor":0xDD1B48,
    "kids_typehash_getter":0xDD1C30,
    "pokemon_dex_id_literal_consumer":0x1136AA4,
    "main_pokemon_list_literal_consumer":0x5FD168,
}
MAX=10000
SUMMARY_NAME="m29_1_runtime_source_trace_validation.json"
CALLER_NAME="m29_1_per_site_return_address_inventory.csv"

def h(v,what):
    try:
        if isinstance(v,bool):raise TypeError
        q=int(v,0) if isinstance(v,str) else int(v)
    except (ValueError,TypeError) as e:raise ValueError(f"Bad address {what}: {v!r}") from e
    if q<0 or q>0xFFFFFFFFFFFFFFFF:raise ValueError("Address outside unsigned 64-bit")
    return q

def check_header(x):
    if (x.get("record_type")!="M28_READ_ONLY_SOURCE_CONTEXT_HEADER"
        or x.get("original_version")!="2.0.1"
        or x.get("original_main_nso_sha256")!=SHA
        or x.get("runtime_id_bindings_verified")!=0):
        raise ValueError("Trace header is missing or contains a false provenance claim")
    base=h(x.get("main_base"),"runtime main base")
    if base==0 or base%4:raise ValueError("Runtime main base must be aligned and nonzero")
    limit=x.get("max_events")
    if not isinstance(limit,int) or not 1<=limit<=MAX:
        raise ValueError("Original trace sample limit invalid")
    original=x.get("source_offsets",{})
    if original!={k:hex(v) for k,v in EVENTS.items()}:
        raise ValueError("Trace does not use the original four source code offsets")
    return base,limit

def inspect(path):
    with Path(path).open(encoding="utf-8") as f:
        entries=[(n,json.loads(line)) for n,line in enumerate(f,1) if line.strip()]
    if not entries or len(entries)>MAX+1:
        raise ValueError("JSONL must contain one header and at most 10000 records")
    if entries[0][0]!=1:raise ValueError("Header must be first JSONL record")
    base,limit=check_header(entries[0][1])
    data=entries[1:]
    if len(data)>limit:raise ValueError("Trace exceeds configured limit")
    by_event=Counter()
    callers=Counter()
    descriptor=Counter()
    events=[]
    for lineno,r in data:
        event=r.get("event")
        if event not in EVENTS:raise ValueError(f"Unexpected instruction event line {lineno}")
        expected=EVENTS[event]
        pc=h(r.get("runtime_pc"),"runtime PC")
        if (pc!=base+expected or h(r.get("static_original_nso_offset"),"original PC")!=expected
            or h(r.get("actual_main_base_supplied_by_user"),"main base")!=base):
            raise ValueError(f"Original code PC/base inconsistent on line {lineno}")
        if any(r.get(field) not in (False,None) for field in (
            "game_species_id_verified","kids_source_oid_verified",
            "runtime_same_instance_link_verified")):
            raise ValueError("Trace falsely asserts an actual game ID mapping")
        lr=r.get("caller_return_lr_x30")
        lr_value=h(lr,"LR") if lr is not None else None
        regs=r.get("registers")
        if not isinstance(regs,dict):raise ValueError("Missing register provenance")
        for k,v in regs.items():
            if not k.startswith(("x","sp")) or (v is not None and not isinstance(v,str)):
                raise ValueError(f"Unexpected register field or representation: {k}")
            if v is not None:h(v,k)
        desc=r.get("descriptor_index_w3_if_applicable")
        if event=="kids_property_descriptor":
            if desc is not None and (not isinstance(desc,int) or not 0<=desc<=0xffffffff):
                raise ValueError("Invalid raw 32-bit property descriptor index")
            descriptor[str(desc) if desc is not None else "UNKNOWN"]+=1
        elif desc is not None:
            raise ValueError("Non-descriptor event claims a property index")
        by_event[event]+=1
        callers[(event,lr_value)]+=1
        events.append((event,lr_value))
    caller_data=[{
        "event_name":event,
        "original_function_pc":hex(EVENTS[event]),
        "sampled_original_LR":hex(lr-base) if lr is not None and lr>=base else "",
        "absolute_runtime_LR":hex(lr) if lr is not None else "",
        "observed_samples":count,
        "original_caller_function_boundary_verified":"",
        "original_id_to_kids_source_mapping_verified":"",
    } for (event,lr),count in sorted(callers.items(),key=lambda z:(z[0][0],-z[1],z[0][1] or 0))]
    summary={
        "input_filename":Path(path).name,
        "version":"2.0.1",
        "original_main_source_sha256_declared_in_trace":SHA,
        "runtime_main_base_reported_by_user":hex(base),
        "events_total":len(data),
        "events_per_site":dict(sorted(by_event.items())),
        "distinct_event_and_return_LR_combinations":len(callers),
        "raw_KIDS_property_descriptor_index_observations":dict(sorted(descriptor.items())),
        "same_session_with_both_identity_and_KIDS_events":(
            bool(by_event["kids_property_descriptor"] or by_event["kids_typehash_getter"])
            and bool(by_event["pokemon_dex_id_literal_consumer"]
                     or by_event["main_pokemon_list_literal_consumer"])),
        "same_session_is_same_runtime_instance_proof":False,
        "native_kids_source_oid_extracted_from_trace":False,
        "game_species_ID_to_KIDS_lookup_proven":False,
        "game_villager_ID_to_icon_proven":False,
        "static_code_Build_ID_verified_against_running_target":False,
        "next_proof":"Prove actual runtime type instance and extracted original KIDS key + Source OID together with a true game species/form ID from the same object; correlate with pinned original KIDS bytes and texture OID.",
        "warning":"A debugger event is a real GDB observation if supplied honestly, but a JSONL header cannot authenticate the running build or establish same-object dataflow. No game ID is inferred.",
    }
    return summary,caller_data

def run(inp,out):
    summary,callers=inspect(inp)
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    (out/SUMMARY_NAME).write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with (out/CALLER_NAME).open("w",newline="",encoding="utf-8") as f:
        cols=("event_name","original_function_pc","sampled_original_LR",
              "absolute_runtime_LR","observed_samples",
              "original_caller_function_boundary_verified",
              "original_id_to_kids_source_mapping_verified")
        w=csv.DictWriter(f,fieldnames=cols)
        w.writeheader();w.writerows(callers)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary

def selftest():
    base=0x7100000000
    head={"record_type":"M28_READ_ONLY_SOURCE_CONTEXT_HEADER","original_version":"2.0.1",
          "original_main_nso_sha256":SHA,"main_base":hex(base),"max_events":5,
          "source_offsets":{k:hex(v) for k,v in EVENTS.items()},
          "runtime_id_bindings_verified":0}
    sample={"event":"kids_property_descriptor",
            "static_original_nso_offset":hex(EVENTS["kids_property_descriptor"]),
            "runtime_pc":hex(base+EVENTS["kids_property_descriptor"]),
            "actual_main_base_supplied_by_user":hex(base),
            "caller_return_lr_x30":hex(base+0xABC),
            "registers":{"x3":"0x2","x19":"0x10","x21":"0x20","x22":"0x30"},
            "descriptor_index_w3_if_applicable":2,
            "game_species_id_verified":False,"kids_source_oid_verified":False,
            "runtime_same_instance_link_verified":False}
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/"mock.jsonl"
        p.write_text(json.dumps(head)+"\n"+json.dumps(sample)+"\n",encoding="utf-8")
        result,callers=inspect(p)
        assert result["events_total"]==1
        assert result["raw_KIDS_property_descriptor_index_observations"]=={"2":1}
        assert not result["game_species_ID_to_KIDS_lookup_proven"]
        assert len(callers)==1
        # Detect spoofed invalid game-ID proof, mismatched original PC, wrong
        # NSO version and inflated record count instead of silently accepting.
        for change in (
            {"game_species_id_verified":True},
            {"runtime_pc":hex(base+4+EVENTS["kids_property_descriptor"])},
            {"descriptor_index_w3_if_applicable":-1},
        ):
            altered={**sample,**change}
            p.write_text(json.dumps(head)+"\n"+json.dumps(altered)+"\n",encoding="utf-8")
            try:inspect(p)
            except ValueError:pass
            else:raise AssertionError(f"Accepted incorrect original runtime evidence {change}")
        other={**head,"original_main_nso_sha256":"wrong"}
        p.write_text(json.dumps(other)+"\n"+json.dumps(sample)+"\n",encoding="utf-8")
        try:inspect(p)
        except ValueError:pass
        else:raise AssertionError("Original build provenance mismatch accepted")
    print("PASS M29.1 JSONL runtime-source strictness, no ungrounded ID proofs")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",type=Path)
    p.add_argument("--out",type=Path,default=Path("m29_runtime_validation"))
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test:selftest()
    elif args.input:run(args.input,args.out)
    else:p.error("Provide --input <M28 JSONL> or --self-test")
if __name__=="__main__":main()
