#!/usr/bin/env python3
"""Conservative original ExeFS static candidates: LINKDATA 983 -> item ID * 68.

Matches are not caller/source-register proof. Do not label +0x26/0x3a enum
fields until the item-table loader and 68-byte pointer calculation are traced.
"""
from __future__ import annotations
import argparse
from bisect import bisect_left,bisect_right
from collections import Counter,defaultdict
import hashlib,json,struct
from pathlib import Path
from Scripts.resources.trace_native_species_item_callers import get_sections

MAIN=Path("2.0.1/exefs/main")
ITEM=Path("UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin")
OUT=Path("UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M11")
MAIN_SHA="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
ITEM_SHA="2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f"
FIELDS={0x22,0x26,0x3a}
IMMS={983,4600,68}

def validate_sources(main,item):
    a,b=hashlib.sha256(main).hexdigest(),hashlib.sha256(item).hexdigest()
    if (a,b)!=(MAIN_SHA,ITEM_SHA):
        raise ValueError("Unexpected original SHA256: ExeFS "+a+" / 00983 "+b)
    if len(item)!=64+4600*68 or struct.unpack_from("<II",item,0)!=(4600,3):
        raise ValueError("Original 00983.bin table header / record stride mismatch")
    return {"main_sha256":a,"item_sha256":b,"item_header_bytes":64,
            "record_count":4600,"record_stride":68,
            "verified_name_index_field_offset":"0x22"}

def decode(word):
    """Limited exact AArch64 encodings, not general purpose disassembly."""
    width="x" if word & 0x80000000 else "w"
    rd=word&31
    rn=(word>>5)&31
    rm=(word>>16)&31
    if (word & 0xff800000) in (0x52800000,0xd2800000):
        imm=((word>>5)&0xffff)<<(((word>>21)&3)*16)
        if imm in IMMS:
            return {"kind":"constant","op":"movz","value":imm,"dest_reg":f"{width}{rd}"}
    if (word & 0x7f00001f)==0x7100001f:
        imm=((word>>10)&0xfff) << (12 if word&(1<<22) else 0)
        if imm in IMMS:
            return {"kind":"constant","op":"cmp","value":imm,"source_reg":f"{width}{rn}"}
    if (word & 0x7f000000) in (0x11000000,0x51000000):
        imm=((word>>10)&0xfff)<<(12 if word&(1<<22) else 0)
        if imm==68:
            return {"kind":"stride","op":"sub" if word&(1<<30) else "add","value":68,
                    "dest_reg":f"{width}{rd}","source_reg":f"{width}{rn}"}
    types={0x39400000:("ldrb",1),0x79400000:("ldrh",2),
           0xb9400000:("ldr_w",4),0xf9400000:("ldr_x",8)}
    op=word&0xffc00000
    if op in types:
        name,scale=types[op]
        disp=((word>>10)&0xfff)*scale
        if disp in FIELDS:
            return {"kind":"field","op":name,"value":disp,
                    "base_reg":f"x{rn}","dest_reg":f"{width if name.startswith('ldr_') else 'w'}{rd}"}
    if (word&0x7f000000)==0x1b000000 and not(word&(1<<15)):
        ra=(word>>10)&31
        return {"kind":"multiply","op":"mul" if ra==31 else "madd",
                "regs":[rn,rm,ra,rd],"width":width}
    if (word&0x7f200000)==0x0b000000 and not(word&(3<<22)) and ((word>>10)&63)==4 and rn==rm:
        return {"kind":"scale17","op":"add_same_reg_lsl4","regs":[rn,rd],"width":width}
    return None

