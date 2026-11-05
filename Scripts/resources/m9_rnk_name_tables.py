#!/usr/bin/env python3
"""M9.3: resolve native KIDSOBJDB companion _RNK0000 name resources.

Only on-disk, hash-qualified matches become name-source evidence.
IRNK string positions do NOT automatically describe property field names.
U32 coincidences and ExeFS numeric literals NEVER become text foreign keys.
"""
from __future__ import annotations
import argparse
import collections
import csv
import hashlib
import json
import os
import re
import struct
import subprocess
from pathlib import Path

MAGIC = b"_RNK0000"
RECORD = b"IRNK0000"
DOK = b"_DOK0000"
MAX_STRINGS = 100000
MAX_NAMES = 400000
COLS = ("owner_m3_record_id","owner_name_hash","expected_rnk_hash","rnk_repository_path",
        "rnk_sha256","irnk_key_hash","irnk_record_offset","string_index",
        "string_byte_offset","string_sha256","text_utf8","evidence_grade")

def u32(data, pos):
    if pos < 0 or pos+4 > len(data):
        raise ValueError(f"u32 field out of bounds at {pos:#x}")
    return struct.unpack_from("<I",data,pos)[0]

def hx(v): return f"{v:08x}"
def sha(data): return hashlib.sha256(data).hexdigest()

def parse_dok_header(data):
    if len(data)<28 or data[:8]!=DOK or u32(data,8)!=28 or u32(data,12)!=24:
        raise ValueError("Unsupported KIDSOBJDB _DOK0000 header")
    if u32(data,24)!=len(data):
        raise ValueError("KIDSOBJDB declared size does not match original bytes")
    return {"native_object_count":u32(data,16),"name_resource_hash":hx(u32(data,20))}

def parse_rnk(data):
    """Strict IRNK records; return entries with source byte offsets and raw bytes."""
    if len(data)<24 or data[:8]!=MAGIC:
        raise ValueError("NOT_RNK_NAME_TABLE")
    head=u32(data,8);platform=u32(data,12);count=u32(data,16);declared=u32(data,20)
    if head!=24 or declared!=len(data) or count>MAX_NAMES:
        raise ValueError("BAD_RNK_HEADER")
    p=head
    out=[]
    for record_index in range(count):
        if p+20>len(data) or data[p:p+8]!=RECORD:
            raise ValueError(f"INVALID_IRNK_MAGIC at entry={record_index}, offset={p}")
        size=u32(data,p+8);key=u32(data,p+12);n=u32(data,p+16)
        if n>MAX_STRINGS or size<20+4*n or p+size>len(data):
            raise ValueError(f"INVALID_IRNK_SIZE at entry={record_index}")
        offsets=[u32(data,p+20+i*4) for i in range(n)]
        if offsets != sorted(offsets) or any(x<20+4*n or x>=size for x in offsets):
            raise ValueError(f"INVALID_IRNK_STRING_OFFSETS at entry={record_index}")
        strings=[]
        bounds=offsets[1:]+[size]
        for j,(begin,end) in enumerate(zip(offsets,bounds)):
            raw=data[p+begin:p+end].rstrip(b"\0")
            try:text=raw.decode("utf-8","strict")
            except UnicodeDecodeError as exc:
                raise ValueError(f"INVALID_IRNK_UTF8 at record={record_index} string={j}") from exc
            strings.append({"index":j,"abs_offset":p+begin,"raw_sha256":sha(raw),"text":text})
        aligned=(p+size+3)&~3
        if aligned>len(data) or any(data[p+size:aligned]):
            raise ValueError(f"INVALID_IRNK_PADDING at record={record_index}")
        out.append({"index":record_index,"key":key,"offset":p,"strings":strings})
        p=aligned
    if p!=len(data): raise ValueError(f"RNK_COUNT_OR_TRAILING_BYTES at offset={p}, size={len(data)}")
    return out,{"entries":count,"platform_raw":platform,"rnk_header_size":head,"size":len(data)}

