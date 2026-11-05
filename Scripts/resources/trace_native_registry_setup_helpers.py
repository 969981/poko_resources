#!/usr/bin/env python3
"""M18: audit contiguous C6/C7/C8 setup-call helpers before classifying them.

Original ExeFS only. Does not infer registration from a numeric argument.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from Scripts.resources.trace_native_species_item_callers import get_sections

MAIN=Path("2.0.1/exefs/main")
OUT=Path("UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M18")
SHA="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
REGISTRY_VA=0x35618f0
TARGETS={
    "C7_setup_first_helper":(0xA70AD8,0x500),
    "C7_setup_second_helper":(0xA70BB4,0x500),
    "C6_C7_C8_first_call_sequence":(0xFE8A30,0x120),
    "C6_C7_C8_second_call_sequence":(0xFE8B90,0xF0),
    "C7_ID_accessor":(0x2F1F0,0x90),
}

def audit(blob):
    sha=hashlib.sha256(blob).hexdigest()
    if sha!=SHA:raise ValueError("Wrong original main SHA256 "+sha)
    fmt,parts=get_sections(blob)
    if fmt!="NSO0":raise ValueError("Expected original NSO0")
    text=next(p for p in parts if p["name"]=="text")
    base=text["mem_offset"];code=text["data"]
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    md=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    result={}
    for name,(addr,size) in TARGETS.items():
        off=addr-base
        if off<0 or off+size>len(code):raise ValueError("Unmapped requested method")
        dis=[{"pc":hex(ins.address),"asm":ins.mnemonic+" "+ins.op_str}
             for ins in md.disasm(code[off:off+size],addr)]
        # Return the code exactly. Classify the helper only after register
        # level x0 and w1 propagation, not by naming the caller.
        stores=[e for e in dis if e["asm"].split()[0] in ("str","strb","strh","stp","stur","sturb","sturh")]
        calls=[e for e in dis if e["asm"].startswith(("bl ","blr ","b "))]
        result[name]={"address":hex(addr),"disassembly":dis,
                      "stores":stores[:60],"calls":calls[:45],
                      "instructions_scanned":len(dis)}
    return {"status":"C7_CONTIGUOUS_HELPERS_DISASSEMBLED_UNVERIFIED_REGISTRY_INIT",
        "sha256_main":sha,"registry_global":hex(REGISTRY_VA),
        "exact_methods":result,
        "is_C7_class_constructor":False,
        "proves_C7_vtable_plus30_target":False,
        "proves_item_record_pointer_source":False,
        "warning":"C6/C7/C8 sequential calls also occur in bitsets, state-flags, object arrays. Establish real x0 object allocation and class-vtable assignment before claiming registry insertion."}

def selftest():
    try:audit(b"fake");raise AssertionError("Forged binary accepted")
    except ValueError:pass
    assert TARGETS["C7_setup_first_helper"][0]==0xA70AD8
    assert TARGETS["C7_setup_second_helper"][0]==0xA70BB4
    print("PASS original-source guarding and exact native helper targets")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--main",type=Path,default=MAIN)
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test:selftest();return
    r=audit(args.main.read_bytes())
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"registry_C7_setup_helpers_disassembly.json").write_text(
        json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    brief={k:r[k] for k in ("status","sha256_main","registry_global",
                        "is_C7_class_constructor",
                        "proves_C7_vtable_plus30_target",
                        "proves_item_record_pointer_source")}
    brief["targets"]={k:{"address":v["address"],"instructions_scanned":v["instructions_scanned"],
                         "stores":v["stores"][:15],"calls":v["calls"][:15],
                         "first_50":v["disassembly"][:50]} for k,v in r["exact_methods"].items()}
    (args.out/"registry_C7_setup_helpers_summary.json").write_text(
        json.dumps(brief,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(brief,ensure_ascii=False,indent=2)[:18000])
if __name__=="__main__":main()
