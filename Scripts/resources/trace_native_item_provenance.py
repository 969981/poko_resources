#!/usr/bin/env python3
"""M11: bounded AArch64 item-field consumer dataflow on native Pokopia 2.0.1 main.

This is original-byte *static* evidence, not a loader, category or stack limit
proof. Co-access of +0x22/+0x26/+0x3a is not an identified 68-byte Item record
unless its base register is traced to the original 00983.bin parser.
"""
from __future__ import annotations

import argparse
import bisect
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

try:
    from .trace_native_species_item_callers import get_sections
except ImportError:
    from trace_native_species_item_callers import get_sections

MAIN_SHA = "8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
ITEM_SHA = "2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f"
FIELD_CODES = {(0x22, "ldrh"): 0x79400000,
               (0x26, "ldrb"): 0x39400000,
               (0x3a, "ldrb"): 0x39400000}
IMMEDIATES = (68, 99, 100, 255, 983, 4600)
OUT = Path("UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M11")


def field_load(word):
    opcode = word & 0xffc00000
    if opcode == 0x79400000:
        disp = ((word >> 10) & 0xfff) * 2
        kind = "ldrh"
    elif opcode == 0x39400000:
        disp = (word >> 10) & 0xfff
        kind = "ldrb"
    else:
        return None
    if (disp, kind) not in FIELD_CODES:
        return None
    return {"field": disp, "kind": kind,
            "base_register": (word >> 5) & 31,
            "target_register": word & 31}


def cmp_immediate(word):
    if (word & 0x7f00001f) != 0x7100001f:
        return None
    shift = (word >> 22) & 3
    if shift not in (0, 1):
        return None
    value = ((word >> 10) & 0xfff) << (12 if shift == 1 else 0)
    return {"constant": value, "compare_register": (word >> 5) & 31,
            "width": 64 if (word >> 31) & 1 else 32}


def movz_immediate(word):
    if (word & 0x7f800000) != 0x52800000:
        return None
    shift = ((word >> 21) & 3) * 16
    return ((word >> 5) & 0xffff) << shift


def scan(code: bytes, base: int):
    fields = {0x22: [], 0x26: [], 0x3a: []}
    compares = {x: [] for x in IMMEDIATES}
    movz = {x: [] for x in IMMEDIATES}
    for i, (word,) in enumerate(struct.iter_unpack("<I", code[:len(code) & ~3])):
        pc = base + 4 * i
        field = field_load(word)
        if field is not None:
            fields[field["field"]].append({"pc": pc, "word": f"{word:08x}", **field})
        c = cmp_immediate(word)
        if c is not None and c["constant"] in compares:
            compares[c["constant"]].append({"pc": pc, "word": f"{word:08x}", **c})
        m = movz_immediate(word)
        if m is not None and m in movz:
            movz[m].append(pc)
    return fields, compares, movz


def canonical(name: str):
    name = name.lower()
    if len(name) >= 2 and name[0] in "wx" and name[1:].isdigit():
        return "x" + name[1:]
    return name


def is_barrier(insn):
    from capstone import CS_GRP_JUMP, CS_GRP_CALL, CS_GRP_RET
    return insn.group(CS_GRP_JUMP) or insn.group(CS_GRP_CALL) or insn.group(CS_GRP_RET)


def write_names(insn):
    _, writes = insn.regs_access()
    return {canonical(insn.reg_name(r)) for r in writes}


def slice_instructions(md, code: bytes, base: int, start: int, end: int):
    if start < base or end > base + len(code) or end < start:
        return []
    return list(md.disasm(code[start-base:end-base], start))


def no_register_kill(md, code, base, first, second, reg, skip_first_write=False):
    """Is this same-register co-access *linear*? No branch/write in between."""
    if first > second:
        first, second = second, first
    seq = slice_instructions(md, code, base, first, second+4)
    if len(seq) != (second-first)//4 + 1:
        return False
    for index, insn in enumerate(seq[:-1]):
        if is_barrier(insn) or (reg in write_names(insn) and not (index == 0 and skip_first_write)):
            return False
    return True


