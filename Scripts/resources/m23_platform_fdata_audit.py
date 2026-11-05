#!/usr/bin/env python3
"""M23: audit original RDX platform flags, two absent FDATA containers and G1T links.

No FDATA payloads are invented or copied. A type hash is a catalog hint, not
a decoded sprite or proof of a game's platform-specific resource consumer.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from Scripts.unpack.core import parse_rdb, parse_rdx

SOURCE = Path("2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE")
REPORTS = Path("UnPack/2.0.1/_reports")
RES = Path("UnPack/2.0.1/Resources")
OUT = RES / "Villagers/Native_2.0.1/M23"
PRIORITY = {"0x03a38715.fdata": (5, 623, 227),
            "0xfd6af828.fdata": (44, 525, 294)}
TYPE = {"afbec60c": "g1t", "8e39aa37": "ktid",
        "f20de437": "texinfo", "20a6a0bb": "kidsobjdb"}

def read_csv(p: Path, sep=","):
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=sep))

def output_csv(p, records):
    if not records: raise ValueError(f"Refuse empty original-source table: {p}")
    p.parent.mkdir(parents=True, exist_ok=True)
    fields=list(records[0])
    with p.open("w", encoding="utf-8", newline="") as f:
        w=csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(records)

def output_json(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")

def tracked_sources():
    """Read committed archive tree, including LFS-style Git references if any."""
    names=subprocess.check_output(["git","ls-tree","-r","--name-only","HEAD","--",
                                   SOURCE.as_posix()],text=True,encoding="utf-8")
    return names.splitlines()

def physical_location(filename, tracked):
    """Original archive and first 7z volume count; never claim unlisted files."""
    matches=[]
    base=SOURCE.as_posix()+"/"
    for entry in tracked:
        if not entry.startswith(base): continue
        name=entry.rsplit("/",1)[-1]
        if name==filename or name==filename+".7z.001":
            parent=entry[:-(len(name)+1)]
            matches.append({"parent":parent,"tracked_path":entry,
                            "representation":"DIRECT" if name==filename else "FIRST_7Z_VOLUME"})
    return matches

def check_source(original, missing):
    bytes_rdx=(SOURCE/"root.rdx").read_bytes()
    rdex=parse_rdx(bytes_rdx)
    entries, metadata=parse_rdb((SOURCE/"root.rdb").read_bytes(),"root",rdex)
    if len(rdex)!=45 or len(entries)!=60722: raise ValueError("Original root RDX/RDB version changed")
    if len(missing)!=6118: raise ValueError("Original missing-input baseline changed")
    unique={(r["catalog"],int(r["record_index"])):r for r in missing}
    if len(unique)!=len(missing): raise ValueError("Missing report has duplicated RDB rows")
    records=[]
    for e in rdex:
        loc=physical_location(e.filename, original)
        records.append({
            "rdx_position":e.position,"fdata_index":e.fdata_index,
            "raw_platform_flags":f"{e.platform_flags:04x}",
            "fdata_filename":e.filename,
            "tracked_location_status":"IN_GIT_ARCHIVE" if loc else "ABSENT_FROM_GIT_ARCHIVE",
            "tracked_archive_paths":";".join(x["tracked_path"] for x in loc),
            "platform_semantics":"UNVERIFIED" if e.platform_flags not in (0xffff,0xff01,0xff02) else
                                  "PATH_CONVENTION_ONLY__NO_RUNTIME_PROOF",
        })
    focus={}; g1t=[]
    for name,(idx,expected,ng1t) in PRIORITY.items():
        e=rdex[idx]
        if e.filename!=name or e.platform_flags!=0xff03:
            raise ValueError("Original RDX priority entry differs; refuse assumptions")
        if physical_location(name,original):
            raise ValueError(f"Original priority input is now archived: {name}; rerun coverage first")
        subset=[x for x in entries if x.fdata_index==idx and x.footer_magic==0x0401
                and x.footer_layout in ("standard_13","extended_17")]
        if len(subset)!=expected:
            raise ValueError(f"Original RDB record count mismatch for {name}: {len(subset)}")
        kinds=Counter(f"{x.type_hash:08x}" for x in subset)
        if kinds["afbec60c"]!=ng1t: raise ValueError(f"Missing G1T count changed: {name}")
        for x in subset:
            report=unique.get(("root",x.record_index))
            if not report or report["source_file"]!=name or report["name_hash"]!=f"{x.name_hash:08x}" or report["type_hash"]!=f"{x.type_hash:08x}" or report["platform_flags"]!="ff03" or int(report["unpacked_size"])!=x.uncompressed_size:
                raise ValueError(f"Original RDB entry and missing manifest contradict: {name}:{x.record_index}")
            if x.type_hash==int("afbec60c",16):
                g1t.append({
                    "original_fdata_name":name,
                    "rdx_position":idx,
                    "platform_flags_raw":"ff03",
                    "rdb_record_index":x.record_index,
                    "rdb_original_file_offset":x.rdb_offset,
                    "g1t_name_hash":f"{x.name_hash:08x}",
                    "original_type_hash":f"{x.type_hash:08x}",
                    "expected_uncompressed_size":x.uncompressed_size,
                    "fdata_original_byte_offset":x.fdata_offset,
                    "fdata_entry_size":x.fdata_entry_size,
                    "archive_state":"MISSING_PHYSICAL_INPUT",
                })
        focus[name]={
            "rdx_position":idx, "raw_platform_flag":"ff03",
            "rdb_entries_checked":len(subset),
            "inferred_type_hash_counts":dict(kinds.most_common()),
            "g1t_records":kinds["afbec60c"],
            "ktid_records":kinds["8e39aa37"],
            "stored_bytes_per_rdb":sum(x.fdata_entry_size for x in subset),
            "unpacked_bytes_per_rdb":sum(x.uncompressed_size for x in subset),
            "first_7z_volume_tracked":False,
            "source_container_recovered":False,
        }
    if len(g1t)!=521: raise ValueError(f"Priority G1T rows: {len(g1t)} != 521")
    ff03=[r for r in records if r["raw_platform_flags"]=="ff03"]
    if len(ff03)!=10: raise ValueError("Original root.RDX FF03 entry count changed")
    observed=sum(r["tracked_location_status"]=="IN_GIT_ARCHIVE" for r in ff03)
    return records,focus,g1t,rdex,metadata,observed

def references(g1t):
    lookup=defaultdict(lambda: {"native_objdb_hashes":set(), "misc_names":set(), "pokemon_names":set()})
    for r in read_csv(RES/"Textures/Indexes/layout-textures.tsv","\t"):
        if r["g1t_hash"] and r["g1t_hash"]!="00000000":
            lookup[r["g1t_hash"]]["native_objdb_hashes"].add(r["object_hash"])
    for r in read_csv(RES/"Textures/Indexes/native_misc_texture_index.csv"):
        if r["g1t_hash"] and r["g1t_hash"]!="00000000":
            lookup[r["g1t_hash"]]["misc_names"].add(r["texture_name"])
    for r in read_csv(RES/"Pokemon/pokemon_texture_index.csv"):
        if r["g1t_hash"] and r["g1t_hash"]!="00000000":
            lookup[r["g1t_hash"]]["pokemon_names"].add(r["texture_name"])
    count=Counter()
    for r in g1t:
        ref=lookup.get(r["g1t_name_hash"])
        flags=ref or {}
        obj=sorted(flags.get("native_objdb_hashes",[]))
        misc=sorted(flags.get("misc_names",[]))
        poke=sorted(flags.get("pokemon_names",[]))
        r.update({
            "native_index_objdb_reference_count":len(obj),
            "native_index_objdb_hashes":";".join(obj[:10]),
            "misc_texinfo_sprite_reference_count":len(misc),
            "misc_texinfo_names":";".join(misc[:10]),
            "pokemon_texinfo_sprite_reference_count":len(poke),
            "pokemon_texinfo_names":";".join(poke[:10]),
            "reference_status":("LINKED_NATIVE_TEXINFO_HASH_CANDIDATE" if (obj or misc or poke)
                                else "NO_LINK_IN_THREE_EXISTING_SOURCE_INDICES"),
            "villager_id_proven":"NO",
        })
        count[r["reference_status"]]+=1
    return dict(count)

def analyze():
    original=tracked_sources()
    missing=read_csv(REPORTS/"missing_input_records.csv")
    rows,focus,g1t,rdex,meta,present=check_source(original,missing)
    linkcounts=references(g1t)
    output_csv(OUT/"m23_original_rdx_platform_inventory.csv",rows)
    output_csv(OUT/"m23_521_missing_g1t_original_rdb.csv",g1t)
    report={
        "version":"2.0.1",
        "original_root_rdx_sha256":__import__("hashlib").sha256((SOURCE/"root.rdx").read_bytes()).hexdigest(),
        "original_root_rdb_sha256":__import__("hashlib").sha256((SOURCE/"root.rdb").read_bytes()).hexdigest(),
        "original_rdb_entry_count":meta["parsed"],
        "root_rdx_entry_count":len(rdex),
        "raw_ff03_rdx_entry_count":10,
        "raw_ff03_entries_present_in_git_archive":present,
        "priority_original_fdata":focus,
        "priority_original_g1t_records_verified_from_rdb":len(g1t),
        "g1t_reference_in_existing_native_index_counts":linkcounts,
        "root_rdx_ff03_directory_semantics_proven":False,
        "original_ff03_platform_owner_proven":False,
        "original_priority_fdata_binary_bytes_available":False,
        "missing_79_native_portrait_sources_verified":0,
        "native_species_id_bindings_verified":0,
        "native_villager_id_bindings_verified":0,
        "next_gate":"Find original ff03 source container(s), confirm platform and IDRK headers, or establish a game ID to typed object consumer chain.",
        "warning":"No G1T hash hit in existing indices is NOT proof these FDATA contain no portraits; archives and native consumers were not recovered.",
    }
    output_json(OUT/"m23_platform_source_report.json",report)
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test",action="store_true")
    args=parser.parse_args()
    if args.self_test:
        assert len(PRIORITY)==2 and sum(x[2] for x in PRIORITY.values())==521
        assert len(set(TYPE))==len(TYPE)
        print("M23 source-check self-tests passed")
        return
    report=analyze()
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
