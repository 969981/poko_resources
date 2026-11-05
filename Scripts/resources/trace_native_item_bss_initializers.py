#!/usr/bin/env python3
"""M21: xrefs to BSS default item/type records and pointer cells.

After M20 showed default pointers 0x3483c58->0x35b6128 and
0x3484a38->0x35b617c, find real ADRP + ADD/LDR/STR users for construction.
Does not conflate defaults with 00983 physical item rows.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import Counter,defaultdict
from pathlib import Path
from Scripts.resources.trace_native_species_item_callers import get_sections
MAIN=Path("2.0.1/exefs/main")
ITEM=Path("UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin")
OUT=Path("UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M21")
SHA_MAIN="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
SHA_ITEM="2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f"
TARGETS={
  0x35b6128:"C7_fallback_BSS_default_record",
  0x35b617c:"C9_fallback_BSS_default_record",
  0x35b5b3c:"related_BSS_default_record",
  0x35b7af8:"related_BSS_default_record_other",
  0x3483c58:"C7_global_pointer_cell",
  0x3484a38:"C9_global_pointer_cell",
}
def signed21(w):
    t=(((w>>5)&0x7ffff)<<2)|((w>>29)&3)
    return t-(1<<21) if t&(1<<20) else t
def find_xrefs(code,base):
    hits=[]
    for o in range(0,(len(code)&~3)-4,4):
        word=struct.unpack_from("<I",code,o)[0]
        if word&0x9f000000!=0x90000000:continue
        pc=base+o
        page=(pc&~0xfff)+(signed21(word)<<12)
        matching=[v for v in TARGETS if v&~0xfff==page]
        if not matching:continue
        rn=word&31
        # Both X-address materializations and scaled LDR/STR [ADRP,#imm].
        for d in (4,8,12,16,20,24,28,32):
            if o+d+4>len(code):break
            w=struct.unpack_from("<I",code,o+d)[0]
            op=w&0xffc00000
            target=None
            typ=None
            dst=None
            if (w&0xff000000)==0x91000000 and ((w>>5)&31)==rn:
                shift=(w>>22)&3
                if shift in (0,1):
                    target=page+(((w>>10)&0xfff)<<(12 if shift else 0))
                    typ="ADRP_ADD_address"
                    dst=w&31
            elif ((w>>5)&31)==rn and op in (0xf9400000,0xf9000000,
                                                     0xb9400000,0xb9000000,
                                                     0x39400000,0x39000000):
                scale=8 if op in (0xf9400000,0xf9000000) else 4 if op in (0xb9400000,0xb9000000) else 1
                target=page+(((w>>10)&0xfff)*scale)
                typ={0xf9400000:"ADRP_LDR64_target",
                     0xf9000000:"ADRP_STR64_target",
                     0xb9400000:"ADRP_LDR32_target",
                     0xb9000000:"ADRP_STR32_target",
                     0x39400000:"ADRP_LDR8_target",
                     0x39000000:"ADRP_STR8_target"}[op]
                dst=w&31
            if target in TARGETS:
                hits.append({"target_va":hex(target),"target_name":TARGETS[target],
                  "adrp_pc":hex(pc),"consumer_pc":hex(pc+d),"kind":typ,
                  "base_reg":"x"+str(rn),
                  "consumer_reg":str(dst),
                  "distance":d,
                  "status":"STATIC_ADDRESS_REFERENCE__WRITER_IDENTITY_NOT_PROVEN"})
    return hits
def report(main,item):
    sha=hashlib.sha256(main).hexdigest()
    sha_item=hashlib.sha256(item).hexdigest()
    if sha!=SHA_MAIN or sha_item!=SHA_ITEM:raise ValueError("original source SHA256 mismatch")
    fmt,parts=get_sections(main)
    if fmt!="NSO0":raise ValueError("invalid original NSO")
    text=next(s for s in parts if s["name"]=="text")
    code=text["data"];base=text["mem_offset"]
    hits=find_xrefs(code,base)
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    md=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    grouped=defaultdict(list)
    for hit in hits:grouped[hit["target_va"]].append(hit)
    contexts={}
    for va,refs in grouped.items():
        contexts[va]=[]
        # Prefer direct stores and address materializations over reads.
        ordered=sorted(refs,key=lambda h:(0 if "STR" in h["kind"] else 1 if "ADD" in h["kind"] else 2,
                                          int(h["adrp_pc"],16)))
        visited=set()
        for hit in ordered:
            pc=int(hit["adrp_pc"],16)
            if any(abs(pc-q)<0xa0 for q in visited):continue
            visited.add(pc)
            off=pc-base
            start=max(0,(off-0x80)&~3);end=min(len(code),(off+0x120)&~3)
            asm=[{"pc":hex(i.address),"asm":i.mnemonic+" "+i.op_str}
                 for i in md.disasm(code[start:end],base+start)]
            contexts[va].append({"xref":hit,"asm":asm})
            if len(contexts[va])>=24:break
    pointer_targets={}
    for cell in (0x3483c58,0x3484a38):
        raw=None
        for p in parts:
            if p["mem_offset"]<=cell<=p["mem_offset"]+len(p["data"])-8:
                raw=struct.unpack_from("<Q",p["data"],cell-p["mem_offset"])[0]
                break
        pointer_targets[hex(cell)]=hex(raw) if raw is not None else None
    return {
       "status":"ORIGINAL_BSS_DEFAULT_REFERENCE_CANDIDATES__NO_LOADER_PROOF",
       "original_main_sha256":sha,
       "original_item_sha256":sha_item,
       "default_pointer_cells":pointer_targets,
       "default_record_va_difference":hex(0x35b617c-0x35b6128),
       "xref_counts":{hex(v):len(grouped.get(hex(v),[])) for v in TARGETS},
       "all_xrefs":hits,
       "disassembly_contexts":contexts,
       "confirmed_item_default_constructor":False,
       "confirmed_record_wrapper_plus8_source":False,
       "confirmed_00983_table_loader":False,
       "limits":[
           "BSS has no initializer bytes in NSO; look for runtime writes/constructors.",
           "Matching ADRP and later address consumer is a candidate xref, not proof of alive register along all paths.",
           "0x35B6128 and 0x35B617C differ by 0x54 (84), which does NOT show normal item records have 84-byte stride.",
           "No virtual method identity established until V1 object and V2 table vptr stores are recovered."
       ]
    }
def selftest():
    # ADRP X8, target page 0x35b61000 from PC at address 0x35b61000
    global TARGETS
    old=TARGETS
    try:
        TARGETS={0x35b6128:"test"}
        pc=0x35b61000
        # adrp x8,#pc-page; add x8,x8,#0x128
        blob=struct.pack("<2I",0x90000008,0x91000000|(0x128<<10)|(8<<5)|8)
        hits=find_xrefs(blob,pc)
        assert len(hits)==1 and hits[0]["target_va"]=="0x35b6128",hits
    finally:TARGETS=old
    try:report(b"forged",b"forged")
    except ValueError:pass
    else:raise AssertionError("Wrong original SHA was accepted")
    print("PASS BSS ADRP/ADD xref patterns, strict original source gating")
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--main",type=Path,default=MAIN)
    ap.add_argument("--item",type=Path,default=ITEM)
    ap.add_argument("--out",type=Path,default=OUT)
    ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test:selftest();return
    x=report(a.main.read_bytes(),a.item.read_bytes())
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/"native_default_item_BSS_xrefs.json").write_text(json.dumps(x,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    sm={k:x[k] for k in ("status","original_main_sha256","original_item_sha256",
      "default_pointer_cells","default_record_va_difference","xref_counts",
      "confirmed_item_default_constructor","confirmed_record_wrapper_plus8_source",
      "confirmed_00983_table_loader")}
    sm["top_xrefs"]={va:[r["xref"] for r in v[:18]] for va,v in x["disassembly_contexts"].items()}
    (a.out/"native_default_item_BSS_summary.json").write_text(json.dumps(sm,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps(sm,ensure_ascii=False,indent=2)[:19000])
if __name__=="__main__":main()
