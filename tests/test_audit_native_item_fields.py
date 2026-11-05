"""Record layout and type-semantics safety of 2.0.1 items entry 983."""
import struct
import unittest

from Scripts.resources.audit_native_item_fields import COUNT, HEADER, STRIDE, parse, summary, STATUS


class ItemFieldAuditTests(unittest.TestCase):
    @staticmethod
    def sample():
        data=bytearray(HEADER+COUNT*STRIDE)
        struct.pack_into("<II",data,0,COUNT,3)
        catalog=[{"item_id":str(i),"native_name_index":"0","en":""} for i in range(COUNT)]
        for i,name,code,index in ((6,"cave mushrooms",15,520),(105,"brick",16,929),
                                  (107,"iron ore",16,155),(314,"camping chair",4,1141)):
            pos=HEADER+i*STRIDE
            data[pos+0x26]=code
            struct.pack_into("<H",data,pos+0x22,index)
            catalog[i]["native_name_index"]=str(index)
            catalog[i]["en"]=name
        return data,catalog

    def test_source_offsets_and_unverified_semantics(self):
        data,catalog=self.sample()
        rows=parse(bytes(data),catalog)
        self.assertEqual(len(rows),COUNT)
        self.assertEqual(rows[107]["record_file_offset"],HEADER+107*STRIDE)
        self.assertEqual(rows[107]["native_name_index"],155)
        self.assertEqual(rows[107]["raw_candidate_0x26_u8"],16)
        self.assertEqual(rows[107]["candidate_material_group_flag"],"PROBE_0X26_EQUALS_0X10")
        self.assertEqual(rows[107]["semantic_classification_status"],STATUS)
        self.assertEqual(len(rows[107]["record_hex_68"]),STRIDE*2)
        self.assertEqual(rows[314]["candidate_material_group_flag"],"")
        report=summary(rows,"00983.bin",bytes(data))
        self.assertEqual(report["native_material_item_ids_verified"],0)
        self.assertEqual(report["candidate_field"]["offset"],38)
        self.assertEqual(report["candidate_field_counts"]["16"]["with_native_names"],2)

    def test_bad_native_name_index_or_corrupt_header_fails_closed(self):
        data,catalog=self.sample()
        bad=[dict(x) for x in catalog]
        bad[105]["native_name_index"]="1000"
        with self.assertRaisesRegex(ValueError,"NameIndex"):
            parse(bytes(data),bad)
        broken=bytearray(data)
        struct.pack_into("<I",broken,4,2)
        with self.assertRaisesRegex(ValueError,"count/version"):
            parse(bytes(broken),catalog)
        with self.assertRaisesRegex(ValueError,"length"):
            parse(bytes(data[:-1]),catalog)


if __name__=="__main__":
    unittest.main()