def survey_code(code,base):
    anchors,loads,mults=[],[],[]
    regs68=defaultdict(list)
    counts=Counter()
    for i,(word,) in enumerate(struct.iter_unpack("<I",code[:len(code)&~3])):
        event=decode(word)
        if event is None: continue
        pc=base+i*4
        counts[f"{event['kind']}:{event['op']}:{event.get('value','')}"]+=1
        event.update(pc=pc,opcode=f"{word:08x}")
        if event["kind"]=="constant" and event["op"]=="movz" and event["value"]==68:
            regs68[event["dest_reg"]].append(pc)
        if event["kind"]=="field": loads.append(event)
        if event["kind"]=="multiply": mults.append(event)
        if event["kind"] in ("constant","stride","scale17"): anchors.append(event)
    return anchors,loads,mults,regs68,counts

def rank_candidates(anchors,loads,mults,regs68,radius=0x500):
    anchor_pc=[x["pc"] for x in anchors]
    load_pc=[x["pc"] for x in loads]
    mul_pc=[x["pc"] for x in mults]
    ranked=[]
    for e in anchors:
        if e.get("value") not in (983,4600,68) and e["kind"]!="scale17":continue
        pc=e["pc"]
        near=anchors[bisect_left(anchor_pc,pc-radius):bisect_right(anchor_pc,pc+radius)]
        f=loads[bisect_left(load_pc,pc-radius):bisect_right(load_pc,pc+radius)]
        ms=mults[bisect_left(mul_pc,pc-radius):bisect_right(mul_pc,pc+radius)]
        n983=[x for x in near if x.get("value")==983]
        n4600=[x for x in near if x.get("value")==4600]
        n68=[x for x in near if x.get("value")==68 or x["kind"]=="scale17"]
        m68=[]
        for m in ms:
            for regno in m["regs"][:2]:
                reg=m["width"]+str(regno)
                all_prev=regs68.get(reg,[])
                idx=bisect_left(all_prev,m["pc"])-1
                if idx>=0 and 0<m["pc"]-all_prev[idx]<=0x180:
                    m68.append({"mul_pc":hex(m["pc"]),"movz_pc":hex(all_prev[idx]),
                                "reg":reg,"warning":"CFG/clobber not checked"})
        score=9*bool(n983)+8*bool(n4600)+5*bool(n68)+3*bool(f)+3*bool(ms)+4*bool(m68)
        if score<8:continue
        ranked.append({"pc":hex(pc),"anchor_kind":e["kind"],"anchor_value":e.get("value"),
                      "score_proximity_only":score,
                      "near_983":[hex(x["pc"]) for x in n983[:6]],
                      "near_4600":[hex(x["pc"]) for x in n4600[:6]],
                      "near_stride68":[hex(x["pc"]) for x in n68[:9]],
                      "near_fields":[{"pc":hex(x["pc"]),"offset":hex(x["value"]),
                                      "base_reg":x["base_reg"]} for x in f[:14]],
                      "near_mul68":m68[:8]})
    ranked.sort(key=lambda x:(-x["score_proximity_only"],int(x["pc"],16)))
    kept=[]
    for r in ranked:
        addr=int(r["pc"],16)
        if not any(abs(addr-int(k["pc"],16))<0x180 for k in kept):
            kept.append(r)
        if len(kept)==40:break
    return kept,len(ranked)

def context(code,base,pc):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    o=pc-base
    begin=max(0,(o-0x90)&~3)
    end=min(len(code),(o+0x110)&~3)
    md=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    return [{"pc":hex(i.address),"asm":i.mnemonic+" "+i.op_str}
            for i in md.disasm(code[begin:end],base+begin)]

