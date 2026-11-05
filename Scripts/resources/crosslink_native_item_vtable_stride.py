#!/usr/bin/env python3
"""M17: crosslink native vtable +0x30 methods with straight-line ID*68 code.

Uses precise executable pointer arrays from the original NSO and the M13
68-byte arithmetic search. Does not prove the +0xC7 registry class owns
any matching vtable unless registration constructor/instance is recovered.
"""
from __future__ import annotations
import argparse,hashlib,json
from bisect import bisect_left,bisect_right
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.trace_native_item_registry_vtables import raw_pointers
from Scripts.resources.trace_native_item_stride68 import scan,straightline_constant_live

SHA_MAIN="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
SHA_ITEM="2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f"
MAIN=Path("2.0.1/exefs/main")
ITEM=Path("UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin")
OUT=Path("UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M17")

def real_stride_candidates(code,base):
    consts,fields,muls,counts=scan(code,base)
    out=[]
    for m in muls:
        evidence=[]
        for regno in (m["rn"],m["rm"]):
            width="w" if m["kind"]=="mul_long" else m["width"]
            arr=consts.get((68,regno,width),[])
            i=bisect_left(arr,m["pc"])-1
            if i<0:continue
            before=arr[i]
            if 0<m["pc"]-before<=0x100 and straightline_constant_live(
                    code,base,before,m["pc"],regno):
                evidence.append({"movz_pc":hex(before),"register":width+str(regno)})
        if evidence:
            out.append({"pc":m["pc"],"op":m["op"],"dest":"x"+str(m["dest"]),
                        "base_register":"x"+str(m["ra"]),
                        "constant_68":evidence,
                        "status":"REGISTER_LOCAL_ARITHMETIC_ONLY"})
    return out

def starts(pointers):
    out=[]
    for addr in pointers:
        if addr-8 in pointers:continue
        if any(addr+8*i not in pointers for i in range(7)):continue
        out.append((addr,pointers[addr+0x30]))
    return out

def inspect(code,base,pointer_cells,strides):
    s=starts(pointer_cells)
    steps=sorted(strides,key=lambda x:x["pc"])
    pcs=[x["pc"] for x in steps]
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    md=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    result=[]
    for vtable,func in s:
        hi=func+0x160
        lo=bisect_left(pcs,func)
        end=bisect_right(pcs,hi)
        if lo==end:continue
        neighbors=steps[lo:end]
        start=func-base
        if start<0 or start>=len(code):continue
        asm=[{"pc":hex(x.address),"asm":x.mnemonic+" "+x.op_str}
             for x in md.disasm(code[start:min(len(code),start+0x1c0)],func)]
        field_loads=[x for x in asm if
            ("#0x26" in x["asm"] or "#0x3a" in x["asm"] or
             "#0x22" in x["asm"] or "#0x39" in x["asm"])]
        matches=[
            {"pc":hex(x["pc"]),"op":x["op"],
             "constant_68":x["constant_68"],
             "base_register":x["base_register"]}
            for x in neighbors
        ]
        result.append({"vtable_address_point":hex(vtable),
            "vtable_plus30_slot_va":hex(vtable+0x30),
            "virtual_method_pc":hex(func),"stride_arithmetic":matches,
            "field_loads_in_window":field_loads[:20],
            "method_disassembly":asm,
            "status":"METHOD_MATCH_UNBOUND_TO_0XC7_REGISTRY"})
    result.sort(key=lambda x:(-len(x["stride_arithmetic"]),
         -len(x["field_loads_in_window"]),int(x["virtual_method_pc"],16)))
    return result,len(s)

def audit(main,item):
    a=hashlib.sha256(main).hexdigest()
    b=hashlib.sha256(item).hexdigest()
    if a!=SHA_MAIN or b!=SHA_ITEM or len(item)!=(64+4600*68):
        raise ValueError("Wrong native 2.0.1 original main/00983")
    fmt,parts=get_sections(main)
    if fmt!="NSO0":raise ValueError("Not NSO0")
    seg=next(p for p in parts if p["name"]=="text")
    code,base=seg["data"],seg["mem_offset"]
    pointers=raw_pointers(parts,base+len(code))
    strides=real_stride_candidates(code,base)
    linked,run_count=inspect(code,base,pointers,strides)
    return {"status":"METHOD_68_STRIDE_CROSSREFERENCE_UNBOUND_TO_REGISTRY_CLASS",
       "source_main_sha256":a,"source_item_sha256":b,
       "raw_executable_pointer_count":len(pointers),
       "vtable_like_pointer_runs":run_count,
       "straightline_68_multipliers":len(strides),
       "vtable_plus30_68_matches":len(linked),
       "matched_method_candidates":linked[:70],
       "registry_index":"0xc7",
       "registry_global_va":"0x35618f0",
       "registry_slot_offset":"0x648",
       "registry_concrete_vtable_confirmed":False,
       "method_return_object_plus8_to_00983_confirmed":False,
       "true_item_id_to_record_offset_confirmed":False,
       "warnings":[
         "Dense pointer runs may be callback tables, not C++ vtables.",
         "68-byte arrays are common; same method address region does not establish the physical record base.",
         "The function may call another helper that performs the indexing and be absent from this shortlist.",
         "Registry 0xC7 instance constructor and its virtual pointer assignment remain necessary."
       ]}

def selftest():
    from collections import defaultdict
    fake={0x1000+i*8:0x2000+i*0x20 for i in range(9)}
    assert starts(fake)==[(0x1000,fake[0x1030])]
    fake[0x0ff8]=0x3000
    assert starts(fake)==[(0x0ff8,fake[0x1028])]
    try:
        audit(b"invalid",b"not real")
        raise AssertionError("Unexpected forged source acceptance")
    except ValueError:pass
    print("PASS pointer-run starts / 0x30 slot lookup / forged source rejection")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--main",type=Path,default=MAIN)
    p.add_argument("--item",type=Path,default=ITEM)
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test:selftest();return
    result=audit(args.main.read_bytes(),args.item.read_bytes())
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"registry_vtable_stride68_crosslinks.json").write_text(
        json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    summary={k:result[k] for k in ("status","source_main_sha256","source_item_sha256",
         "raw_executable_pointer_count","vtable_like_pointer_runs","straightline_68_multipliers",
         "vtable_plus30_68_matches","registry_index",
         "registry_concrete_vtable_confirmed","method_return_object_plus8_to_00983_confirmed",
         "true_item_id_to_record_offset_confirmed")}
    summary["shortlist"]=[{k:x[k] for k in ("vtable_address_point","virtual_method_pc",
                                "stride_arithmetic","field_loads_in_window")}
                          for x in result["matched_method_candidates"][:20]]
    (args.out/"registry_vtable_stride68_summary.json").write_text(
        json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2)[:18000])
if __name__=="__main__":main()
