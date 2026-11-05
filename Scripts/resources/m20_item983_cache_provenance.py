#!/usr/bin/env python3
"""M20: native 983 resource-cache and item virtual accessor provenance survey.

A byte-verified ID lookup/cache chain and a separate 4600-ID item consumer
chain do not establish that they share a physical 00983.bin backing buffer.
This investigation only promotes links established from raw AArch64 bytes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.trace_native_item_resource_loader import (
    FIRST, SECOND, PAGE, DISP, CALLERS, chain, readword,
    adrp_target, bl_target, verify_indexed_lookup_table,
)
from Scripts.resources.trace_native_item_provenance import MAIN_SHA, ITEM_SHA
from Scripts.resources.trace_native_item_consumers import CHECKS as ITEM_CONSUMERS

TABLE_BASE=0x3354500
TABLE_STRIDE=0x28
TABLE_CAP=0x4ab
ITEM_ID=983
TARGET_GLOBAL=PAGE+DISP
LOOKUPS=(FIRST,SECOND,0x1444210,0x1471990)
ORIGINAL_ITEM_RECORD_COUNT=4600
ORIGINAL_ITEM_RECORD_SIZE=68
OUT=Path("UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M20")


def section_read(parts, addr, length):
    for section in parts:
        base=section["mem_offset"]
        if base<=addr and addr+length<=base+len(section["data"]):
            return section["data"][addr-base:addr-base+length],section["name"]
    raise ValueError(f"UNMAPPED_NSO_VIRTUAL_RANGE:{addr:#x}+{length:#x}")


def inspect_descriptor(parts, index):
    if not 0<=index<TABLE_CAP:
        raise ValueError("NATIVE_REGISTRY_ID_OUT_OF_BOUNDS")
    address=TABLE_BASE+TABLE_STRIDE*index
    raw,section=section_read(parts,address,TABLE_STRIDE)
    words=struct.unpack("<10I",raw)
    return {
        "registry_index":index,"descriptor_rva":hex(address),
        "section":section,"original_40_bytes_hex":raw.hex(),
        "original_40_sha256":hashlib.sha256(raw).hexdigest(),
        "u32_words_le":[f"0x{x:08x}" for x in words],
        "verified_reader_word_at_0x10":f"0x{words[4]:08x}",
        "evidence":"ORIGINAL_DESCRIPTOR_BYTES_NOT_LINKDATA_PAYLOAD_IDENTITY",
    }


def descriptor_survey(parts):
    # 983 is a registry index in a distinct 40-byte table; inspect its
    # neighbors and 4600x68 possible table length without asserting a match.
    sampled=[inspect_descriptor(parts,i) for i in (0,982,983,984,TABLE_CAP-1)]
    contains=[]
    exact_record_bytes=64+ORIGINAL_ITEM_RECORD_COUNT*ORIGINAL_ITEM_RECORD_SIZE
    for index in range(TABLE_CAP):
        raw,_=section_read(parts,TABLE_BASE+TABLE_STRIDE*index,TABLE_STRIDE)
        words=struct.unpack("<10I",raw)
        for j,x in enumerate(words):
            if x in (ORIGINAL_ITEM_RECORD_COUNT,ORIGINAL_ITEM_RECORD_SIZE,exact_record_bytes):
                contains.append({"index":index,"word_offset":hex(4*j),"value":x})
    return {
        "source_registry_base_rva":hex(TABLE_BASE),
        "descriptor_stride":TABLE_STRIDE,
        "descriptor_count_if_zero_based":TABLE_CAP,
        "original_linkdata_bytes":exact_record_bytes,
        "samples":sampled,"exact_original_size_word_hits":contains[:40],
        "exact_original_size_word_hit_total":len(contains),
        "descriptor_is_same_as_00983_table":False
    }


def disassembly(code,base,pc,before=16,after=192):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    md=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    first=max(base,(pc-before)&~3)
    end=min(base+len(code),(pc+after)&~3)
    return [
        {"pc":hex(i.address),"asm":i.mnemonic+" "+i.op_str,
         "bytes_le":i.bytes.hex()}
        for i in md.disasm(code[first-base:end-base],first)
    ]


def all_bl_callers(code,base,targets):
    # Direct BL instruction encoding only. Indirect BLR, PLT and data-vtable
    # address references must not be inferred to be direct caller sites.
    callers={t:[] for t in targets}
    for pos in range(0,len(code)&~3,4):
        pc=base+pos
        word=struct.unpack_from("<I",code,pos)[0]
        if (word&0xfc000000)!=0x94000000:
            continue
        dest=bl_target(word,pc)
        if dest in callers:
            callers[dest].append(hex(pc))
    return {hex(t):{"direct_bl_count":len(c),"first_pcs":c[:120]}
            for t,c in callers.items()}


def exact_global_xrefs(code,base,max_instructions=24):
    """Resolve ADRP page + local register adds, direct memory ops and alias.

    Stop at branches/calls; values loaded *from* a pointer are unknown. No
    interprocedural address provenance or false negative 'unreferenced' claim.
    """
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM,CS_GRP_JUMP,CS_GRP_CALL,CS_GRP_RET
    from capstone.arm64 import ARM64_OP_REG,ARM64_OP_MEM,ARM64_OP_IMM
    md=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    md.detail=True
    all_sites=[]
    page_hits=0
    for pos in range(0,len(code)&~3,4):
        pc=base+pos
        w=struct.unpack_from("<I",code,pos)[0]
        if adrp_target(w,pc)!=PAGE:continue
        page_hits+=1
        reg=w&31
        known={reg:PAGE}
        end=min(len(code),pos+4*(max_instructions+1))
        prior_pc=pc
        for insn in md.disasm(code[pos+4:end],pc+4):
            if insn.address!=prior_pc+4:
                break
            prior_pc=insn.address
            if insn.group(CS_GRP_JUMP) or insn.group(CS_GRP_CALL) or insn.group(CS_GRP_RET):
                break
            ops=insn.operands
            if len(ops)>=2 and ops[1].type==ARM64_OP_MEM:
                mem=ops[1].mem
                base_reg=insn.reg_name(mem.base)
                base_index=int(base_reg[1:]) if base_reg.startswith("x") and base_reg[1:].isdigit() else -1
                if base_index in known:
                    absolute=known[base_index]+int(mem.disp)
                    if absolute==TARGET_GLOBAL and insn.mnemonic in (
                        "ldr","str","ldur","stur","ldrb","strb","ldrh","strh","ldrsw","ldursw"
                    ):
                        all_sites.append({
                            "adrp_pc":hex(pc),"memory_pc":hex(insn.address),
                            "assembly":insn.mnemonic+" "+insn.op_str,
                            "absolute_rva":hex(absolute),
                            "kind":"direct_memory_read" if insn.mnemonic.startswith(("ldr","ldur")) else "direct_memory_write",
                            "provenance":"ADRP_PAGE_PLUS_STRAIGHT_LINE_REGISTER_BASE"
                        })
            destination=None
            if ops and ops[0].type==ARM64_OP_REG:
                dst_name=insn.reg_name(ops[0].reg)
                if dst_name.startswith("x") and dst_name[1:].isdigit():
                    destination=int(dst_name[1:])
            resolved=None
            if (destination is not None and insn.mnemonic in ("add","sub") and
                len(ops)>=3 and ops[1].type==ARM64_OP_REG and ops[2].type==ARM64_OP_IMM):
                name=insn.reg_name(ops[1].reg)
                if name.startswith("x") and name[1:].isdigit():
                    source=int(name[1:])
                    if source in known:
                        resolved=known[source]+int(ops[2].imm)*(1 if insn.mnemonic=="add" else -1)
            # Unknown writes to a tracked register invalidate its address.
            _,writes=insn.regs_access()
            killed=set()
            for wr in writes:
                name=insn.reg_name(wr)
                if name[0:1] in ("x","w") and name[1:].isdigit():
                    killed.add(int(name[1:]))
            for k in killed:known.pop(k,None)
            if destination is not None and resolved is not None:
                known[destination]=resolved
    return {
        "target_global_rva":hex(TARGET_GLOBAL),
        "raw_adrp_page_match_count":page_hits,
        "exact_direct_load_store_site_count":len(all_sites),
        "direct_sites":all_sites[:250],
        "unresolved_indirect_reader_count":"NOT_ENUMERABLE_FROM_LINEAR_ADRP",
        "limitation":"A dynamic pointer loaded from a global/object may have readers not encoded as direct ADRP+offset."
    }


def find_unqualified_global_displacements(code,base):
    # Raw LDR/STR Xt offset 0x4c8 independent of pointer base; not an xref.
    matches=[]
    for pos in range(0,len(code)&~3,4):
        w=struct.unpack_from("<I",code,pos)[0]
        opcode=w&0xffc00000
        if opcode not in (0xf9400000,0xf9000000):
            continue
        disp=((w>>10)&0xfff)*8
        if disp==DISP:
            matches.append({"pc":hex(base+pos),"operation":"ldr" if opcode==0xf9400000 else "str",
                            "base_register":"x"+str((w>>5)&31),
                            "target_register":"x"+str(w&31)})
    return {"raw_offset_hits_unqualified":len(matches),
            "examples":matches[:80],
            "warning":"Same offset 0x4c8 on an arbitrary pointer is not evidence of addressing this global."}


def item_consumer_evidence(code,base):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    md=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    validated=[]
    for pc,(mnemonic,op) in ITEM_CONSUMERS.items():
        offset=pc-base
        inst=next(md.disasm(code[offset:offset+4],pc),None)
        if inst is None or inst.mnemonic!=mnemonic or inst.op_str!=op:
            raise ValueError(f"M20_ORIGINAL_ITEM_CONSUMER_CHANGED:{pc:#x}")
        if pc in (0xe5aa38,0xe5aa60,0x10289e0,0x10289f4,0xabbb48,0xabbb64,
                  0xabbbd4,0xe5a99c,0x1028968):
            validated.append({"pc":hex(pc),"instruction":mnemonic+" "+op})
    return {"verified_original_consumer_anchors":validated,
            "native_4600_id_virtual_accessor_to_raw_fields":True,
            "concrete_accessor_vtable_0x30_proven":False,
            "original_00983_buffer_identity_proven":False,
            "record_formula_64_plus_id_times_68_proven":False}


def analyze(main,item):
    sha_main=hashlib.sha256(main).hexdigest()
    sha_item=hashlib.sha256(item).hexdigest()
    if sha_main!=MAIN_SHA or sha_item!=ITEM_SHA:
        raise ValueError("M20_ORIGINAL_SOURCE_SHA_MISMATCH")
    if len(item)!=64+4600*68 or struct.unpack_from("<II",item)!=(4600,3):
        raise ValueError("M20_ORIGINAL_00983_TABLE_LAYOUT_MISMATCH")
    kind,parts=get_sections(main)
    if kind!="NSO0":raise ValueError("M20_UNEXPECTED_BINARY_FORMAT")
    seg=next(x for x in parts if x["name"]=="text")
    code,base=seg["data"],seg["mem_offset"]
    descriptor_layout=verify_indexed_lookup_table(code,base)
    paths=[chain(code,base,pc) for pc in CALLERS]
    destinations={*LOOKUPS,0x1443780,0x1471990}
    return {
        "status":"M20_983_DESCRIPTOR_AND_GLOBAL_XREF_EVIDENCE_WITH_UNLINKED_ITEM_CONSUMER",
        "sha256_main":sha_main,"sha256_item":sha_item,
        "original_table_record_count":4600,"original_table_record_stride":68,
        "original_table_header_bytes":64,
        "original_table_byte_length":len(item),
        "native_983_lookup_chains":paths,
        "indexed_descriptor_layout":descriptor_layout,
        "original_40_byte_descriptor_samples":descriptor_survey(parts),
        "wrapper_and_calex_disassembly":{hex(t):disassembly(code,base,t,16,256) for t in LOOKUPS},
        "direct_bl_callers":all_bl_callers(code,base,destinations),
        "global_static_xrefs":exact_global_xrefs(code,base),
        "unqualified_global_offset_survey":find_unqualified_global_displacements(code,base),
        "independent_item_consumers":item_consumer_evidence(code,base),
        "semantic_proofs":{
            "983_descriptor_indexed_by_original_main":True,
            "global_cache_store_from_983_chain":True,
            "global_cache_runtime_load_back_to_item_accessor":False,
            "983_descriptor_is_original_00983_bin":False,
            "concrete_registry_0xc7_virtual_method":False,
            "original_00983_68_byte_record_identity":False,
            "native_material_enum_class_names":False,
            "native_per_item_max_stack":False
        },
        "warning":"The 983 registry descriptor, the 4600-item virtual accessor, and physical 00983.bin records are separate components until pointer/caller provenance connects them."
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--main",type=Path,default=Path("2.0.1/exefs/main"))
    p.add_argument("--item",type=Path,default=Path("UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin"))
    p.add_argument("--out",type=Path,default=OUT)
    a=p.parse_args()
    report=analyze(a.main.read_bytes(),a.item.read_bytes())
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/"m20_native_983_cache_provenance.json").write_text(json.dumps(
        report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary={k:report[k] for k in (
        "status","sha256_main","sha256_item","original_table_byte_length",
        "native_983_lookup_chains","indexed_descriptor_layout",
        "global_static_xrefs","unqualified_global_offset_survey",
        "independent_item_consumers","semantic_proofs","warning"
    )}
    summary["descriptor_samples"]=report["original_40_byte_descriptor_samples"]["samples"]
    summary["direct_bl_callers"]=report["direct_bl_callers"]
    (a.out/"m20_native_983_cache_summary.json").write_text(json.dumps(
        summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("M20_CACHE_SUMMARY",json.dumps({
        "status":report["status"],"descriptor_samples":summary["descriptor_samples"],
        "global_xrefs":summary["global_static_xrefs"],
        "callers":summary["direct_bl_callers"],
        "proofs":summary["semantic_proofs"]
    },separators=(",",":"))[:20000])
    for target in (0x14718f0,0x1471990,0x1444210):
        ins=report["wrapper_and_calex_disassembly"][hex(target)]
        print("M20_CALLER_CONTEXT",hex(target),json.dumps(
            [x["pc"]+" "+x["asm"] for x in ins[:56]],separators=(",",":")))


if __name__=="__main__":
    main()
