#!/usr/bin/env python3
"""M30.1: validate raw GDB runtime witness against exact original KIDS bytes.

This accepts a JSONL from Scripts/gdb/m30_pokopia_two_phase_witness.py.
Evidence grades are separate:
1) original 2.0.1 NSO addresses/record-layout references are byte-verified
   by previous M25-M29 static reports;
2) raw GDB memory bytes have coherent PC, register and address provenance;
3) an operator-chosen KIDS slot/key/OID pair can be compared with *original*
   root_019167_50ae86ef.kidsobjdb, SHA256-pinned;
4) no automatic proof of a gameplay species ID or same-instance runtime
   consumer is allowed. A same-session marker or matching memory value does
   not prove that the KIDS table was selected by that entity's game ID.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
import tempfile
from collections import Counter
from pathlib import Path

from Scripts.resources.m16_verify_pokemon_texture_kidsobjdb import parse_kids

ORIGINAL=Path("UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0xacd220a8.fdata/native/root_019167_50ae86ef.kidsobjdb")
KIDS_SHA="86f90b4c11da9bc2b3e28889a5090ff507f96ca713fe4fad1dd50f6f692d7541"
MAIN_SHA="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
OWNER=0xB4A1803B
TYPE=0x9D1AFA46
ARRAYS=(0xE88C8D60,0x34CBB458)
COUNT=3543
# Verified original ARM64 words at source-qualified breakpoint sites.
SOURCE_WORDS={
    0x1136A60:0x794012C8,
    0x5FD168:0x912CD463,
    0xDD1B48:0x2A1F03E8,
    0xDD1B74:0xB863D92C,
}
DESC_HASHES=(0x2F610FEA,0xE88C8D60,0x34CBB458)
CODE={
    "identity":{
        "three_u16_record_before_read":0x1136A60,
        "pokemon_list_string_reference":0x5FD168,
    },
    "kids":{
        "kids_property_descriptor_entry":0xDD1B48,
        "kids_property_descriptor_hash_read":0xDD1B74,
    },
}
ROOT=Path("UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M30")

def q(v,label):
    if isinstance(v,bool) or not isinstance(v,(str,int)):
        raise ValueError(f"{label}: integer/hex required")
    try:i=int(v,0) if isinstance(v,str) else v
    except ValueError as ex:raise ValueError(f"{label}: invalid integer") from ex
    if i<0 or i>0xffffffffffffffff:raise ValueError(f"{label}: u64 out of range")
    return i

def raw_arrays(path=ORIGINAL):
    b=path.read_bytes()
    if hashlib.sha256(b).hexdigest()!=KIDS_SHA:
        raise ValueError("Original root_019167 KIDSOBJDB byte hash mismatch")
    _,objects=parse_kids(b)
    obj=objects.get(OWNER)
    if not obj or obj["type"]!=TYPE:
        raise ValueError("Original KIDS class/OID changed")
    entries=[]
    for prop,expected in zip(ARRAYS,(364556,378728)):
        f=obj["fields"].get(prop)
        if not f or f["count"]!=COUNT or f["offset"]!=expected:
            raise ValueError("Original double KIDS arrays changed")
        entries.append(struct.unpack_from("<"+"I"*COUNT,b,f["offset"]))
    if len(set(entries[0]))!=COUNT or len(set(entries[1]))!=COUNT:
        raise ValueError("Native 3543 source key/value arrays lost uniqueness")
    return entries

def check_header(rec):
    if (rec.get("kind")!="header"
        or rec.get("schema")!="M30_POKOPIA_2_0_1_NATIVE_WITNESS_V1"
        or rec.get("source_game_version")!="2.0.1"
        or rec.get("source_main_sha256_claim")!=MAIN_SHA
        or rec.get("runtime_build_verified_by_target_bytes") is not False
        or rec.get("identity_binding_proven") is not False):
        raise ValueError("Missing M30 original provenance header or false run-time verification")
    mode=rec.get("phase")
    if mode not in CODE:
        raise ValueError("Expected M30 identity or kids phase")
    if rec.get("code_offsets")!={k:hex(v) for k,v in CODE[mode].items()}:
        raise ValueError("Trace event code address set does not match pinned version")
    if rec.get("requested_hardware_breakpoints") is not True:
        raise ValueError("Hardware breakpoint request provenance unavailable")
    base=q(rec.get("actual_main_base_supplied_by_operator"),"main base")
    if base<0x10000 or base%4:raise ValueError("Bad runtime main base")
    limit=rec.get("limit")
    if type(limit) is not int or not 1<=limit<=500:raise ValueError("Bad trace limit")
    return mode,base,limit

def check_memory(r,expected_address=None,expected_size=None):
    if not isinstance(r,dict) or type(r.get("read_ok")) is not bool:
        raise ValueError("Malformed bounded memory reading")
    if not r["read_ok"]:
        if expected_address is None and r.get("address") is not None:
            # Address could be recorded even for target access errors.
            q(r["address"],"failed-read address")
        return None
    if expected_address is None:
        raise ValueError("Memory read without source register or original address provenance")
    a=q(r.get("address"),"read address")
    n=r.get("size")
    if type(n) is not int or n not in (1,4,6):
        raise ValueError("Unbounded / unrecognized memory read")
    if expected_size is not None and n!=expected_size:
        raise ValueError("Bounded original instruction read size changed")
    if expected_address is not None and a!=expected_address:
        raise ValueError("Observed memory address doesn't follow original register")
    b=r.get("raw_hex")
    if not isinstance(b,str) or len(b)!=2*n:
        raise ValueError("Truncated or non-hex memory response")
    try:by=bytes.fromhex(b)
    except ValueError as ex:raise ValueError("Invalid memory bytes") from ex
    if r.get("decoded_u32_le") is not None:
        if n!=4 or type(r["decoded_u32_le"]) is not int or r["decoded_u32_le"]!=int.from_bytes(by,"little"):
            raise ValueError("Memory uint32 decode differs from actual raw bytes")
    return by

def verify(path,original_arrays):
    with Path(path).open(encoding="utf-8") as f:
        lines=[(n,json.loads(x)) for n,x in enumerate(f,1) if x.strip()]
    if not lines or len(lines)>10000:raise ValueError("Trace missing header or too long")
    mode,base,limit=check_header(lines[0][1])
    counts=Counter()
    samples=0
    markers=Counter()
    read_errors=Counter()
    desc=Counter()
    original_opcode_matches=Counter()
    original_opcode_read_errors=Counter()
    pair_evidence=[]
    record_triplets=[]
    flag_values=Counter()
    for lineno,r in lines[1:]:
        kind=r.get("kind")
        if kind=="operator_marker":
            if r.get("same_game_instance_proven") is not False:
                raise ValueError(f"Operator marker falsely proves identity on line {lineno}")
            label=r.get("label")
            if not isinstance(label,str) or not 1<=len(label)<=72:
                raise ValueError("Operator marker malformed")
            markers[label]+=1
        elif kind=="event":
            samples+=1
            if samples>limit or r.get("ordinal")!=samples:
                raise ValueError("Sample count or order inconsistent")
            label=r.get("event")
            if label not in CODE[mode] or r.get("phase")!=mode:
                raise ValueError("Trace claims event outside requested hardware-breakpoint phase")
            expected=CODE[mode][label]
            if q(r.get("original_main_offset"),"offset")!=expected or q(r.get("absolute_pc"),"pc")!=base+expected:
                raise ValueError("Original program counter and supplied load base disagree")
            for field in ("same_game_instance_proven","native_species_ID_proven","native_KIDS_source_OID_proven"):
                if r.get(field) is not False:raise ValueError(f"Unproven runtime identity claim: {field}")
            regs=r.get("registers")
            if not isinstance(regs,dict):raise ValueError("Registers required")
            for k,v in regs.items():
                if k!="sp" and (not k.startswith("x") or not k[1:].isdigit()):
                    raise ValueError("Unexpected register name")
                if v is not None:q(v,k)
            opcode=r.get("current_instruction_original_code_read")
            source_word=q(r.get("expected_original_instruction_word"),"original opcode word")
            if source_word!=SOURCE_WORDS[expected]:
                raise ValueError("Record changed expected pinned AArch64 instruction word")
            check=check_memory(opcode,expected_address=base+expected,expected_size=4)
            if check is None:
                original_opcode_read_errors[label]+=1
            elif int.from_bytes(check,"little")!=source_word:
                raise ValueError("Target breakpoint instruction differs from original pinned 2.0.1 source bytes")
            else:
                original_opcode_matches[label]+=1
            reads=r.get("bounded_original_instruction_reads")
            if not isinstance(reads,dict):raise ValueError("Missing bounded memory map")
            expect={
                "three_u16_record_before_read":"x22_plus4_to_plus9",
                "pokemon_list_string_reference":"x19_plus26_byte",
                "kids_property_descriptor_hash_read":"descriptor_hash_at_x9_plus_index",
            }.get(label)
            if (set(reads)!={expect}) if expect is not None else bool(reads):
                raise ValueError("Wrong original instruction memory-read site")
            if expect:
                src={"three_u16_record_before_read":"x22",
                     "pokemon_list_string_reference":"x19",
                     "kids_property_descriptor_hash_read":"x9"}[label]
                pointer=q(regs[src],src) if regs.get(src) is not None else None
                idx=r.get("descriptor_index_w3") if label=="kids_property_descriptor_hash_read" else None
                address=pointer+(
                    4 if src=="x22" else 0x26 if src=="x19" else 4*idx
                ) if pointer is not None and (src!="x9" or type(idx) is int and 0<=idx<=2) else None
                n={"x22":6,"x19":1,"x9":4}[src]
                b=check_memory(reads[expect],expected_address=address,expected_size=n)
                if b is None:read_errors[label]+=1
                elif src=="x22":
                    bits=list(struct.unpack("<3H",b))
                    record_triplets.append({
                        "native_pc":hex(expected),"u16_plus4":bits[0],"u16_plus6":bits[1],"u16_plus8":bits[2],
                        "original_game_species_ID_field_proven":False,
                    })
                elif src=="x19":flag_values[b[0]]+=1
                else:
                    if idx is None or type(idx) is not int or not 0<=idx<=2:
                        raise ValueError("Descriptor read with invalid index")
                    val=int.from_bytes(b,"little")
                    if val!=DESC_HASHES[idx]:
                        raise ValueError("Observed runtime property descriptor Hash disagrees with original NSO property schema")
                    desc[f"index_{idx}_hash_0x{val:08x}"]+=1
            counts[label]+=1
        elif kind=="operator_raw_pair_candidate":
            if r.get("operator_supplied_address_provenance") is not False:
                raise ValueError("Operator-supplied raw addresses cannot be auto-verified")
            for f in ("same_instance_link_proven","game_species_ID_verified"):
                if r.get(f) is not False:raise ValueError("Unverified raw source pair promoted as real species ID")
            slot=r.get("original_kids_array_slot_claim")
            if type(slot) is not int or not 0<=slot<COUNT:
                raise ValueError("Out-of-bounds original KIDS slot")
            kb=check_memory(r.get("key_u32_raw"),expected_size=4)
            vb=check_memory(r.get("source_oid_u32_raw"),expected_size=4)
            if kb is not None and vb is not None:
                observed=(int.from_bytes(kb,"little"),int.from_bytes(vb,"little"))
                expected=(original_arrays[0][slot],original_arrays[1][slot])
                exact=observed==expected
            else:
                observed=None;expected=(original_arrays[0][slot],original_arrays[1][slot])
                exact=False
            pair_evidence.append({
                "slot":slot,
                "observed_key_u32":f"{observed[0]:08x}" if observed else None,
                "observed_Source_OID_u32":f"{observed[1]:08x}" if observed else None,
                "original_key_u32":f"{expected[0]:08x}",
                "original_Source_OID_u32":f"{expected[1]:08x}",
                "raw_value_pair_matches_original_KIDS_bytes":exact,
                "operator_provided_address_provenance_verified":False,
                "runtime_same_game_entity_instance_proven":False,
                "native_game_species_ID_verified":False,
            })
        elif kind=="error":
            raise ValueError("GDB recorder reported its own runtime original PC mismatch")
        else:
            raise ValueError(f"Unexpected GDB trace record kind: {kind!r}")
    summary={
        "trace_file":Path(path).name,
        "original_Pokopia_version":"2.0.1",
        "phase":mode,
        "declared_main_base":hex(base),
        "original_KIDS_root_sha256_reverified":KIDS_SHA,
        "source_pairs_reverified":COUNT,
        "observed_event_samples":samples,
        "observed_event_by_site":dict(counts),
        "runtime_original_opcode_spotcheck_matches":dict(original_opcode_matches),
        "runtime_original_opcode_spotcheck_unavailable":dict(original_opcode_read_errors),
        "operator_scenario_markers":dict(markers),
        "bounded_read_failures":dict(read_errors),
        "raw_16_bit_record_triplets":record_triplets[:50],
        "original_property_descriptor_hash_observations":dict(desc),
        "list_record_flag_byte_frequencies":{str(k):v for k,v in sorted(flag_values.items())},
        "operator_supplied_raw_pairs_total":len(pair_evidence),
        "operator_supplied_raw_pairs_with_exact_original_KIDS_values":sum(
            p["raw_value_pair_matches_original_KIDS_bytes"] for p in pair_evidence),
        "raw_pair_evidence":pair_evidence[:100],
        "same_scenario_equals_same_game_instance":False,
        "runtime_target_build_sha_verified":False,
        "runtime_opcode_spotcheck_is_complete_build_proof":False,
        "game_entity_ID_field_proven":False,
        "game_species_ID_to_KIDS_key_proven":False,
        "game_species_ID_to_KIDS_source_OID_proven":False,
        "warning":"A GDB memory value matching a static original source pair establishes byte-value equality only; source memory address ownership, dynamic runtime ID/form selection and same-instance causal dataflow remain unproven.",
    }
    return summary

def selftest():
    assert check_memory({"read_ok":True,"address":"0x20000","size":4,
                         "raw_hex":"00ff0100","decoded_u32_le":130816},
                        expected_address=0x20000,expected_size=4)==bytes.fromhex("00ff0100")
    base=0x7100000000
    head={
        "kind":"header","schema":"M30_POKOPIA_2_0_1_NATIVE_WITNESS_V1",
        "source_game_version":"2.0.1","source_main_sha256_claim":MAIN_SHA,
        "actual_main_base_supplied_by_operator":hex(base),
        "requested_hardware_breakpoints":True,
        "runtime_build_verified_by_target_bytes":False,
        "phase":"kids","limit":5,
        "code_offsets":{k:hex(v) for k,v in CODE["kids"].items()},
        "identity_binding_proven":False}
    rows=[head,{
        "kind":"event","event":"kids_property_descriptor_hash_read","phase":"kids",
        "ordinal":1,"original_main_offset":"0xdd1b74","absolute_pc":hex(base+0xDD1B74),
        "return_lr_x30":hex(base+0x400),"registers":{"x9":"0x100000","x3":"0x2"},
        "expected_original_instruction_word":hex(SOURCE_WORDS[0xDD1B74]),
        "current_instruction_original_code_read":{
            "read_ok":True,"address":hex(base+0xDD1B74),"size":4,
            "raw_hex":struct.pack("<I",SOURCE_WORDS[0xDD1B74]).hex(),
            "decoded_u32_le":SOURCE_WORDS[0xDD1B74]},
        "descriptor_index_w3":2,
        "bounded_original_instruction_reads":{
            "descriptor_hash_at_x9_plus_index":{
                "read_ok":True,"address":hex(0x100000+8),"size":4,
                "raw_hex":struct.pack("<I",0x34CBB458).hex(),
                "decoded_u32_le":0x34CBB458}},
        "same_game_instance_proven":False,
        "native_species_ID_proven":False,
        "native_KIDS_source_OID_proven":False}]
    with tempfile.TemporaryDirectory() as tmp:
        file=Path(tmp)/"mock.jsonl"
        # only original sample at slot 455 needed for mock pair
        keys=[0]*COUNT;values=[0]*COUNT
        keys[455]=0x469E2C00;values[455]=0x06AB845F
        file.write_text("\n".join(json.dumps(r) for r in rows)+"\n",encoding="utf-8")
        got=verify(file,(keys,values))
        assert got["original_property_descriptor_hash_observations"]=={
            "index_2_hash_0x34cbb458":1}
        assert not got["game_species_ID_to_KIDS_key_proven"]
        good={ "kind":"operator_raw_pair_candidate",
            "original_kids_array_slot_claim":455,
            "operator_supplied_address_provenance":False,
            "key_u32_raw":{"read_ok":True,"address":"0x20000","size":4,
                           "raw_hex":struct.pack("<I",keys[455]).hex(),
                           "decoded_u32_le":keys[455]},
            "source_oid_u32_raw":{"read_ok":True,"address":"0x30000","size":4,
                           "raw_hex":struct.pack("<I",values[455]).hex(),
                           "decoded_u32_le":values[455]},
            "same_instance_link_proven":False,
            "game_species_ID_verified":False}
        file.write_text("\n".join(json.dumps(r) for r in rows+[good])+"\n",encoding="utf-8")
        result=verify(file,(keys,values))
        assert result["operator_supplied_raw_pairs_with_exact_original_KIDS_values"]==1
        assert result["runtime_original_opcode_spotcheck_matches"]=={
            "kids_property_descriptor_hash_read":1}
        assert not result["game_species_ID_to_KIDS_source_OID_proven"]
        for changed in [
            {"source_oid_u32_raw":{**good["source_oid_u32_raw"],"raw_hex":"12345678",
                                    "decoded_u32_le":0x78563412}},
            {"operator_supplied_address_provenance":True},
            {"game_species_ID_verified":True},
            {"original_kids_array_slot_claim":COUNT},
        ]:
            altered={**good,**changed}
            file.write_text("\n".join(json.dumps(r) for r in rows+[altered])+"\n",encoding="utf-8")
            try:result=verify(file,(keys,values))
            except ValueError:continue
            # Wrong *values* are not fabricated proof; validator may retain
            # the candidate explicitly marked NONMATCH.
            if "source_oid_u32_raw" in changed:
                assert not result["raw_pair_evidence"][0]["raw_value_pair_matches_original_KIDS_bytes"]
                continue
            raise AssertionError(f"Unverified runtime proof accepted: {changed}")
        wrong={**head,"source_main_sha256_claim":"wrong"}
        file.write_text("\n".join(json.dumps(r) for r in [wrong,rows[1]])+"\n",encoding="utf-8")
        try:verify(file,(keys,values))
        except ValueError:pass
        else:raise AssertionError("Bad runtime original NSO header accepted")
    print("PASS M30 original property descriptor, record snapshots, source pairs and safety gates")

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path)
    parser.add_argument("--out",type=Path,default=Path("m30_validation"))
    parser.add_argument("--self-test",action="store_true")
    a=parser.parse_args()
    if a.self_test:selftest()
    elif a.input:
        arrays=raw_arrays()
        result=verify(a.input,arrays)
        a.out.mkdir(parents=True,exist_ok=True)
        (a.out/"m30_native_runtime_witness_review.json").write_text(
            json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(result,ensure_ascii=False,indent=2))
    else:parser.error("--input <real M30 witness JSONL> or --self-test required")

if __name__=="__main__":main()
