"""Import provenance-checked RDOK candidates into an existing M3 SQLite copy.

All 40 rows remain candidate hash edges. This command is dry-run by default.
No original assets or raw game bytes are written.
"""
import argparse,csv,json,sqlite3
from pathlib import Path

TABLE="""
CREATE TABLE IF NOT EXISTS rdok_reference_candidates(
 source_record_id TEXT NOT NULL REFERENCES resources(record_id),
 block_index INTEGER NOT NULL,
 target_record_id TEXT NOT NULL REFERENCES resources(record_id),
 name_hash TEXT NOT NULL,
 same_container INTEGER NOT NULL,
 evidence TEXT NOT NULL CHECK(evidence='HASH_EQUALITY_ONLY_NOT_PROVEN_POINTER'),
 PRIMARY KEY(source_record_id,block_index)
);
CREATE INDEX IF NOT EXISTS rdok_reference_target_idx
 ON rdok_reference_candidates(target_record_id);
"""
def audit(conn,row):
 src=row["source_record_id"];dst=row["target_record_id"];hash_=row["candidate_name_hash"].lower()
 i=int(row["rdok_block_index"])
 original=conn.execute("SELECT decoded_sha256,catalog FROM resources WHERE record_id=?",(src,)).fetchone()
 target=conn.execute("SELECT decoded_sha256,catalog,name_hash FROM resources WHERE record_id=?",(dst,)).fetchone()
 if not original or not target:raise ValueError("RDOK_SOURCE_OR_TARGET_MISSING:"+src)
 if original[0].lower()!=row["source_decoded_sha256"].lower():raise ValueError("RDOK_SOURCE_SHA_MISMATCH:"+src)
 if target[0].lower()!=row["target_decoded_sha256"].lower():raise ValueError("RDOK_TARGET_SHA_MISMATCH:"+dst)
 if target[2]!=hash_:raise ValueError("RDOK_TARGET_NAME_HASH_MISMATCH:"+dst)
 if original[1]!=target[1] or row["same_catalog"].lower()!="true":raise ValueError("RDOK_CATALOG_MISMATCH:"+src)
 raw=conn.execute("SELECT kind,raw_u32_json FROM kidsobjdb_blocks WHERE record_id=? AND block_index=?",(src,i)).fetchone()
 if not raw or raw[0]!="RDOK":raise ValueError("RDOK_BLOCK_NOT_PRESENT:"+src+":"+str(i))
 words=json.loads(raw[1])
 if len(words)!=4 or words[:3]!=[hash_]*3 or words[3]!="00000000":
  raise ValueError("RDOK_BLOCK_WORDS_MISMATCH:"+src)
 n=conn.execute("SELECT COUNT(*) FROM kidsobjdb_blocks WHERE record_id=? AND kind='IDOK'",(dst,)).fetchone()[0]
 if n<1 or n!=int(row["target_idok_blocks"]):raise ValueError("RDOK_TARGET_IDOK_MISMATCH:"+dst)
 containers=conn.execute("SELECT original_container_path FROM source_locations WHERE record_id IN (?,?)",(src,dst)).fetchall()
 src_container=conn.execute("SELECT original_container_path FROM source_locations WHERE record_id=?",(src,)).fetchone()
 dst_container=conn.execute("SELECT original_container_path FROM source_locations WHERE record_id=?",(dst,)).fetchone()
 if not src_container or not dst_container:raise ValueError("RDOK_MISSING_LOCATION:"+src)
 same=src_container[0]==dst_container[0]
 if (row["same_container"].lower()=="true")!=same:raise ValueError("RDOK_CONTAINER_MISMATCH:"+src)
 if src_container[0]!=row["source_container"] or dst_container[0]!=row["target_container"]:
  raise ValueError("RDOK_CONTAINER_PATH_MISMATCH:"+src)
 return (src,i,dst,hash_,int(same),"HASH_EQUALITY_ONLY_NOT_PROVEN_POINTER")
def run(database,crosswalk,apply=False,expected=40):
 with open(crosswalk,encoding="utf-8-sig",newline="") as f:
  rows=list(csv.DictReader(f))
 if expected is not None and len(rows)!=expected:
  raise ValueError("RDOK_CROSSWALK_COUNT:"+str(len(rows)))
 # Read-only mode is explicit; default cannot mutate the DB.
 uri=Path(database).resolve().as_uri()+"?mode="+("rw" if apply else "ro")
 conn=sqlite3.connect(uri,uri=True)
 try:
  conn.execute("PRAGMA foreign_keys=ON")
  keys=[];validated=[];targets=set()
  for row in rows:
   value=audit(conn,row);key=value[:2]
   if key in keys:raise ValueError("DUPLICATE_RDOK_SOURCE_BLOCK")
   if value[2] in targets:raise ValueError("DUPLICATE_RDOK_TARGET")
   keys.append(key);targets.add(value[2]);validated.append(value)
  summary={"audited":len(validated),"unique_targets":len(targets),
           "same_fdata":sum(v[4] for v in validated),
           "cross_fdata":sum(1-v[4] for v in validated),
           "candidate_not_verified_runtime_edges":len(validated),
           "confirmed_runtime_edges":0,"db_modified":bool(apply)}
  if apply:
   with conn:
    conn.executescript(TABLE)
    for v in validated:
     prev=conn.execute("SELECT target_record_id,name_hash,same_container,evidence FROM rdok_reference_candidates WHERE source_record_id=? AND block_index=?",v[:2]).fetchone()
     if prev and prev!=v[2:]:raise ValueError("RDOK_STORED_CONFLICT:"+v[0])
     if not prev:conn.execute("INSERT INTO rdok_reference_candidates VALUES(?,?,?,?,?,?)",v)
    if conn.execute("PRAGMA foreign_key_check").fetchone():
     raise ValueError("RDOK_FOREIGN_KEY_CHECK_FAILED")
  return summary
 finally:
  conn.close()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--db",type=Path,required=True);p.add_argument("--crosswalk",type=Path,required=True)
 p.add_argument("--apply",action="store_true");p.add_argument("--expected",type=int,default=40)
 a=p.parse_args();print(json.dumps(run(a.db,a.crosswalk,a.apply,a.expected),indent=2))
if __name__=="__main__":main()
