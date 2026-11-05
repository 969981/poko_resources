#!/usr/bin/env python3
"""Look for original AArch64 ID*68 record address computation, esp UMADDL.

Use exact original NSO and item table. Matching W-multiplier and load offsets
is necessary but *not sufficient* to identify 00983.bin as their data source.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from bisect import bisect_left,bisect_right
from collections import Counter,defaultdict
from pathlib import Path
from Scripts.resources.trace_native_species_item_callers import get_sections

MAIN=Path("2.0.1/exefs/main")
ITEM=Path("UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin")
OUT=Path("UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M13")
MAIN_SHA="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
ITEM_SHA="2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f"

def record(word):
    if (word&0xff800000) in (0x52800000,0xd2800000):
        imm=((word>>5)&0xffff)<<(((word>>21)&3)*16)
        if imm in (68,4600,983):
            return {"kind":"constant","value":imm,"reg":word&31,
                    "width":"x" if word&(1<<31) else "w"}
    if (word&0xffe08000) in (0x9ba00000,0x9b200000):
        return {"kind":"mul_long","op":"umaddl" if word&(1<<23) else "smaddl",
                "dest":word&31,"rn":(word>>5)&31,"rm":(word>>16)&31,"ra":(word>>10)&31}
    if (word&0xffe08000) in (0x9b000000,0x1b000000):
        return {"kind":"madd","op":"madd","width":"x" if word&(1<<31) else "w",
                "dest":word&31,"rn":(word>>5)&31,"rm":(word>>16)&31,"ra":(word>>10)&31}
    loads={0x79400000:("ldrh",2),0x39400000:("ldrb",1)}
    op=word&0xffc00000
    if op in loads:
        kind,scale=loads[op]
        disp=((word>>10)&0xfff)*scale
        if disp in (0x22,0x26,0x39,0x3a):
            return {"kind":"field","op":kind,"disp":disp,
                    "base":(word>>5)&31,"dst":word&31}
    return None

def scan(code,base):
    constants=defaultdict(list)
    fields=[]
    muls=[]
    counts=Counter()
    for i,(w,) in enumerate(struct.iter_unpack("<I",code[:len(code)&~3])):
        e=record(w)
        if not e:continue
        e["pc"]=base+i*4
        counts[e["kind"]+":"+str(e.get("op",e.get("value","")))]+=1
        if e["kind"]=="constant":constants[(e["value"],e["reg"],e["width"])].append(e["pc"])
        if e["kind"]=="field":fields.append(e)
        if e["kind"] in ("mul_long","madd"):muls.append(e)
    return constants,fields,muls,counts

def build(code,base):
    c,fields,muls,counts=scan(code,base)
    fpcs=[x["pc"] for x in fields]
    candidates=[]
    for m in muls:
        regs=[m["rn"],m["rm"]]
        likely=[]
        for reg in regs:
            width="w" if m["kind"]=="mul_long" else m["width"]
            arr=c.get((68,reg,width),[])
            at=bisect_left(arr,m["pc"])-1
            if at>=0 and 0<m["pc"]-arr[at]<=0x100:
                likely.append({"pc":hex(arr[at]),"reg":width+str(reg),
                               "warning":"no CFG clobber proof"})
        if not likely:continue
        pc=m["pc"]
        nearby=fields[bisect_left(fpcs,pc-0x100):bisect_right(fpcs,pc+0x200)]
        same_result=[x for x in nearby if x["base"]==m["dest"] and x["pc"]>pc]
        # same register name does not yet prove the register wasn't overwritten
        score=5+(8 if same_result else 0)+(3 if nearby else 0)
        candidates.append({"pc":hex(pc),"op":m["op"],"dest":"x"+str(m["dest"]),
                           "id_candidate_registers":["w"+str(r) for r in regs],
                           "base_accumulator_register":"x"+str(m["ra"]),
                           "constant68_producers":likely,"score":score,
                           "nearby_fields":[{"pc":hex(x["pc"]),"op":x["op"],
                                  "offset":hex(x["disp"]),"base":"x"+str(x["base"])}
                                  for x in nearby[:20]],
                           "same_output_register_field_loads":[{"pc":hex(x["pc"]),"offset":hex(x["disp"])}
                                  for x in same_result[:12]],
                           "status":"ARITHMETIC_CANDIDATE_UNPROVEN_00983_BASE"})
    candidates.sort(key=lambda x:(-x["score"],int(x["pc"],16)))
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    md=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    unique=[]
    for x in candidates:
        addr=int(x["pc"],16)
        if any(abs(addr-int(y["pc"],16))<0x80 for y in unique):continue
        o=addr-base
        begin=max(0,(o-0x80)&~3)
        end=min(len(code),(o+0x100)&~3)
        x["disassembly"]=[{"pc":hex(ins.address),"asm":ins.mnemonic+" "+ins.op_str}
                          for ins in md.disasm(code[begin:end],base+begin)]
        unique.append(x)
        if len(unique)==40:break
    return unique,len(candidates),dict(sorted(counts.items()))

def run(main,item):
    sha_main=hashlib.sha256(main).hexdigest()
    sha_item=hashlib.sha256(item).hexdigest()
    if sha_main!=MAIN_SHA or sha_item!=ITEM_SHA:
        raise ValueError("Original source identity mismatch")
    if len(item)!=64+4600*68 or struct.unpack_from("<II",item,0)!=(4600,3):
        raise ValueError("Incorrect native 4600 x 68 item layout")
    fmt,parts=get_sections(main)
    if fmt!="NSO0":raise ValueError("Wrong original executable kind")
    code=next(x for x in parts if x["name"]=="text")
    windows,total,counts=build(code["data"],code["mem_offset"])
    return {"status":"ORIGINAL_68_STRIDE_MUL_CANDIDATES_ONLY",
            "sha256_main":sha_main,"sha256_item":sha_item,
            "item_count":4600,"item_stride":68,
            "total_candidates":total,"top_nonoverlapping_count":len(windows),
            "opcode_counts":counts,"top_candidates":windows,
            "verified_00983_loader":False,"verified_item_ID_times_68_base":False,
            "notes":[
               "UMADDL / SMADDL / MADD with MOVZ #68 near source register.",
               "Same-register offset loads are candidate edges, no CFG clobber proof.",
               "Allocator, indirect table lookup, and 00983.bin file-source provenance remain untraced.",
               "Optimized 68 = (ID * 17) << 2 and helper or literal-pool calculations may be missed."
            ]}

def selftest():
    wz=0x52800000|(68<<5)|10
    maddl=0x9ba00000|(10<<16)|(3<<10)|(2<<5)|1
    assert record(wz)["value"]==68
    assert record(maddl)["kind"]=="mul_long"
    assert record(maddl)["op"]=="umaddl"
    assert record(maddl)["rn"]==2 and record(maddl)["rm"]==10
    code=struct.pack("<4I",wz,maddl,0x79400000|(0x11<<10)|(1<<5)|4,
                     0x39400000|(0x26<<10)|(1<<5)|5)
    c,fields,muls,counts=scan(code,0)
    assert len(fields)==2 and len(muls)==1
    fake=bytearray(64+4600*68)
    struct.pack_into("<II",fake,0,4600,3)
    try:
        run(b"not real",fake)
        raise AssertionError("Invalid original accepted")
    except ValueError:pass
    print("PASS strict original hash gating, UMADDL and field offset fixtures")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--main",type=Path,default=MAIN)
    p.add_argument("--item",type=Path,default=ITEM)
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:selftest();return
    report=run(a.main.read_bytes(),a.item.read_bytes())
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/"native_stride68_candidates.json").write_text(
        json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    summary={k:report[k] for k in ("status","sha256_main","sha256_item","total_candidates",
                                   "opcode_counts","verified_00983_loader","verified_item_ID_times_68_base")}
    summary["shortlist"]=[{k:x[k] for k in ("pc","op","dest","score","constant68_producers",
                                           "nearby_fields","same_output_register_field_loads")}
                          for x in report["top_candidates"][:15]]
    (a.out/"native_stride68_summary.json").write_text(
        json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
