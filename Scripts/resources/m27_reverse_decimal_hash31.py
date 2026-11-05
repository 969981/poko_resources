#!/usr/bin/env python3
"""M27: falsifiable 31-polynomial / reversed 4-digit numeric pattern audit.

SOURCE: original Pokopia 2.0.1 NSO-independent KIDSOBJDB class
0x9D1AFA46, OID 0xB4A1803B, property hashes:
keys 0xE88C8D60, values 0x34CBB458, 3543 indexed pairs.

Observed model, NOT native hash implementation proof:
  hash31(bytes) = (31*h + ASCII) modulo 2^32, initialized at 0.
  key_or_oid = hash31(reverse(four ASCII digits))*pow(31,shift)+C
  shifts for icon_poke: 11/66, icon_poke_uni: 15/70.
  C depends on variant, including _nh and _11/_12/_13 forms.

Verify every known source byte; fit per group on only first sample, test
other held-out records, test all canonical 0000..9999 candidates
against the full 3543 original key/value array. No numeric game ID proof.
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

from Scripts.resources.m16_verify_pokemon_texture_kidsobjdb import parse_kids

ROOT=Path("UnPack/2.0.1/Resources")
OUT=ROOT/"Villagers/Native_2.0.1/M27"
M26=ROOT/"Villagers/Native_2.0.1/M26/m26_4_original_3543_parallel_key_value_pairs.csv"
M25=ROOT/"Pokemon/NativeRecoveryM25/m25_8_complete_native_629_kids_icon_source_index.csv"
RAW=Path("UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0xacd220a8.fdata/native/root_019167_50ae86ef.kidsobjdb")
PIN="86f90b4c11da9bc2b3e28889a5090ff507f96ca713fe4fad1dd50f6f692d7541"
OWNER=0xB4A1803B
TYPE=0x9D1AFA46
KEY_HASH=0xE88C8D60
VALUE_HASH=0x34CBB458
SIZE=3543
FAMILIES={
    "normal":{"from":429,"to":741,"shifts":(11,66),"prefix":"icon_poke_"},
    "uni":{"from":743,"to":1055,"shifts":(15,70),"prefix":"icon_poke_uni_"},
}
NAME=re.compile(r"^icon_poke_(uni_)?(\d{4})_(\d{2})_(\d{2})_(\d{2})(_nh)?$")
COLS=("original_slot","native_family","four_digit_name_component","native_variant",
      "original_source_oid","original_texture_oid","original_name",
      "original_key_hash","original_source_oid_value",
      "model_predicted_key_hash","model_predicted_source_oid",
      "model_key_exact","model_value_exact","independent_holdout",
      "key_template_constant","value_template_constant",
      "native_31_hash_function_verified","native_game_species_ID_verified")

def rows(path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def sha256(buf):return hashlib.sha256(buf).hexdigest()

def power31(exp:int):
    if exp<0:raise ValueError("Negative degree")
    return pow(31,exp,1<<32)

def h31(text:str):
    r=0
    for b in text.encode("ascii"):
        r=(31*r+b)&0xffffffff
    return r

def reverse_four(raw:str):
    if len(raw)!=4 or not raw.isdigit():raise ValueError("Original four-digit component invalid")
    return raw[::-1]

def bits(v):return int(v,16)

def parse_source_name(src):
    names=src["original_texture_name_variants"].split(";")
    accepted=[(n,NAME.fullmatch(n)) for n in names]
    accepted=[(n,m) for n,m in accepted if m]
    if not accepted:raise ValueError(f"Original icon name variants missing expected 4 digits: {names}")
    # Aliased same source/texture object can have both normal and _nh
    # names. Choosing the non-_nh entry must not invent another source.
    preferred=sorted(accepted,key=lambda p:(p[1].group(6) is not None,p[0]))[0]
    n,m=preferred
    family="uni" if m.group(1) else "normal"
    form="_".join(m.group(i) for i in (3,4,5))+(m.group(6) or "")
    return family,m.group(2),form,n

def native_input():
    b=RAW.read_bytes()
    if sha256(b)!=PIN:raise ValueError("Original KIDSOBJDB SHA256 mismatch")
    _,nodes=parse_kids(b)
    obj=nodes.get(OWNER)
    if obj is None or obj["type"]!=TYPE:raise ValueError("Native class/source OID changed")
    k=obj["fields"].get(KEY_HASH);v=obj["fields"].get(VALUE_HASH)
    if not k or not v or (k["count"],v["count"])!=(SIZE,SIZE):
        raise ValueError("Original twin 3543-u32 arrays missing")
    if k["offset"]!=364556 or v["offset"]!=378728:
        raise ValueError("Original source file field byte offsets changed")
    key=struct.unpack_from("<"+"I"*SIZE,b,k["offset"])
    values=struct.unpack_from("<"+"I"*SIZE,b,v["offset"])
    return key,values

def audit():
    keys,vals=native_input()
    canonical=rows(M26)
    source=rows(M25)
    if len(canonical)!=SIZE or len(source)!=629:
        raise ValueError("M25/26 original source inventory changed")
    by_slot={}
    for src in source:
        if src["original_owner_oid"]!="b4a1803b":continue
        slot=int(src["original_array_index"])
        if slot in by_slot:raise ValueError("Duplicate original source slot")
        by_slot[slot]=src
    if len(by_slot)!=628 or set(by_slot)!=set(range(429,1057)):
        raise ValueError("M25 verified 628 native source OIDs changed")
    for idx,r in enumerate(canonical):
        if (int(r["native_array_index"])!=idx
            or bits(r["original_key_u32"])!=keys[idx]
            or bits(r["original_value_u32"])!=vals[idx]):
            raise ValueError(f"Native original source-byte crosscheck failed: {idx}")
    model_inputs=[]
    unmodeled=[]
    for slot,src in sorted(by_slot.items()):
        try:family,number,form,name=parse_source_name(src)
        except ValueError:
            unmodeled.append({"slot":slot,"names":src["original_texture_name_variants"]})
            continue
        familycfg=FAMILIES[family]
        if not familycfg["from"]<=slot<=familycfg["to"]:
            raise ValueError(f"Source family and original array block disagree at {slot}")
        if bits(src["source_oid"])!=vals[slot]:
            raise ValueError(f"Original source OID mismatch at {slot}")
        x=h31(reverse_four(number))
        a,b=familycfg["shifts"]
        ckey=(keys[slot]-x*power31(a))&0xffffffff
        cval=(vals[slot]-x*power31(b))&0xffffffff
        model_inputs.append({
            "slot":slot,"family":family,"number":number,"variant":form,
            "name":name,"source":src,
            "ckey":ckey,"cval":cval,
        })
    if len(model_inputs)!=626 or len(unmodeled)!=2:
        raise ValueError(f"Unexpected native source shape {len(model_inputs)} / {len(unmodeled)}")
    groups=defaultdict(list)
    for row in model_inputs:groups[(row["family"],row["variant"])].append(row)
    fitted={}
    failures=[]
    count_heldout=0
    evidence=[]
    for (family,variant),items in sorted(groups.items()):
        a,b=FAMILIES[family]["shifts"]
        items.sort(key=lambda r:r["slot"])
        ckey=items[0]["ckey"]
        cval=items[0]["cval"]
        heldout_correct=0
        for i,row in enumerate(items):
            idx=row["slot"]
            num=reverse_four(row["number"])
            x=h31(num)
            predicted_key=(x*power31(a)+ckey)&0xffffffff
            predicted_val=(x*power31(b)+cval)&0xffffffff
            correct=predicted_key==keys[idx] and predicted_val==vals[idx]
            if not correct:failures.append({"slot":idx,"model":f"{family}:{variant}"})
            if i:
                count_heldout+=1
                heldout_correct+=int(correct)
            evidence.append({
                "original_slot":idx,
                "native_family":family,
                "four_digit_name_component":row["number"],
                "native_variant":variant,
                "original_source_oid":row["source"]["source_oid"],
                "original_texture_oid":row["source"]["target_texture_oid"],
                "original_name":row["name"],
                "original_key_hash":f"{keys[idx]:08x}",
                "original_source_oid_value":f"{vals[idx]:08x}",
                "model_predicted_key_hash":f"{predicted_key:08x}",
                "model_predicted_source_oid":f"{predicted_val:08x}",
                "model_key_exact":int(predicted_key==keys[idx]),
                "model_value_exact":int(predicted_val==vals[idx]),
                "independent_holdout":int(i>0),
                "key_template_constant":f"{ckey:08x}",
                "value_template_constant":f"{cval:08x}",
                "native_31_hash_function_verified":"",
                "native_game_species_ID_verified":"",
            })
        fitted[(family,variant)]={"family":family,"variant":variant,"sample_count":len(items),
                                   "heldout_count":len(items)-1,"heldout_exact":heldout_correct,
                                   "shift_key":a,"shift_value":b,
                                   "constant_key":f"{ckey:08x}",
                                   "constant_value":f"{cval:08x}",
                                   "evidence_grade":"MULTI_SAMPLE_EXACT_MODEL" if len(items)>1
                                       else "SINGLE_SAMPLE_FIT_NOT_INDEPENDENT",
                                   "anchor_slot":items[0]["slot"]}
    if failures:raise ValueError(f"M27 31 polynomial key/value model rejected by original bytes: {failures[:12]}")
    originals_by_key=defaultdict(list)
    for i,key in enumerate(keys):originals_by_key[key].append(i)
    scan_rows=[]
    all_probe_count=0
    new_full=[]
    key_only=[]
    for (family,variant),fit in fitted.items():
        a,b=fit["shift_key"],fit["shift_value"]
        ckey,cval=bits(fit["constant_key"]),bits(fit["constant_value"])
        for idnum in range(10000):
            name=f"{idnum:04d}"
            x=h31(reverse_four(name))
            pk=(x*power31(a)+ckey)&0xffffffff
            pv=(x*power31(b)+cval)&0xffffffff
            all_probe_count+=1
            for slot in originals_by_key.get(pk,[]):
                match=vals[slot]==pv
                out={
                    "family":family,"variant":variant,"numeric_four_digit_component":name,
                    "original_slot":slot,"predicted_key":f"{pk:08x}",
                    "predicted_source_oid":f"{pv:08x}",
                    "original_source_oid":f"{vals[slot]:08x}",
                    "key_and_value_both_exact":match,
                    "previously_M25_icon_source":slot in by_slot,
                    "verified_game_ID":"",
                }
                scan_rows.append(out)
                if match and slot not in by_slot:new_full.append(out)
                if not match:key_only.append(out)
    OUT.mkdir(parents=True,exist_ok=True)
    evidence.sort(key=lambda x:int(x["original_slot"]))
    with (OUT/"m27_626_native_icon_hash31_template_validation.csv").open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=COLS);writer.writeheader();writer.writerows(evidence)
    probes=("family","variant","numeric_four_digit_component","original_slot",
            "predicted_key","predicted_source_oid","original_source_oid",
            "key_and_value_both_exact","previously_M25_icon_source","verified_game_ID")
    with (OUT/"m27_10k_per_variant_reverse_numeric_probes.csv").open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=probes);writer.writeheader();writer.writerows(scan_rows)
    with (OUT/"m27_hash31_candidate_family_constants.json").open("w",encoding="utf-8") as f:
        json.dump(list(fitted.values()),f,ensure_ascii=False,indent=2);f.write("\n")
    pair_key_diff={
        "normal":{
            "key_p14":f"{power31(14):08x}",
            "value_p69":f"{power31(69):08x}"},
        "uni":{
            "key_p18":f"{power31(18):08x}",
            "value_p73":f"{power31(73):08x}"},
    }
    summary={
        "version":"2.0.1","original_sha256":PIN,
        "original_3543_key_value_slots_verified":SIZE,
        "source_icon_OIDs_verified":len(by_slot),
        "source_icon_rows_with_4digit_numeric_pattern":len(evidence),
        "excluded_nonnumeric_image_records":unmodeled,
        "independent_holdout_bytes_both_key_and_value_exact":count_heldout,
        "numeric_31_template_groups":len(fitted),
        "single_observation_variant_groups":sum(x["sample_count"]==1 for x in fitted.values()),
        "normal_canonical_template_rows":sum(x["native_family"]=="normal"
            and x["native_variant"]=="00_00_00" for x in evidence),
        "uni_canonical_template_rows":sum(x["native_family"]=="uni"
            and x["native_variant"]=="00_00_00" for x in evidence),
        "all_model_predicted_keys_match":all(x["model_key_exact"] for x in evidence),
        "all_model_predicted_source_OIDs_match":all(x["model_value_exact"] for x in evidence),
        "observed_base31_powers":pair_key_diff,
        "synthetic_numeric_names_tested_across_all_groups":all_probe_count,
        "numeric_candidate_probe_key_match_count":len(scan_rows),
        "numeric_candidate_probe_both_key_value_exact_count":sum(x["key_and_value_both_exact"] for x in scan_rows),
        "numeric_probe_new_non_M25_source_OIDs_confirmed":len(new_full),
        "numeric_probe_key_only_conflicts":len(key_only),
        "native_hash31_implementation_located":False,
        "native_species_ID_to_source_OID_verified":False,
        "original_numeric_name_is_national_dex_ID_proven":False,
        "warning":"Mathematical 31-polynomial source-byte model, including independently tested holdouts, is not yet an original game native hash implementation or gameplay species ID consumer. One-sample form groups cannot be independently validated.",
    }
    (OUT/"m27_original_reverse31_model_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary

def selftest():
    assert power31(14)==0x59DB6A41
    assert power31(69)==0x38E0609F
    assert power31(18)==0xCDAA61C1
    assert power31(73)==0x1A70F91F
    assert h31("abc")==96354
    assert reverse_four("0043")=="3400"
    print("PASS 31 polynomial arithmetic and reverse four-digit template")

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test",action="store_true")
    a=parser.parse_args()
    if a.self_test:selftest()
    else:audit()

if __name__=="__main__":main()
