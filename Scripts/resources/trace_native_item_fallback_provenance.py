#!/usr/bin/env python3
"""M20: compare original NSO fallback-pointer targets with 00983.bin records.

Source-specific hypothesis, not an automatic declaration that runtime item
record pointers alias the physical decoded LINKDATA array.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from collections import Counter
from pathlib import Path
from Scripts.resources.trace_native_species_item_callers import get_sections

MAIN=Path("2.0.1/exefs/main")
ITEM=Path("UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin")
OUT=Path("UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M20")
MAIN_SHA="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
ITEM_SHA="2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f"
FALLBACK_CELLS={
    "C7_item_default_record":0x3483c58,
    "C9_type_default_record":0x3484a38,
    "related_default_0x3484_8f8":0x34848f8,
    "related_default_0x3484_ba8":0x3484ba8,
    "related_default_0x3485_0b0":0x348500b0,
}

def image_at(parts,va,n):
    for p in parts:
        if p["mem_offset"]<=va and va+n<=p["mem_offset"]+len(p["data"]):
            o=va-p["mem_offset"]
            return p["name"],p["data"][o:o+n]
    return None,None

def records(blob):
    if len(blob)!=64+4600*68 or struct.unpack_from("<II",blob,0)!=(4600,3):
        raise ValueError("Not original item header/count/stride")
    return [blob[64+68*i:64+68*(i+1)] for i in range(4600)]

def similarity(target,entries):
    if target is None or len(target)<68:return {}
    full=[i for i,record in enumerate(entries) if record==target[:68]]
    exact_prefix=[i for i,record in enumerate(entries)
                  if record[:24]==target[:24] and record[:24]!=b"\0"*24]
    prefix_distance=[]
    for i,record in enumerate(entries):
        same=sum(a==b for a,b in zip(target[:68],record))
        if same>=60:prefix_distance.append((same,i))
    prefix_distance.sort(reverse=True)
    return {"exact_68_byte_ids":full[:20],
            "exact_nonzero_24byte_prefix_ids":exact_prefix[:20],
            "top_60of68_matches":[{"id":i,"equal_bytes":n}
                                   for n,i in prefix_distance[:8]]}

def test_embedded_records(parts,entries):
    # Nonzero sample ids. Looking for a byte-identical embedded record, not
    # merely a matching field value or a single identical 4-byte word.
    selected=[1,2,3,4,7,8,16,32,64,128,256,512,777,983,1024,1500,2000,3000,4000,4599]
    results=[]
    for id in selected:
        row=entries[id]
        if row==b"\0"*68:continue
        for p in parts:
            if p["name"]=="text":continue
            data=p["data"]
            start=0
            while True:
                start=data.find(row,start)
                if start<0:break
                results.append({"item_id":id,"section":p["name"],"va":hex(p["mem_offset"]+start),
                                "match_kind":"EXACT_68_BYTES","record_sha256":hashlib.sha256(row).hexdigest()})
                start+=1
                if len(results)>100:return results
    return results

def inspect(main,item):
    a=hashlib.sha256(main).hexdigest()
    b=hashlib.sha256(item).hexdigest()
    if a!=MAIN_SHA or b!=ITEM_SHA:raise ValueError("Original executable/file hash mismatch")
    kind,parts=get_sections(main)
    if kind!="NSO0":raise ValueError("Not original NSO")
    entries=records(item)
    pointers=[]
    for name,cell in FALLBACK_CELLS.items():
        section,data=image_at(parts,cell,8)
        if data is None:
            pointers.append({"name":name,"cell_va":hex(cell),"status":"CELL_NOT_MAPPED"})
            continue
        val=struct.unpack("<Q",data)[0]
        target_section,target=image_at(parts,val,68) if val else (None,None)
        if target is None:
            status="ZERO_INITIALIZED_RUNTIME_POINTER" if val==0 else "NOT_IN_STATIC_NSO_SEGMENTS"
        else:
            status="POINTER_TARGET_IN_STATIC_NSO"
        pointers.append({"name":name,"cell_va":hex(cell),
                         "cell_section":section,"cell_raw_hex":data.hex(),
                         "pointer_raw_va":hex(val),"target_section":target_section,
                         "status":status,"target_68_hex":target.hex() if target else None,
                         "record_matches":similarity(target,entries)})
    embedded=test_embedded_records(parts,entries)
    return {"status":"FALLBACK_POINTER_AND_EMBEDDED_RECORD_SOURCE_AUDIT",
            "original_main_sha256":a,"original_item_sha256":b,
            "item_rows":4600,"item_stride":68,
            "fallback_cells":pointers,"embedded_exact_68byte_records":embedded,
            "fallback_pointer_is_proven_item_record":False,
            "V2_getter_0x30_source_proven":False,
            "item_type_enum_proven":False,
            "limits":[
                "Fallback pointer cells can be initialized during startup, not visible in static NSO files.",
                "A static pointer's bytewise equality to a record (if found) is correlation; it still needs constructor and caller provenance.",
                "Absent embedded matches do not exclude 00983.bin being read from LINKDATA at runtime.",
                "Do not infer V2 method identity from C7 4600/68 matching alone."
            ]}

def selftest():
    fake=bytearray(64+4600*68)
    struct.pack_into("<II",fake,0,4600,3)
    fake[64+68*12:64+68*12+68]=bytes(range(68))
    assert records(fake)[12]==bytes(range(68))
    assert similarity(bytes(range(68)),records(fake))["exact_68_byte_ids"]==[12]
    try:inspect(b"fake",bytes(fake))
    except ValueError:pass
    else:raise AssertionError("Accepted invalid NSO")
    print("PASS full record comparison, original source gating and sample fixtures")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--main",type=Path,default=MAIN)
    p.add_argument("--item",type=Path,default=ITEM)
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:selftest();return
    r=inspect(a.main.read_bytes(),a.item.read_bytes())
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/"item_fallback_source_audit.json").write_text(
        json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    summary={k:r[k] for k in ("status","original_main_sha256","original_item_sha256",
        "item_rows","item_stride","fallback_pointer_is_proven_item_record",
        "V2_getter_0x30_source_proven","item_type_enum_proven",
        "fallback_cells","embedded_exact_68byte_records")}
    (a.out/"item_fallback_source_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps(summary,ensure_ascii=False,indent=2)[:25000])
if __name__=="__main__":main()
