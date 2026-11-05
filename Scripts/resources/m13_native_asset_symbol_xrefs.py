#!/usr/bin/env python3
"""Find native Pokémon/Item/asset loader symbols and their actual AArch64 xrefs.

Source: original Pokopia 2.0.1 NSO0 only. The module records candidates for
subsequent register-level reverse engineering; it never asserts species IDs,
Item enum semantics, or arbitrary string names as source file bindings.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import struct
from collections import Counter,defaultdict
from pathlib import Path
from .trace_native_species_item_callers import get_sections

SHA="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
TOKENS=(b"pokemon",b"pokemo",b"pokedex",b"pokekind",b"pokemonkind",
        b"item",b"recipe",b"craft",b"texinfo",b"g1t",b"sprite",b"portrait",b"texture")
KEEP_SYMBOLS=12000
INDICATORS=[
    ("POKEMON_ID",r"(pokemon.*(?:dex|id|kind|list|model|icon|image|texture|portrait|name)|(?:dex|kind|species|icon|image|portrait).*pokemon|pokedex|pokekind|icon_poke)"),
    ("ITEM_METADATA",r"(?:item.*(?:data|table|kind|type|class|category|name|list|group|icon|resource)|(?:kind|type|class|category|name|list|group).*item)"),
    ("RESOURCE_LOADER",r"(?:texture|texinfo|g1t|sprite|portrait|resource.*item|asset.*pokemon)"),
    ("CRAFTING",r"(?:craft|recipe)"),
]

def classify(s):
    for group,pattern in INDICATORS:
        if re.search(pattern,s,re.IGNORECASE):
            return group
    return "OTHER_TEXT"

def find_strings(ro):
    raw=ro["data"]
    seen=set()
    entries=[]
    # Null-terminated printable strings; preserve original virtual addresses.
    for match in re.finditer(rb"[\x20-\x7e]{4,220}\x00",raw):
        text=match.group(0)[:-1]
        if not any(tok in text.lower() for tok in TOKENS):
            continue
        decoded=text.decode("ascii","replace")
        loc=ro["mem_offset"]+match.start()
        if loc in seen: raise ValueError("Duplicate rodata address")
        seen.add(loc)
        entries.append({"rva":loc,"text":decoded,"category":classify(decoded),
                        "rodata_local_offset":match.start()})
    return entries

def scan_xrefs(code,base,targets):
    index={int(s["rva"]):s for s in targets}
    pages=set(x>>12 for x in index)
    refs=[]
    seen=set()
    end=len(code)&~3
    for off in range(0,end,4):
        word=struct.unpack_from("<I",code,off)[0]
        pc=base+off
        if (word&0x9f000000)==0x90000000:
            imm=(((word>>5)&0x7ffff)<<2)|((word>>29)&3)
            if imm&(1<<20):imm-=1<<21
            page=(pc&~4095)+(imm<<12)
            if (page>>12) not in pages:continue
            reg=word&31
            for stride in (4,8,12,16,20):
                if off+stride>=end:break
                nextword=struct.unpack_from("<I",code,off+stride)[0]
                if (nextword&0xff000000)!=0x91000000 or ((nextword>>5)&31)!=reg:
                    continue
                shift=(nextword>>22)&3
                if shift not in (0,1):continue
                immediate=((nextword>>10)&4095)<<(12 if shift else 0)
                address=page+immediate
                if address not in index:continue
                key=(pc+stride,address)
                if key in seen:continue
                seen.add(key)
                t=index[address]
                refs.append({"pc":pc+stride,"adrp_pc":pc,"literal_rva":address,
                             "text":t["text"],"category":t["category"],
                             "uses":"ADRP_ADD_CANDIDATE","base_reg":reg})
        elif (word&0x9f000000)==0x10000000:
            imm=(((word>>5)&0x7ffff)<<2)|((word>>29)&3)
            if imm&(1<<20):imm-=1<<21
            address=pc+imm
            if address in index:
                t=index[address]
                refs.append({"pc":pc,"adrp_pc":None,"literal_rva":address,
                             "text":t["text"],"category":t["category"],
                             "uses":"ADR_CANDIDATE","base_reg":word&31})
    return sorted(refs,key=lambda x:(x["category"],x["text"],x["pc"]))

def run(blob):
    if hashlib.sha256(blob).hexdigest()!=SHA:
        raise ValueError("Original 2.0.1 NSO main SHA256 does not match")
    kind,parts=get_sections(blob)
    if kind!="NSO0":
        raise ValueError("Expected NSO0 source")
    text=next(x for x in parts if x["name"]=="text")
    ro=next(x for x in parts if x["name"]=="rodata")
    symbols=find_strings(ro)
    if len(symbols)>KEEP_SYMBOLS:
        raise ValueError(f"Too many native source symbols: {len(symbols)}")
    if not any(x["text"]=="pokemon_dex_id" for x in symbols):
        raise ValueError("The known original pokemon_dex_id anchor was not found")
    refs=scan_xrefs(text["data"],text["mem_offset"],symbols)
    by_category=Counter(x["category"] for x in symbols)
    by_xref_category=Counter(x["category"] for x in refs)
    top=sorted(refs,key=lambda x:(
        {"POKEMON_ID":0,"ITEM_METADATA":1,"RESOURCE_LOADER":2,"CRAFTING":3,"OTHER_TEXT":4}.get(x["category"],8),
        x["text"].lower(),x["pc"]))
    return {"status":"ORIGINAL_RODATA_AND_ARM64_REFERENCE_GRAPH__SPECIES_UNVERIFIED",
            "game_version":"2.0.1","exe_sha256":SHA,
            "text_bytes":len(text["data"]),"rodata_bytes":len(ro["data"]),
            "symbol_count":len(symbols),"xref_count":len(refs),
            "symbol_category_counts":dict(by_category),
            "xref_category_counts":dict(by_xref_category),
            "interesting_xrefs":[{"name":x["text"],"rva":f"0x{x['pc']:x}",
                                 "category":x["category"]}
                                for x in top[:120]],
            "native_species_bindings_verified":0,
            "item_0x26_semantics_verified":False,
            "warning":"Strings/ADRP references may be UI, logging, serializer, tooling or texture loaders; positive ID binding requires concrete native dataflow.",
            },symbols,refs

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--main",type=Path,default=Path("2.0.1/exefs/main"))
    p.add_argument("--out",type=Path,default=Path("UnPack/2.0.1/Resources/Pokemon/NativeCallers/M13"))
    args=p.parse_args()
    report,strings,xrefs=run(args.main.read_bytes())
    args.out.mkdir(parents=True,exist_ok=True)
    for name,rows,columns in (
        ("native_asset_symbols.csv",strings,("rva","text","category","rodata_local_offset")),
        ("native_asset_string_xrefs.csv",xrefs,("pc","adrp_pc","literal_rva","text","category","uses","base_reg")),
    ):
        with (args.out/name).open("w",encoding="utf-8",newline="") as f:
            w=csv.DictWriter(f,fieldnames=columns)
            w.writeheader()
            w.writerows(rows)
    (args.out/"m13_summary.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="interesting_xrefs"},ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