def scan_dok_property_identity(data):
    """Count native property-name hashes and object IDs without guessing value semantics."""
    head=parse_dok_header(data)
    count=head["native_object_count"];p=28
    objectids=set(); propfreq=collections.Counter()
    for i in range(count):
        if p+24>len(data) or data[p:p+8]!=b"IDOK0000":
            raise ValueError(f"KIDSOBJDB unexpected record at {i}:{p}")
        size=u32(data,p+8)
        if size<24 or p+size>len(data):raise ValueError("INVALID_IDOK_SIZE")
        objectids.add(u32(data,p+12))
        n=u32(data,p+20)
        if n>4096 or p+24+12*n>p+size: raise ValueError("IDOK property descriptors overflow")
        for j in range(n):
            propfreq[u32(data,p+24+12*j+8)]+=1
        end=p+size;p=(end+3)&~3
        if any(data[end:p]):raise ValueError("NONZERO_IDOK_PADDING")
    if p!=len(data): raise ValueError("KIDSOBJDB trailing native bytes")
    return objectids,propfreq

def candidate_paths(index_file, wanted):
    matches={h:[] for h in wanted}; rows=0
    with index_file.open(encoding="utf-8-sig",newline="") as fh:
        reader=csv.DictReader(fh)
        for col in ("name_hash","output_path"):
            if col not in (reader.fieldnames or []):raise ValueError(f"M3 index missing {col}")
        for r in reader:
            rows+=1;h=str(r["name_hash"]).lower().removeprefix("0x").zfill(8)
            if h not in wanted:continue
            val=r["output_path"].strip().replace("\\","/")
            if not val:continue
            path=val if val.startswith("UnPack/2.0.1/") else "UnPack/2.0.1/"+val.lstrip("/")
            if ".." in Path(path).parts:continue
            matches[h].append({"path":path,"m3_record_id":r.get("record_id",""),
                               "type_hash":r.get("type_hash",""),"signature":r.get("signature",""),
                               "index_sha256":r.get("output_sha256","")})
    return matches,rows

def ls_tree_fallback(wanted):
    """The tracked path name may carry the 8-character resource hash."""
    r=subprocess.run(["git","ls-tree","-r","--name-only","HEAD",
         "UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE"],
         capture_output=True,text=True,check=True)
    result={h:[] for h in wanted}
    for line in r.stdout.splitlines():
        match=re.search(r"_(?P<hash>[0-9a-f]{8})\.fdata_idrk\.bin$",line,re.I)
        if match and match["hash"].lower() in wanted:
            result[match["hash"].lower()].append({"path":line,"m3_record_id":"",
                   "type_hash":"","signature":"","index_sha256":""})
    return result

def git_read(path,max_bytes=128*1024*1024):
    # Use Git's verified object path and blobless partial-clone lazy fetch.  Do
    # not checkout every FDATA asset; no network requests outside Git itself.
    if not path.startswith("UnPack/2.0.1/") or ".." in Path(path).parts:
        raise ValueError("Unsafe source path")
    chk=subprocess.run(["git","cat-file","-s",f"HEAD:{path}"],capture_output=True,text=True)
    if chk.returncode!=0:return None,"MISSING_GIT_BLOB"
    size=int(chk.stdout.strip())
    if size>max_bytes:return None,"NAME_RESOURCE_TOO_LARGE"
    r=subprocess.run(["git","show",f"HEAD:{path}"],capture_output=True,check=False)
    if r.returncode!=0:return None,"GIT_SHOW_FAILED"
    if len(r.stdout)!=size:return None,"BLOB_READ_SIZE_MISMATCH"
    return r.stdout,"READ"

