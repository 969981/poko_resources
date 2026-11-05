#!/usr/bin/env python3
"""M26: audit the 62 contiguous PokoHex-only portrait references and select
VISUAL-ONLY one-to-one candidate assignments for 9 ambiguous portraits.

Do not promote a visual choice to a verified Pokopia native game ID.
All 378 PokoHex IDs are THIRD-PARTY reference identifiers, not game IDs.
"""
from __future__ import annotations
import argparse
import csv
import itertools
import json
from collections import Counter,defaultdict
from pathlib import Path

R=Path("UnPack/2.0.1/Resources")
V=R/"Villagers"
O=V/"Native_2.0.1/M26"
SUMMARY=V/"Native_2.0.1/M25/m25_6_complete_378_villager_candidate_inventory.csv"
M25=V/"Native_2.0.1/M25/m25_9_nine_ambiguous_native_array_slot_dossier.csv"
CAT=V/"villager_catalog.csv"
GROUPS=((16,18),(96,98),(218,220),(296,297,298))
REMAINING=range(317,379)

def read(path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def save(rows,name):
    if not rows:raise ValueError("Empty output not permitted")
    O.mkdir(parents=True,exist_ok=True)
    with (O/name).open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),extrasaction="ignore")
        w.writeheader();w.writerows(rows)

