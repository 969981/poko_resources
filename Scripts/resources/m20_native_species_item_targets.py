#!/usr/bin/env python3
"""M20: exact native 2.0.1 property-hash sites and two-stage item-query callers.

Static source evidence only. No property name, Pokemon species ID, registry
class identity, item-file loader or material enum is inferred from a hash hit.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections

MAIN = Path("2.0.1/exefs/main")
ITEM = Path("UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin")
EDGES = Path("UnPack/2.0.1/Resources/Pokemon/NativeCallers/M19/m19_verified_texture_object_edges.csv")
POKEMON_OUT = Path("UnPack/2.0.1/Resources/Pokemon/NativeCallers/M20")
ITEM_OUT = Path("UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M20")
SHA_MAIN = "8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
SHA_ITEM = "2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f"
FIELD = 0x2856A1B3
WRAPPER = 0x2F1F0
ITEM_ANCHORS = (0x2F210, 0x2F220, 0x2F234, 0x2F238,
                0x2F244, 0x2F24C, 0x2F258,
                0xE5AA38, 0xE5AA58, 0xE5AA60,
                0xABBB48, 0xABBB50, 0xABBB64, 0xABBBD4)
MAX_SITES = 100
MAX_CALLERS = 80


def u32(buf: bytes, pos: int) -> int:
    return struct.unpack_from("<I", buf, pos)[0]


def branch_target(pc: int, word: int):
    op = word & 0xFC000000
    if op not in (0x94000000, 0x14000000):
        return None
    imm = word & 0x03FFFFFF
    if imm & (1 << 25):
        imm -= 1 << 26
    return pc + (imm << 2), ("BL" if op == 0x94000000 else "B")


def scan_direct_callers(code: bytes, base: int, target: int):
    calls = []
    tails = []
    for off in range(0, len(code) - 3, 4):
        pc = base + off
        decoded = branch_target(pc, u32(code, off))
        if decoded and decoded[0] == target:
            (calls if decoded[1] == "BL" else tails).append(pc)
    return calls, tails


def arm64_window(code: bytes, base: int, center: int, before=0x40, after=0x80):
    from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
    off = center - base
    if off < 0 or off + 4 > len(code) or off % 4:
        raise ValueError("Original instruction anchor not mapped")
    start = max(0, (off - before) & ~3)
    stop = min(len(code) & ~3, (off + after) & ~3)
    dis = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    rows = [
        {"pc": hex(ins.address), "word": f"{u32(code, ins.address-base):08x}",
         "asm": (ins.mnemonic + " " + ins.op_str).strip()}
        for ins in dis.disasm(code[start:stop], base + start)
    ]
    if not any(int(r["pc"], 16) == center for r in rows):
        raise ValueError(f"Undecodable native instruction at {center:#x}")
    return rows


def mov_literal_parts(word: int):
    """Recognize AArch64 32/64-bit MOVZ/MOVK (not arbitrary MOV alias)."""
    op = word & 0x7F800000
    if op not in (0x52800000, 0x72800000):
        return None
    return ("MOVZ" if op == 0x52800000 else "MOVK",
            word & 31, (word >> 5) & 0xFFFF, (word >> 21) & 3,
            (word >> 31) & 1)


def hash_mov_pairs(code: bytes, base: int, target: int):
    sites = []
    low = target & 0xFFFF
    high = target >> 16
    # Candidate pair windows must remain bounded and in the same register.
    # Only adjacent pairs are marked direct; intervening instructions are
    # expressly NOT asserted to preserve register values.
    for off in range(0, len(code) - 3, 4):
        second = mov_literal_parts(u32(code, off))
        if second is None or second[0] != "MOVK" or second[2:4] != (high, 1):
            continue
        for back in range(4, 49, 4):
            if off < back:
                break
            first = mov_literal_parts(u32(code, off-back))
            if (first and first[0] == "MOVZ" and
                    first[1] == second[1] and first[2:4] == (low, 0) and
                    first[4] == second[4]):
                sites.append({
                    "movz_pc": hex(base+off-back), "movk_pc": hex(base+off),
                    "register": ("x" if second[4] else "w") + str(second[1]),
                    "movz_word": f"{u32(code,off-back):08x}",
                    "movk_word": f"{u32(code,off):08x}",
                    "instruction_gap": back//4,
                    "grade": ("ADJACENT_EXACT_IMMEDIATE_PAIR" if back == 4 else
                              "NONADJACENT_PAIR_REGISTER_LIVENESS_UNPROVEN"),
                    "property_consumer_verified": False,
                })
                break
    return sites


def decode_adrp(word: int, pc: int):
    if word & 0x9F000000 != 0x90000000:
        return None
    imm = (((word >> 5) & 0x7FFFF) << 2) | ((word >> 29) & 3)
    if imm & (1 << 20):
        imm -= 1 << 21
    return ((pc & ~0xFFF) + (imm << 12), word & 31)


def literal_sites(parts, target: int):
    needle = struct.pack("<I", target)
    out = []
    for section in parts:
        if section["name"] not in ("rodata", "data"):
            continue
        blob, base = section["data"], section["mem_offset"]
        i = 0
        while True:
            p = blob.find(needle, i)
            if p == -1:
                break
            out.append({"va": base+p, "section": section["name"],
                        "section_offset": p, "aligned_u32": p % 4 == 0})
            i = p + 1
    return out


def literal_xrefs(code: bytes, base: int, cells: list[dict]):
    # Scan ADRP -> immediate ADD or LDR W against exact matching literal
    # addresses. Only an adjacent LDR W proves a 32-bit value load.
    wanted = {x["va"]: x for x in cells}
    by_page = {}
    for addr in wanted:
        by_page.setdefault(addr >> 12, set()).add(addr)
    found = []
    for off in range(0, len(code)-3, 4):
        pc = base + off
        dec = decode_adrp(u32(code,off), pc)
        if dec is None or dec[0] >> 12 not in by_page:
            continue
        page, reg = dec
        for delta in range(4, 37, 4):
            p = off+delta
            if p+4 > len(code):
                break
            w = u32(code,p)
            if (w & 0xFFC00000) == 0xB9400000 and ((w >> 5) & 31) == reg:
                va = page + ((w >> 10) & 0xFFF) * 4
                typ = "LDR_W_VALUE"
            elif (w & 0xFF000000) == 0x91000000 and ((w >> 5) & 31) == reg:
                shift = (w >> 22) & 3
                if shift > 1:
                    continue
                va = page + (((w >> 10) & 0xFFF) << (12 if shift else 0))
                typ = "ADD_ADDRESS_ONLY"
            else:
                continue
            if va not in wanted:
                continue
            found.append({
                "adrp_pc": hex(pc), "candidate_pc": hex(base+p),
                "target_va": hex(va), "literal_section": wanted[va]["section"],
                "instruction_kind": typ, "instruction_gap": delta//4,
                "grade": ("ADJACENT_ARM64_ADDRESS_OR_VALUE_ACCESS" if delta == 4
                          else "NONADJACENT_REGISTER_LIVENESS_UNPROVEN"),
                "property_consumer_verified": False,
            })
    return found


def verify_edges(rows: list[dict]):
    if len(rows) != 603:
        raise ValueError("M19 603-edge original corpus is absent or changed")
    keys = set()
    for r in rows:
        a, b = r["source_object_hash"], r["target_object_hash"]
        if not a or not b or a == b or r["native_species_id_verified"]:
            raise ValueError("Cannot promote texture-object edge to species ID")
        if (a,b) in keys:
            raise ValueError("Duplicate original native edge")
        keys.add((a,b))
        if r["source_field_hash"].lower() != f"{FIELD:08x}":
            raise ValueError("Incorrect original typed property hash")
    return len(keys)


def analyze(main: bytes, item: bytes, edges: list[dict]):
    if hashlib.sha256(main).hexdigest() != SHA_MAIN:
        raise ValueError("Original Pokopia 2.0.1 NSO SHA-256 mismatch")
    if hashlib.sha256(item).hexdigest() != SHA_ITEM:
        raise ValueError("Original Pokopia 2.0.1 item table SHA-256 mismatch")
    if len(item) != 64 + 4600*68 or struct.unpack_from("<II", item, 0) != (4600,3):
        raise ValueError("Original 00983 item table layout mismatch")
    edge_count = verify_edges(edges)
    kind, sections = get_sections(main)
    if kind != "NSO0":
        raise ValueError("Expected mapped NSO0, not raw or ELF file")
    code = next(x for x in sections if x["name"] == "text")
    buf, base = code["data"], code["mem_offset"]
    cells = literal_sites(sections, FIELD)
    movs = hash_mov_pairs(buf, base, FIELD)
    xrefs = literal_xrefs(buf, base, cells)
    # Exact instruction existence check; never silently reuse stale RVAs.
    anchors = {hex(pc): arm64_window(buf, base, pc, 0x10, 0x18)
               for pc in ITEM_ANCHORS}
    instructions = {}
    for pc in ITEM_ANCHORS:
        row = next(x for x in anchors[hex(pc)] if int(x["pc"],16)==pc)
        instructions[pc] = row["asm"].lower()
    required = {
        0x2F210: ("cmp ", "0xc7"),
        0x2F220: ("ldr x0,", "#0x10"),
        0x2F234: ("ldr x8,", "#0x38"),
        0x2F238: ("blr x8",),
        0x2F244: ("mov w1,", "w19"),
        0x2F24C: ("ldr x2,", "#0x30"),
        0x2F258: ("br x2",),
        0xE5AA60: ("ldrb w0,", "#0x26"),
        0xABBB64: ("ldrb w8,", "#0x3a"),
    }
    for pc, tokens in required.items():
        if not all(tok in instructions[pc] for tok in tokens):
            raise ValueError(f"Two-stage caller instruction changed at {pc:#x}: {instructions[pc]}")
    calls, tails = scan_direct_callers(buf, base, WRAPPER)
    species = {
        "status": "M20_EXACT_ORIGINAL_HASH_LITERAL_SITES__CONSUMER_UNPROVEN",
        "original_main_sha256": SHA_MAIN, "typed_edge_corpus_size": edge_count,
        "property_hash": f"0x{FIELD:08x}",
        "literal_cells_total": len(cells),
        "literal_cells_first": [{**x, "va": hex(x["va"])} for x in cells[:MAX_SITES]],
        "movz_movk_pairs_total": len(movs),
        "movz_movk_pairs_first": movs[:MAX_SITES],
        "adrp_literal_xrefs_total": len(xrefs),
        "adrp_literal_xrefs_first": xrefs[:MAX_SITES],
        "code_windows": [
            {"pc": r["movz_pc"], "instructions": arm64_window(buf, base, int(r["movz_pc"],16),0x20,0x50)}
            for r in movs[:24]
        ] + [
            {"pc": r["candidate_pc"], "instructions": arm64_window(buf, base, int(r["candidate_pc"],16),0x20,0x50)}
            for r in xrefs[:24]
        ],
        "native_property_consumer_verified": False,
        "species_id_bindings_verified": 0,
        "warning": "Constant construction or read is not a typed property consumer or species identity.",
    }
    item_result = {
        "status": "M20_TWO_STAGE_VIRTUAL_CALLER_REVERSE_GRAPH__CLASS_UNBOUND",
        "original_main_sha256": SHA_MAIN, "original_item_sha256": SHA_ITEM,
        "registry_global": "0x35618f0", "registry_index": "0xc7",
        "registry_instance_member": "0x648",
        "two_stage_wrapper_pc": hex(WRAPPER),
        "first_object_vtable_slot": "0x38", "second_object_vtable_slot": "0x30",
        "original_instruction_anchors": anchors,
        "direct_BL_callers_total": len(calls), "tail_B_callers_total": len(tails),
        "direct_BL_callers": [hex(x) for x in calls],
        "tail_B_callers": [hex(x) for x in tails],
        "caller_instruction_windows": [
            {"caller_pc": hex(pc), "call_kind": kind,
             "instructions": arm64_window(buf,base,pc,0x58,0x34)}
            for kind, sites in (("BL",calls[:MAX_CALLERS]),("B",tails[:MAX_CALLERS]))
            for pc in sites
        ],
        "v1_concrete_class_verified": False, "v2_concrete_class_verified": False,
        "returned_record_to_00983_verified": False,
        "material_type_enum_verified": False,
        "warning": "Callers and tail-calls prove control-flow references, not V1/V2 vtable targets or 00983 provenance.",
    }
    return species, item_result


def selftest():
    assert branch_target(0x1000,0x94000400) == (0x2000,"BL")
    assert branch_target(0x1000,0x14000400) == (0x2000,"B")
    assert branch_target(0x1000,0xD65F03C0) is None
    lo,hi=FIELD&0xffff,FIELD>>16
    movz=0x52800000|(lo<<5)|9
    movk=0x72800000|(1<<21)|(hi<<5)|9
    pairs=hash_mov_pairs(struct.pack("<II",movz,movk),0x4000,FIELD)
    assert len(pairs)==1 and pairs[0]["grade"]=="ADJACENT_EXACT_IMMEDIATE_PAIR"
    try:
        verify_edges([{"source_object_hash":"a","target_object_hash":"a"}]*603)
    except ValueError:
        pass
    else:
        raise AssertionError("Accepted self-referential or forged species records")
    try:
        analyze(b"forged",b"forged",[])
    except ValueError:
        pass
    else:
        raise AssertionError("Accepted invalid native originals")
    print("PASS branch immediates, strict literal encoding, edge and source guards")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--main",type=Path,default=MAIN)
    p.add_argument("--item",type=Path,default=ITEM)
    p.add_argument("--edges",type=Path,default=EDGES)
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test:
        selftest()
        return
    with args.edges.open(encoding="utf-8",newline="") as f:
        edges=list(csv.DictReader(f))
    species, item = analyze(args.main.read_bytes(), args.item.read_bytes(), edges)
    for out,filename,obj in (
        (POKEMON_OUT,"m20_original_property_hash_sites.json",species),
        (ITEM_OUT,"m20_two_stage_item_callers.json",item),
    ):
        out.mkdir(parents=True,exist_ok=True)
        (out/filename).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "property_literal_cells": species["literal_cells_total"],
        "property_immediate_pairs": species["movz_movk_pairs_total"],
        "property_literal_xrefs": species["adrp_literal_xrefs_total"],
        "two_stage_BL_callers": item["direct_BL_callers_total"],
        "two_stage_tail_B_callers": item["tail_B_callers_total"],
        "species_id_bindings_verified":0,"material_type_enum_verified":False
    },ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
