#!/usr/bin/env python3
"""M22: dereference ONLY original native descriptor IDs 982/983/984.

A 40-byte engine descriptor is *not* a 68-byte item record. Check pointer
fields to read original ASCII/UTF8 resource/type metadata, rather than
assuming 983 equals the physical file 00983.bin.
"""
from __future__ import annotations
import argparse,hashlib,json,struct,string
from pathlib import Path
from Scripts.resources.trace_native_species_item_callers import get_sections

MAIN=Path("2.0.1/exefs/main")
ITEM=Path("UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin")
OUT=Path("UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M22")
SHA_MAIN="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
SHA_ITEM="2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f"
DESCRIPTOR_BASE=0x3354500
STRIDE=0x28
IDS=[0,982,983,984,1194]

def read_va(parts,va,size):
    for p in parts:
        start=p["mem_offset"]
        b=p["data"]
        if start<=va and va+size<=start+len(b):
            return b[va-start:va-start+size],p["name"]
    return None,None
def as_cstring(parts,va):
    b,section=read_va(parts,va,196)
    if b is None:return {"mapped":False}
    end=b.find(b"\0")
    raw=b[:end if end>=0 else len(b)]
    good=bool(raw) and len(raw)<=180 and all((c in range(0x20,0x7f) or c in (9,10,13)) for c in raw)
    return {"mapped":True,"section":section,"string":raw.decode("utf8","replace") if good else None,
            "hex_prefix":b[:64].hex(),"text_is_printable":good,
            "nul_terminated_in_window":end>=0}
def pointer_info(parts,va,offset,val):
    entry={"field_offset":hex(offset),"raw_u64":hex(val)}
    if val==0:return {**entry,"kind":"ZERO"}
    # 64-bit offsets with high bits are often type/ID pairs, not pointers.
    if val>=1<<32:return {**entry,"kind":"NON_POINTER_OR_COMPOSITE_U64"}
    info=as_cstring(parts,val)
    entry.update(info)
    if info.get("mapped"):
        raw,_=read_va(parts,val,32)
        entry["u32_le_sample"]=[hex(x) for x in struct.unpack("<8I",raw)]
    entry["kind"]="MAPPED_IMAGE_ADDRESS" if info.get("mapped") else "UNMAPPED"
    return entry
def inspect(main,item):
    ma=hashlib.sha256(main).hexdigest()
    it=hashlib.sha256(item).hexdigest()
    if ma!=SHA_MAIN or it!=SHA_ITEM:raise ValueError("Incorrect original SHA256")
    if len(item)!=64+4600*68 or struct.unpack_from("<II",item,0)!=(4600,3):
        raise ValueError("Incorrect original item table count/stride")
    kind,parts=get_sections(main)
    if kind!="NSO0":raise ValueError("Unexpected format")
    out=[]
    for id in IDS:
        va=DESCRIPTOR_BASE+STRIDE*id
        raw,seg=read_va(parts,va,40)
        if raw is None:raise ValueError("Unmapped original descriptor "+hex(va))
        fields=[struct.unpack_from("<Q",raw,off)[0] for off in (0,8,16,24,32)]
        refs=[pointer_info(parts,va,i*8,val) for i,val in enumerate(fields)]
        out.append({"id":id,"descriptor_va":hex(va),"section":seg,"raw_40_hex":raw.hex(),
                    "raw_40_sha256":hashlib.sha256(raw).hexdigest(),
                    "u32_words":[hex(x) for x in struct.unpack("<10I",raw)],
                    "u64_interpretations":refs})
    return {"status":"NATIVE_983_40BYTE_DESCRIPTOR_POINTER_REFERENTS",
            "original_main_sha256":ma,"original_item_sha256":it,
            "descriptor_base_va":hex(DESCRIPTOR_BASE),"descriptor_stride":40,
            "descriptors":out,
            "confirmed_983_is_00983_file":False,
            "confirmed_983_pointer_is_4600x68_table":False,
            "confirmed_V1_V2_constructor_link":False,
            "notes":[
              "Resource-name strings, if found, are descriptors; verify which resource ID namespace maps to LD_C0_R.BIN.",
              "u64 values may be composite IDs and flags, not pointers: treating all as addresses is invalid.",
              "Mapped strings alone cannot establish that V2 get(ID) uses this descriptor's decoded bytes."
            ]}
def selftest():
    dummy=[{"mem_offset":0x1000,"name":"rodata","data":b"item\x00"+b"\x00"*251}]
    assert as_cstring(dummy,0x1000)["string"]=="item"
    assert pointer_info(dummy,0x0,0,0)["kind"]=="ZERO"
    assert pointer_info(dummy,0x0,0,0x8000000000003d7)["kind"]=="NON_POINTER_OR_COMPOSITE_U64"
    try:inspect(b"no",b"no")
    except ValueError:pass
    else:raise AssertionError("Forged original inputs accepted")
    print("PASS strict original SHA guarding, string and composite-pointer fixtures")
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
    (a.out/"descriptor_983_referents.json").write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    brief={k:r[k] for k in ("status","original_main_sha256","original_item_sha256",
                            "descriptor_base_va","descriptor_stride",
                            "confirmed_983_is_00983_file","confirmed_983_pointer_is_4600x68_table",
                            "confirmed_V1_V2_constructor_link")}
    brief["descriptors"]=r["descriptors"]
    (a.out/"descriptor_983_referents_summary.json").write_text(json.dumps(brief,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps(brief,ensure_ascii=False,indent=2)[:22000])
if __name__=="__main__":main()
