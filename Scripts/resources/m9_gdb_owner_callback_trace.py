"""Pokopia 2.0.1 M9.23 read-only GDB ARM64 runtime callback evidence capture.

Load from an already connected ARM64 GDB session:
    (gdb) source -s python Scripts/resources/m9_gdb_owner_callback_trace.py
    (gdb) m9trace-install 0x<ACTUAL_MAIN_LOAD_BASE> /tmp/m9_23_trace.jsonl
    (gdb) continue

Only the original ExeFS main with SHA-256
8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f
is supported. Verify that local build independently before attaching.
Never use file offsets as load addresses: module main+0x... = actual base + offset.

All breakpoints are software debugger breakpoints. They read registers and
memory and append JSONL locally. They do NOT write target memory, choose
emulator save methods, patch code, or promote static candidates to evidence.

The important dynamic success condition is an actual HIT at main+0xD59420
with x0.vptr = loaded_main_base + 0x32FDFA0. A hit at main+0xD59250
on x22 alone is *not* proof that the inner x23 callback was invoked.
"""
from __future__ import annotations

import json
import os
import shlex
import time
from pathlib import Path

import gdb

MAIN_SHA="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
INNER_VPTR_OFFSET=0x32FDFA0
DESCRIPTOR_CALLBACK_OFFSET=0xD59420

# ALL locations originate from original static raw NSO validation M9.12–22.
# Do not add raw guessed addresses as breakpoints without an evidence record.
POINTS={
    "owner_constructor_entry":0xD590E0,
    "owner_constructor_x23_vptr_write":0xD591C8,
    "owner_constructor_before_store":0xD59274,
    "owner_cleanup_entry":0xD58E34,
    "owner_slot0_blr":0xD58F10,
    "owner_constructor_sibling_entry":0xD592B4,
    "source_x22_slot38_blr":0xD59250,
    "actual_inner_descriptor_callback_entry":DESCRIPTOR_CALLBACK_OFFSET,
}
MAX_PER_POINT=24


def as_register(name):
    try:
        return int(gdb.parse_and_eval("$"+name)) & ((1<<64)-1)
    except (gdb.error,ValueError):
        return None


def ptr(inferior,address):
    if address is None or address<0x10000 or address>=1<<63:
        return None
    try:
        return int.from_bytes(inferior.read_memory(address,8).tobytes(),"little")
    except (gdb.error,ValueError,MemoryError):
        return None


def h(value):
    return hex(value) if isinstance(value,int) else None


