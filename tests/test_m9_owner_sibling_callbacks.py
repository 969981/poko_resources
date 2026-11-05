"""M9.20 callback table sibling source identity tests."""
import struct
import unittest

from Scripts.resources.m9_owner_sibling_callbacks import (
    sibling_table_entries,decode_sibling,ROOTS,
)


def ldr(base,dst,offset):
    return 0xf9400000 | ((offset//8)<<10) | (base<<5) | dst


class SiblingTableTests(unittest.TestCase):
    def test_source_callback_pointer_slots_and_neighbors(self):
        base=0x32fde38
        raw=bytearray(0x120)
        struct.pack_into("<Q",raw,0,ROOTS["cleanup_table"][1])
        struct.pack_into("<Q",raw,0x100,ROOTS["constructor_table"][1])
        for k in (8,16,24,32,40):
            struct.pack_into("<Q",raw,k,0x1000+k)
            struct.pack_into("<Q",raw,0x100+k,0x2000+k)
        old={"data_pointer_xrefs":[
            {"function":"owner_cleanup_callback","pointer_data_va":base,
             "callback_entry_pc":ROOTS["cleanup_table"][1]},
            {"function":"owner_constructor_callback","pointer_data_va":base+0x100,
             "callback_entry_pc":ROOTS["constructor_table"][1]},
        ]}
        entries=sibling_table_entries({"mem_offset":base,"data":bytes(raw)},old)
        self.assertEqual(len(entries),12)
        self.assertEqual(sum(x["root_entry_verified"] for x in entries),2)
        self.assertFalse(any(x["runtime_owner_identity_verified"] for x in entries))

    def test_contiguous_native_call_shape_does_not_prove_target_class(self):
        base=0x1000
        src=[ldr(19,23,0x28),ldr(23,8,0),ldr(8,8,0x38),0xd63f0100,0xd65f03c0]
        raw=struct.pack("<"+"I"*len(src),*src)
        row={"native_function_pc":base}
        d=decode_sibling(raw,base,row)
        self.assertEqual(len(d["owner_slot38_call_shapes"]),1)
        self.assertFalse(d["owner_slot38_call_shapes"][0]["specific_target_class_proven"])
        self.assertEqual(len(d["owner_member_0x28_reads"]),1)


if __name__=="__main__":unittest.main()
