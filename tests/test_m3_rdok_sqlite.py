"""Minimal isolated SQLite import/replay tests; no game resource data."""
import csv,json,sqlite3,tempfile,unittest
from pathlib import Path
from Scripts.unpack.m3_rdok_sqlite import run

def make_fixture(folder):
 folder=Path(folder);dbp=folder/"catalog.sqlite";cp=folder/"rdok.csv"
 db=sqlite3.connect(dbp)
 db.executescript("""
 CREATE TABLE resources(record_id TEXT PRIMARY KEY, catalog TEXT, name_hash TEXT, decoded_sha256 TEXT);
 CREATE TABLE kidsobjdb_blocks(record_id TEXT, block_index INTEGER, kind TEXT, raw_u32_json TEXT);
 CREATE TABLE source_locations(record_id TEXT, original_container_path TEXT);
 INSERT INTO resources VALUES('root:1','root','33333333','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa');
 INSERT INTO resources VALUES('root:2','root','55235e67','bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb');
 INSERT INTO kidsobjdb_blocks VALUES('root:1',0,'RDOK','["55235e67","55235e67","55235e67","00000000"]');
 INSERT INTO kidsobjdb_blocks VALUES('root:2',0,'IDOK',NULL);
 INSERT INTO source_locations VALUES('root:1','romfs/fdata/0x1.fdata');
 INSERT INTO source_locations VALUES('root:2','romfs/fdata/0x1.fdata');
 """);db.close()
 columns=["source_record_id","rdok_block_index","candidate_name_hash","target_record_id","target_idok_blocks","source_container","target_container","same_catalog","same_container","source_decoded_sha256","target_decoded_sha256","evidence_level"]
 with cp.open("w",encoding="utf-8",newline="") as f:
  writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader()
  writer.writerow(dict(source_record_id="root:1",rdok_block_index=0,candidate_name_hash="55235e67",target_record_id="root:2",target_idok_blocks=1,source_container="romfs/fdata/0x1.fdata",target_container="romfs/fdata/0x1.fdata",same_catalog="true",same_container="true",source_decoded_sha256="a"*64,target_decoded_sha256="b"*64,evidence_level="HASH_ONLY"))
 return dbp,cp

class ImportTests(unittest.TestCase):
 def test_default_dry_run_does_not_mutate(self):
  with tempfile.TemporaryDirectory() as folder:
   dbp,cp=make_fixture(folder)
   result=run(dbp,cp,expected=1)
   self.assertFalse(result["db_modified"])
   with sqlite3.connect(dbp) as db:
    self.assertFalse(db.execute("SELECT name FROM sqlite_master WHERE name='rdok_reference_candidates'").fetchone())
 def test_apply_replay_and_tamper_guard(self):
  with tempfile.TemporaryDirectory() as folder:
   dbp,cp=make_fixture(folder)
   self.assertEqual(run(dbp,cp,apply=True,expected=1)["same_fdata"],1)
   self.assertEqual(run(dbp,cp,apply=True,expected=1)["unique_targets"],1)
   with sqlite3.connect(dbp) as db:
    row=db.execute("SELECT target_record_id,evidence FROM rdok_reference_candidates").fetchone()
   self.assertEqual(row,("root:2","HASH_EQUALITY_ONLY_NOT_PROVEN_POINTER"))
   body=cp.read_text(encoding="utf-8").replace("55235e67,root:2","ffffffff,root:2")
   cp.write_text(body,encoding="utf-8")
   with self.assertRaisesRegex(ValueError,"RDOK_TARGET_NAME_HASH_MISMATCH"):
    run(dbp,cp,apply=True,expected=1)

if __name__=="__main__":unittest.main()
