"""Verify version-pinned group extraction does not pretend raw type is official enum."""
import hashlib,struct,unittest
from unittest.mock import patch
from Scripts.resources import export_native_material_candidate_crosswalk as m

class NativeMaterialCrosswalkTest(unittest.TestCase):
    def fixture(self):
        data=bytearray(64+4600*68)
        struct.pack_into("<II",data,0,4600,3)
        catalog=[]
        for i in range(4600):
            catalog.append({"item_id":str(i),"native_name_index":"0",
                            "jp":f"j{i}","en":f"e{i}","de":f"d{i}","es":f"s{i}","fr":f"f{i}","it":f"i{i}","ko":f"k{i}","zhs":f"z{i}","zht":f"t{i}"})
        for i in m.SECONDARY_PUBLIC_IDS:
            data[64+i*68+0x26]=(15 if i==532 else 10 if i==1291 else 16)
        return bytes(data),catalog

    def test_forty_eight_raw_native_ids_and_two_cross_group_public_examples(self):
        blob,catalog=self.fixture()
        with patch.object(m,"ORIGINAL_SHA",hashlib.sha256(blob).hexdigest()):
            rows,report=m.build(blob,catalog)
        self.assertEqual(len(rows),50)
        self.assertEqual(report["native_raw_kind_16_item_ids"],48)
        self.assertEqual(report["reference_intersection_with_native_kind_16"],48)
        self.assertEqual({r["item_id"] for r in report["reference_outside_native_kind_16"]},{532,1291})
        self.assertFalse(report["official_native_enum_name_verified"])
        self.assertTrue(all(not r["native_enum_name_verified"] for r in rows))
        self.assertTrue(all(not r["native_983_consumer_link_verified"] for r in rows))

    def test_rejects_mismatched_byte_source(self):
        blob,catalog=self.fixture()
        with self.assertRaisesRegex(ValueError,"source SHA"):
            m.build(blob,catalog)
        with patch.object(m,"ORIGINAL_SHA",hashlib.sha256(blob[:-1]).hexdigest()):
            with self.assertRaisesRegex(ValueError,"68-byte"):
                m.build(blob[:-1],catalog)

if __name__=="__main__":unittest.main()