def audit(main,item):
    source=validate_sources(main,item)
    fmt,sections=get_sections(main)
    if fmt!="NSO0":raise ValueError("Expected NSO0")
    section=next(s for s in sections if s["name"]=="text")
    code,base=section["data"],section["mem_offset"]
    anchors,loads,muls,regs68,counts=survey_code(code,base)
    top,total=rank_candidates(anchors,loads,muls,regs68)
    for r in top:r["context"]=context(code,base,int(r["pc"],16))
    return {"status":"UNVERIFIED_STATIC_CANDIDATES","source":source,
        "text_module_offset":hex(base),"text_bytes":len(code),
        "opcode_counts":dict(sorted(counts.items())),
        "raw_ranked_windows":total,"distinct_windows":len(top),
        "windows":top,
        "verified_loader":False,"verified_item_id_stride68":False,
        "verified_category_0x26":False,"verified_category_0x3a":False,
        "limitations":[
          "Direct MOVZ/CMP, ADD/SUB immediate and MUL/MADD pattern coverage only.",
          "Record indexing may use strength reduction or helper functions not in the same 0x500 byte range.",
          "Nearby opcode hits do not prove function boundaries or live register provenance.",
          "Need 983 resource accessor -> 4600-row base -> item ID indexing -> actual +0x22/+0x26/+0x3a consumers."
        ]}

def self_test():
    assert decode(0xd2800000|(983<<5)|2)["value"]==983
    assert decode(0xd2800000|(4600<<5)|1)["value"]==4600
    assert decode(0x52800000|(68<<5)|3)["value"]==68
    assert decode(0x7100001f|(983<<10))["value"]==983
    assert decode(0x39400000|(0x26<<10)|(8<<5))["base_reg"]=="x8"
    assert decode(0x79400000|((0x22//2)<<10))["value"]==0x22
    assert decode(0x9b000000|(31<<10)|(2<<16)|(1<<5))["op"]=="mul"
    assert decode(0x8b000000|(2<<16)|(4<<10)|(2<<5)|3)["kind"]=="scale17"
    assert decode(0xd503201f) is None
    synthetic=struct.pack("<5I",0xd2800000|(983<<5)|2,
        0xd2800000|(4600<<5)|1,0xd2800000|(68<<5)|3,
        0x9b000000|(31<<10)|(3<<16)|(0<<5)|4,
        0x39400000|(0x26<<10)|(4<<5))
    anchors,loads,muls,regs,counts=survey_code(synthetic,0x1000)
    rank,total=rank_candidates(anchors,loads,muls,regs)
    assert total>0 and rank and any(x["near_mul68"] for x in rank)
    invalid=bytearray(64+4600*68)
    struct.pack_into("<II",invalid,0,4600,3)
    try:
        validate_sources(b"not original",invalid)
        raise AssertionError("Failed to reject forged original")
    except ValueError:pass
    print("PASS strict source rejection, ARM64 983/4600/68, MUL, field and rank fixtures")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--main",type=Path,default=MAIN)
    p.add_argument("--item",type=Path,default=ITEM)
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test:self_test();return
    r=audit(args.main.read_bytes(),args.item.read_bytes())
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"native_item_loader_candidates.json").write_text(
        json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary={k:r[k] for k in ("status","source","text_bytes","opcode_counts","raw_ranked_windows","distinct_windows")}
    summary["top_windows"]=[{k:x[k] for k in ("pc","score_proximity_only","near_983","near_4600","near_stride68","near_fields","near_mul68")}
                            for x in r["windows"][:12]]
    summary["verified_loader"]=False
    (args.out/"native_item_loader_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=["# Pokopia 2.0.1 00983.bin 原生加载与 ID×68 静态候选","",
      "ExeFS sha256: "+r["source"]["main_sha256"],
      "00983.bin sha256: "+r["source"]["item_sha256"],"",
      "**仅候选，尚未证明 983 资源调用、记录基址和 ID×68 在同一数据流中。**",""]
    for x in r["windows"][:20]:
        lines.append(f"- main+{x['pc']} score={x['score_proximity_only']} 983={x['near_983']} 4600={x['near_4600']} stride={x['near_stride68']}")
    lines.extend(["","Next: resolve exact 983 asset call -> table base -> item ID indexing -> +0x22 field -> +0x26 / +0x3A consumer.",""])
    (args.out/"NATIVE_ITEM_LOADER_RESEARCH.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