def producer_chain(md, code, base, pc, reg, max_instructions=28):
    """Backward straight-line defining instruction; not interprocedural proof."""
    start = max(base, pc - max_instructions * 4)
    seq = slice_instructions(md, code, base, start, pc)
    result = {"status": "NO_STRAIGHT_LINE_DEFINITION_IN_WINDOW", "max_instructions": max_instructions}
    for insn in reversed(seq):
        if is_barrier(insn):
            return {"status": "STOPPED_AT_CONTROL_FLOW", "barrier_pc": hex(insn.address)}
        if reg in write_names(insn):
            return {"status": "LOCAL_REGISTER_DEFINITION_ONLY",
                    "pc": hex(insn.address),
                    "assembly": insn.mnemonic + " " + insn.op_str,
                    "word": code[insn.address-base:insn.address-base+4].hex()}
    return result


def windows(md, code, base, pc, before=40, after=56):
    start = max(base, (pc-before) & ~3)
    end = min(base+len(code), (pc+after+3) & ~3)
    return [{"pc": hex(i.address), "assembly": i.mnemonic+" "+i.op_str,
             "word_le": code[i.address-base:i.address-base+4].hex()}
            for i in slice_instructions(md,code,base,start,end)]


def nearby(sorted_positions, center, radius):
    lo = bisect.bisect_left(sorted_positions, center-radius)
    hi = bisect.bisect_right(sorted_positions, center+radius)
    return sorted_positions[lo:hi]


def evaluate(fields, compares, movz, code, base, max_output=120):
    from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = True
    other = {k: {x["pc"]: x for x in v} for k, v in fields.items()}
    pcs = {k: sorted(v) for k, v in (
        (key, [x["pc"] for x in values]) for key, values in fields.items())}
    cmps = sorted([(r["pc"], number, r["compare_register"]) for number, rows in compares.items()
                   for r in rows if number in (99, 100, 255)])
    cmp_pcs = [x[0] for x in cmps]
    constants = {k: sorted(movz[k] + [r["pc"] for r in compares[k]])
                 for k in (68, 983, 4600)}

    candidates = []
    aggregate = Counter()
    for candidate in fields[0x26]:
        pc = candidate["pc"]
        basereg = "x" + str(candidate["base_register"])
        siblings = []
        for k in (0x22, 0x3a):
            for near in nearby(pcs[k], pc, 0x100):
                f = other[k][near]
                if f["base_register"] != candidate["base_register"]:
                    continue
                if no_register_kill(md, code, base, pc, near, basereg):
                    siblings.append({"pc": hex(near), "field": hex(k),
                                     "same_straight_line_base_register": basereg})
        if not siblings:
            continue
        kinds = {s["field"] for s in siblings}
        grade = ("SAME_BASE_22_26_3A" if len(kinds) == 2
                 else "SAME_BASE_22_26" if "0x22" in kinds else "SAME_BASE_26_3A")
        aggregate[grade] += 1
        close_cmp = []
        for idx in nearby(cmp_pcs, pc, 0x120):
            at = bisect.bisect_left(cmp_pcs, idx)
            for q in cmps[at:bisect.bisect_right(cmp_pcs, idx)]:
                cmp_pc, limit, rnum = q
                if cmp_pc <= pc:
                    continue
                if rnum != candidate["target_register"]:
                    attribution = "DIFFERENT_REGISTER_NOT_DIRECT_FIELD_COMPARE"
                elif no_register_kill(md, code, base, pc, cmp_pc,
                                       "x"+str(candidate["target_register"]), skip_first_write=True):
                    attribution = "STRAIGHT_LINE_SAME_FIELD_REGISTER_NO_ITEM_BASE_PROOF"
                else:
                    attribution = "REGISTER_REDEFINED_OR_CONTROL_FLOW"
                close_cmp.append({"pc":hex(cmp_pc), "constant":limit,
                                  "compare_register":"x"+str(rnum),
                                  "relation_to_0x26":attribution})
        closest_constant = {
            str(k): [hex(x) for x in nearby(constants[k], pc, 0x180)[:6]]
            for k in constants
        }
        score = (30 if grade == "SAME_BASE_22_26_3A" else 20
                 if grade == "SAME_BASE_22_26" else 10)
        score += len(close_cmp[:4])
        score += sum(2 for k in (68, 983, 4600) if closest_constant[str(k)])
        aggregate["with_nearby_cmp"] += bool(close_cmp)
        aggregate["with_nearby_stride_68"] += bool(closest_constant["68"])
        aggregate["with_nearby_bound_4600"] += bool(closest_constant["4600"])
        candidates.append({
            "pc": hex(pc), "raw_opcode": candidate["word"],
            "base_register": basereg,
            "target_register": "x"+str(candidate["target_register"]),
            "coaccess": grade, "same_base_siblings": siblings[:14],
            "nearby_99_100_255_compares": close_cmp[:12],
            "nearby_immediate_positions": closest_constant,
            "base_producer": producer_chain(md, code, base, pc, basereg),
            "score_for_review_only": score,
            "evidence": "STATIC_SAME_REGISTER_WITHOUT_CROSS_BRANCH_NOT_ITEM_BASE_PROVEN"
        })
    candidates.sort(key=lambda c: (-c["score_for_review_only"], int(c["pc"],16)))
    for c in candidates[:max_output]:
        c["assembly_context"] = windows(md, code, base, int(c["pc"],16))
    return candidates[:max_output], dict(aggregate), len(candidates)