def inspect():
    inventory=read(SUMMARY)
    catalog=read(CAT)
    variants=read(M25)
    if len(inventory)!=378 or len(variants)!=54:
        raise ValueError("M25 input changed")
    ref={int(x["portrait_id_pokohex"]):x for x in inventory}
    if len(ref)!=378:raise ValueError("Duplicate PokoHex portrait IDs")
    outstanding=[int(x["portrait_id_pokohex"]) for x in inventory
       if x["candidate_status"]=="NO_CONFIDENT_SOURCE_2_0_1"]
    if outstanding!=list(REMAINING):
        raise ValueError(f"Missing reference is not contiguous original 62: {outstanding}")
    reference=defaultdict(list)
    for x in catalog:
        key=x["portrait_id_raw_u16"]
        if key and int(key) in REMAINING:
            reference[int(key)].append(x)
    if set(reference)!=set(REMAINING):
        raise ValueError("62 PokoHex reference roster entries not all present")
    roster=[]
    for p in REMAINING:
        a=reference[p]
        if len(a)!=1 or not a[0]["en"] or a[0]["is_public"]!="1":
            raise ValueError(f"Invalid third-party 62-record provenance: {p}")
        x=a[0]
        original=ref[p]
        roster.append({
            "reference_pokohex_portrait_id":p,
            "reference_pokohex_game_record_id":x["villager_id"],
            "reference_pokohex_english_name":x["en"],
            "reference_pokohex_japanese_name":x["jp"],
            "reference_pokohex_zh_hans_name":x["zhs"],
            "reference_pokohex_is_public":x["is_public"],
            "reference_png":original["pokohex_reference_png"],
            "original_m25_status":original["candidate_status"],
            "source_native_g1t_found":"",
            "source_native_texinfo_found":"",
            "game_villager_id_consumer_verified":"",
            "game_species_id_consumer_verified":"",
            "version_availability_from_native_romfs_proven":"",
            "status":"REFERENCE_ONLY__NATIVE_2_0_1_ASSET_NOT_YET_VERIFIED",
        })
    if min(int(x["reference_pokohex_game_record_id"]) for x in roster)!=508 or max(int(x["reference_pokohex_game_record_id"]) for x in roster)!=607:
        raise ValueError("Observed PokoHex game record range changed")
    variant_by_id=defaultdict(list)
    for x in variants:
        variant_by_id[int(x["reference_pokohex_portrait_id"])].append(x)
    if set(variant_by_id)!={p for group in GROUPS for p in group}:
        raise ValueError("Unexpected M25 nine ambiguous references")
    assignments=[]
    group_reports=[]
    for group in GROUPS:
        # Keep source-disjoint NORMAL icon slots with strong visual similarity.
        # Do not count duplicate source files with normal and '_nh' aliases
        # as different source OIDs. UNI thumbnails have distinct semantics.
        choices={}
        for pid in group:
            found={}
            for x in variant_by_id[pid]:
                if (not x["native_texture_name"].startswith("icon_poke_")
                     or x["native_texture_name"].startswith("icon_poke_uni_")
                     or float(x["visual_mae_32px"])>0.016):
                    continue
                slot=int(x["original_icon_array_index"])
                if slot not in found or float(x["visual_mae_32px"]) < float(found[slot]["visual_mae_32px"]):
                    found[slot]=x
            choices[pid]=found
        candidate_slots=sorted({s for group_slots in choices.values() for s in group_slots})
        if len(candidate_slots)!=len(group):
            raise ValueError(f"Visual variation group does not have one slot per PokoHex ID: {group}")
        possibilities=[]
        for order in itertools.permutations(candidate_slots,len(group)):
            if any(order[i] not in choices[pid] for i,pid in enumerate(group)):
                continue
            distance=sum(float(choices[pid][order[i]]["visual_mae_32px"]) for i,pid in enumerate(group))
            possibilities.append((distance,order))
        possibilities.sort(key=lambda v:(v[0],v[1]))
        if len(possibilities)<2:
            raise ValueError(f"No alternative candidates to demonstrate ambiguity: {group}")
        first,runner=possibilities[:2]
        gap=runner[0]-first[0]
        # An optimization best candidate is only a *visual* proposal. A
        # small score separation does not prove runtime variant selection.
        group_reports.append({
            "reference_pokohex_portrait_ids":";".join(map(str,group)),
            "candidate_native_array_slots":";".join(map(str,candidate_slots)),
            "minimum_total_normalized_visual_mae":round(first[0],8),
            "second_best_total_normalized_visual_mae":round(runner[0],8),
            "visual_assignment_margin":round(gap,8),
            "best_slot_order_for_reference_group":";".join(map(str,first[1])),
            "runner_up_slot_order_for_reference_group":";".join(map(str,runner[1])),
            "assignment_is_runtime_ID_proof":False,
        })
        for i,pid in enumerate(group):
            s=first[1][i]
            selected=choices[pid][s]
            assignments.append({
                "reference_pokohex_portrait_id":pid,
                "candidate_native_array_slot":s,
                "original_source_oid":selected["source_oid"],
                "original_texture_oid":selected["target_texture_oid"],
                "original_texture_name":selected["native_texture_name"],
                "original_g1t_hash":selected["native_g1t_hash"],
                "original_texinfo_hash":selected["native_texinfo_hash"],
                "reference_to_source_visual_mae":selected["visual_mae_32px"],
                "group_best_total_visual_distance":round(first[0],8),
                "group_second_total_visual_distance":round(runner[0],8),
                "group_assignment_score_margin":round(gap,8),
                "status":"PREFERRED_ONE_TO_ONE_VISUAL_CANDIDATE_ONLY",
                "original_runtime_villager_id_binding_verified":"",
            })
    assignments.sort(key=lambda x:x["reference_pokohex_portrait_id"])
    save(roster,"m26_62_third_party_portrait_roster.csv")
    save(assignments,"m26_9_visual_only_disjoint_slot_assignments.csv")
    save(group_reports,"m26_4_visual_variant_group_alternatives.csv")
    result={
        "version":"2.0.1",
        "reference_pokohex_roster_total":378,
        "original_native_visual_candidates_confirmed_m25":307,
        "still_unmatched_reference_portraits":62,
        "reference_missing_id_range":[317,378],
        "third_party_public_named_villager_records_for_missing":len(roster),
        "reference_game_record_id_min":min(int(x["reference_pokohex_game_record_id"]) for x in roster),
        "reference_game_record_id_max":max(int(x["reference_pokohex_game_record_id"]) for x in roster),
        "ambiguous_reference_portraits_with_preferred_visual_only_assignment":len(assignments),
        "ambiguous_reference_groups":len(GROUPS),
        "source_distinct_visual_assignments":len({x["original_source_oid"] for x in assignments})==9,
        "native_villager_id_bindings_proven":0,
        "native_species_id_bindings_proven":0,
        "third_party_reference_is_native_version_proof":False,
        "status":"VISUAL_PROPOSALS_ONLY__M25_NATIVE_SOURCE_BYTES_UNCHANGED",
        "warning":"PokoHex is_public and game_record_id are third-party metadata. One-to-one visual assignment is not proof of original game species ID or 2.0.1 asset availability for the 62 missing portraits.",
    }
    (O/"m26_roster_variant_summary.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result

def selftest():
    assert len(list(REMAINING))==62
    assert sum(map(len,GROUPS))==9
    # Basic exact assignment example: 2x2 row-min cost.
    scores={(1,11):0.001,(1,12):0.003,(2,11):0.002,(2,12):0.001}
    valid=[(sum(scores[(i+1,s)] for i,s in enumerate(a)),a) for a in itertools.permutations((11,12))]
    assert min(valid)[1]==(11,12)
    print("PASS PokoHex 62 roster and visual assignment solver tests")

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test:selftest()
    else:inspect()
if __name__=="__main__":main()
