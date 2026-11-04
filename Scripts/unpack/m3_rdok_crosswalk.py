"""Cross-reference real KIDSOBJDB RDOK word patterns, IDOK names, and native RDB hashes.

This is an equality survey, NOT a proven object-pointer decoder.
"""
import argparse,csv,gzip,hashlib,json,re
from collections import Counter,defaultdict
from pathlib import Path

H=re.compile(r"^[0-9a-f]{8}$")
def h32(s):
 s=str(s).lower().removeprefix("0x")
 if not H.fullmatch(s): raise ValueError("INVALID_HEX32:"+s)
 return s
def rows(path):
 with open(path,encoding="utf-8-sig",newline="") as f:
  yield from csv.DictReader(f)
def output_csv(path,fields,items):
 with open(path,"w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(items)
def scan_exefs(path):
 data=Path(path).read_bytes()
 terms=("MissionSettings","MissionInfo_array.bfbs","pe_FlatbuffersDataComponent","FlatBuffers","MissionInfo_array")
 obs=[]
 for term in terms:
  for code in ("utf-8","utf-16le"):
   pattern=term.encode(code);start=0;positions=[]
   while True:
    at=data.find(pattern,start)
    if at<0: break
    positions.append(at);start=at+len(pattern)
   obs.append({"text":term,"encoding":code,"hits":len(positions),"offsets_first_100":positions[:100]})
 return {"sha256":hashlib.sha256(data).hexdigest(),"file_size":len(data),
         "matches":obs,"verified_runtime_linkage":False}
def run(types,shards,out,expected=4144,expected_rdok=40,exefs=None):
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 type_index={};file_matches=defaultdict(list);file_counts=Counter()
 for row in rows(types):
  rid=row["record_id"]
  if rid in type_index: raise ValueError("DUPLICATE_TYPE_ID:"+rid)
  type_index[rid]=row
  if row.get("name_hash"):
   hash_=h32(row["name_hash"]);file_counts[hash_]+=1
   if len(file_matches[hash_])<30:file_matches[hash_].append(rid)
 paths=sorted(Path(shards).glob("m4_shard*.jsonl.gz"))
 if len(paths)!=8:raise ValueError("EXPECTED_8_M4_SHARDS:"+str(len(paths)))
 seen=set();counts=Counter();idok_counts=Counter();idok_matches=defaultdict(list)
 doc_counts=Counter();doc_matches=defaultdict(list)
 prop_counts=Counter();rdok=[]
 for path in paths:
  with gzip.open(path,"rt",encoding="utf-8") as f:
   for line in f:
    if not line.strip():continue
    src=json.loads(line);rid=src["record_id"];parsed=src["decoded"]
    if rid in seen:raise ValueError("DUPLICATE_M4:"+rid)
    seen.add(rid)
    if rid not in type_index:raise ValueError("UNKNOWN_M4_ID:"+rid)
    original=type_index[rid]
    if parsed["sha256"].lower()!=original["output_sha256"].lower() or parsed["bytes"]!=int(original["unpacked_size"]):
     raise ValueError("M4_PROVENANCE_MISMATCH:"+rid)
    dh=h32(parsed["header"]["name_file_hash"]);doc_counts[dh]+=1
    if len(doc_matches[dh])<30:doc_matches[dh].append(rid)
    for b in parsed["blocks"]:
     kind=b["kind"];counts[kind]+=1
     if kind=="IDOK":
      hash_=h32(b["name_hash"]);idok_counts[hash_]+=1
      if len(idok_matches[hash_])<30:idok_matches[hash_].append(rid+"#"+str(b["index"]))
      for field in b.get("properties",[]):
       prop_counts[(h32(field["name_hash"]),int(field["type_code"]))]+=1
     elif kind=="RDOK":
      words=b.get("raw_u32_hex")
      valid=isinstance(words,list) and len(words)==4
      if valid:words=[h32(w) for w in words]
      valid=valid and words[0]==words[1]==words[2] and words[3]=="00000000"
      rdok.append({"source_record_id":rid,"block_index":b["index"],
                   "raw_words":",".join(words) if isinstance(words,list) else "",
                   "layout":"TRIPLE_EQUAL_ZERO_TAIL" if valid else "UNSUPPORTED_OR_OTHER",
                   "candidate_hash":words[0] if valid else ""})
     else:raise ValueError("UNKNOWN_M4_BLOCK_KIND:"+str(kind))
 if expected is not None and len(seen)!=expected:raise ValueError("M4_COUNT:"+str(len(seen)))
 if expected_rdok is not None and counts["RDOK"]!=expected_rdok:raise ValueError("RDOK_COUNT:"+str(counts["RDOK"]))
 status=Counter();result=[]
 for b in rdok:
  key=b["candidate_hash"]
  fc=file_counts[key] if key else 0
  ic=idok_counts[key] if key else 0
  dc=doc_counts[key] if key else 0
  grade=("NOT_A_TRIPLE" if not key else "NO_MATCH" if not (fc+ic+dc) else
         "MATCH_BOTH_RESOURCE_AND_IDOK" if fc and ic else "MATCH_CANDIDATE_ONLY")
  status[grade]+=1
  result.append({**b,"resource_hash_matches":fc,"idok_name_matches":ic,
                 "document_header_hash_matches":dc,
                 "resource_target_ids_first_30":";".join(file_matches[key]) if key else "",
                 "idok_target_ids_first_30":";".join(idok_matches[key]) if key else "",
                 "document_header_target_ids_first_30":";".join(doc_matches[key]) if key else "",
                 "evidence":grade+"_NOT_PROVEN_POINTER"})
 output_csv(out/"rdok_crosswalk.csv",
   ["source_record_id","block_index","raw_words","layout","candidate_hash",
    "resource_hash_matches","idok_name_matches","document_header_hash_matches",
    "resource_target_ids_first_30","idok_target_ids_first_30",
    "document_header_target_ids_first_30","evidence"],result)
 props=[{"field_hash":k[0],"type_code":k[1],"occurrences":v,
         "resource_name_matches":file_counts[k[0]]} for k,v in prop_counts.items()]
 props.sort(key=lambda x:(-x["occurrences"],x["field_hash"],x["type_code"]))
 output_csv(out/"field_hash_frequency.csv",["field_hash","type_code","occurrences","resource_name_matches"],props)
 summary={"published_resources":len(type_index),"kidsobjdb_records":len(seen),
          "blocks":dict(counts),"rdok_exact_triplet":sum(x["layout"]=="TRIPLE_EQUAL_ZERO_TAIL" for x in result),
          "rdok_evidence":dict(status),"unique_property_hash_types":len(prop_counts),
          "property_occurrences":sum(prop_counts.values()),"verified_pointer_edges":0,
          "field_plaintext_names_verified":0,"fully_decoded_semantics":False}
 if exefs:
  audit=scan_exefs(exefs)
  (out/"exefs_string_audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
  summary["exefs_total_static_matches"]=sum(x["hits"] for x in audit["matches"])
  summary["mission_settings_resource_identity_verified"]=False
 (out/"rdok_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(json.dumps(summary,ensure_ascii=False),flush=True)
 return summary
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--types",type=Path,required=True);p.add_argument("--shards",type=Path,required=True)
 p.add_argument("--out",type=Path,required=True);p.add_argument("--exefs",type=Path)
 a=p.parse_args();run(a.types,a.shards,a.out,exefs=a.exefs)
if __name__=="__main__":main()
