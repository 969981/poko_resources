# Pokopia 2.0.1 GDB (Python 3) — read-only runtime item-983 identity evidence
#
# Source inside GDB:
#   (gdb) source Scripts/resources/m15_gdb_verify_item983_runtime.py
#   (gdb) pokopia_item983_verify 0xMAIN_MODULE_BASE /absolute/path/00983.bin /tmp/pokopia_item983.jsonl
#
# This captures TWO exact already-proven native 4600-ID virtual accessor
# consumer addresses. Neither breakpoints nor this program write to game
# memory. stop() returns False, allowing GDB to resume automatically.
# It does not install ROM/IPS patches or set candidate enum values.
#
# Running this file as ordinary Python requires gdb; it is intentionally NOT
# part of unattended CI, since actual runtime module base is target-specific.

import hashlib
import json
import struct
import shlex
from pathlib import Path

import gdb

EXPECTED_TABLE_SHA="2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f"
COUNT=4600
STRIDE=68
HEADER=64
# Two independent loop consumers from M12; they read [x8 + 0x26].
SITES={0xE5AA60:"loop_A_native_item_type_consumer",
       0x10289F4:"loop_B_native_item_type_consumer"}

def source_item(blob,index):
    p=HEADER+index*STRIDE
    return blob[p:p+STRIDE]

def capture_original(inferior,index,address,table):
    if not 0<=index<COUNT:
        raise ValueError(f"item id outside original 4600-slot range: {index}")
    if not address:
        raise ValueError("null original candidate record pointer")
    original=source_item(table,index)
    memory=bytes(inferior.read_memory(address,STRIDE))
    return {
        "item_id":index,"runtime_ptr":f"0x{address:x}",
        "full_68_byte_original_record_equal":memory==original,
        "raw_name_index_original":struct.unpack_from("<H",original,0x22)[0],
        "raw_name_index_runtime":struct.unpack_from("<H",memory,0x22)[0],
        "raw_kind_original":original[0x26],"raw_kind_runtime":memory[0x26],
        "raw_subgroup_original":original[0x39],"raw_subgroup_runtime":memory[0x39],
        "raw_group_0x3a_original":original[0x3a],"raw_group_0x3a_runtime":memory[0x3a],
        "source_row_sha256":hashlib.sha256(original).hexdigest(),
        "runtime_row_sha256":hashlib.sha256(memory).hexdigest(),
        "original_byte_mismatches":sum(a!=b for a,b in zip(original,memory)),
    }

class _Item983Breakpoint(gdb.Breakpoint):
    def __init__(self,base,rva,owner):
        super().__init__(f"*0x{base+rva:x}",type=gdb.BP_BREAKPOINT,internal=True)
        self.silent=True
        self.owner=owner
        self.rva=rva

    def stop(self):
        state=self.owner
        if state.stopped:
            return False
        try:
            f=gdb.newest_frame()
            item_id=int(f.read_register("x20"))&0xFFFF
            pointer=int(f.read_register("x8"))
            evidence=capture_original(gdb.selected_inferior(),item_id,pointer,state.original)
            evidence.update({
                "exefs_main_sha256":"8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f",
                "source_item_table_sha256":EXPECTED_TABLE_SHA,
                "breakpoint_rva":f"0x{self.rva:x}",
                "breakpoint_role":SITES[self.rva],
                "proof_grade":"ORIGINAL_BYTES_RUNTIME_68B_MATCH" if
                       evidence["full_68_byte_original_record_equal"] else
                       "RUNTIME_POINTER_UNRESOLVED_OR_TRANSFORMED",
            })
            state.hits+=1
            if evidence["full_68_byte_original_record_equal"]:
                state.matched_ids.add(item_id)
            else:
                state.unmatched_ids.add(item_id)
            if state.hits<=state.limit:
                state.output.write(json.dumps(evidence,ensure_ascii=False)+"\n")
                state.output.flush()
            if state.hits>=state.limit:
                state.disable()
        except Exception as ex:
            # Read-only GDB sampling must not change the emulated game state.
            state.errors+=1
            if state.errors<=5:
                gdb.write("[Pokopia M15] read-only item983 probe: "+str(ex)+"\n")
        return False

class _RuntimeProbe:
    def __init__(self,base,original,out,limit):
        self.base=base
        self.original=original
        self.hits=0
        self.errors=0
        self.matched_ids=set()
        self.unmatched_ids=set()
        self.limit=limit
        self.stopped=False
        self.output=open(out,"a",encoding="utf-8",buffering=1)
        self.breakpoints=[_Item983Breakpoint(base,rva,self) for rva in SITES]

    def disable(self):
        if self.stopped:return
        self.stopped=True
        for bp in self.breakpoints:
            bp.enabled=False
        gdb.write(f"[Pokopia M15] disabled after {self.hits} hits, "
                  f"{len(self.matched_ids)} exact record IDs, "
                  f"{len(self.unmatched_ids)} non-matching IDs; read log for evidence.\n")
        self.output.close()

class _Verify983Command(gdb.Command):
    def __init__(self):
        super().__init__("pokopia_item983_verify",gdb.COMMAND_USER)
        self.active=None

    def invoke(self,arg,from_tty):
        a=shlex.split(arg)
        if len(a) not in (3,4):
            raise gdb.GdbError("Usage: pokopia_item983_verify 0xMAIN_BASE /path/to/00983.bin /path/to/evidence.jsonl [max_hits=150]")
        base=int(a[0],0)
        source=Path(a[1])
        output=Path(a[2])
        limit=int(a[3]) if len(a)==4 else 150
        if base<=0 or base%4096 or not 3<=limit<=5000:
            raise gdb.GdbError("Main module base must be aligned; max_hits must be 3..5000")
        blob=source.read_bytes()
        if (hashlib.sha256(blob).hexdigest()!=EXPECTED_TABLE_SHA or
            len(blob)!=HEADER+COUNT*STRIDE or struct.unpack_from("<II",blob,0)!=(COUNT,3)):
            raise gdb.GdbError("Provided 00983.bin is not the original verified Pokopia 2.0.1 entry 983")
        if self.active:self.active.disable()
        output.parent.mkdir(parents=True,exist_ok=True)
        self.active=_RuntimeProbe(base,blob,output,limit)
        gdb.write("[Pokopia M15] read-only auto-resuming breakpoints armed at "+
                  ", ".join(f"main+0x{x:x}" for x in SITES)+"\n")
        gdb.write("Match standard: original 68 bytes from source 00983.bin versus live pointer; "
                  "just matching +0x26 is insufficient. Save JSONL and inspect 3+ different matched IDs.\n")

class _Stop983Command(gdb.Command):
    def __init__(self,creator):
        self.creator=creator
        super().__init__("pokopia_item983_stop",gdb.COMMAND_USER)
    def invoke(self,arg,from_tty):
        probe=self.creator.active
        if not probe:
            gdb.write("[Pokopia M15] no running probe\n")
            return
        probe.disable()
        gdb.write(f"[Pokopia M15] matched IDs: {sorted(probe.matched_ids)[:30]}\n")

_probe983=_Verify983Command()
_Stop983Command(_probe983)