def analyze(main: bytes, item_table: bytes, max_output=120):
    digest = hashlib.sha256(main).hexdigest()
    if digest != MAIN_SHA:
        raise ValueError("ORIGINAL_NSO_SHA_MISMATCH:"+digest)
    itemdigest = hashlib.sha256(item_table).hexdigest()
    if itemdigest != ITEM_SHA:
        raise ValueError("ORIGINAL_ITEM_TABLE_SHA_MISMATCH:"+itemdigest)
    if len(item_table) != 64+4600*68 or struct.unpack_from("<II",item_table) != (4600,3):
        raise ValueError("ITEM_TABLE_RECORD_LAYOUT_INVALID")
    kind, parts = get_sections(main)
    if kind != "NSO0":
        raise ValueError("UNEXPECTED_EXEFS_FORMAT")
    text = next(x for x in parts if x["name"] == "text")
    code, base = text["data"], text["mem_offset"]
    fields, compares, movz = scan(code,base)
    ranked, summary, matches = evaluate(fields, compares, movz,code,base,max_output)
    return {
        "status": "STATIC_SAME_REGISTER_COACCESS_ONLY__ITEM_LOADER_UNPROVEN",
        "source_main_sha256": digest,
        "source_00983_sha256": itemdigest,
        "text_base_rva": hex(base), "text_bytes": len(code),
        "inspected_instruction_slots": len(code)//4,
        "item_header_count": 4600, "item_record_stride":68,
        "field_opcodes":{hex(k):len(v) for k,v in fields.items()},
        "numeric_imm_opcode_counts": {
            str(k): {"cmp":len(compares[k]),"movz":len(movz[k])} for k in IMMEDIATES
        },
        "coaccess_summary": summary,
        "coaccess_candidates_total": matches,
        "top_bounded_candidates": ranked,
        "verified_00983_loader_or_base_producer": False,
        "verified_item_category_consumer": False,
        "verified_material_type_enum": False,
        "verified_per_item_max_stack": False,
        "verified_inventory_slot_capacity": False,
        "verified_99_stack_merge_limit": False,
        "limitation": [
            "SAME_BASE means two load instructions have the same register in a straight-line local window; it does not prove that register is a 68-byte 00983 Item record.",
            "A nearby MOVZ 68, 983 or 4600 may be unrelated; it is not yet a traced value/data dependency.",
            "Linear windows do not resolve phi merges, indirect calls, other threads, or object lifetime.",
            "Stack limit requires original inventory merge/split/store call-chain and positive/negative gameplay evidence."
        ]
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--main", type=Path, default=Path("2.0.1/exefs/main"))
    p.add_argument("--item-table", type=Path,
                   default=Path("UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin"))
    p.add_argument("--out", type=Path, default=OUT)
    p.add_argument("--max-candidates", type=int, default=120)
    args = p.parse_args()
    if args.max_candidates<1 or args.max_candidates>300:
        raise ValueError("BAD_MAX_CANDIDATES")
    report = analyze(args.main.read_bytes(),args.item_table.read_bytes(),args.max_candidates)
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"item_consumer_register_provenance.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    compact={k:v for k,v in report.items() if k!="top_bounded_candidates"}
    compact["priority_sites"]=[
        {k:c[k] for k in ("pc","coaccess","base_register","base_producer","nearby_immediate_positions",
                         "nearby_99_100_255_compares","evidence")}
        for c in report["top_bounded_candidates"][:24]
    ]
    (args.out/"item_consumer_review_shortlist.json").write_text(
        json.dumps(compact,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:report[k] for k in (
        "status","source_main_sha256","inspected_instruction_slots","field_opcodes",
        "coaccess_summary","coaccess_candidates_total","verified_00983_loader_or_base_producer",
        "verified_99_stack_merge_limit")},indent=2))


if __name__ == "__main__":
    main()
