"""Strict 3,930 source record partitioning, deterministic resume, and no overwrite."""
import unittest
from Scripts.resources.export_native_misc_batches import EXPECTED, key, linked_rows, select_batch


def make(i):
    return {"status":"INDEXED_ORIGINAL_TEXINFO_G1T_PAIR",
            "texinfo_path":f"t/{i:05d}.texinfo","record_index":"0",
            "g1t_path":f"g/{i:05d}.g1t","layer":"0"}


class NativeMiscBatchTests(unittest.TestCase):
    def test_exhaustive_disjoint_partition(self):
        source=[make(i) for i in reversed(range(EXPECTED))]
        chunks=[]
        for batch in range(17):
            group,total=select_batch(source,batch,240)
            self.assertEqual(total,17)
            chunks.extend(group)
            self.assertEqual(len(group),240 if batch<16 else 90)
        self.assertEqual(len(chunks),EXPECTED)
        self.assertEqual(len({key(row) for row in chunks}),EXPECTED)
        self.assertEqual([key(row) for row in chunks],
                         [key(row) for row in linked_rows(source)])
        with self.assertRaisesRegex(ValueError,"out of range"):
            select_batch(source,17,240)

    def test_ambiguous_index_and_duplicate_keys_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"Expected 3930"):
            linked_rows([make(i) for i in range(20)])
        bad=[make(i) for i in range(EXPECTED)]
        bad[-1]=dict(bad[0])
        with self.assertRaisesRegex(ValueError,"collision"):
            linked_rows(bad)
        with self.assertRaises(ValueError):
            select_batch([make(i) for i in range(EXPECTED)],0,481)


if __name__=="__main__":
    unittest.main()
