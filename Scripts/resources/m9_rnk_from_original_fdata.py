#!/usr/bin/env python3
"""M9.8: recover original RNK bytes from the three proven RDB/FDATA offsets.

Run only with physical FDATA from an authorized copy of the game. Never
substitute filenames, infer IRNK semantic field names or promote M7 FKs.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path

from Scripts.unpack.core import read_idrk, decode_kt_payload
from Scripts.resources.m9_rnk_name_tables import parse_rnk

MAX_NATIVE_RNK = 64 * 1024 * 1024
EXPECTED = {"a91711c6", "aa91cb96", "cb3c8b15"}
FIELDS = ("expected_rnk_hash","rdb_record_id","physical_source","status",
          "idrk_name_hash","idrk_type_hash","decoded_sha256","irnk_entries",
          "verified_native_rnk","semantic_property_name_verified","text_fk_verified")


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def resolve_source(base: Path, row):
    names = {Path(p).name for p in json.loads(row["candidate_source_paths"])}
    if len(names) != 1:
        raise ValueError("Ambiguous RDB container source filenames")
    name = next(iter(names))
    if not name.endswith(".fdata") and not name.endswith(".file"):
        raise ValueError("Invalid original FDATA filename")
    matches = sorted(p for p in base.rglob(name) if p.is_file())
    return matches


def decode_native(fdata: Path, record):
    expected_name = int(record["expected_rnk_hash"],16)
    expected_type = int(record["type_hash"],16)
    offset = int(record["fdata_offset"])
    entry_size = int(record["fdata_entry_size"])
    unpacked = int(record["uncompressed_size"])
    if unpacked <= 0 or unpacked > MAX_NATIVE_RNK:
        raise ValueError("Native RNK size out of supported bounds")
    if int(record["footer_magic"],16) != 0x0401:
        raise ValueError("Not an original FDATA-backed IDRK record")
    with fdata.open("rb") as stream:
        header, _metadata = read_idrk(stream, offset, fdata.stat().st_size)
        if (header.name_hash != expected_name or header.type_hash != expected_type
            or header.entry_size != entry_size or header.unpacked_size != unpacked):
            raise ValueError("Original RDB/IDRK identity or byte count mismatch")
        if header.packed_size > MAX_NATIVE_RNK:
            raise ValueError("Original packed payload too large")
        packed = stream.read(header.packed_size)
        if len(packed) != header.packed_size:
            raise ValueError("Incomplete original IDRK payload")
    blob = decode_kt_payload(packed,header)
    entries, info = parse_rnk(blob)
    return entries, info, hashlib.sha256(blob).hexdigest()


def run(audit: Path, source_root: Path, dest: Path):
    source = read_csv(audit)
    if {row["expected_rnk_hash"] for row in source} != EXPECTED:
        raise ValueError("The three original-RDB RNK identities changed")
    output = []
    names = []
    for row in source:
        result = {
            "expected_rnk_hash":row["expected_rnk_hash"],
            "rdb_record_id":row["record_id"], "physical_source":"",
            "status":"ORIGINAL_FDATA_NOT_PRESENT",
            "idrk_name_hash":"", "idrk_type_hash":"", "decoded_sha256":"",
            "irnk_entries":0, "verified_native_rnk":False,
            "semantic_property_name_verified":False, "text_fk_verified":False,
        }
        matches=resolve_source(source_root,row)
        if len(matches)>1:
            result["status"]="AMBIGUOUS_ORIGINAL_FDATA_MATCHES"
        elif len(matches)==1:
            result["physical_source"]=str(matches[0])
            try:
                entries, info, checksum=decode_native(matches[0],row)
                result.update(status="NATIVE_RNK_IRNK_BYTES_VERIFIED",
                              idrk_name_hash=row["expected_rnk_hash"],
                              idrk_type_hash=row["type_hash"],
                              decoded_sha256=checksum,
                              irnk_entries=info["entries"],
                              verified_native_rnk=True)
                for ent in entries:
                    for item in ent["strings"]:
                        names.append({
                            "source_rnk_hash":row["expected_rnk_hash"],
                            "source_rdb_record_id":row["record_id"],
                            "source_sha256":checksum,
                            "irnk_key_hash":f'{ent["key"]:08x}',
                            "irnk_record_offset":ent["offset"],
                            "string_index":item["index"],
                            "string_byte_offset":item["abs_offset"],
                            "raw_sha256":item["raw_sha256"],
                            "text_utf8":item["text"],
                            "semantic_property_name_verified":False,
                            "text_fk_verified":False,
                        })
            except (ValueError, OSError) as exc:
                result["status"]="NATIVE_RNK_VALIDATION_REJECTED"
                result["error"]=str(exc)
        output.append(result)
    dest.mkdir(parents=True,exist_ok=True)
    cols=["source_rnk_hash","source_rdb_record_id","source_sha256",
          "irnk_key_hash","irnk_record_offset","string_index","string_byte_offset",
          "raw_sha256","text_utf8","semantic_property_name_verified","text_fk_verified"]
    with (dest/"rnk_recovered_irnk_strings.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(names)
    report={
        "status":"M9_ORIGINAL_FDATA_RNK_EXTRACTION_STRICT",
        "sources":output,
        "verified_original_rnk_sources":sum(x["verified_native_rnk"] for x in output),
        "native_irnk_strings_extracted":len(names),
        "verified_semantic_property_names":0,
        "new_script_scene_quest_building_text_foreign_keys":0,
        "numeric_oid_candidates_still_unverified":87445,
        "limitations":["IRNK key/hash collisions do not establish property-name semantics.",
                       "A valid RNK is not evidence of a script/M7 text foreign key."],
    }
    (dest/"rnk_original_fdata_recovery.json").write_text(
        json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--audit-csv",type=Path,required=True)
    p.add_argument("--fdata-dir",type=Path,required=True)
    p.add_argument("--dest",type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(run(args.audit_csv,args.fdata_dir,args.dest),indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
