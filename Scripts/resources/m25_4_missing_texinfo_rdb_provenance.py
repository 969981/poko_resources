#!/usr/bin/env python3
"""M25.4: original root/system RDB provenance for 26 native TEXINFO hashes.

Find whether their original name_hash exists in RDB, and if so determine its
type, FDATA archive, platform flag, original record index and Git publication.
The absence of a .texinfo alias does NOT itself mean an original FDATA is missing.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import subprocess
from collections import defaultdict,Counter
from pathlib import Path

from Scripts.unpack.core import parse_rdb,parse_rdx

ROOT=Path("2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE")
R=Path("UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M25")
NATIVE=Path("UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE")
CANDIDATES=R/"m25_3_26_original_source_to_texture_objects.csv"
TEXINFO=0xF20DE437
G1T=0xAFBEC60C

def read_csv(path):
    with path.open(encoding="utf-8",newline="") as f:
        return list(csv.DictReader(f))

def tree():
    return subprocess.check_output(
        ["git","ls-tree","-r","--name-only","HEAD","--",
         ROOT.as_posix(),NATIVE.as_posix()],
        text=True,encoding="utf-8").splitlines()

def analyze():
    prior=read_csv(CANDIDATES)
    if len(prior)!=26 or len({int(x["original_array_slot"]) for x in prior})!=26:
        raise ValueError("M25.3 recovered original 26 inputs not available")
    expected={}
    for r in prior:
        for ext in ("texinfo","g1t"):
            key=int(r["target_"+ext+"_hash"],16)
            expected.setdefault(key,[]).append((r,ext))
    if len(expected)!=52: raise ValueError("Native texture hash collision requiring separate handling")
    paths=tree()
    tracked=set(paths)
    by_hash=defaultdict(list)
    for kind in ("root","system"):
        rdx=parse_rdx((ROOT/(kind+".rdx")).read_bytes())
        rec,meta=parse_rdb((ROOT/(kind+".rdb")).read_bytes(),kind,rdx)
        for item in rec:
            if item.name_hash not in expected:continue
            container=rdx[item.fdata_index] if item.fdata_index>=0 else None
            name=(container.filename if container else f"0x{item.name_hash:08x}.file")
            src_base=ROOT.as_posix()
            location=[v for v in paths if v.startswith(src_base+"/") and
                      (v.endswith("/"+name) or v.endswith("/"+name+".7z.001"))]
            output_root=NATIVE/(name if container else "data")
            native_name=f"{kind}_{item.record_index:06d}_{item.name_hash:08x}"
            native_alias=(output_root/"native"/(native_name+"."+(
                "texinfo" if item.type_hash==TEXINFO else
                "g1t" if item.type_hash==G1T else "bin"))).as_posix()
            # Source may have decoded payload even if original native extension
            # was never reassembled. Check both filenames by record hash.
            decoded=[v for v in paths if v.startswith(output_root.as_posix()+"/decoded/")
                     and f"_{item.name_hash:08x}." in v]
            published=[v for v in paths if v.startswith(output_root.as_posix()+"/native/")
                       and f"_{item.name_hash:08x}." in v]
            by_hash[item.name_hash].append({
                "catalog":kind,
                "record_index":item.record_index,
                "original_rdb_offset":item.rdb_offset,
                "original_type_hash":f"{item.type_hash:08x}",
                "expected_type":("texinfo" if item.name_hash in
                      {int(x["target_texinfo_hash"],16) for x in prior} else "g1t"),
                "original_unpacked_bytes":item.uncompressed_size,
                "original_footer_magic":f"{item.footer_magic:04x}",
                "original_fdata_index":item.fdata_index,
                "original_fdata_name":name,
                "original_platform_flag":f"{container.platform_flags:04x}" if container else "STANDALONE",
                "physical_input_tracked":bool(location),
                "physical_input_tracked_paths":";".join(location[:5]),
                "expected_native_alias":native_alias,
                "expected_native_alias_tracked":native_alias in tracked,
                "matching_decoded_artifact_paths":";".join(decoded[:8]),
                "matching_native_artifact_paths":";".join(published[:8]),
            })
    output=[]
    for row in sorted(prior,key=lambda x:int(x["original_array_slot"])):
        for extension in ("g1t","texinfo"):
            hashvalue=int(row["target_"+extension+"_hash"],16)
            match=by_hash.get(hashvalue,[])
            if match:
                for rec in match:
                    output.append({
                        "array_slot":row["original_array_slot"],
                        "target_texture_oid":row["native_target_oid"],
                        "resource_extension_expected":extension,
                        "native_resource_hash":f"{hashvalue:08x}",
                        "original_rdb_record_found":True,
                        "original_type_matches_expected":rec["original_type_hash"]==(
                            f"{G1T:08x}" if extension=="g1t" else f"{TEXINFO:08x}"),
                        **rec,
                        "native_species_id_proven":"",
                        "native_villager_id_proven":"",
                    })
            else:
                output.append({
                    "array_slot":row["original_array_slot"],
                    "target_texture_oid":row["native_target_oid"],
                    "resource_extension_expected":extension,
                    "native_resource_hash":f"{hashvalue:08x}",
                    "original_rdb_record_found":False,
                    "original_type_matches_expected":False,
                    "catalog":"","record_index":"","original_rdb_offset":"",
                    "original_type_hash":"","expected_type":extension,
                    "original_unpacked_bytes":"","original_footer_magic":"",
                    "original_fdata_index":"","original_fdata_name":"",
                    "original_platform_flag":"","physical_input_tracked":False,
                    "physical_input_tracked_paths":"","expected_native_alias":"",
                    "expected_native_alias_tracked":False,
                    "matching_decoded_artifact_paths":"",
                    "matching_native_artifact_paths":"",
                    "native_species_id_proven":"","native_villager_id_proven":"",
                })
    buckets=Counter()
    for row in output:
        buckets[(row["resource_extension_expected"],bool(row["original_rdb_record_found"]),
                 row["original_fdata_name"],str(row["physical_input_tracked"]),
                 str(row["expected_native_alias_tracked"]))]+=1
    out={
        "version":"2.0.1",
        "original_source_26_texture_OIDs":len(prior),
        "original_native_resource_hashes":52,
        "original_rdb_mapped_records":sum(x["original_rdb_record_found"] for x in output),
        "original_rdb_unresolved_hashes":sum(not x["original_rdb_record_found"] for x in output),
        "resource_provenance_groups":[
            {"extension":ext,"rdb_found":found,"original_fdata":source,
             "input_tracked":physical,"native_alias_tracked":alias,"count":n}
            for (ext,found,source,physical,alias),n in sorted(buckets.items())],
        "native_species_ids_verified":0,
        "native_villager_ids_verified":0,
        "warning":"TEXINFO hash absent from RDB may be an object-internal hash or resource variant. Never invent corresponding physical archive or image.",
    }
    R.mkdir(parents=True,exist_ok=True)
    with (R/"m25_4_26_texture_hash_rdb_provenance.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(output[0]),extrasaction="ignore")
        w.writeheader();w.writerows(output)
    (R/"m25_4_rdb_provenance_summary.json").write_text(
        json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,indent=2))
    return out

def self_test():
    assert TEXINFO==0xF20DE437 and G1T==0xAFBEC60C
    print("PASS original RDB type hash guard")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:self_test()
    else:analyze()
if __name__=="__main__":main()
