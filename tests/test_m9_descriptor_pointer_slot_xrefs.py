"""M9.9 exact pointer slots and conservative reference classification."""
import unittest
from Scripts.resources.m9_descriptor_pointer_slot_xrefs import pointer_slots


class DescriptorPointerSlotTests(unittest.TestCase):
    def test_three_distinct_data_slots(self):
        rows=[
          ("0x0b6e1578",0x32ecf60,0xca2c40),
          ("0xe21ff09f",0x32fa020,0xd384c0),
          ("0xf92c5190",0x32fdfd8,0xd59420)
        ]
        graph={
          "report":{"entry_functions":[{"hash":h} for h,_,_ in rows]},
          "xrefs":[{"hash":h,"kind":"U64_LITERAL_ADDRESS_CANDIDATE",
                   "section":"data","site_pc":slot,"entry_pc":entry}
                   for h,slot,entry in rows],
        }
        slots=pointer_slots(graph)
        self.assertEqual(len(slots),3)
        self.assertEqual(slots["0x0b6e1578"],(0x32ecf60,0xca2c40))
        graph["xrefs"].append(dict(graph["xrefs"][0]))
        with self.assertRaises(ValueError):
            pointer_slots(graph)

    def test_unverified_rodata_does_not_become_function_pointer_slot(self):
        graph={"report":{"entry_functions":[{"hash":"0x12345678"}]},
               "xrefs":[{"hash":"0x12345678","kind":"U64_LITERAL_ADDRESS_CANDIDATE",
                         "section":"rodata","site_pc":100,"entry_pc":200}]}
        with self.assertRaises(ValueError):
            pointer_slots(graph)


if __name__=="__main__":
    unittest.main()
