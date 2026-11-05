"""Synthetic and source-independent tests for M8 native reference edges."""
from __future__ import annotations
import struct
import unittest

from Scripts.resources.recover_native_text_ids import NativeTable
from Scripts.resources.link_native_text_references import (
    LANGS, ITEM_COUNT, check_fixed_table, link_item_table, link_map_parts,
    link_role_group, u16,
)


def fixed(count, version, stride):
    data=bytearray(64+count*stride)
    struct.pack_into("<II",data,0,count,version)
    return data


def fake_names():
    tables={}
    catalog={}
    for i,lang in enumerate(LANGS):
        rows=[]
        line=[""]*ITEM_COUNT
        line[0]="(Empty)"
        line[1]=f"first_{lang}"
        line[2]=f"second_{lang}"
        line[1357]=f"first_{lang}"
        line[1628]=f"second_{lang}"
        for row in range(3001):
            value=""
            if row==1:value=f"first_{lang}"
            if row==2:value=f"second_{lang}"
            rows.append(((value,"","","","",""), (200+row,)*6, (0,0)))
        tables[lang]=NativeTable(4645+i,f"/raw/{4645+i:05d}.bin",
                                "sha256",3001,32,2,rows)
        catalog[lang]=line
    return tables,catalog


def fake_items():
    blob=fixed(ITEM_COUNT,3,68)
    for item_id,index in [(1,1),(2,2),(1357,1),(1628,2)]:
        struct.pack_into("<H",blob,64+item_id*68+34,index)
    return bytes(blob)


def fake_map():
    tables={40:fixed(4096,0,80),41:fixed(4096,3,16),
            42:fixed(255,0,4),44:fixed(4096,0,100)}
    # 1498 -> variation.part 37 -> part.item 1357
    # 3197 -> variation.part 38 -> part.item 1628
    for variation,part,item,model in [(1498,37,1357,1),(3197,38,1628,2)]:
        v=64+variation*16
        struct.pack_into("<H",tables[41],v,model)
        struct.pack_into("<H",tables[41],v+4,part)
        struct.pack_into("<H",tables[40],64+part*80+6,item)
        tables[44][64+model*100+0x5B]=1
    tables[42][64+4:64+7]=b"\x02\x01\x01"
    return {n:bytes(x) for n,x in tables.items()}


class M8NativeReferenceTests(unittest.TestCase):
    def test_items_native_name_index_and_fields(self):
        tables,catalog=fake_names()
        rows,summary=link_item_table(fake_items(),tables,catalog)
        self.assertEqual(len(rows),4600)
        self.assertEqual(summary["slots_verified_all_9_languages"],4600)
        self.assertEqual(summary["items_with_native_name"],4)
        self.assertEqual(rows[1]["source_field_offset"],64+68+34)
        self.assertEqual(rows[1]["target_text_id"],1)
        self.assertEqual(rows[1]["en"],"first_en")
        self.assertEqual(rows[2]["target_text_id"],2)
        self.assertEqual(rows[0]["target_text_id"],"")
        self.assertEqual(rows[0]["en"],"(Empty)")
    def test_invalid_item_index_fails_not_clamps(self):
        tables,catalog=fake_names()
        blob=bytearray(fake_items())
        struct.pack_into("<H",blob,64+3*68+34,65535)
        with self.assertRaisesRegex(ValueError,"invalid text index"):
            link_item_table(bytes(blob),tables,catalog)
    def test_map_part_chain_preserves_category_uncertainty(self):
        tables,catalog=fake_names()
        items,_=link_item_table(fake_items(),tables,catalog)
        rows,report=link_map_parts(fake_map(),items)
        self.assertEqual(report["linked_map_part_variations"],2)
        self.assertEqual(report["unique_item_ids"],2)
        self.assertEqual([(r["source_record_id"],r["item_id"]) for r in rows],
                         [(1498,1357),(3197,1628)])
        self.assertEqual(rows[0]["part_item_id_offset"],64+37*80+6)
        self.assertEqual(rows[0]["building_classification"],"UNVERIFIED")
        self.assertEqual(rows[1]["item_name_en"],"second_en")
    def test_map_invalid_item_fails(self):
        tables,catalog=fake_names()
        items,_=link_item_table(fake_items(),tables,catalog)
        native=fake_map()
        altered=bytearray(native[40])
        struct.pack_into("<H",altered,64+37*80+6,9999)
        native[40]=bytes(altered)
        with self.assertRaisesRegex(ValueError,"invalid item_id"):
            link_map_parts(native,items)
    def test_role_different_flags_are_preserved(self):
        tables={}
        for i,lang in enumerate(LANGS):
            flags=(0,258 if i%2 else 256,256)
            rows=[((val,),(100+rowid,),(flags[rowid],))
                  for rowid,val in enumerate(("",lang,"button"))]
            tables[lang]=NativeTable(2332+i,"fake","sha",3,8,2,rows)
        rows,summary=link_role_group("Reactions",2332,3,tables)
        self.assertEqual(summary["nonempty_text_ids"],2)
        self.assertEqual(summary["different_raw_flags_across_languages"],1)
        self.assertEqual(rows[1]["jp_raw_flag"],256)
        self.assertEqual(rows[1]["en_raw_flag"],258)
        self.assertEqual(rows[1]["category"],"Reactions")
    def test_map_table_record_strides_must_match(self):
        with self.assertRaisesRegex(ValueError,"expected size"):
            check_fixed_table(bytes(64+100),4096,0,80,"bad")


if __name__=="__main__":
    unittest.main()