class CsvShards:
    def __init__(self,dest,prefix,fields,limit=22*1024*1024):
        self.dest=dest;self.prefix=prefix;self.fields=fields;self.limit=limit
        self.num=-1;self.count=0;self.writer=None;self.file=None;self.rotate()
    def rotate(self):
        if self.file:self.file.close()
        self.num+=1
        self.file=(self.dest/f"{self.prefix}_{self.num:03d}.csv").open("w",encoding="utf-8",newline="")
        self.writer=csv.DictWriter(self.file,fieldnames=self.fields);self.writer.writeheader()
    def add(self,row):
        if self.file.tell()>self.limit:self.rotate()
        self.writer.writerow(row);self.count+=1
    def close(self):self.file.close()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sources",type=Path,required=True)
    ap.add_argument("--m3-index",type=Path,required=True)
    ap.add_argument("--unpack-root",type=Path,default=Path("UnPack/2.0.1"))
    ap.add_argument("--dest",type=Path,required=True)
    args=ap.parse_args()
    args.dest.mkdir(parents=True,exist_ok=True)
    for old in args.dest.glob("rnk_strings_*.csv"):old.unlink()
    with args.sources.open(encoding="utf-8",newline="") as fh: owners=list(csv.DictReader(fh))
    if len(owners)!=3:raise ValueError("Expected exactly three original KIDSOBJDB sources")
    owner_data=[];expected={}
    for row in owners:
        path=args.unpack_root/row["output_path"]
        data=path.read_bytes()
        if sha(data)!=row["output_sha256"]:raise ValueError(f"M3 source hash changed: {path}")
        header=parse_dok_header(data)
        ids,props=scan_dok_property_identity(data)
        owner_data.append((row,header,ids,props))
        expected.setdefault(header["name_resource_hash"],[]).append(row["m3_record_id"])
    m3, m3rows=candidate_paths(args.m3_index,set(expected))
    fallback=ls_tree_fallback(set(expected))
    found={}
    candidates=[]
    for h in sorted(expected):
        choices={r["path"]:r for r in (m3.get(h,[])+fallback.get(h,[]))}
        for path,meta in sorted(choices.items()):
            blob,status=git_read(path)
            entry={**meta,"expected_name_hash":h,"source_read_status":status,
                   "magic":"","sha256":"","parse_status":"","irnk_entries":0}
            if blob is not None:
                entry["magic"]=blob[:8].decode("ascii","replace")
                entry["sha256"]=sha(blob)
                if blob.startswith(MAGIC):
                    try:
                        rows,info=parse_rnk(blob)
                        entry["parse_status"]="RNK_PARSED_EXACT"
                        entry["irnk_entries"]=len(rows)
                        found.setdefault(h,[]).append((path,blob,rows,info))
                    except ValueError as ex:
                        entry["parse_status"]=f"RNK_INVALID:{ex}"
                else:entry["parse_status"]="NOT_RNK_MAGIC"
            candidates.append(entry)
    names=CsvShards(args.dest,"rnk_strings",list(COLS))
    source_rows=[]; property_matches=[];object_matches=[]
    for row,header,ids,props in owner_data:
        h=header["name_resource_hash"]
        valid=found.get(h,[])
        source_rows.append({"m3_record_id":row["m3_record_id"],
             "kidsobjdb_name_hash":row["name_hash"],
             "kidsobjdb_sha256":row["output_sha256"],
             "expected_rnk_name_hash":h,
             "matching_m3_resource_rows":len(m3.get(h,[])),
             "tracked_path_candidates":len(fallback.get(h,[])),
             "rnk_valid_sources":len(valid),
             "status":"UNIQUE_RNK_SOURCE" if len(valid)==1 else (
                 "RNK_NAME_FILE_MISSING" if not valid else "AMBIGUOUS_RNK_SOURCES"),
             "native_object_count":header["native_object_count"],
             "unique_native_object_ids":len(ids),
             "unique_property_hashes":len(props)})
        if len(valid)!=1:continue
        source_path,blob,irnk,info=valid[0]
        keys={e["key"] for e in irnk}
        for e in irnk:
            key=e["key"];v=hx(key)
            for s in e["strings"]:
                names.add(dict(owner_m3_record_id=row["m3_record_id"],
                    owner_name_hash=row["name_hash"],expected_rnk_hash=h,
                    rnk_repository_path=source_path,rnk_sha256=sha(blob),
                    irnk_key_hash=v,irnk_record_offset=e["offset"],
                    string_index=s["index"],string_byte_offset=s["abs_offset"],
                    string_sha256=s["raw_sha256"],text_utf8=s["text"],
                    evidence_grade="NATIVE_RNK_IRNK_BYTES_EXACT"))
            if key in ids:
                object_matches.append({"owner":row["m3_record_id"],"rnk_source":source_path,
                       "irnk_key_hash":v,"string_count":len(e["strings"]),
                       "strings_json":json.dumps([s["text"] for s in e["strings"][:12]],ensure_ascii=False),
                       "evidence":"RNK_IRNK_KEY_EQUALS_NATIVE_OBJECT_ID"})
            if key in props:
                property_matches.append({"owner":row["m3_record_id"],"rnk_source":source_path,
                       "property_hash":v,"field_occurrences":props[key],
                       "string_count":len(e["strings"]),
                       "strings_json":json.dumps([s["text"] for s in e["strings"][:12]],ensure_ascii=False),
                       "evidence":"RNK_IRNK_KEY_EQUALS_PROPERTY_DESCRIPTOR_HASH_ONLY",
                       "semantic_property_name_verified":0})
    names.close()
    def write_csv(path,rows,fields):
        with path.open("w",encoding="utf-8",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    write_csv(args.dest/"rnk_owner_sources.csv",source_rows,
              ["m3_record_id","kidsobjdb_name_hash","kidsobjdb_sha256",
               "expected_rnk_name_hash","matching_m3_resource_rows",
               "tracked_path_candidates","rnk_valid_sources","status",
               "native_object_count","unique_native_object_ids","unique_property_hashes"])
    write_csv(args.dest/"rnk_resource_candidates.csv",candidates,
              ["path","m3_record_id","type_hash","signature","index_sha256",
               "expected_name_hash","source_read_status","magic","sha256",
               "parse_status","irnk_entries"])
    write_csv(args.dest/"rnk_property_hash_matches.csv",property_matches,
              ["owner","rnk_source","property_hash","field_occurrences",
               "string_count","strings_json","evidence","semantic_property_name_verified"])
    write_csv(args.dest/"rnk_object_id_matches.csv",object_matches,
              ["owner","rnk_source","irnk_key_hash","string_count","strings_json","evidence"])
    report={"status":"M9_RNK_NAME_RESOURCE_PROVENANCE",
      "m3_index_records_inspected":m3rows,"native_owner_files":len(owner_data),
      "source_name_hashes":{r["m3_record_id"]:h["name_resource_hash"] for r,h,_,_ in owner_data},
      "rnk_source_resolution":source_rows,"resolved_native_irnk_strings":names.count,
      "irnk_key_matches_property_hashes":len(property_matches),
      "irnk_key_matches_object_ids":len(object_matches),
      "verified_property_semantic_names":0,
      "verified_scene_quest_building_text_foreign_keys":0,
      "numeric_oid_candidates_still_unverified":87445,
      "evidence_limits":[
       "M3 header @+0x14 explicitly references companion name-file resource hash.",
       "Only exact resource hash + _RNK0000/IRNK0000 record structure establishes name source.",
       "IRNK keys can be object IDs and/or property hashes; collisions alone do not prove property labels.",
       "Actual ExeFS or script property-hash usage requires instruction/control-flow verification.",
       "The 87,445 numeric matches are still NOT foreign keys."
      ]}
    (args.dest/"rnk_report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2,ensure_ascii=False))

if __name__=="__main__":main()
