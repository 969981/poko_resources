#!/usr/bin/env python3
"""M9.4: exact static AArch64 xrefs to known KIDSOBJDB hash literals in NSO.

This is instruction/address evidence, NOT a verified KIDSOBJDB property lookup.
Only a demonstrated loader, object field and caller chain can promote to FK.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import struct
from collections import defaultdict
from pathlib import Path
try:
    from .trace_native_species_item_callers import get_sections
except ImportError:
    from trace_native_species_item_callers import get_sections

def u32(data,p):
    return struct.unpack_from("<I",data,p)[0]

def decode_adrp(word,pc):
    if word&0x9f000000!=0x90000000:return None
    immlo=(word>>29)&3
    immhi=(word>>5)&0x7ffff
    delta=(immhi<<2)|immlo
    if delta&(1<<20):delta-=1<<21
    return (pc &~0xfff)+(delta<<12),word&31

def decode_load(word):
    # Unsigned immediate LDR Wt, [Xn, #imm12*4].
    # 64-bit LDR X is retained but cannot be called a 32-bit hash load.
    if word&0xffc00000==0xb9400000:
        return ((word>>5)&31,word&31,((word>>10)&0xfff)*4,"LDR_W")
    if word&0xffc00000==0xf9400000:
        return ((word>>5)&31,word&31,((word>>10)&0xfff)*8,"LDR_X")
    return None

def decode_add(word):
    # ADD Xd, Xn, #imm12 optionally shifted by 12.
    if word&0xff000000!=0x91000000:return None
    shift=(word>>22)&3
    if shift not in (0,1):return None
    return ((word>>5)&31,word&31,((word>>10)&0xfff)<<(12 if shift else 0))

def find_references(text_data,text_base,site_by_va,max_per_hash=80):
    """Search bounded ADRP→LDR and ADRP→ADD for exact hash data positions."""
    pages={}
    for va,h in site_by_va.items():
        pages.setdefault(va>>12,{})[va]=h
    out=[]
    limit=defaultdict(int)
    for p in range(0,len(text_data)-3,4):
        word=u32(text_data,p)
        v=decode_adrp(word,text_base+p)
        if v is None:continue
        page,adrpreg=v
        relevant=pages.get(page>>12)
        if not relevant:continue
        # Intervening instructions may change the base register. Only adjacent
        # pairs are marked structural, nonadjacent ones are uncertain.
        for delta in (4,8,12,16,20,24,28,32):
            off=p+delta
            if off+4>len(text_data):break
            nextword=u32(text_data,off)
            ld=decode_load(nextword)
            kind="";r=-1;va=-1
            if ld is not None and ld[0]==adrpreg:
                r=ld[1];va=page+ld[2];kind=ld[3]
            else:
                add=decode_add(nextword)
                if add is None or add[0]!=adrpreg:continue
                r=add[1];va=page+add[2];kind="ADD_ADDRESS"
            h=relevant.get(va)
            if h is None or limit[h]>=max_per_hash:continue
            limit[h]+=1
            out.append({
                "property_hash":f"0x{h:08x}","literal_virtual_offset":va,
                "adrp_pc":text_base+p,"consumer_pc":text_base+off,
                "distance_instructions":delta//4,
                "base_reg":adrpreg,"dst_reg":r,
                "instruction_kind":kind,
                "adrp_word":f"0x{word:08x}",
                "second_word":f"0x{nextword:08x}",
                "evidence":"DIRECT_ADJACENT_ARM64_LITERAL_ACCESS" if delta==4 else
                           "NONADJACENT_AARCH64_POSSIBLE_ACCESS",
                "property_consumer_verified":0,
                "scene_quest_building_fk_verified":0
            })
    return out

def disassembly_windows(data,text_base,sites):
    try:
        from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    except ImportError:
        return [{"pc":r["text_va_movz"],"error":"capstone unavailable"} for r in sites]
    engine=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    out=[]
    for rec in sites:
        first=rec["text_va_movz"]
        p=first-text_base
        if p<0 or p>=len(data):continue
        start=max(0,(p-40)&~3)
        end=min(len(data),(p+112)&~3)
        ins=[{"pc":f"0x{x.address:x}","mnemonic":x.mnemonic,"op_str":x.op_str}
             for x in engine.disasm(data[start:end],text_base+start)]
        out.append({"hash":rec["hash"],"movz_va":first,"movk_va":rec["text_va_movk"],
                    "instruction_evidence":rec["status"],"disassembly":ins,
                    "semantic_property_consumer":"NOT_VERIFIED"})
    return out

def analyze(main_blob,prior):
    kind,sections=get_sections(main_blob)
    if kind!="NSO0":raise ValueError("Expected original Switch2 NSO0 main")
    code=next(x for x in sections if x["name"]=="text")
    site_by_va={}
    for record in prior["raw_hash_matches"]:
        if record["section"]!="rodata":continue
        h=int(record["hash"],16)
        for addr in record["first_virtual_offsets"]:
            site_by_va[addr]=h
    xrefs=find_references(code["data"],code["mem_offset"],site_by_va)
    windows=disassembly_windows(code["data"],code["mem_offset"],
                                prior["arm64_immediate_candidates"])
    return {
        "status":"M9_ARM64_DIRECT_LITERAL_SITES_ONLY",
        "original_main_sha256":hashlib.sha256(main_blob).hexdigest(),
        "original_static_probe_sha256":hashlib.sha256(json.dumps(prior,sort_keys=True).encode()).hexdigest(),
        "rodata_hash_sites_checked":len(site_by_va),
        "direct_arm64_xref_records":len(xrefs),
        "adjacent_direct_literal_access_count":sum(r["distance_instructions"]==1 for r in xrefs),
        "arm64_code_xrefs":xrefs,
        "movz_movk_instruction_windows":windows,
        "actual_kidsobjdb_field_consumer_confirmed":0,
        "verified_scene_quest_building_text_foreign_keys":0,
        "limitations":[
            "A code instruction accessing a matching hash literal does not identify KIDSOBJDB lookup semantics.",
            "Nonadjacent ADRP+LDR/ADD uses require register clobber and control flow verification.",
            "Only the bounded first samples of aligned rodata hashes from M9.3 were probed.",
            "No Lua/script side property access is claimed without native script source.",
        ]
    }

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--main",type=Path,required=True)
    ap.add_argument("--prior",type=Path,required=True)
    ap.add_argument("--dest",type=Path,required=True)
    args=ap.parse_args()
    prior=json.loads(args.prior.read_text(encoding="utf-8"))
    blob=args.main.read_bytes()
    if hashlib.sha256(blob).hexdigest()!=prior["original_exefs_sha256"]:
        raise ValueError("ExeFS SHA-256 changed from M9.3")
    result=analyze(blob,prior)
    args.dest.mkdir(parents=True,exist_ok=True)
    (args.dest/"exefs_property_hash_xrefs.json").write_text(
       json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    fields=["property_hash","literal_virtual_offset","adrp_pc","consumer_pc",
       "distance_instructions","base_reg","dst_reg","instruction_kind",
       "adrp_word","second_word","evidence","property_consumer_verified",
       "scene_quest_building_fk_verified"]
    with (args.dest/"exefs_property_hash_xrefs.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        w.writerows(result["arm64_code_xrefs"])
    print(json.dumps({k:result[k] for k in ("status","rodata_hash_sites_checked",
          "direct_arm64_xref_records","adjacent_direct_literal_access_count",
          "actual_kidsobjdb_field_consumer_confirmed")},indent=2))

if __name__=="__main__":main()
