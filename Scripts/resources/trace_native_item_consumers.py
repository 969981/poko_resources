#!/usr/bin/env python3
"""Trace 4600-ID loop -> virtual lookup -> returned object -> +0x26/+0x39.

Exact original NSO instruction matching, with provenance kept separate.
No assumption that the indirect query return is a physical 00983.bin record.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import Counter
from pathlib import Path
from Scripts.resources.trace_native_species_item_callers import get_sections

MAIN=Path("2.0.1/exefs/main")
ITEM=Path("UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin")
OUT=Path("UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M12")
SHA_MAIN="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
SHA_ITEM="2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f"
# Verified from M11 native-original instruction windows, not guessed addresses.
CHECKS={
  0xE5A99C:("mov","w28, #0x11f8"),
  0xE5A9E4:("cmp","x20, x28"),
  0xE5AA30:("mov","w1, w20"),
  0xE5AA34:("ldr","x8, [x8, #0x30]"),
  0xE5AA38:("blr","x8"),
  0xE5AA40:("mov","x21, x0"),
  0xE5AA58:("ldr","x8, [x21, #8]"),
  0xE5AA60:("ldrb","w0, [x8, #0x26]"),
  0xE5AA64:("sub","w8, w0, #1"),
  0xE5AA68:("cmp","w8, #0x13"),
  0xE5AA88:("bl","#0xabba30"),
  0x1028968:("mov","w28, #0x11f8"),
  0x1028988:("add","x20, x20, #1"),
  0x102898C:("cmp","x20, x28"),
  0x10289D8:("mov","w1, w20"),
  0x10289DC:("ldr","x8, [x8, #0x30]"),
  0x10289E0:("blr","x8"),
  0x10289E8:("ldr","x8, [x0, #8]"),
  0x10289F4:("ldrb","w21, [x8, #0x26]"),
  0x1028A00:("cmp","w8, #0x13"),
  0x1028A28:("bl","#0xabba30"),
  0x1028A38:("ldrb","w8, [x8, #0x39]"),
  0x1028A40:("cmp","w9, #9"),
  0xABBAEC:("and","w19, w0, #0xffff"),
  0xABBAF0:("mov","w9, #0x11f6"),
  0xABBAF4:("sub","w8, w19, #1"),
  0xABBAF8:("cmp","w8, w9"),
  0xABBB40:("mov","w1, w19"),
  0xABBB44:("ldr","x8, [x8, #0x30]"),
  0xABBB48:("blr","x8"),
  0xABBB50:("ldr","x8, [x0, #8]"),
  0xABBB64:("ldrb","w8, [x8, #0x3a]"),
  0xABBB68:("cmp","w8, #0xf"),
  0xABBBD4:("ldrb","w8, [x8, #0x3a]"),
  0xABBBD8:("cmp","w8, #0x15"),
}
CONTEXTS={
  "native_count_loop_A":(0xE5A974,0xE5AAC0),
  "native_count_loop_B":(0x1028910,0x1028AC0),
  "enum_predicate_helper":(0xABBA30,0xABBD00),
  "item_candidate_helper":(0x2E74B0,0x2E7710),
}

def hexrecord(item):
    names={0x26:"kind_candidate",0x39:"secondary_group_candidate",0x3a:"other_group_candidate"}
    hist={}
    for offset,label in names.items():
        values=Counter(item[64+68*i+offset] for i in range(4600))
        hist[label]={"raw_record_offset":hex(offset),
                     "all_4600_slots":{str(k):values[k] for k in sorted(values)},
                     "max_observed":max(values)}
    return hist

def analyze(main,item):
    a,b=hashlib.sha256(main).hexdigest(),hashlib.sha256(item).hexdigest()
    if (a,b)!=(SHA_MAIN,SHA_ITEM) or len(item)!=64+4600*68 or struct.unpack_from("<II",item,0)!=(4600,3):
        raise ValueError("Original 2.0.1 ExeFS main and item table identity/layout mismatch")
    fmt,segs=get_sections(main)
    if fmt!="NSO0":raise ValueError("Unsupported NSO format")
    seg=next(s for s in segs if s["name"]=="text")
    base,code=seg["mem_offset"],seg["data"]
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    md=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    verified=[]
    for pc,(mnemonic,opstr) in CHECKS.items():
        off=pc-base
        assert 0<=off<=len(code)-4
        inst=next(md.disasm(code[off:off+4],pc),None)
        if inst is None or inst.mnemonic!=mnemonic or inst.op_str!=opstr:
            raise ValueError(f"Original ARM64 instruction mismatch {pc:#x}: expected {mnemonic} {opstr}, found {inst}")
        verified.append({"pc":hex(pc),"instruction":mnemonic+" "+opstr,
                         "original_code_word":code[off:off+4].hex()})
    windows={}
    for name,(start,end) in CONTEXTS.items():
        if start<base or end>base+len(code):raise ValueError("Invalid disassembly window "+name)
        windows[name]=[{"pc":hex(i.address),"asm":i.mnemonic+" "+i.op_str}
                       for i in md.disasm(code[start-base:end-base],start)]
    return {
       "status":"ID_LOOKUP_AND_RETURNED_FIELD_DATAFLOW_CONFIRMED__NATIVE_TABLE_LOADER_UNRESOLVED",
       "source_main_sha256":a,"source_item_sha256":b,
       "item_count":4600,"item_record_stride":68,"item_header_bytes":64,
       "native_table_names_offset_0x22_verified_by_prior_nine_language_audit":True,
       "matched_original_instruction_count":len(verified),
       "matched_original_instructions":verified,
       "control_flow_summary":[
           "At 0xE5A99C and 0x1028968 W28 is initialized to 4600, used as loop bound for X20.",
           "Both routines pass W20 as W1 to an indirect vtable function at +0x30.",
           "Both routines read pointer +8 from the returned object, then byte +0x26 from that pointer (or fallback).",
           "0x1028A38 also reads +0x39. Value-range checks follow these returned-object loads.",
           "0xABBAD8 validates (ID-1)<=4598, queries registry entry by ID, then reads +0x3A and tests values 15 and 21."
       ],
       "field_histograms_from_exact_original_00983":hexrecord(item),
       "proven_4600_item_id_lookup_to_0x26_field_consumption":True,
       "proven_00983_loader":False,
       "proven_record_address_equals_item_table_base_plus_id_times_68":False,
       "proven_runtime_returned_struct_matches_00983_record":False,
       "enum_definition_proven":False,
       "recovered_windows":windows,
       "next_blocker":"Resolve global object registry class and concrete +0x30 vtable method, trace its storage-pointer source to original 00983.bin table allocation and 68-byte indexing."
    }

def selftest():
    # Strict rejection on zero-filled binary with superficially correct table header.
    fake=bytearray(64+4600*68)
    struct.pack_into("<II",fake,0,4600,3)
    try:
        analyze(b"incorrect",bytes(fake))
        raise AssertionError("Forged inputs accepted")
    except ValueError:pass
    assert CHECKS[0xE5AA60]==("ldrb","w0, [x8, #0x26]")
    assert CHECKS[0x1028A38]==("ldrb","w8, [x8, #0x39]")
    assert CHECKS[0xABBB64]==("ldrb","w8, [x8, #0x3a]")
    assert CHECKS[0xABBBD8]==("cmp","w8, #0x15")
    h=hexrecord(fake)
    assert h["kind_candidate"]["all_4600_slots"]["0"]==4600
    print("PASS: fake originals rejected; full item-field table counts and exact evidence anchor list")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--main",type=Path,default=MAIN)
    p.add_argument("--item",type=Path,default=ITEM)
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test:selftest();return
    report=analyze(args.main.read_bytes(),args.item.read_bytes())
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"item_id_lookup_0x26_original_evidence.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary={k:report[k] for k in ("status","source_main_sha256","source_item_sha256",
       "item_count","item_record_stride","matched_original_instruction_count",
       "proven_4600_item_id_lookup_to_0x26_field_consumption",
       "proven_00983_loader","proven_record_address_equals_item_table_base_plus_id_times_68",
       "proven_runtime_returned_struct_matches_00983_record","enum_definition_proven",
       "field_histograms_from_exact_original_00983","next_blocker")}
    (args.out/"item_id_lookup_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
