"""M9.18: exact non-text function pointer entries, not calls."""
import struct
import unittest
from Scripts.resources.m9_owner_callback_table_xrefs import find_exact_qwords,neighborhood


class ExactCallbackTableTests(unittest.TestCase):
    def test_two_entries_same_static_neighborhood_are_only_byte_evidence(self):
        data=bytearray(0x100)
        struct.pack_into("<Q",data,0x40,0xd58e34)
        struct.pack_into("<Q",data,0x50,0xd590e0)
        part={"name":"data","data":bytes(data),"mem_offset":0x3200000,"file_offset":100}
        out=find_exact_qwords(part,{"owner_cleanup_callback":0xd58e34,
                                    "owner_constructor_callback":0xd590e0})
        self.assertEqual(len(out),2)
        self.assertEqual(sorted(x["pointer_data_va"] for x in out),
                         [0x3200040,0x3200050])
        context=neighborhood(part,0x3200040)
        self.assertTrue(any(x["qword"]==f"0x{0xd590e0:016x}" for x in context))

    def test_unaligned_false_positive_is_not_published(self):
        data=bytearray(100)
        data[3:11]=struct.pack("<Q",0xd58e34)
        p={"name":"rodata","data":bytes(data),"mem_offset":0x20000,"file_offset":0}
        self.assertEqual(find_exact_qwords(p,{"callback":0xd58e34}),[])

if __name__=="__main__":unittest.main()
