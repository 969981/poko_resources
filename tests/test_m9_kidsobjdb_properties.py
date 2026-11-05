"""M9 typed property descriptor and value boundary regression tests."""
import struct
import unittest
from Scripts.resources.m9_kidsobjdb_framing import decode_nodes
from Scripts.resources.m9_kidsobjdb_properties import parse_property_fields


def blob():
    a=bytearray(124)
    a[:8]=b"_DOK0000"
    for at,value in ((8,28),(12,24),(16,2),(24,len(a))):
        struct.pack_into("<I",a,at,value)
    p=28
    a[p:p+8]=b"IDOK0000"
    struct.pack_into("<4I",a,p+8,54,0x12345678,0xABCDEF01,2)
    # Property 0: u32 name hash 0x11, one value, no OID relationship
    struct.pack_into("<3I",a,p+24,5,1,0x11)
    # Property 1: unsigned byte array, 2 bytes
    struct.pack_into("<3I",a,p+36,1,2,0x22)
    struct.pack_into("<I",a,p+48,100)
    a[p+52:p+54]=b"Hi"
    p=84
    a[p:p+8]=b"IDOK0000"
    struct.pack_into("<4I",a,p+8,40,0x99887766,0xABCDEF01,1)
    struct.pack_into("<3I",a,p+24,5,1,0x33)
    struct.pack_into("<I",a,p+36,0x12345678)
    return bytes(a)


class TypedPropertiesTests(unittest.TestCase):
    def test_properties_and_oid_candidates_from_bounded_native_ranges(self):
        data=blob()
        records,_=decode_nodes(data,"root:fixture")
        entries=list(parse_property_fields(data,records,"root:fixture"))
        fields=[x for kind,x in entries if kind=="field"]
        candidates=[x for kind,x in entries if kind=="candidate"]
        summary=[x for kind,x in entries if kind=="stats"][0]
        self.assertEqual(len(fields),3)
        self.assertEqual(fields[0]["property_name_hash_hex"],"0x00000011")
        self.assertEqual(fields[0]["value_byte_offset"],28+48)
        self.assertEqual(fields[0]["first_u32_values_json"],"[100]")
        self.assertEqual(fields[1]["value_byte_length"],2)
        self.assertEqual(fields[1]["preview_hex"],b"Hi".hex())
        self.assertEqual(summary["counts"]["complete_node_properties"],2)
        self.assertEqual(candidates[0]["target_native_node_index"],0)
        self.assertEqual(candidates[0]["value_u32_hex"],"0x12345678")
        self.assertEqual(candidates[0]["is_verified_fk"],0)

    def test_reject_unknown_property_type(self):
        data=bytearray(blob())
        struct.pack_into("<I",data,28+24,99)
        records,_=decode_nodes(data,"fixture")
        with self.assertRaisesRegex(ValueError,"Unsupported property type"):
            list(parse_property_fields(bytes(data),records,"fixture"))

    def test_reject_property_value_overrun(self):
        data=bytearray(blob())
        struct.pack_into("<I",data,28+24+4,300)
        records,_=decode_nodes(data,"fixture")
        with self.assertRaisesRegex(ValueError,"exceeds"):
            list(parse_property_fields(bytes(data),records,"fixture"))

if __name__=="__main__":
    unittest.main()
