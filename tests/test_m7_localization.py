"""Synthetic regression tests for the two observed Pokopia text layouts."""
import struct
import unittest
from Scripts.resources.recover_native_text_ids import NativeTable, parse, groups_of_nine

def make(records, width=8, flags=None):
    count=len(records)
    index=bytearray(64+count*width)
    struct.pack_into("<I",index,0,count)
    struct.pack_into("<I",index,4,2)
    body=bytearray()
    for i,forms in enumerate(records):
        assert len(forms)==(1 if width==8 else 6)
        for j,value in enumerate(forms):
            field=64+i*width+4*j
            target=len(index)+len(body)
            struct.pack_into("<I",index,field,target-field)
            body += value.encode("utf-8")+b"\0"
        if width==8:
            struct.pack_into("<I",index,64+i*8+4,(flags or [1]*count)[i])
    return bytes(index+body)

class NativeTextTests(unittest.TestCase):
    def test_record8_relative_pointers_and_empty_slots(self):
        data=make([[""],["Hello"],["<oneline>中文"]],flags=[0,1,8])
        table,status=parse(data,123,"test/00123.bin")
        self.assertEqual(status,"PARSED")
        self.assertEqual(table.width,8)
        self.assertEqual(table.rows[0][0],("",))
        self.assertEqual(table.rows[1][0],("Hello",))
        self.assertEqual(table.rows[2][0],("<oneline>中文",))
        self.assertEqual(table.rows[2][2],(8,))
        self.assertEqual(table.rows[0][1][0],64+3*8)
        self.assertEqual(table.nonempty,2)
    def test_full_width_unicode_spaces_are_valid_text(self):
        data=make([["なにを　しますか？"],["新刊公告　3月"],["おや　なにか　おさがしですか？"]])
        table,status=parse(data,2323,"native/02323.bin")
        self.assertEqual(status,"PARSED")
        self.assertEqual(table.rows[0][0][0],"なにを　しますか？")
        self.assertEqual(table.rows[1][0][0],"新刊公告　3月")

    def test_record32_six_raw_forms(self):
        data=make([["a","","b","","c",""],["d","e","","f","","g"]],width=32)
        t,status=parse(data,500,"test")
        self.assertEqual(status,"PARSED")
        self.assertEqual(t.forms,6)
        self.assertEqual(t.rows[1][0][3],"f")
        self.assertEqual(t.rows[0][1][0],128)
    def test_reject_bad_pointer(self):
        data=bytearray(make([["ok"],["good"]]))
        struct.pack_into("<I",data,64+8,0xffffffff)
        t,status=parse(bytes(data),50,"test")
        self.assertIsNone(t)
        self.assertEqual(status,"INVALID_RELATIVE_POINTER")
    def test_reject_unrecognized_record_width(self):
        data=bytearray(make([["text"]]))
        struct.pack_into("<I",data,64,12)
        t,status=parse(bytes(data),51,"test")
        self.assertIsNone(t)
        self.assertEqual(status,"OTHER_LAYOUT")
    def test_group_nine_requires_structural_alignment(self):
        texts=["こんにちは","Hello","Bonjour","Ciao","Hallo","Hola","你好","안녕하세요","你好"]
        tables={}
        for i,txt in enumerate(texts):
            data=make([[txt],[""],[txt+"!"]],flags=[1,0,1])
            t,status=parse(data,100+i,"native")
            self.assertEqual(status,"PARSED")
            tables[100+i]=t
        g,amb=groups_of_nine(tables)
        self.assertEqual(len(g),1)
        self.assertEqual(g[0][0],list(range(100,109)))
        self.assertEqual(g[0][1],"STRUCTURE_AND_SCRIPT_WITNESS")
        t,status=parse(make([["different"],["text"],[""]]),109,"native")
        tables[109]=t
        self.assertEqual(len(groups_of_nine(tables)[0]),1)

if __name__=="__main__": unittest.main()
