"""M9.13: typed numeric tuple is NEVER a verified script/text foreign key."""
import csv
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

from Scripts.resources.m9_typed_text_tuple_triage import (
    LANGS, typed_scalar, node_candidates, fill_candidate,
    validate_sample_source, add_m7_context,
)


def field(idx,value,kind="4",src="root:1"):
    raw=struct.pack("<I",value)
    return {
        "m3_record_id":src,"native_node_index":"7",
        "object_id_hex":"0x00000030","object_type_hash_hex":"0x01234567",
        "property_index":str(idx),"property_name_hash_hex":f"0x{idx:08x}",
        "property_type_code":kind,"property_value_count":"1",
        "value_byte_offset":str(idx*4),"value_byte_length":"4",
        "first_u32_values_json":json.dumps([value]),
        "value_sha256":hashlib.sha256(raw).hexdigest(),
    }


class NativeTypedTextTupleTests(unittest.TestCase):
    def test_same_node_pair_is_numeric_only(self):
        group={"record_count":"100","evidence_grade":"STRUCTURE_AND_SCRIPT_WITNESS"}
        rows=[field(2,2323),field(3,17)]
        x=node_candidates(rows,{2323:group})
        self.assertEqual(len(x),1)
        c=fill_candidate(*x[0])
        self.assertEqual((c["m7_group_start"],c["row_candidate_value"]),(2323,17))
        self.assertEqual(c["category"],"UNKNOWN")
        self.assertFalse(c["verified_text_fk"])
        self.assertFalse(c["verified_script_caller"])

    def test_zero_and_distant_rows_not_misrepresented(self):
        group={"record_count":"100","evidence_grade":"STRUCTURE_ONLY"}
        self.assertFalse(node_candidates([field(2,2323),field(3,0)],{2323:group}))
        self.assertFalse(node_candidates([field(2,2323),field(8,12)],{2323:group}))
        self.assertIsNone(typed_scalar(field(3,2,kind="8")))
        self.assertEqual(typed_scalar(field(3,0x12345678)),0x12345678)

    def test_byte_revalidation_rejects_incorrect_source(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            root=p/"UnPack"
            root.mkdir()
            blob=b"\0"*8+struct.pack("<I",2323)+struct.pack("<I",17)
            source=root/"source.bin"
            source.write_bytes(blob)
            meta=[{"m3_record_id":"root:1","output_path":"source.bin",
                   "output_sha256":hashlib.sha256(blob).hexdigest()},
                  {"m3_record_id":"root:2","output_path":"other1.bin","output_sha256":hashlib.sha256(b"").hexdigest()},
                  {"m3_record_id":"root:3","output_path":"other2.bin","output_sha256":hashlib.sha256(b"").hexdigest()}]
            (root/"other1.bin").write_bytes(b"")
            (root/"other2.bin").write_bytes(b"")
            samples=[{"source_m3_id":"root:1","table_field_byte_offset":8,
                      "table_candidate_value":2323,"row_field_byte_offset":12,
                      "row_candidate_value":17,"native_bytes_revalidated":False}]
            validate_sample_source(samples,meta,root)
            self.assertTrue(samples[0]["native_bytes_revalidated"])
            samples[0]["row_candidate_value"]=18
            with self.assertRaises(ValueError):
                validate_sample_source(samples,meta,root)

    def test_language_context_cannot_promote_fk(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"texts.csv"
            cols=["start_entry","text_id","form_index",*LANGS]
            with p.open("w",newline="",encoding="utf-8") as f:
                w=csv.DictWriter(f,fieldnames=cols)
                w.writeheader()
                w.writerow({"start_entry":2323,"text_id":17,"form_index":0,
                            **{x:x+"_name" for x in LANGS}})
            samples=[{"m7_group_start":2323,"row_candidate_value":17,"verified_text_fk":False}]
            self.assertEqual(add_m7_context(samples,[p]),1)
            self.assertIn("zhs_name",samples[0]["m7_texts_form0_json"])
            self.assertFalse(samples[0]["verified_text_fk"])


if __name__=="__main__":
    unittest.main()
