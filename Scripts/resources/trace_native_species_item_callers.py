#!/usr/bin/env python3
"""Static-only investigation of original Switch2 ExeFS main.

Recovers NSO0 text/rodata with strict LZ4 bounds, surveys real icon_poke_
strings and searches ARM64 ADRP+ADD references.  Separately lists ldrb #0x26
instructions for later manual tracing of the candidate item type byte.

An address match is not itself species identity or material enum proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from collections import deque
from pathlib import Path

MAX_SEGMENT=256*1024*1024
TEXT_HINTS=(b"icon_poke", b"item_type", b"itemkind", b"material", b"craft",b"pokemon")
printable=re.compile(rb"[\x20-\x7e]{5,400}(?:\x00|$)")


def u32(b,p):
    if p<0 or p+4>len(b):
        raise ValueError(f"NSO field missing at {p:#x}")
    return struct.unpack_from("<I",b,p)[0]


def get_sections(blob):
    if blob[:4]==b"NSO0":
        flags=u32(blob,0x0c)
        result=[]
        for i,name in enumerate(("text","rodata","data")):
            pos=0x10+i*0x10
            fileoff=u32(blob,pos)
            memoff=u32(blob,pos+4)
            unpacked=u32(blob,pos+8)
            packed=u32(blob,0x60+4*i)
            compressed=bool(flags & (1<<i))
            n=packed if compressed else unpacked
            if not 0<=n<=MAX_SEGMENT or not 0<=unpacked<=MAX_SEGMENT or fileoff+n>len(blob):
                raise ValueError(f"invalid NSO0 {name} section bounds")
            buf=blob[fileoff:fileoff+n]
            if compressed:
                try:
                    import lz4.block
                except ImportError as ex:
                    raise RuntimeError("NSO compressed sections need pip install lz4") from ex
                buf=lz4.block.decompress(buf,uncompressed_size=unpacked)
            if len(buf)!=unpacked:
                raise ValueError(f"{name} decompressed size mismatch")
            result.append({"name":name,"mem_offset":memoff,
                "file_offset":fileoff,"compressed":compressed,
                "size":len(buf),"data":buf})
        return "NSO0",result
    if blob[:4]==b"\x7fELF":
        # Avoid pretending an ELF file has linear 1:1 section virtual offsets.
        return "ELF_UNMAPPED",[{"name":"file_image",
            "mem_offset":0,"file_offset":0,"compressed":False,
            "size":len(blob),"data":blob}]
    return f"UNKNOWN_{blob[:8].hex()}",[{"name":"raw_blob","mem_offset":0,
        "file_offset":0,"compressed":False,"size":len(blob),"data":blob}]


def scan_strings(parts):
    found=[]
    for part in parts:
        if part["name"]=="text":
            continue
        blob=part["data"]
        for match in printable.finditer(blob):
            raw=match.group(0).rstrip(b"\0")
            low=raw.lower()
            if not any(token in low for token in TEXT_HINTS):
                continue
            found.append({"section":part["name"],"raw_file_offset":part["file_offset"]+match.start(),
                "virtual_offset":part["mem_offset"]+match.start(),
                "text":raw[:220].decode("ascii","replace"),
                "target_group":"POKEMON_ICON" if b"icon_poke" in low
                    else ("MATERIAL_CRAFT_REFERENCE" if any(w in low for w in (b"material",b"craft",b"item_type",b"itemkind"))
                          else "OTHER_POKEMON_TEXT")})
    return found


def arm64_scan(text_segment,string_targets,max_type_loads=300):
    try:
        from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
        from capstone.arm64_const import ARM64_OP_IMM,ARM64_OP_REG,ARM64_OP_MEM
    except ImportError as exc:
        raise RuntimeError("ARM64 static scan requires capstone>=5") from exc
    md=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    md.detail=True
    refs=[]
    candidate_loads=[]
    # ADRP may be followed by one or more independent instructions before ADD.
    active=deque(maxlen=20)
    prior=deque(maxlen=8)
    pages={t["virtual_offset"]//4096 for t in string_targets}
    targets={t["virtual_offset"]:t for t in string_targets}
    for inst in md.disasm(text_segment["data"],text_segment["mem_offset"]):
        prev=list(prior)
        mnemonic=inst.mnemonic
        operands=inst.operands
        if mnemonic=="adrp" and len(operands)>=2 and operands[0].type==ARM64_OP_REG and operands[1].type==ARM64_OP_IMM:
            # Capstone IMM is page-absolute in ARM64 disassembly.
            page=int(operands[1].imm)
            if page//4096 in pages:
                active.append((inst.address,operands[0].reg,page))
        elif mnemonic=="adr" and len(operands)>=2 and operands[1].type==ARM64_OP_IMM:
            v=int(operands[1].imm)
            if v in targets:
                refs.append({"address":inst.address,"kind":"ADR","string":targets[v]["text"],
                             "target_va":v,"disasm":f"{inst.mnemonic} {inst.op_str}"})
        elif mnemonic=="add" and len(operands)>=3 and operands[0].type==ARM64_OP_REG and operands[1].type==ARM64_OP_REG and operands[2].type==ARM64_OP_IMM:
            dst,src,imm=operands[:3]
            for at,reg,page in list(active):
                if src.reg==reg and inst.address-at<=20:
                    v=page+int(imm.imm)
                    if v in targets:
                        refs.append({"address":inst.address,"adrp_address":at,
                                     "kind":"ADRP_ADD_STRING","string":targets[v]["text"],
                                     "target_va":v,"disasm":f"{inst.mnemonic} {inst.op_str}",
                                     "previous_instructions":[f"{x.mnemonic} {x.op_str}" for x in prev]})
        if len(candidate_loads)<max_type_loads and mnemonic.startswith("ldrb"):
            # A field access at struct offset +0x26 is a candidate, not proof
            # the base register is pointing at a 68-byte item record.
            for op in operands:
                if op.type==ARM64_OP_MEM and int(op.mem.disp)==0x26:
                    candidate_loads.append({
                        "address":inst.address,"instruction":f"{mnemonic} {inst.op_str}",
                        "previous_instructions":[f"{x.mnemonic} {x.op_str}" for x in prev]
                    })
        prior.append(inst)
        while active and inst.address-active[0][0]>20:
            active.popleft()
    return refs,candidate_loads


def analyze(blob, max_xref=100):
    kind,parts=get_sections(blob)
    matches=scan_strings(parts)
    icon=[x for x in matches if x["target_group"]=="POKEMON_ICON"]
    others=[x for x in matches if x["target_group"]!="POKEMON_ICON"]
    refs,loads=[],[]
    code=next((p for p in parts if p["name"]=="text"),None)
    if code and icon:
        refs,loads=arm64_scan(code,icon)
    elif code:
        # Without a native icon string target, ldrb candidates alone cannot
        # identify the item table. Keep that limitation explicit.
        refs,loads=arm64_scan(code,[])
    return {
        "status":"STATIC_FORENSICS_ONLY__NATIVE_ID_NOT_PROVEN",
        "original_main_sha256":hashlib.sha256(blob).hexdigest(),
        "format":kind,
        "header_bytes_hex":blob[:32].hex(),
        "segments":[{k:v for k,v in p.items() if k!="data"} for p in parts],
        "pokemon_literal_count":len(icon),
        "pokemon_literals":icon[:max_xref],
        "other_related_string_count":len(others),
        "other_related_strings":others[:max_xref],
        "arm64_string_xrefs_count":len(refs),
        "arm64_string_xrefs":refs[:max_xref],
        "ldrb_struct_offset_0x26_samples":loads[:max_xref],
        "species_id_confirmed":0,
        "material_enum_confirmed":False,
        "warning":"String or ldrb offsets in ExeFS are candidate anchors only. Confirm struct base, caller, ID input dataflow and runtime bindings before assigning any species/material type."
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--main",type=Path,default=Path("2.0.1/exefs/main"))
    p.add_argument("--output",type=Path,default=Path("UnPack/2.0.1/Resources/Pokemon/NativeCallers/main_string_xrefs.json"))
    args=p.parse_args()
    report=analyze(args.main.read_bytes())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("status","format","segments",
        "pokemon_literal_count","other_related_string_count",
        "arm64_string_xrefs_count","species_id_confirmed")},ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
