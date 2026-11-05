#!/usr/bin/env python3
"""M16: Find 0xC7 passed as an argument to a native BL/BLR call.

Groups calls by target and argument register; compares adjacent 0xC6/0xC8
initializers. Does not label all 0xC7 constants as registry registrations.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import Counter,defaultdict
from pathlib import Path
from Scripts.resources.trace_native_species_item_callers import get_sections

MAIN=Path("2.0.1/exefs/main")
OUT=Path("UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M16")
MAIN_SHA="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"

def constants(code,base,values=(0xc6,0xc7,0xc8)):
    hits=defaultdict(list)
    for off in range(0,len(code)&~3,4):
        w=struct.unpack_from("<I",code,off)[0]
        if (w&0xff800000) not in (0x52800000,0xd2800000):continue
        val=((w>>5)&0xffff)<<(((w>>21)&3)*16)
        if val not in values:continue
        hits[val].append({"pc":base+off,"reg":w&31,
                          "width":"x" if w&(1<<31) else "w",
                          "raw_word":f"{w:08x}"})
    return hits

def reachable_calls(code,base,anchor,md):
    off=anchor["pc"]-base
    buf=code[off:off+0x88]
    regno=anchor["reg"]
    results=[]
    done=0
    for ins in md.disasm(buf,anchor["pc"]):
        if ins.address==anchor["pc"]:continue
        done+=1
        mnemonic=ins.mnemonic
        if mnemonic in ("bl","blr","braa","blraa","blrab","blraaz"):
            results.append({"call_pc":hex(ins.address),
                            "call_instruction":mnemonic+" "+ins.op_str,
                            "call_target":ins.op_str if mnemonic=="bl" else None,
                            "argument_reg":f"{anchor['width']}{regno}",
                            "distance":ins.address-anchor["pc"],
                            "flow_status":"STRAIGHTLINE_PARAMETER_NOT_PROVEN"})
            break
        if (mnemonic.startswith("b.") or mnemonic in
             ("b","br","ret","retab","cbz","cbnz","tbz","tbnz","brk")):break
        _,written=ins.regs_access()
        # Avoid registers modified by any instruction before the call.
        if any(md.reg_name(r) in (f"w{regno}",f"x{regno}") for r in written):
            break
        if done>=32:break
    return results

def analyze(blob):
    sha=hashlib.sha256(blob).hexdigest()
    if sha!=MAIN_SHA:raise ValueError("Not exact Pokopia 2.0.1 main SHA256 "+sha)
    fmt,parts=get_sections(blob)
    if fmt!="NSO0":raise ValueError("Not NSO0")
    text=next(p for p in parts if p["name"]=="text")
    code,base=text["data"],text["mem_offset"]
    c=constants(code,base)
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    md=Cs(CS_ARCH_ARM64,CS_MODE_ARM);md.detail=True
    sites=[]
    for e in c[0xc7]:
        calls=reachable_calls(code,base,e,md)
        neighbors=[]
        for val in (0xc6,0xc8):
            candidates=[p["pc"] for p in c[val] if abs(p["pc"]-e["pc"])<=0x600]
            neighbors.extend({"id":hex(val),"pc":hex(pc)} for pc in candidates[:10])
        before=max(0,e["pc"]-base-0x60)
        after=min(len(code),e["pc"]-base+0x80)
        context=[{"pc":hex(i.address),"asm":i.mnemonic+" "+i.op_str}
                 for i in md.disasm(code[before:after],base+before)]
        sites.append({"constant_pc":hex(e["pc"]),"arg_register":e["width"]+str(e["reg"]),
                      "nearest_straightline_call":calls[:1],
                      "adjacent_C6_C8_constants":neighbors[:16],
                      "context":context})
    by_target=defaultdict(list)
    for x in sites:
        if not x["nearest_straightline_call"]:continue
        call=x["nearest_straightline_call"][0]
        key=f"{call['argument_reg']}:{call.get('call_target')}:{call['call_instruction'].split()[0]}"
        by_target[key].append(x["constant_pc"])
    groups=[{"key":k,"count":len(v),"constant_pcs":v[:15]}
            for k,v in by_target.items()]
    groups.sort(key=lambda x:(-x["count"],x["key"]))
    return {"status":"REGISTRY_PARAMETER_CANDIDATES_UNVERIFIED",
        "original_main_sha256":sha,
        "constant_counts":{hex(k):len(v) for k,v in c.items()},
        "0xc7_argument_call_groups":groups,
        "0xc7_immediate_sites":sites,
        "registration_constructor_confirmed":False,
        "vtable_0x30_target_confirmed":False,
        "warnings":[
            "Argument register could be clobbered by implicit side effects or predicated control flow.",
            "No proof the called function is the 0xC7 registry initializer; compare C6/C8 sequences and constructor dataflow.",
            "No proof of 00983.bin base, 68-byte indexing, or object+8 pointer.",
        ]}

def selftest():
    # mov w1,#C7; BL PC+8; ret. Other constant must be decoded as well.
    word=0x52800000|(0xc7<<5)|1
    b=struct.pack("<4I",word,0x94000001,0xd65f03c0,
                 0x52800000|(0xc6<<5)|1)
    rows=constants(b,0x1000)
    assert len(rows[0xc7])==1 and len(rows[0xc6])==1
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    md=Cs(CS_ARCH_ARM64,CS_MODE_ARM);md.detail=True
    found=reachable_calls(b,0x1000,rows[0xc7][0],md)
    assert len(found)==1 and found[0]["call_pc"]=="0x1004"
    try:
        analyze(b"not actual 2.0.1")
        raise AssertionError("Invalid source accepted")
    except ValueError:pass
    print("PASS: M16 immediate-to-branch parameter and invalid source tests")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--main",type=Path,default=MAIN)
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:selftest();return
    r=analyze(a.main.read_bytes())
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/"registry_0xc7_parameter_calls.json").write_text(
         json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    small={k:r[k] for k in ("status","original_main_sha256","constant_counts",
        "registration_constructor_confirmed","vtable_0x30_target_confirmed")}
    small["call_groups"]=r["0xc7_argument_call_groups"][:70]
    small["candidate_examples"]=[
        {"constant_pc":x["constant_pc"],"arg_register":x["arg_register"],
         "nearest_straightline_call":x["nearest_straightline_call"],
         "adjacent_C6_C8_constants":x["adjacent_C6_C8_constants"]}
        for x in r["0xc7_immediate_sites"][:80]]
    (a.out/"registry_0xc7_parameter_summary.json").write_text(
         json.dumps(small,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(small,ensure_ascii=False,indent=2)[:14000])
if __name__=="__main__":main()
