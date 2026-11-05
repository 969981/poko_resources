#!/usr/bin/env python3
"""M25.7: original NSO literal/ARM64 consumers for NEW KIDS icon registry hash.

Objects from the 678 KIDSDB graph establish:
0xB4A1803B node type 0x9D1AFA46
0x34CBB458 typed 3543-u32 property
602 source OID references across original icon_poke and icon_poke_uni blocks.

Search exact original NSO's constants and nearby AArch64 accesses. A code
reference to a hash is not a proven species ID or array-index consumer.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m20_native_species_item_targets import (
    MAIN,SHA_MAIN,arm64_window,literal_sites,literal_xrefs,hash_mov_pairs,
)
ROOT=Path("UnPack/2.0.1/Resources")
M25=ROOT/"Villagers/Native_2.0.1/M25"
INPUT=M25/"m25_2_original_registry_summary.json"
HASHES={
    "array_3543_property":0x34CBB458,
    "array_owner_type":0x9D1AFA46,
    "array_owner_oid":0xB4A1803B,
    "source_to_texture_property":0x2856A1B3,
}
OUT=M25/"m25_7_original_registry_hash_assembly.json"
SUMMARY=M25/"m25_7_original_registry_hash_consumer_summary.json"

def run():
    orig=json.loads(INPUT.read_text(encoding="utf-8"))
    if (orig["original_owner_oid"]!="b4a1803b"
            or orig["original_owner_type_hash"]!="9d1afa46"
            or orig["original_field_hash"]!="34cbb458"
            or orig["native_property_element_count"]!=3543
            or orig["original_known_icon_source_oids_byte_verified"]!=602):
        raise ValueError("M25.2 original register/hash evidence changed")
    data=MAIN.read_bytes()
    if hashlib.sha256(data).hexdigest()!=SHA_MAIN:
        raise ValueError("Original Pokopia NSO SHA256 changed")
    kind,parts=get_sections(data)
    if kind!="NSO0":raise ValueError("Not an original NSO0")
    code=next(x for x in parts if x["name"]=="text")
    b,base=code["data"],code["mem_offset"]
    all_results={}
    for label,hash_value in HASHES.items():
        cells=literal_sites(parts,hash_value)
        mov=hash_mov_pairs(b,base,hash_value)
        xrefs=literal_xrefs(b,base,cells)
        windows=[]
        for x in mov[:20]:
            pc=int(x["movk_pc"],16)
            windows.append({"via":"MOVZ_MOVK","candidate_pc":x["movk_pc"],"grade":x["grade"],
                            "original_assembly":arm64_window(b,base,pc,0x30,0x48)})
        for x in xrefs[:20]:
            pc=int(x["candidate_pc"],16)
            windows.append({"via":"ADRP_LITERAL","candidate_pc":x["candidate_pc"],"grade":x["grade"],
                            "original_assembly":arm64_window(b,base,pc,0x30,0x48)})
        all_results[label]={
            "constant":f"0x{hash_value:08x}",
            "original_rodata_or_data_literal_cells":cells,
            "literal_cell_count":len(cells),
            "original_movz_movk_candidates":mov[:200],
            "movz_movk_candidate_count":len(mov),
            "exact_adjacent_movz_movk_count":sum(x["grade"]=="ADJACENT_EXACT_IMMEDIATE_PAIR" for x in mov),
            "original_adrp_literal_xref_candidates":xrefs[:200],
            "literal_xref_candidate_count":len(xrefs),
            "exact_adjacent_literal_xref_count":sum(x["grade"]=="ADJACENT_ARM64_ADDRESS_OR_VALUE_ACCESS" for x in xrefs),
            "candidate_windows":windows,
            "actual_3543_array_consumer_verified":False,
            "game_pokemon_id_to_native_KIDS_array_index_verified":False,
        }
    summary={
        "version":"2.0.1",
        "original_nso_sha256":SHA_MAIN,
        "native_KIDS_registry_array_owner_oid":"b4a1803b",
        "native_KIDS_registry_array_type_hash":"9d1afa46",
        "native_KIDS_registry_property_hash":"34cbb458",
        "original_KIDS_u32_array_elements":3543,
        "original_pokemon_source_OID_links_in_array":602,
        "original_native_hash_code_matches":{
            key:{"literal_cells":x["literal_cell_count"],
                 "movz_movk_candidates":x["movz_movk_candidate_count"],
                 "exact_adjacent_mov_pairs":x["exact_adjacent_movz_movk_count"],
                 "adrp_literal_xrefs":x["literal_xref_candidate_count"],
                 "exact_adjacent_literal_accesses":x["exact_adjacent_literal_xref_count"]}
            for key,x in all_results.items()},
        "native_registry_array_consumer_semantics_proven":False,
        "game_species_id_to_array_slot_verified":False,
        "game_villager_id_to_source_OID_verified":False,
        "warning":"An immediate/literal Hash match or indirect property descriptor does not prove access to the 3543-value array by a native species ID.",
    }
    M25.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(all_results,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary

def selftest():
    assert len(HASHES)==4
    assert HASHES["array_3543_property"]==0x34CBB458
    print("PASS original registry array typed hash constants")
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test",action="store_true")
    args=parser.parse_args()
    if args.self_test:selftest()
    else:run()
if __name__=="__main__":main()
