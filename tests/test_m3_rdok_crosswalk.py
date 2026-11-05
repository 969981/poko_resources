import csv,gzip,json,tempfile,unittest
from pathlib import Path
from Scripts.unpack.m3_rdok_crosswalk import run,scan_exefs

class TestM3Rdok(unittest.TestCase):
 def fixture(self,folder,valid=True):
  root=Path(folder);shards=root/"shards";shards.mkdir()
  idx=root/"types.csv"
  idx.write_text("record_id,name_hash,output_sha256,unpacked_size\nroot:1,55235e67,"+"a"*64+",56\nroot:2,12345678,"+"b"*64+",56\n",encoding="utf-8")
  idok={"record_id":"root:1","decoded":{
    "sha256":"a"*64,"bytes":56,"header":{"name_file_hash":"12345678"},
    "blocks":[{"kind":"IDOK","index":0,"name_hash":"55235e67",
               "properties":[{"name_hash":"99999999","type_code":5}]}]}}
  words=["55235e67","55235e67","55235e67","00000000"]
  if not valid:words[1]="87654321"
  rdok={"record_id":"root:2","decoded":{
    "sha256":"b"*64,"bytes":56,"header":{"name_file_hash":"12345678"},
    "blocks":[{"kind":"RDOK","index":0,"raw_u32_hex":words}]}}
  for i in range(8):
   with gzip.open(shards/("m4_shard%02d.jsonl.gz"%i),"wt",encoding="utf-8") as f:
    if i==0:
     for row in (idok,rdok):f.write(json.dumps(row)+"\n")
  return idx,shards
 def test_exact_match_not_prematurely_proven_pointer(self):
  with tempfile.TemporaryDirectory() as d:
   idx,shards=self.fixture(d)
   result=run(idx,shards,Path(d)/"out",expected=2,expected_rdok=1)
   self.assertEqual(result["rdok_exact_triplet"],1)
   self.assertEqual(result["verified_pointer_edges"],0)
   self.assertEqual(result["property_occurrences"],1)
   with (Path(d)/"out"/"rdok_crosswalk.csv").open(newline="") as f:
    row=next(csv.DictReader(f))
   self.assertEqual(row["resource_hash_matches"],"1")
   self.assertEqual(row["idok_name_matches"],"1")
   self.assertEqual(row["resource_target_ids_first_30"],"root:1")
   self.assertIn("NOT_PROVEN_POINTER",row["evidence"])
 def test_inconsistent_triplet_does_not_link(self):
  with tempfile.TemporaryDirectory() as d:
   idx,shards=self.fixture(d,valid=False)
   result=run(idx,shards,Path(d)/"out",expected=2,expected_rdok=1)
   self.assertEqual(result["rdok_exact_triplet"],0)
   self.assertEqual(result["rdok_evidence"],{"NOT_A_TRIPLE":1})
 def test_static_search_only(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"main"
   p.write_bytes(b"A MissionSettings Z"+ "MissionInfo_array.bfbs".encode("utf-16le"))
   report=scan_exefs(p)
   self.assertFalse(report["verified_runtime_linkage"])
   # Both the complete schema name and its shorter prefix are searched.
   # The prefix is one overlapping observation, not a third unique string.
   by_term={(x["text"],x["encoding"]):x["hits"] for x in report["matches"]}
   self.assertEqual(by_term[("MissionSettings","utf-8")],1)
   self.assertEqual(by_term[("MissionInfo_array.bfbs","utf-16le")],1)
   self.assertEqual(by_term[("MissionInfo_array","utf-16le")],1)
   self.assertEqual(sum(x["hits"] for x in report["matches"]),3)
if __name__=="__main__":unittest.main()
