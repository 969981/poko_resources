#!/usr/bin/env python3
"""M18: bounded original AArch64 caller/callee evidence around item metadata consumers.

This is NOT a decompiler, nor proof of 00983.bin loader provenance.  Only
instruction-level call targets, pointer values, original file hashes and local
field-dependent branch patterns are asserted.  Indirect C++ calls are unresolved.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import struct

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.trace_native_item_registry_vtables import raw_pointers

SHA_MAIN = "8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
SHA_ITEM = "2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f"
MAIN = Path("2.0.1/exefs/main")
ITEM = Path("UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin")
OUT = Path("UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M18")
ANCHORS = {
    0xE5A99C: "item_loop_A_prelookup",
    0xE5AA38: "item_loop_A_vcall_region",
    0xE5AA60: "item_loop_A_plus26_read",
    0x1028968: "item_loop_B_prelookup",
    0x10289E0: "item_loop_B_vcall_region",
    0x10289F4: "item_loop_B_plus26_read",
    0xABBB48: "item_id_classification_access_A",
    0xABBBB8: "item_id_classification_access_B",
}
FIELD_RE = re.compile(r"\[(x\d+),\s*#0x(22|26|39|3a)\]", re.I)
LDR30_RE = re.compile(r"^(x\d+),\s*\[(x\d+),\s*#0x30\]$", re.I)
REG_RE = re.compile(r"\b[wx](\d+)\b")


def signed_bl_target(pc: int, word: int):
    if word & 0xFC000000 != 0x94000000:
        return None
    imm = word & 0x03FFFFFF
    if imm & (1 << 25):
        imm -= 1 << 26
    return pc + 4 * imm


def calls_to_targets(code: bytes, base: int, targets: set[int]):
    """One original full-text pass, using actual branch immediate encoding."""
    found = defaultdict(list)
    for off in range(0, len(code) & ~3, 4):
        word = struct.unpack_from("<I", code, off)[0]
        if word & 0xFC000000 != 0x94000000:
            continue
        pc = base + off
        dest = signed_bl_target(pc, word)
        if dest in targets:
            found[dest].append(pc)
    return found


def window(code: bytes, base: int, center: int):
    if center < base or center >= base + len(code):
        raise ValueError("Native address not in text segment")
    from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    start = max(base, (center - 0x100) & ~3)
    end = min(base + len(code), (center + 0x140) & ~3)
    insts = []
    for ins in md.disasm(code[start-base:end-base], start):
        word = struct.unpack_from("<I", code, ins.address-base)[0]
        insts.append({"pc": ins.address, "mnemonic": ins.mnemonic,
                      "operands": ins.op_str, "word": f"{word:08x}"})
    if not any(x["pc"] == center for x in insts):
        raise ValueError("Focal ARM64 address not aligned/decodable")
    return insts


def local_patterns(insts):
    """Only same-window facts; never assume register values across BL/branch."""
    direct = []
    indirect = []
    fields = []
    for i, ins in enumerate(insts):
        pc, m, op = ins["pc"], ins["mnemonic"], ins["operands"]
        if m == "bl":
            dest = signed_bl_target(pc, int(ins["word"], 16))
            if dest is not None:
                direct.append({"callsite": hex(pc), "target": hex(dest),
                               "encoding": ins["word"]})
        if m == "blr":
            target_reg = op.lower().strip()
            # Look for a preceding LDR Xt,[Xn,#0x30] without branching across
            # the local instructions. There can still be unrelated register
            # modifications, so this is a candidate, not dataflow proof.
            prev = insts[max(0, i-10):i]
            for k in range(len(prev)-1, -1, -1):
                x = prev[k]
                if x["mnemonic"] in ("bl", "blr", "br", "ret", "b",
                                      "cbz", "cbnz", "tbz", "tbnz") or x["mnemonic"].startswith("b."):
                    break
                if x["mnemonic"] != "ldr":
                    continue
                match = LDR30_RE.match(x["operands"])
                if match and match.group(1).lower() == target_reg:
                    indirect.append({
                        "load_pc": hex(x["pc"]), "call_pc": hex(pc),
                        "register": target_reg, "table_base_register": match.group(2),
                        "slot_offset": "0x30",
                        "status": "LOCAL_LDR30_BLR_PATTERN__CLASS_UNBOUND"})
                    break
        if m in ("ldrb", "ldrh"):
            match = FIELD_RE.search(op)
            if not match:
                continue
            dst = op.split(",", 1)[0].strip().lower()
            dependents = []
            for after in insts[i+1:i+14]:
                a = after["mnemonic"]
                args = after["operands"].lower()
                r = re.search(r"\b" + re.escape(dst) + r"\b", args)
                if r and (a in ("cmp", "cmn", "tst", "tbz", "tbnz", "cbz", "cbnz") or a in ("subs", "ands")):
                    dependents.append({"pc": hex(after["pc"]), "asm": a+" "+args})
                if a in ("bl", "blr", "br", "ret", "b") or a.startswith("b."):
                    break
            fields.append({"pc": hex(pc), "instruction": m+" "+op,
                           "base_register": match.group(1), "offset": hex(int(match.group(2),16)),
                           "local_test_candidates": dependents,
                           "status": "UNPROVEN_SOURCE_AND_SEMANTICS"})
    return direct, indirect, fields


def analyze(main: bytes, item: bytes):
    sha_main = hashlib.sha256(main).hexdigest()
    sha_item = hashlib.sha256(item).hexdigest()
    if sha_main != SHA_MAIN or sha_item != SHA_ITEM:
        raise ValueError("Not the verified Pokopia 2.0.1 original source")
    if len(item) != 64+4600*68 or struct.unpack_from("<II", item, 0) != (4600,3):
        raise ValueError("Not original 00983 4600x68 record layout")
    kind, segments = get_sections(main)
    if kind != "NSO0":
        raise ValueError("Input must be NSO0")
    t = next(x for x in segments if x["name"] == "text")
    code, base = t["data"], t["mem_offset"]
    pointers = raw_pointers(segments, base + len(code))
    reverse_pointers = defaultdict(list)
    for slot, target in pointers.items():
        reverse_pointers[target].append(slot)
    rows = []
    targets = set()
    for anchor, role in ANCHORS.items():
        ins = window(code,base,anchor)
        direct,indirect,fields = local_patterns(ins)
        targets.update(int(x["target"],16) for x in direct)
        rows.append({
            "anchor_rva":hex(anchor), "role":role,
            "local_direct_bl":direct,
            "local_indirect_ldr30_blr":indirect,
            "local_item_field_reads":fields,
            "disassembly":[{"pc":hex(x["pc"]),"word":x["word"],
                            "asm":x["mnemonic"]+" "+x["operands"]} for x in ins],
            "warning":"Window is not a recovered function or CFG; do not infer 00983 provenance."})
    inbound = calls_to_targets(code,base,targets)
    intersections=[]
    for target in sorted(targets):
        slots=reverse_pointers.get(target,[])
        # A function-pointer occurrence is not proof of a vtable slot.
        # Retain the original pointer cell and adjacent executable pointers.
        inferred=[]
        for slot in slots[:100]:
            before=sum((slot-8*i) in pointers for i in range(1,7))
            after=sum((slot+8*i) in pointers for i in range(1,4))
            inferred.append({"pointer_slot":hex(slot),
                             "six_preceding_executable_pointer_cells":before,
                             "three_following_executable_pointer_cells":after,
                             "vtable_plus30_position_candidate":before==6,
                             "status":"POINTER_CELL_ONLY__OBJECT_OWNER_UNPROVEN"})
        intersections.append({
            "direct_callee_va":hex(target),
            "direct_callers_count":len(inbound.get(target,[])),
            "direct_caller_pcs":[hex(x) for x in inbound.get(target,[])[:60]],
            "matching_original_function_pointer_cells":inferred,
            "pointer_cells_total":len(slots)})
    return {
        "status":"ORIGINAL_NATIVE_LOCAL_CALL_GRAPH__ITEM_LOADER_UNPROVEN",
        "original_main_sha256":sha_main,"original_item_sha256":sha_item,
        "native_text_bytes":len(code),
        "registered_slot_index_candidate":"0xc7",
        "registered_member_offset_candidate":"0x648",
        "source_record_count":4600,"source_record_stride":68,
        "anchor_count":len(rows),
        "local_ldr30_blr_patterns":sum(len(x["local_indirect_ldr30_blr"]) for x in rows),
        "local_field_reads":sum(len(x["local_item_field_reads"]) for x in rows),
        "direct_callee_count":len(targets),
        "verified_original_item_loader":False,
        "verified_material_type_enum":False,
        "verified_virtual_class_vtable_binding":False,
        "anchor_evidence":rows,"direct_callee_reverse_references":intersections,
        "requirements_for_proof":[
            "Identify a concrete C7 registry object constructor and its vtable pointer assignment.",
            "Show the vtable +0x30 destination and returned object +8 pointer origin.",
            "Prove its backing bytes or transformed record provenance from 00983.bin.",
            "Show field +0x26/+0x3a affecting a named material/classification branch."
        ]}
    

def selftest():
    assert signed_bl_target(0x1000, 0x94000400)==0x2000
    assert signed_bl_target(0x2000,0x97fffc00)==0x1000
    assert signed_bl_target(0x1000,0xd65f03c0) is None
    code = struct.pack("<3I", 0x94000400,0xd65f03c0,0x97fffbfe)
    assert calls_to_targets(code,0x1000,{0x2000})[0x2000]==[0x1000]
    # LDR X9,[X8,#0x30] followed by BLR X9, recognized as local,
    # but NEVER declared a proven concrete registry class.
    ldr=0xf9400000|((0x30//8)<<10)|(8<<5)|9
    blr=0xd63f0000|(9<<5)
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    md=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    ins=[{"pc":i.address,"mnemonic":i.mnemonic,"operands":i.op_str,"word":f"{struct.unpack('<I',i.bytes)[0]:08x}"} for i in md.disasm(struct.pack("<2I",ldr,blr),0x4000)]
    _, virtual, _=local_patterns(ins)
    assert len(virtual)==1 and virtual[0]["slot_offset"]=="0x30",virtual
    try:
        analyze(b"fake",b"fake")
        raise AssertionError("Forged original sources accepted")
    except ValueError:
        pass
    print("PASS original BL decoding, bounded indirect-call candidates, strict source hash rejection")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--main",type=Path,default=MAIN)
    parser.add_argument("--item",type=Path,default=ITEM)
    parser.add_argument("--out",type=Path,default=OUT)
    parser.add_argument("--self-test",action="store_true")
    args=parser.parse_args()
    if args.self_test:
        selftest()
        return
    out=analyze(args.main.read_bytes(),args.item.read_bytes())
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"m18_original_item_callgraph.json").write_text(
        json.dumps(out,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    summary={k:v for k,v in out.items() if k not in ("anchor_evidence","direct_callee_reverse_references","requirements_for_proof")}
    summary["anchor_summary"]=[{
        "rva":r["anchor_rva"],"role":r["role"],
        "direct_calls":len(r["local_direct_bl"]),
        "indirect_ldr30_blr":len(r["local_indirect_ldr30_blr"]),
        "field_reads":len(r["local_item_field_reads"])
    } for r in out["anchor_evidence"]]
    summary["direct_callee_targets"]=[x["direct_callee_va"] for x in out["direct_callee_reverse_references"]]
    (args.out/"m18_original_item_callgraph_summary.json").write_text(
        json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
