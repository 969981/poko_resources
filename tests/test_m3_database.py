"""Synthetic, copyright-free M3 relational catalogue tests."""
import csv
import gzip
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from Scripts.unpack.m3_database import build, lookup, hash_value, relative_asset_path

SHA = hashlib.sha256(b'valid synthetic data').hexdigest()


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


class DatabaseTests(unittest.TestCase):
    def test_build_provenance_lookup_and_unverified_link(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            types=root/'types.csv'
            write_csv(types,[{
                'record_id':rid,'source_path': '2.0.1/romfs/demo.fdata' if rid=='root:1' else '2.0.1/romfs/LD_C0_R.BIN',
                'output_path':f'romfs/{rid.split(":")[0]}/{rid.split(":")[1]}.bin',
                'output_sha256': SHA,'name_hash': 'deadbeef' if rid=='root:1' else '',
                'type_hash':'20a6a0bb' if rid=='root:1' else '',
                'unpacked_size':'96' if rid=='root:1' else '13',
                'native_extension_hint':'.kidsobjdb' if rid=='root:1' else '',
                'evidence_grade':'MAGIC_AND_TKID' if rid=='root:1' else 'UNKNOWN_NATIVE_FORMAT',
                'signature':'KIDSOBJDB_SIGNATURE' if rid=='root:1' else 'UNKNOWN_BINARY',
                'head_64_hex':'5f444f4b','m3_probe_status':'PROBED'
            } for rid in ('root:1','link:0')])
            missing=root/'missing.csv'
            write_csv(missing,[{'record_id':'system:2','source_file':'0xdeadbeef.fdata',
                'name_hash':'aabbccdd','type_hash':'00000000','unpacked_size':'500',
                'platform_flags':'ffff','reason':'PHYSICAL_INPUT_NOT_IN_2.0.1_ROMFS'}])
            m4idx=root/'m4.csv'
            write_csv(m4idx,[{'record_id':'root:1','status':'FIXED_WIDTH_ONLY'}])
            shards=root/'shards';shards.mkdir()
            doc={
                'record_id':'root:1', 'source_path':'2.0.1/romfs/demo.fdata',
                'status':'FIXED_WIDTH_ONLY',
                'decoded':{
                    'magic':'_DOK0000','bytes':96,'sha256':SHA,
                    'header':{'entry_count':1}, 'summary':{'IDOK':1,'RDOK':0,'PARTIAL_BLOCKS':0},
                    'warnings':[], 'blocks':[{ 'index':0,'kind':'IDOK','offset':28,'size':68,
                        'sha256':SHA,'status':'FIXED_WIDTH_VALUES_PARSED','name_hash':'aabbccdd',
                        'type_hash':'12345678','property_count':1,'properties':[
                        {'index':0,'name_hash':'a1b2c3d4','type_code':5,'count':1,
                         'value_bytes':4,'status':'DECODED_FIXED_WIDTH','sample_values':[0xdeadbeef]}
                    ]}]
                }
            }
            for shard in range(8):
                with gzip.open(shards/f'm4_shard{shard:02d}.jsonl.gz','wt',encoding='utf-8') as f:
                    if shard == 0:
                        f.write(json.dumps(doc)+'\n')
            dbfile=root/'data.sqlite';ex=root/'out'
            summary=build(types,m4idx,shards,missing,dbfile,ex,strict=False,
                          expected_types=2,expected_m4=1,expected_missing=1)
            self.assertEqual(summary['m3_resources'],2)
            self.assertEqual(summary['m4_fields'],1)
            self.assertEqual(summary['unverified_numeric_hash_matches'],1)
            self.assertFalse(summary['semantic_complete'])
            with sqlite3.connect(dbfile) as db:
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                self.assertEqual(db.execute('SELECT count(*) FROM resources').fetchone()[0],2)
                self.assertEqual(db.execute('SELECT count(*) FROM missing_records').fetchone()[0],1)
                self.assertEqual(db.execute('SELECT count(*) FROM kidsobjdb_fields').fetchone()[0],1)
            got=lookup(dbfile,record='root:1',hash_text=None,limit=10)
            self.assertEqual(got['unverified_hash_matches'][0]['target_record_id'],'root:1')
            self.assertIn('UNVERIFIED',got['unverified_hash_matches'][0]['evidence'])
            self.assertEqual(len(lookup(dbfile,record=None,hash_text='20a6a0bb',limit=10)['resources']),1)
            self.assertTrue((ex/'resources.csv').is_file())
            with gzip.open(ex/'resources.jsonl.gz','rt') as f:
                self.assertEqual(len(f.readlines()),2)

    def test_unsafe_source_path_rejected(self):
        with self.assertRaisesRegex(ValueError,'UNSAFE_ASSET_PATH'):
            relative_asset_path('../outside')
        with self.assertRaisesRegex(ValueError,'UNSAFE_ASSET_PATH'):
            relative_asset_path('/root/private')
        self.assertEqual(hash_value('0x20A6A0BB'),'20a6a0bb')
        with self.assertRaisesRegex(ValueError,'INVALID_HASH'):
            hash_value('gopher')

    def test_lookup_limit_rejected(self):
        with self.assertRaisesRegex(ValueError,'LOOKUP_LIMIT_OUT_OF_RANGE'):
            lookup(Path('/nonexistent'),record='root:1',hash_text=None,limit=0)


if __name__=='__main__':
    unittest.main()
