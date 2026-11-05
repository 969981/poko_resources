#!/usr/bin/env python3
"""M25.6: unify original 290 M21 + newly recovered 17 native portrait candidates.

Copy only byte-verified M25 original PNGs into the existing villager Native Icons
directory, without changing the old M21 baseline CSV or promoting image
similarity to a game-villager-ID assertion.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

R=Path("UnPack/2.0.1/Resources")
VILLAGERS=R/"Villagers/Native_2.0.1"
M25=VILLAGERS/"M25"
M21=VILLAGERS/"native_icon_crosswalk.csv"
M25_CROSS=M25/"m25_5_79_portrait_visual_crosscheck.csv"
NEW_PNG=R/"Pokemon/NativeRecoveryM25/m25_5_native_icon_export_manifest.csv"
MATCH="NEW_VISUAL_NEAR_IDENTICAL_CANDIDATE_REVIEW"
OUTPUT=VILLAGERS/"Icons"
COLS=("portrait_id_pokohex","pokohex_reference_png","candidate_status","candidate_origin",
      "source_texture_name","native_source_oid","native_target_oid",
      "native_original_array_slot","native_g1t_hash","native_texinfo_hash",
      "source_qualified_png","source_qualified_png_sha256",
      "visual_normalized_mae_32px","runtime_villager_id_binding_verified")

def csvrows(path):
    with path.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main_run():
    old=csvrows(M21)
    newer=csvrows(M25_CROSS)
    pngs=csvrows(NEW_PNG)
    if len(old)!=378 or len(newer)!=79 or len(pngs)!=26:
        raise ValueError("Native M21+M25 input baseline mismatch")
    oldids={int(x["reference_sprite_id"]):x for x in old}
    if len(oldids)!=378:raise ValueError("Duplicate old portrait ID")
    recovered=[x for x in newer if x["status"]==MATCH]
    if len(recovered)!=17:
        raise ValueError(f"Recovery baseline changed: {len(recovered)} instead of 17")
    native_png_by_slot={int(x["original_array_slot"]):x for x in pngs}
    if len(native_png_by_slot)!=26:raise ValueError("Nonunique recovered native icon slot")
    new_by_portrait={int(x["portrait_id_pokohex"]):x for x in recovered}
    if len(new_by_portrait)!=17:raise ValueError("One recovered portrait was assigned twice")
    for portrait,entry in new_by_portrait.items():
        if oldids[portrait]["status"]!="NO_CONFIDENT_IMAGE_CANDIDATE":
            raise ValueError(f"Attempted to replace already validated M21 icon: {portrait}")
        slot=int(entry["best_m25_original_array_slot"])
        actual=native_png_by_slot[slot]
        if (actual["png_file"]!=entry["best_m25_png"]
                or actual["texture_name_original_texinfo"]!=entry["best_m25_texture_name"]
                or actual["original_source_oid"]!=entry["best_m25_source_oid"]
                or actual["original_texture_oid"]!=entry["best_m25_target_oid"]):
            raise ValueError(f"Original KIDS/PNG byte provenance does not match portrait {portrait}")
        if not actual["png_sha256"] or sha(actual["png_file"])!=actual["png_sha256"]:
            raise ValueError(f"PNG original byte hash changed: {portrait}")
    OUTPUT.mkdir(parents=True,exist_ok=True)
    rows=[];copied=0
    for pid,x in sorted(oldids.items()):
        if x["status"]=="VISUAL_NEAR_IDENTICAL_CANDIDATE":
            result={
                "portrait_id_pokohex":pid,"pokohex_reference_png":x["reference_png"],
                "candidate_status":"VISUAL_NEAR_IDENTICAL_CANDIDATE",
                "candidate_origin":"M21_609_ORIGINAL_POKEMON_SOURCE_PNGS",
                "source_texture_name":x["native_texture_name"],
                "native_source_oid":"","native_target_oid":"",
                "native_original_array_slot":"",
                "native_g1t_hash":x["native_g1t_hash"],
                "native_texinfo_hash":x["native_texinfo_hash"],
                "source_qualified_png":x["native_export_png"],
                "source_qualified_png_sha256":x["native_png_sha256"],
                "visual_normalized_mae_32px":x["nearest_normalized_mae"],
                "runtime_villager_id_binding_verified":"",
            }
        elif pid in new_by_portrait:
            match=new_by_portrait[pid]
            src=native_png_by_slot[int(match["best_m25_original_array_slot"])]
            target=OUTPUT/f"{src['texture_name_original_texinfo']}__{src['texinfo_hash']}__{src['g1t_hash']}.png"
            payload=Path(src["png_file"]).read_bytes()
            if target.exists():
                if sha(target)!=src["png_sha256"]:
                    raise ValueError(f"Unexpected preexisting native villager source file hash: {target}")
            else:
                target.write_bytes(payload)
                copied+=1
            result={
                "portrait_id_pokohex":pid,"pokohex_reference_png":x["reference_png"],
                "candidate_status":"VISUAL_NEAR_IDENTICAL_CANDIDATE",
                "candidate_origin":"M25_5_ORIGINAL_TEXINFO_BIN_PLUS_G1T_PNG",
                "source_texture_name":src["texture_name_original_texinfo"],
                "native_source_oid":src["original_source_oid"],
                "native_target_oid":src["original_texture_oid"],
                "native_original_array_slot":src["original_array_slot"],
                "native_g1t_hash":src["g1t_hash"],"native_texinfo_hash":src["texinfo_hash"],
                "source_qualified_png":target.as_posix(),
                "source_qualified_png_sha256":src["png_sha256"],
                "visual_normalized_mae_32px":match["best_m25_distance"],
                "runtime_villager_id_binding_verified":"",
            }
        else:
            status=("MULTIPLE_NATIVE_VISUAL_CANDIDATES"
                    if float(x["nearest_normalized_mae"])<=.015
                    else "NO_CONFIDENT_SOURCE_2_0_1")
            result={
                "portrait_id_pokohex":pid,"pokohex_reference_png":x["reference_png"],
                "candidate_status":status,"candidate_origin":"M21_NOT_RESOLVED",
                "source_texture_name":"","native_source_oid":"","native_target_oid":"",
                "native_original_array_slot":"","native_g1t_hash":"","native_texinfo_hash":"",
                "source_qualified_png":"","source_qualified_png_sha256":"",
                "visual_normalized_mae_32px":x["nearest_normalized_mae"],
                "runtime_villager_id_binding_verified":"",
            }
        rows.append(result)
    if any(x["runtime_villager_id_binding_verified"] for x in rows):
        raise ValueError("Unverified gameplay identity promoted")
    counts=Counter(x["candidate_status"] for x in rows)
    if counts!={"VISUAL_NEAR_IDENTICAL_CANDIDATE":307,
                "MULTIPLE_NATIVE_VISUAL_CANDIDATES":9,
                "NO_CONFIDENT_SOURCE_2_0_1":62}:
        raise ValueError(f"Source coverage changed unexpectedly: {counts}")
    missing=[int(x["portrait_id_pokohex"]) for x in rows
             if x["candidate_status"]=="NO_CONFIDENT_SOURCE_2_0_1"]
    if missing!=list(range(317,379)):
        raise ValueError("62 missing portrait IDs no longer a contiguous 317-378 range")
    with (M25/"m25_6_complete_378_villager_candidate_inventory.csv").open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=COLS);writer.writeheader();writer.writerows(rows)
    summary={
        "version":"2.0.1","reference_portraits":378,
        "m21_original_visual_candidates":290,
        "m25_new_original_visual_candidates":17,
        "combined_high_confidence_visual_candidates":307,
        "ambiguous_multiple_native_candidates":9,
        "not_yet_native_mapped":62,
        "unmapped_reference_id_first":317,
        "unmapped_reference_id_last":378,
        "m25_original_pngs_added_to_existing_villager_icon_dir":copied,
        "native_game_villager_id_bindings_verified":0,
        "native_game_species_id_bindings_verified":0,
        "warning":"Visual-source candidate coverage is not native game villager-ID proof. The 62 unmatched may reflect original-version content limitations or unseen assets; their cause remains unproven.",
    }
    (M25/"m25_6_complete_villager_coverage_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary

def selftest():
    assert len(COLS)==14
    assert list(range(317,379))[-1]==378
    print("PASS M25.6 candidate inventory schema")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    x=p.parse_args()
    if x.self_test:selftest()
    else:main_run()

if __name__=="__main__":main()
