#!/usr/bin/env python3
"""Static ExeFS reconnaissance for M9.3 RNK/IRNK and typed property hashes.

A hash literal or MOVZ+MOVK pair is not evidence a game callback consumes a
specific KIDSOBJDB property. This tool emits bounded candidates ONLY.
"""
from __future__ import annotations
import argparse
import collections
import csv
import hashlib
import json
import struct
from pathlib import Path
try:
    from .trace_native_species_item_callers import get_sections, arm64_scan
except ImportError:
    from trace_native_species_item_callers import get_sections, arm64_scan

MAGICS=(b"_RNK0000",b"IRNK0000",b"_DOK0000",b"IDOK0000",b"KIDSOBJDB")

def u32(data,pos):return struct.unpack_from("<I",data,pos)[0]
def normalize(hexkey):
    return int(str(hexkey).lower().removeprefix("0x"),16)

def select_hashes(typed_report,rnk_report,limit=120):
    counter=collections.Counter()
    for row in typed_report.get("files",[]):
        for h,n in row.get("candidate_property_hash_histogram",{}).items():
            counter[normalize(h)]+=n
    hashes=[h for h,_ in counter.most_common(limit)]
    for h in rnk_report["source_name_hashes"].values():
        hashes.append(normalize(h))
    return sorted(set(hashes)),counter

def immediate_pairs(data,base,wanted,limit_per_hash=12):
    """Detect MOVZ low16 -> MOVK high16 on same register within 12 insns.

    Without flow analysis this is only an immediate reconstruction candidate.
    """
    last={}
    hits=collections.defaultdict(list)
    for off in range(0,len(data)-3,4):
        word=u32(data,off)
        kind=word&0x7F800000
        reg=word&31
        sf=(word>>31)&1
        hw=(word>>21)&3
        imm=(word>>5)&0xffff
        key=(reg,sf)
        if kind==0x52800000 and hw==0:
            last[key]=(off,imm)
        elif kind==0x72800000 and hw==1:
            prior=last.get(key)
            if prior and 0<off-prior[0]<=48:
                val=(imm<<16)|prior[1]
                if val in wanted and len(hits[val])<limit_per_hash:
                    hits[val].append({"text_va_movz":base+prior[0],
                                      "text_va_movk":base+off,
                                      "move_reg":reg,"code_words":[f"{u32(data,prior[0]):08x}",f"{word:08x}"],
                                      "status":"ARM64_IMMEDIATE_PAIR_NO_DATAFLOW"})
        elif kind==0x52800000:
            last.pop(key,None)
    return hits

def inspect(main_data,typed_report,rnk_report,max_samples=10):
    kind,sections=get_sections(main_data)
    hashes,counter=select_hashes(typed_report,rnk_report)
    selected=set(hashes)
    result={
        "status":"EXEFS_STATIC_HASH_RECONNAISSANCE_ONLY",
        "original_exefs_sha256":hashlib.sha256(main_data).hexdigest(),
        "main_format":kind,
        "inspected_hashes":len(hashes),
        "section_summary":[{k:v for k,v in x.items() if k!="data"} for x in sections],
        "magic_literals":[],
        "raw_hash_matches":[],
        "arm64_immediate_candidates":[],
        "magic_string_adrp_xrefs":[],
        "confirmed_kidsobjdb_property_consumers":0,
        "confirmed_scene_quest_building_text_foreign_keys":0,
        "warnings":[
            "u32 bytes equal to a property hash may be data or an instruction, not a consumer.",
            "MOVZ+MOVK pair does not establish a property lookup without register/call dataflow.",
            "ADRP+ADD references to a magic string do not identify a specific property semantic.",
            "No text foreign keys are created by this static survey."
        ]
    }
    anchors=[]
    # Collect magic-string targets from *all* sections first; NSO text is
    # encountered before rodata, where most literal strings actually live.
    for section in sections:
        data=section["data"];base=section["mem_offset"]
        for magic in MAGICS:
            pos=0;count=0
            while count<max_samples:
                found=data.find(magic,pos)
                if found<0:break
                va=base+found
                result["magic_literals"].append(
                    {"section":section["name"],"virtual_offset":va,"literal":magic.decode()})
                anchors.append({"virtual_offset":va,"text":magic.decode()})
                count+=1;pos=found+len(magic)
    for section in sections:
        data=section["data"];base=section["mem_offset"]
        # This is exactly aligned u32 data, not arbitrary shifted 4-byte hits.
        counts=collections.Counter()
        samples=collections.defaultdict(list)
        for off in range(0,len(data)-3,4):
            val=u32(data,off)
            if val in selected:
                counts[val]+=1
                if len(samples[val])<max_samples:samples[val].append(base+off)
        for h,n in sorted(counts.items()):
            result["raw_hash_matches"].append({"hash":f"0x{h:08x}",
                "section":section["name"],"aligned_u32_matches":n,
                "first_virtual_offsets":samples[h],
                "status":"STATIC_LITERAL_NO_CALLER"})
        if section["name"]=="text":
            pairs=immediate_pairs(data,base,selected)
            for h,records in sorted(pairs.items()):
                for x in records:
                    result["arm64_immediate_candidates"].append({"hash":f"0x{h:08x}",**x})
            # The existing 2.0.1 AArch64 parser checks ADRP+ADD instruction
            # masks. Store only magic-string references, not all nearby LDRB.
            refs,_,_ = arm64_scan(section,anchors,max_type_loads=0)
            result["magic_string_adrp_xrefs"]=refs[:250]
    result["tracked_property_hashes"]=[{"hash":f"0x{h:08x}","typed_local_oid_matches":counter[h]} for h in hashes]
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--main",type=Path,required=True)
    ap.add_argument("--typed-report",type=Path,required=True)
    ap.add_argument("--rnk-report",type=Path,required=True)
    ap.add_argument("--dest",type=Path,required=True)
    args=ap.parse_args()
    result=inspect(args.main.read_bytes(),
        json.loads(args.typed_report.read_text(encoding="utf-8")),
        json.loads(args.rnk_report.read_text(encoding="utf-8")))
    args.dest.mkdir(parents=True,exist_ok=True)
    (args.dest/"exefs_property_hash_consumers.json").write_text(
        json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    with (args.dest/"exefs_static_hash_sites.csv").open("w",encoding="utf-8",newline="") as file:
        cols=["hash","section","aligned_u32_matches","first_virtual_offsets","status"]
        writer=csv.DictWriter(file,fieldnames=cols);writer.writeheader()
        for row in result["raw_hash_matches"]:
            row={**row,"first_virtual_offsets":json.dumps(row["first_virtual_offsets"])}
            writer.writerow(row)
    print(json.dumps({k:result[k] for k in ("status","original_exefs_sha256",
                 "inspected_hashes","confirmed_kidsobjdb_property_consumers",
                 "confirmed_scene_quest_building_text_foreign_keys")},indent=2))

if __name__=="__main__":main()
