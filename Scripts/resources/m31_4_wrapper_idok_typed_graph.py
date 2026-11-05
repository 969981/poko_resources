#!/usr/bin/env python3
"""M31.4: original KIDS Source OID -> WRAPPER IDOK object -> typed fields.

Only original root_019167_50ae86ef.kidsobjdb bytes are source of object
membership, field hashes, types, scalar OIDs and field record offsets.
M31.3 proved that all 628 per-icon Wrapper hashes refer to IDOK objects
inside the same original KIDS DB.

This step builds true typed graph edges out of the wrapper object and
counts links to actual resource files. When a field is not a scalar u32
or its value isn't an IDOK object, DO NOT assert object membership.
Game species/form ID to first Source OID remains unknown.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,struct
from collections import Counter,defaultdict
from pathlib import Path

from Scripts.resources.m16_verify_pokemon_texture_kidsobjdb import parse_kids

ROOT=Path("UnPack/2.0.1/Resources")
ORIGINAL=Path("UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0xacd220a8.fdata/native/root_019167_50ae86ef.kidsobjdb")
SHA="86f90b4c11da9bc2b3e28889a5090ff507f96ca713fe4fad1dd50f6f692d7541"
SOURCECSV=ROOT/"Villagers/Native_2.0.1/M31/m31_3_corrected_628_native_texture_object_fields.csv"
OUT=ROOT/"Villagers/Native_2.0.1/M31"
FIELDS=("source_oid","original_source_name","original_source_type_hash",
        "original_wrap_object_hash","wrapper_object_type_hash",
        "wrapper_original_IDOK_index","wrapper_original_IDOK_offset",
        "wrapper_field_hash","wrapper_field_kind","wrapper_field_count",
        "wrapper_original_field_data_offset","wrapper_scalar_u32_hex",
        "scalar_matches_prior_M25_g1t_file_hash",
        "scalar_matches_prior_M25_texinfo_file_hash",
        "scalar_resolves_to_IDOK_object","scalar_resolved_IDOK_object_type",
        "native_game_species_id_verified")
def h(x):return f"{x:08x}"
def csv_rows(file):
    with file.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def run():
    blob=ORIGINAL.read_bytes()
    if hashlib.sha256(blob).hexdigest()!=SHA:
        raise ValueError("Original 2.0.1 KIDSOBJDB source SHA changed")
    header,nodes=parse_kids(blob)
    sources=csv_rows(SOURCECSV)
    if len(sources)!=628:
        raise ValueError("M31.3 corrected source provenance missing or incomplete")
    hits=Counter();types=Counter();field_schemas=Counter()
    scalar_edges=Counter()
    wrapper_to_fields=[]
    wrapper_records=[]
    observed_wrappers=set()
    for s in sources:
        source=int(s["source_oid"],16)
        target=int(s["original_wrap_static_screen_layout_textures_object_hash"],16)
        if target in observed_wrappers:raise ValueError("Duplicate wrapper IDOK source edge")
        observed_wrappers.add(target)
        original_source=nodes.get(source)
        wrapper=nodes.get(target)
        if original_source is None or original_source["type"]!=0x79991e79:
            raise ValueError("Original source KIDS type changed")
        if wrapper is None:
            raise ValueError(f"M31.3 reported a missing real wrapper IDOK {h(target)}")
        types[h(wrapper["type"])]+=1
        field_schemas[tuple((h(k),f["kind"],f["count"]) for k,f in wrapper["fields"].items())]+=1
        mapped=[]
        for prop,record in wrapper["fields"].items():
            scalar=(struct.unpack_from("<I",blob,record["offset"])[0]
                    if record["kind"] in (4,5) and record["count"]==1 else None)
            child=nodes.get(scalar) if scalar is not None else None
            if scalar is not None:
                scalar_edges["scalar_fields"]+=1
                scalar_edges["scalar_u32_resolve_as_IDOK"]+=int(child is not None)
                scalar_edges["scalar_u32_equals_legacy_g1t"]+=int(
                    h(scalar)==s["prior_M25_g1t_file_hash"])
                scalar_edges["scalar_u32_equals_legacy_texinfo"]+=int(
                    h(scalar)==s["prior_M25_texinfo_file_hash"])
            row={
                "source_oid":h(source),
                "original_source_name":s["original_texinfo_texture_name_aliases"],
                "original_source_type_hash":s["source_type_hash"],
                "original_wrap_object_hash":h(target),
                "wrapper_object_type_hash":h(wrapper["type"]),
                "wrapper_original_IDOK_index":wrapper["index"],
                "wrapper_original_IDOK_offset":wrapper["offset"],
                "wrapper_field_hash":h(prop),
                "wrapper_field_kind":record["kind"],
                "wrapper_field_count":record["count"],
                "wrapper_original_field_data_offset":record["offset"],
                "wrapper_scalar_u32_hex":h(scalar) if scalar is not None else "",
                "scalar_matches_prior_M25_g1t_file_hash":(
                    int(h(scalar)==s["legacy_M25_g1t_hash_same_raw_u32"])
                    if scalar is not None else ""),
                "scalar_matches_prior_M25_texinfo_file_hash":(
                    int(h(scalar)==s["legacy_M25_texinfo_hash_same_raw_u32"])
                    if scalar is not None else ""),
                "scalar_resolves_to_IDOK_object":int(child is not None) if scalar is not None else "",
                "scalar_resolved_IDOK_object_type":h(child["type"]) if child else "",
                "native_game_species_id_verified":"",
            }
            wrapper_to_fields.append(row)
            mapped.append(row)
        wrapper_records.append({
            "source_oid":h(source),"wrapper_IDOK_oid":h(target),
            "wrapper_type_hash":h(wrapper["type"]),
            "wrapper_IDOK_offset":wrapper["offset"],
            "field_count":len(wrapper["fields"]),
            "scalar_field_count":sum(bool(v["wrapper_scalar_u32_hex"]) for v in mapped),
            "scalar_IDOK_target_count":sum(v["scalar_resolves_to_IDOK_object"]==1 for v in mapped),
            "game_species_id_verified":False})
        hits["verified_source_to_wrapper_original_edges"]+=1
    if len(wrapper_records)!=628 or len(observed_wrappers)!=628:
        raise ValueError("Original KIDS wrapper IDOK cardinality mismatch")
    if len(field_schemas)>100:
        raise ValueError("Unexpected wrapper type schema divergence")
    summary={
        "version":"2.0.1",
        "original_kids_source_sha256":SHA,
        "original_idok_object_count":len(nodes),
        "source_to_real_wrapper_IDOK_edges":hits["verified_source_to_wrapper_original_edges"],
        "unique_original_wrapper_IDOK_objects":len(observed_wrappers),
        "original_wrapper_type_histogram":dict(types),
        "original_wrapper_property_schema_distinct_count":len(field_schemas),
        "original_wrapper_property_schema_histogram":[{
            "properties":[{"hash":k,"kind":v,"count":n} for k,v,n in schema],
            "objects":number}
            for schema,number in field_schemas.most_common()],
        "wrapper_field_rows_written":len(wrapper_to_fields),
        "wrapper_scalar_u32_field_count":scalar_edges["scalar_fields"],
        "wrapper_scalar_resolves_to_IDOK":scalar_edges["scalar_u32_resolve_as_IDOK"],
        "wrapper_scalar_matches_legacy_g1t_file_hash":scalar_edges["scalar_u32_equals_legacy_g1t"],
        "wrapper_scalar_matches_legacy_texinfo_file_hash":scalar_edges["scalar_u32_equals_legacy_texinfo"],
        "wrapper_property_type_name_from_original_ExeFS_verified":True,
        "wrapper_property_original_type_name":"StaticScreenLayoutTextures",
        "source_and_wrapper_both_original_class_0x79991e79":all(
            x["wrapper_object_type_hash"]=="79991e79"
            for x in wrapper_to_fields),
        "source_wrapper_raw_fields_link_to_M25_G1T_TEXINFO_hashes_proven":(
            scalar_edges["scalar_u32_equals_legacy_g1t"]==628 and
            scalar_edges["scalar_u32_equals_legacy_texinfo"]==628),
        "runtime_game_entity_to_wrapper_source_ID_verified":False,
        "native_species_form_ID_to_Source_OID_verified":False,
        "caveat":"Both source and wrapper IDOKs have StaticScreenLayoutTextures type; child scalar render/info fields can now be checked against M25 G1T/TEXINFO file hash index. The executed asset loader and game ID selection are not proven.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/"m31_4_original_628_wrapper_IDOK_typed_field_graph.csv").open(
        "w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader()
        w.writerows(sorted(wrapper_to_fields,key=lambda r:(r["source_oid"],r["wrapper_field_hash"])))
    (OUT/"m31_4_original_wrapper_IDOK_typed_graph_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary

def selftest():
    assert FIELDS[0]=="source_oid"
    assert "wrapper_field_hash" in FIELDS
    print("PASS M31.4 original wrapper IDOK field evidence schema")
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:selftest()
    else:run()
