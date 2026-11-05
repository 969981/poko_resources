#!/usr/bin/env python3
"""M17: native typed-object reverse references to original Pokémon icon OIDs.

Scans the 678 actual KIDSOBJDB files in source FDATA 0xacd220a8.
An IDOK field containing an icon object's ID is a reproducible candidate
reference, but NOT a species ID or official native field semantics.
"""
from __future__ import annotations
import csv,hashlib,json,struct
from collections import Counter,defaultdict
from pathlib import Path
from .m16_verify_pokemon_texture_kidsobjdb import parse_kids

ROOT=Path("UnPack/2.0.1/Resources")
SOURCES=Path("UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0xacd220a8.fdata/native")
OUT=ROOT/"Pokemon/NativeCallers/M17"
FIELDS=("source_path","source_db_sha256","source_db_name_hash","source_node_oid",
        "source_node_type_hash","native_property_hash","native_property_type",
        "native_property_array_count","native_property_absolute_byte_offset",
        "matched_target_object_hash","matched_target_sprites","evidence",
        "proven_species_id_binding")

def u(data,pos):return struct.unpack_from("<I",data,pos)[0]
def h(value):return f"{value:08x}"

def candidates(files,targets):
    matches=[]
    status=Counter()
    errors=[]
    per_hash=Counter()
    per_source=Counter()
    visited=0
    for path in sorted(files):
        visited+=1
        raw=path.read_bytes()
        try:
            db,nodes=parse_kids(raw)
        except (ValueError,struct.error) as exc:
            errors.append({"path":path.as_posix(),"size":len(raw),"error":str(exc)})
            status["PARSE_FAILED"]+=1
            continue
        status["NATIVE_DB_PARSED"]+=1
        check=hashlib.sha256(raw).hexdigest()
        for oid,node in nodes.items():
            for prop_hash,prop in node["fields"].items():
                if prop["kind"] not in (4,5):
                    continue
                if prop["count"]>100000:
                    raise ValueError(f"Too many original native u32 values in {path}")
                for i in range(prop["count"]):
                    offset=prop["offset"]+i*4
                    t=u(raw,offset)
                    if t not in targets:
                        continue
                    matched=targets[t]
                    val={"source_path":path.as_posix(),"source_db_sha256":check,
                         "source_db_name_hash":path.stem.rsplit("_",1)[-1],
                         "source_node_oid":h(oid),
                         "source_node_type_hash":h(node["type"]),
                         "native_property_hash":h(prop_hash),
                         "native_property_type":prop["kind"],
                         "native_property_array_count":prop["count"],
                         "native_property_absolute_byte_offset":offset,
                         "matched_target_object_hash":h(t),
                         "matched_target_sprites":";".join(matched),
                         "evidence":"TYPED_NATIVE_U32_EQUALS_TEXTURE_OBJECT_ID__CONSUMER_UNVERIFIED",
                         "proven_species_id_binding":0}
                    matches.append(val)
                    per_hash[h(prop_hash)]+=1
                    per_source[path.name]+=1
    report={
        "status":"NATIVE_TYPED_TEXTURE_OID_BACKREFERENCE_SURVEY",
        "source_database_files":visited,
        "source_parse_status":dict(status),
        "parse_failures":errors[:100],
        "target_icon_object_ids":len(targets),
        "original_u32_matches":len(matches),
        "unique_target_icon_oids_referenced":len(set(int(x["matched_target_object_hash"],16) for x in matches)),
        "match_property_hash_frequency":dict(per_hash.most_common(40)),
        "top_source_kidsobjdb_files":dict(per_source.most_common(40)),
        "native_species_id_binding_verified":0,
        "warning":"Even an exact object-ID value in a typed native property cannot establish species ID without original native property label or code consumer. Self-contained texture-layout references are not species fields."
    }
    return matches,report

def main():
    with (ROOT/"Pokemon/pokemon_identity_crosswalk.csv").open(encoding="utf-8",newline="") as f:
        rows=list(csv.DictReader(f))
    targets=defaultdict(list)
    for r in rows:
        targets[int(r["object_hash"],16)].append(r["texture_name"])
    source=sorted(SOURCES.glob("*.kidsobjdb"))
    if len(source)!=678:
        raise ValueError(f"Original source pack coverage changed: {len(source)}, expected 678")
    found,report=candidates(source,targets)
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/"pokemon_typed_icon_oid_backrefs.csv").open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS)
        writer.writeheader();writer.writerows(found)
    (OUT/"m17_report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2,ensure_ascii=False))
if __name__=="__main__":main()
