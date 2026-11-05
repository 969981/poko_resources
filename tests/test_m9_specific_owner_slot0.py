"""M9.17: prove branch register and field provenance; keep actual runtime unknown."""
import unittest
from Scripts.resources.m9_specific_owner_slot0 import (
    instructions_match,assert_callee_saved_not_modified,
)

class ConcreteOwnerVirtualCallTests(unittest.TestCase):
    def test_native_call_sequence_exact(self):
        base=0x1000
        code=[
          {"pc":base,"mnemonic":"ldr","operands":"x23, [x19, #0x28]","writes":["x23"]},
          {"pc":base+4,"mnemonic":"ldr","operands":"x8, [x23]","writes":["x8"]},
          {"pc":base+8,"mnemonic":"mov","operands":"x0, x23","writes":["x0"]},
          {"pc":base+12,"mnemonic":"ldr","operands":"x8, [x8]","writes":["x8"]},
          {"pc":base+16,"mnemonic":"blr","operands":"x8","writes":["lr"]},
        ]
        instructions_match(code,{base:("ldr","x23, [x19, #0x28]"),
                                base+16:("blr","x8")})
        assert_callee_saved_not_modified(code,"x23",base,base+16)
        with self.assertRaises(ValueError):
            instructions_match(code,{base+16:("blr","x9")})

    def test_real_x19_or_x23_clobber_rejected(self):
        rows=[
            {"pc":0x1000,"mnemonic":"mov","operands":"x19, x3","writes":["x19"]},
            {"pc":0x1004,"mnemonic":"mov","operands":"x19, x9","writes":["x19"]},
            {"pc":0x1008,"mnemonic":"str","operands":"x23, [x19, #0x28]","writes":[]},
        ]
        with self.assertRaises(ValueError):
            assert_callee_saved_not_modified(rows,"x19",0x1000,0x1008)

    def test_cmp_flags_do_not_erase_callee_saved_register(self):
        rows=[
          {"pc":0x1000,"mnemonic":"ldr","operands":"x23, [x19, #0x28]","writes":["x23"]},
          {"pc":0x1004,"mnemonic":"cmp","operands":"x23, #0","writes":["nzcv","x23"]},
          {"pc":0x1008,"mnemonic":"blr","operands":"x8","writes":["lr"]},
        ]
        assert_callee_saved_not_modified(rows,"x23",0x1000,0x1008)

if __name__=="__main__":unittest.main()