class TracePoint(gdb.Breakpoint):
    def __init__(self,owner,name,offset):
        super().__init__("*"+hex(owner.main_base+offset),
                         type=gdb.BP_BREAKPOINT,internal=False)
        self.silent=True
        self.owner=owner
        self.name=name
        self.offset=offset
        self.hits=0

    def stop(self):
        self.hits+=1
        if self.hits>self.owner.max_per_point:
            self.enabled=False
            return False
        ctx={name:as_register(name) for name in
             ("pc","lr","x0","x1","x2","x3","x8","x19","x22","x23")}
        try:
            inferior=gdb.selected_inferior()
            x0vp=ptr(inferior,ctx["x0"])
            x22vp=ptr(inferior,ctx["x22"])
            x23vp=ptr(inferior,ctx["x23"])
            owner_x3_p28=ptr(inferior,ctx["x3"]+0x28 if ctx["x3"] is not None else None)
            owner_x19_p28=ptr(inferior,ctx["x19"]+0x28 if ctx["x19"] is not None else None)
            desc=ptr(inferior,x0vp+0x38 if x0vp else None)
            caller_pc=ctx["lr"]-4 if ctx["lr"] is not None and ctx["lr"]>=4 else None
            try:
                caller_word=int.from_bytes(inferior.read_memory(caller_pc,4).tobytes(),"little") if caller_pc else None
            except (gdb.error,ValueError,MemoryError):
                caller_word=None
            caller_is_blr=(caller_word & 0xfffffc1f)==0xd63f0000 if caller_word is not None else None
            row={
                "kind":"m9_23_native_runtime_breakpoint_hit",
                "unix_timestamp":time.time(),
                "target":self.name,
                "main_offset":hex(self.offset),
                "breakpoint_pc":h(ctx["pc"]),
                "hit_count_for_target":self.hits,
                "registers":{name:h(value) for name,value in ctx.items()},
                "owner_x3_plus_0x28":h(owner_x3_p28),
                "owner_x19_plus_0x28":h(owner_x19_p28),
                "object_x0_vptr":h(x0vp),
                "object_x22_vptr":h(x22vp),
                "object_x23_vptr":h(x23vp),
                "object_x0_vptr_plus_0x38_callback":h(desc),
                "known_inner_vptr_absolute":hex(self.owner.main_base+INNER_VPTR_OFFSET),
                "x0_has_known_inner_vptr":x0vp==(self.owner.main_base+INNER_VPTR_OFFSET) if x0vp is not None else None,
                "descriptor_callback_pc_expected":hex(self.owner.main_base+DESCRIPTOR_CALLBACK_OFFSET),
                "candidate_caller_pc_from_lr_minus4":h(caller_pc),
                "caller_instruction_word":h(caller_word),
                "caller_instruction_is_arm64_blr":caller_is_blr,
                "actual_descriptor_callback_breakpoint_hit":self.name=="actual_inner_descriptor_callback_entry",
                "same_runtime_owner_instance_proven":False,
                "M7_script_text_fk_verified":False,
            }
            if self.name=="owner_constructor_before_store":
                owner_id=ctx["x19"]
                child=ctx["x23"]
                if owner_id is not None and child is not None:
                    self.owner.owners[owner_id]=child
                    row["candidate_owner_to_inner_object_from_constructor"]={
                        "owner":h(owner_id),"inner":h(child)}
            if ctx["x3"] in self.owner.owners:
                row["previously_observed_inner_for_this_x3"]=h(self.owner.owners[ctx["x3"]])
                row["same_x3_equals_recorded_constructor_owner"]=True
            else:
                row["previously_observed_inner_for_this_x3"]=None
                row["same_x3_equals_recorded_constructor_owner"]=False
            with self.owner.destination.open("a",encoding="utf-8") as file:
                file.write(json.dumps(row,ensure_ascii=False)+"\n")
        except Exception as ex:
            gdb.write("[M9.23] trace write error: "+str(ex)+"\n",gdb.STDERR)
        if self.hits>=self.owner.max_per_point:
            self.enabled=False
        return False


class InstallM9Trace(gdb.Command):
    def __init__(self):
        super().__init__("m9trace-install",gdb.COMMAND_USER)
        self.installed=[]

    def invoke(self,args,from_tty):
        words=shlex.split(args)
        if len(words) not in (2,3):
            raise gdb.GdbError(
                "Usage: m9trace-install 0xACTUAL_MAIN_LOAD_BASE /path/trace.jsonl [max_per_point]")
        if self.installed:
            raise gdb.GdbError("M9.23 breakpoints are already installed in this GDB process")
        base=int(words[0],0)
        if base<0x10000 or base%0x1000:
            raise gdb.GdbError("Supply a nonzero page-aligned ACTUAL main load base")
        maxhits=int(words[2]) if len(words)==3 else MAX_PER_POINT
        if maxhits<1 or maxhits>300:
            raise gdb.GdbError("max_per_point must be 1..300")
        self.main_base=base
        self.max_per_point=maxhits
        self.owners={}
        self.destination=Path(words[1]).expanduser().resolve()
        self.destination.parent.mkdir(parents=True,exist_ok=True)
        with self.destination.open("a",encoding="utf-8") as f:
            f.write(json.dumps({
                "kind":"m9_23_capture_session",
                "timestamp":time.time(),
                "main_base":hex(base),
                "expected_unrelocated_original_main_sha256":MAIN_SHA,
                "source_build_bytes_validated_by_user_before_attach":False,
                "record_mode":"READ_ONLY",
                "owner_lifetime_identity_may_be_reused":True,
                "points":{k:hex(v) for k,v in POINTS.items()},
            },ensure_ascii=False)+"\n")
        for name,offset in POINTS.items():
            self.installed.append(TracePoint(self,name,offset))
        gdb.write(f"[M9.23] {len(self.installed)} read-only probes set; "
                  f"file={self.destination}, max={maxhits} hits/site\n")


InstallM9Trace()
