#!/usr/bin/env python3
"""M15: native code xrefs to registry ID 0xC7 / slot 0x638 / 0x648.

Reads exact 2.0.1 NSO. Finds potential registration (write) callers separately
from confirmed lookup consumers. Numeric immediate overlap is *not* identity.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import Counter
from pathlib import Path
from Scripts.resources.trace_native_species_item_callers import get_sections

EXPECTED="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
MAIN=Path("2.0.1/exefs/main")
OUT=Path("UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M15")
REGISTRY_GLOBAL=0x35618f0
SLOT_ID=0xc7
SLOT_BYTES=0x638

def decode(code,base):
    matches=[]
    counts=Counter()
    words=memoryview(code)
    length=len(code)&~3
    for off in range(0,length,4):
        w=struct.unpack_from("<I",words,off)[0]
        pc=base+off
        e=None
        if (w&0xFF800000) in (0x52800000,0xD2800000):
            val=((w>>5)&0xffff)<<(((w>>21)&3)*16)
            if val in (SLOT_ID,SLOT_BYTES,0x648):
                e=("movz",val)
        elif (w&0x7F00001F)==0x7100001F:
            val=((w>>10)&0xfff)<<(12 if (w>>22)&1 else 0)
            if val in (SLOT_ID,SLOT_BYTES,0x648):
                e=("cmp",val)
        elif (w&0x7F000000) in (0x11000000,0x51000000):
            val=((w>>10)&0xfff)<<(12 if (w>>22)&1 else 0)
            if val in (SLOT_ID,SLOT_BYTES,0x648):
                e=("add_sub",val)
        elif (w&0xffc00000) in (0xf9000000,0xf9400000):
            val=((w>>10)&0xfff)*8
            if val in (SLOT_BYTES,0x648):
                e=("store" if (w&0xffc00000)==0xf9000000 else "load",val)
        if e:
            counts[f"{e[0]}:{e[1]:#x}"]+=1
            matches.append({"pc":pc,"kind":e[0],"value":e[1],"instruction_word":f"{w:08x}"})
        if (w & 0x9f000000)==0x90000000:
            imm=((w>>5)&0x7ffff)*4+((w>>29)&3)
            if imm & (1<<20):imm-=1<<21
            page=(pc&~0xfff)+(imm<<12)
            if page==(REGISTRY_GLOBAL&~0xfff):
                reg=w&31
                for step in (4,8,12,16,20):
                    if off+step+4>length:break
                    nextw=struct.unpack_from("<I",words,off+step)[0]
                    if nextw&0xff000000!=0x91000000:continue
                    if (nextw>>5)&31!=reg:continue
                    sh=(nextw>>22)&3
                    if sh not in (0,1):continue
                    val=page+(((nextw>>10)&0xfff)<<(12 if sh else 0))
                    if val==REGISTRY_GLOBAL:
                        counts["registry_global_adrp_add"]+=1
                        matches.append({"pc":pc,"kind":"registry_global_adrp_add",
                                        "value":val,"add_pc":pc+step})
    return matches,counts

def window(md,code,base,pc,pre=0x60,post=0x90):
    offset=pc-base
    a=max(0,(offset-pre)&~3)
    b=min(len(code),(offset+post)&~3)
    return [{"pc":hex(i.address),"asm":i.mnemonic+" "+i.op_str}
            for i in md.disasm(code[a:b],base+a)]

def rank(matches,code,base):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    md=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    ids=[e for e in matches if e["kind"] in ("movz","cmp") and e["value"]==SLOT_ID]
    global_refs=[e for e in matches if e["kind"]=="registry_global_adrp_add"]
    slot_refs=[e for e in matches if e["kind"] in ("store","load","add_sub") and e["value"] in (0x638,0x648)]
    # Include exact direct callers first; remote co-location is only ranking.
    tagged=[]
    for e in ids+slot_refs:
        pc=e["pc"]
        gs=[g for g in global_refs if abs(g["pc"]-pc)<=0x180]
        same=[s for s in slot_refs if abs(s["pc"]-pc)<=0x80 and s["pc"]!=pc]
        score=8*bool(gs)+5*(e["kind"]=="store")+3*bool(same)+1
        tagged.append({"pc":hex(pc),"kind":e["kind"],"value":hex(e["value"]),
                      "score_co_location_only":score,
                      "near_global":[hex(g["pc"]) for g in gs[:8]],
                      "near_slots":[hex(s["pc"]) for s in same[:8]]})
    tagged.sort(key=lambda e:(-e["score_co_location_only"],int(e["pc"],16)))
    unique=[]
    for e in tagged:
        pc=int(e["pc"],16)
        if any(abs(pc-int(x["pc"],16))<0x60 for x in unique):continue
        e["disassembly"]=window(md,code,base,pc)
        unique.append(e)
        if len(unique)>=120:break
    global_only=[]
    for e in global_refs[:80]:
        global_only.append({"pc":hex(e["pc"]),"add_pc":hex(e["add_pc"]),
                            "context":window(md,code,base,e["pc"],0x30,0x50)})
    return unique,global_only,len(ids),len(slot_refs),len(global_refs)

def audit(blob):
    sha=hashlib.sha256(blob).hexdigest()
    if sha!=EXPECTED:raise ValueError("Wrong original main "+sha)
    fmt,parts=get_sections(blob)
    if fmt!="NSO0":raise ValueError("Not NSO0")
    text=next(x for x in parts if x["name"]=="text")
    data=text["data"];base=text["mem_offset"]
    matches,counts=decode(data,base)
    ranked,global_xref,num_id,num_slot,num_global=rank(matches,data,base)
    return {"status":"REGISTRY_0XC7_REFERENCES__WRITER_CLASS_UNRESOLVED",
        "sha256":sha,"registry_index":hex(SLOT_ID),
        "registry_global_va":hex(REGISTRY_GLOBAL),
        "registry_slot_offset":hex(SLOT_BYTES),
        "registry_member_pointer_offset":"0x10",
        "effective_registry_member_offset":hex(SLOT_BYTES+0x10),
        "raw_opcode_counts":dict(sorted(counts.items())),
        "id_opcode_total":num_id,"slot_opcode_total":num_slot,
        "registry_global_exact_adrp_add_total":num_global,
        "ranked_call_sites":ranked,"global_xrefs":global_xref,
        "proven_registry_writer":False,
        "proven_registry_0xc7_class_constructor":False,
        "proven_0xc7_vtable_plus30_function":False,
        "proven_00983_record_pointer_source":False,
        "warnings":[
            "Numeric 0xC7 might be non-registry in many functions; 0x638 often a regular structure offset.",
            "Direct store to offset 0x648 is not automatically a store to the global registry instance.",
            "Need assembly register provenance of global + index + class object constructor.",
            "After discovering constructor, inspect ADRP/ADD/STR of its vtable and vtable +0x30 method."
        ]}

def selftest():
    # Genuine ARM64 encodings for MOVZ W8,#199, CMP W8,#199, STR X1,[X2,#0x648].
    raw=struct.pack("<3I",0x52800000|(0xc7<<5)|8,
                     0x7100001f|(0xc7<<10)|(8<<5),
                     0xf9000000|((0x648//8)<<10)|(2<<5)|1)
    rows,counts=decode(raw,0x1000)
    assert len(rows)==3,rows
    assert counts["movz:0xc7"]==1
    assert counts["cmp:0xc7"]==1
    assert counts["store:0x648"]==1
    try:
        audit(b"fake")
        raise AssertionError("invalid main passed")
    except ValueError:pass
    print("PASS immediate decoding +0x648 direct store, fake source rejection")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--main",type=Path,default=MAIN)
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test:selftest();return
    result=audit(args.main.read_bytes())
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"registry_slot_0xc7_original_xrefs.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary={k:result[k] for k in ("status","sha256","registry_index","registry_global_va",
        "registry_slot_offset","effective_registry_member_offset",
        "raw_opcode_counts","id_opcode_total","slot_opcode_total",
        "registry_global_exact_adrp_add_total",
        "proven_registry_writer","proven_registry_0xc7_class_constructor",
        "proven_0xc7_vtable_plus30_function","proven_00983_record_pointer_source")}
    summary["top_candidates"]=[{k:x[k] for k in ("pc","kind","value","score_co_location_only",
                        "near_global","near_slots")} for x in result["ranked_call_sites"][:32]]
    (args.out/"registry_slot_0xc7_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
