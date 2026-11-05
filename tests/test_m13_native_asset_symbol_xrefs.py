"""Original rodata address and AArch64 xref tests; no fabricated ID binding."""
import struct
import unittest
from Scripts.resources.m13_native_asset_symbol_xrefs import (
    classify,find_strings,scan_xrefs
)

class NativeSymbolTests(unittest.TestCase):
    def test_source_qualified_symbol_names(self):
        raw=b"\x00pokemon_dex_id\x00m_craftRecipeId\x00MaterialGroup\x00"
        entries=find_strings({"mem_offset":0x3000,"data":raw})
        self.assertEqual([r["text"] for r in entries],["pokemon_dex_id","m_craftRecipeId"])
        self.assertEqual(entries[0]["rva"],0x3001)
        self.assertEqual(entries[0]["category"],"POKEMON_ID")
        self.assertEqual(entries[1]["category"],"CRAFTING")
        self.assertEqual(classify("icon_poke_uni_0025"),"POKEMON_ID")

    def test_arm64_adrp_add_identifies_native_literal_address(self):
        # From .text RVA 0x1000 an ADRP jumps to page 0x3000
        adrp=0x90000001|(2<<29)  # immlo=2 pages, not immhi=2 (8 pages)
        add=0x91000000|(0x123<<10)|(1<<5)|1
        blob=struct.pack("<3I",adrp,add,0xd503201f)
        refs=scan_xrefs(blob,0x1000,[{"rva":0x3123,"text":"pokemon_dex_id",
                                      "category":"POKEMON_ID"}])
        self.assertEqual(len(refs),1)
        self.assertEqual(refs[0]["pc"],0x1004)
        self.assertEqual(refs[0]["literal_rva"],0x3123)
        self.assertEqual(refs[0]["uses"],"ADRP_ADD_CANDIDATE")
        self.assertEqual(refs[0]["base_reg"],1)
        self.assertFalse(scan_xrefs(blob,0x1000,[{"rva":0x3999,
                                                   "text":"other","category":"OTHER_TEXT"}]))

if __name__=="__main__":
    unittest.main()
