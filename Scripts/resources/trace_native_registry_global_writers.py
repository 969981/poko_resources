#!/usr/bin/env python3
"""M19: find direct NSO ARM64 stores to the registry-global pointer cell.

Looks for ADRP+ADD resolving main+0x35618F0 followed by STR [same-base].
Do not confuse a store to the global cell with a write to the registry's
member slot 0x648: the latter needs separate pointer/dataflow proof.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from Scripts.resources.trace_native_species_item_callers import get_sections

MAIN=Path("2.0.1/exefs/main")
OUT=Path("UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M19")
SHA="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
GLOBAL=0x35618f0

def signextend(n,bits):
    return n-(1<<bits) if n&(1<<(bits-1)) else n

def refs(code,base):
    events=[]
    for off in range(0,(len(code)&~3)-4,4):
        word=struct.unpack_from("<I",code,off)[0]
        if (word&0x9f000000)!=0x90000000:continue
        val=signextend((((word>>5)&0x7ffff)<<2)|((word>>29)&3),21)
        pc=base+off
        page=(pc&~0xfff)+(val<<12)
        if page!=(GLOBAL&~0xfff):continue
        reg=word&31
        for delta in (4,8,12,16,20):
            d=off+delta
            if d+4>len(code):continue
            w=struct.unpack_from("<I",code,d)[0]
            if (w&0xff000000)!=0x91000000:continue
            if ((w>>5)&31)!=reg:continue
            shift=(w>>22)&3
            if shift not in (0,1):continue
            imm=((w>>10)&0xfff) << (12 if shift else 0)
            if page+imm!=GLOBAL:continue
            dest=w&31
            # Check directly following STR/STRB; do not assert whole CFG.
            matches=[]
            for at in range(d+4,min(len(code)-4,d+0x78),4):
                w2=struct.unpack_from("<I",code,at)[0]
                opcode=w2&0xffc00000
                if opcode in (0xf9000000,0xb9000000) and ((w2>>5)&31)==dest:
                    disp=((w2>>10)&0xfff)*(8 if opcode==0xf9000000 else 4)
                    if disp==0:
                        matches.append({"pc":hex(base+at),
                                        "source_register":("x" if opcode==0xf9000000 else "w")+str(w2&31),
                                        "store_bits":64 if opcode==0xf9000000 else 32,
                                        "distance_bytes":at-d})
            events.append({"adrp_pc":hex(pc),"add_pc":hex(base+d),
                           "global_reg":"x"+str(dest),
                           "nearby_direct_stores":matches[:8],
                           "status":"LOCAL_OPCODE_CANDIDATE_REGISTER_CLOBBER_UNTESTED"})
    return events

def annotate(code,base,events):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    md=Cs(CS_ARCH_ARM64,CS_MODE_ARM);md.detail=True
    strong=[]
    for e in events:
        if not e["nearby_direct_stores"]:continue
        begin=int(e["add_pc"],16)-base
        regno=int(e["global_reg"][1:])
        real=[]
        for s in e["nearby_direct_stores"]:
            end=int(s["pc"],16)-base
            # Ignore sites that branch or clobber ADRP+ADD result before STR.
            ok=True
            for ins in md.disasm(code[begin+4:end],base+begin+4):
                m=ins.mnemonic
                if m in ("bl","blr","b","br","ret","retab","cbz","cbnz","tbz","tbnz") or m.startswith("b."):
                    ok=False;break
                _,writes=ins.regs_access()
                if any(md.reg_name(x) in (f"w{regno}",f"x{regno}") for x in writes):
                    ok=False;break
            if ok:real.append(s)
        if not real:continue
        pc=int(real[0]["pc"],16)
        start=max(0,(int(e["adrp_pc"],16)-base-0x90)&~3)
        finish=min(len(code),(pc-base+0x80)&~3)
        asm=[{"pc":hex(i.address),"asm":i.mnemonic+" "+i.op_str}
             for i in md.disasm(code[start:finish],base+start)]
        strong.append({**e,"nearby_direct_stores":real,
                       "disassembly":asm,
                       "status":"DIRECT_GLOBAL_CELL_STORE_SITE__VALUE_PROVENANCE_UNKNOWN"})
    return strong

def audit(blob):
    sha=hashlib.sha256(blob).hexdigest()
    if sha!=SHA:raise ValueError("Wrong original NSO SHA256 "+sha)
    fmt,parts=get_sections(blob)
    if fmt!="NSO0":raise ValueError("Not original NSO0")
    text=next(p for p in parts if p["name"]=="text")
    code,base=text["data"],text["mem_offset"]
    allrefs=refs(code,base)
    stores=annotate(code,base,allrefs)
    return {"status":"GLOBAL_REGISTRY_POINTER_DIRECT_STORE_CANDIDATES",
       "main_sha256":sha,
       "registry_global":hex(GLOBAL),
       "static_adrp_add_global_references":len(allrefs),
       "direct_global_cell_store_sites":len(stores),
       "writer_candidates":stores[:90],
       "global_writer_function_identity_proven":False,
       "registered_item_class_0xc7_proven":False,
       "item_record_pointer_source_proven":False,
       "warning":"Only direct global pointer-cell writes, not indexed table member registration. No alias or interprocedural propagation."}

def selftest():
    pc=0x1000
    # ADRP X8, same page; ADD X8,X8,#0x8F0; STR X0,[X8].
    global GLOBAL
    old=GLOBAL
    try:
        GLOBAL=0x18f0
        # page 0x1000, target 0x18f0
        buf=struct.pack("<3I",0x90000008,
             0x91000000|(0x8f0<<10)|(8<<5)|8,
             0xf9000000|(8<<5)|0)
        e=refs(buf,pc)
        assert e and e[0]["nearby_direct_stores"][0]["pc"]=="0x1008",e
        from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
        assert annotate(buf,pc,e)
    finally:
        GLOBAL=old
    try:audit(b"forged")
    except ValueError:pass
    else:raise AssertionError("Forged original accepted")
    print("PASS ADRP/ADD/store same-register and source mismatch fixtures")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--main",type=Path,default=MAIN)
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test:selftest();return
    result=audit(args.main.read_bytes())
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"registry_global_writers.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary={k:result[k] for k in ("status","main_sha256","registry_global",
         "static_adrp_add_global_references","direct_global_cell_store_sites",
         "global_writer_function_identity_proven",
         "registered_item_class_0xc7_proven","item_record_pointer_source_proven")}
    summary["writer_sites"]=[{"adrp_pc":x["adrp_pc"],"add_pc":x["add_pc"],
          "nearby_direct_stores":x["nearby_direct_stores"]}
          for x in result["writer_candidates"]]
    (args.out/"registry_global_writers_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
