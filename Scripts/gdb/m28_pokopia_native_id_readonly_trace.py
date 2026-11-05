#!/usr/bin/env python3
"""Pokopia 2.0.1 M28 read-only GDB sampling helper.

Load only inside an AArch64 target-capable GDB:
    (gdb) source Scripts/gdb/m28_pokopia_native_id_readonly_trace.py
    (gdb) pokopia-m28-start 0xYOUR_ACTUAL_MAIN_LOAD_BASE 150 /tmp/pokopia_m28.jsonl
    (gdb) continue
    (gdb) pokopia-m28-status
    (gdb) pokopia-m28-stop

Offsets are verified against original 2.0.1 NSO SHA256:
8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f

No write memory command, no poked values. Every breakpoint auto-continues.
Address belongs to a loaded NSO0 main segment; Do NOT pass a GitHub
file offset, or a different game/version base. This helper is not an ID
mapping tool: it samples field metadata / caller contexts for analysis.
"""
import datetime
import json
from pathlib import Path
import gdb

OFFSETS = (
    ("kids_property_descriptor", 0xDD1B48),
    ("kids_typehash_getter", 0xDD1C30),
    ("pokemon_dex_id_literal_consumer", 0x1136AA4),
    ("main_pokemon_list_literal_consumer", 0x5FD168),
)
LIMITS = (1, 10000)
_active = None


def reg(name):
    """Read a register. Return None if a target/arch doesn't expose it."""
    try:
        return int(gdb.parse_and_eval("$" + name))
    except (gdb.error, ValueError, RuntimeError):
        return None


def fmt(num):
    return hex(num) if num is not None else None


class Sampler(gdb.Breakpoint):
    def __init__(self, context, label, offset):
        absolute = context.main_base + offset
        super().__init__(f"*0x{absolute:x}", type=gdb.BP_BREAKPOINT,
                         internal=False, temporary=False)
        self.silent = True
        self.label = label
        self.offset = offset
        self.context = context

    def stop(self):
        c = self.context
        if not c.enabled:
            return False
        c.hits += 1
        vals = {r: reg(r) for r in ("pc","sp","x0","x1","x2","x3","x4","x8","x9","x10","x30")}
        # Require exact source PC; if the tool is attached to a different
        # build or the base is wrong, disable rather than assigning meaning.
        if vals["pc"] is not None and vals["pc"] != c.main_base+self.offset:
            c.stop_all()
            gdb.write("M28 WARNING: runtime breakpoint PC does not match expected main+offset.\n")
            return False
        record = {
            "timestamp_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "event": self.label,
            "static_original_nso_offset":hex(self.offset),
            "runtime_pc":fmt(vals["pc"]),
            "actual_main_base_supplied_by_user":hex(c.main_base),
            "caller_return_lr_x30":fmt(vals["x30"]),
            "registers":{k:fmt(v) for k,v in vals.items() if k!="pc"},
            "descriptor_index_w3_if_applicable": (vals["x3"] & 0xffffffff)
                if self.label=="kids_property_descriptor" and vals["x3"] is not None else None,
            "game_species_id_verified":False,
            "kids_source_oid_verified":False,
            "runtime_same_instance_link_verified":False,
        }
        try:
            c.fp.write(json.dumps(record,ensure_ascii=False)+"\n")
            if c.hits % 20 == 0:
                c.fp.flush()
        except (OSError,ValueError) as exc:
            c.stop_all()
            gdb.write(f"M28 WARNING: trace log write failure: {exc}\n")
        if c.hits>=c.hit_limit:
            c.stop_all()
            gdb.write(f"M28 read-only trace reached {c.hit_limit} hits; sampling disabled.\n")
        # Do not keep the target halted or change any of its data.
        return False


class Session:
    def __init__(self,main_base,hit_limit,outpath):
        self.main_base=main_base
        self.hit_limit=hit_limit
        self.outpath=Path(outpath)
        self.outpath.parent.mkdir(parents=True,exist_ok=True)
        self.fp=self.outpath.open("w",encoding="utf-8")
        self.hits=0
        self.enabled=True
        self.breakpoints=[]
        for label,offset in OFFSETS:
            self.breakpoints.append(Sampler(self,label,offset))
        self.fp.write(json.dumps({
            "record_type":"M28_READ_ONLY_SOURCE_CONTEXT_HEADER",
            "original_version":"2.0.1",
            "original_main_nso_sha256":"8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f",
            "main_base":"0x%x"%main_base,
            "max_events":hit_limit,
            "source_offsets":{k:hex(v) for k,v in OFFSETS},
            "runtime_id_bindings_verified":0,
            "warning":"Breakpoint sampling only; every record is unverified until correlated with original object bytes and source OIDs."
        },ensure_ascii=False)+"\n")
        self.fp.flush()

    def stop_all(self):
        if not self.enabled:return
        self.enabled=False
        for b in self.breakpoints:
            try:b.enabled=False
            except gdb.error:pass
        try:self.fp.flush();self.fp.close()
        except OSError:pass


class Start(gdb.Command):
    """pokopia-m28-start MAIN_LOAD_BASE [MAX_HITS] [JSONL_PATH]"""

    def __init__(self):
        super().__init__("pokopia-m28-start",gdb.COMMAND_USER)

    def invoke(self,arg,from_tty):
        global _active
        args=gdb.string_to_argv(arg)
        if not args:
            raise gdb.GdbError(
                "Usage: pokopia-m28-start 0xACTUAL_NS0_MAIN_LOAD_BASE [200] [m28_runtime_trace.jsonl]")
        try:
            base=int(args[0],0)
            count=int(args[1],0) if len(args)>=2 else 200
        except ValueError as exc:
            raise gdb.GdbError("Base and hit limit must be numeric") from exc
        if base<=0 or base&3:
            raise gdb.GdbError("Actual main load base must be positive and 4-byte aligned")
        if not LIMITS[0]<=count<=LIMITS[1]:
            raise gdb.GdbError("Hit limit must be between 1 and 10000")
        if len(args)>3:raise gdb.GdbError("Too many arguments")
        if _active:_active.stop_all()
        outpath=args[2] if len(args)>2 else "m28_runtime_trace.jsonl"
        try:_active=Session(base,count,outpath)
        except Exception as exc:
            raise gdb.GdbError(f"Failed to install read-only M28 breakpoints: {exc}") from exc
        gdb.write(
            f"M28 monitoring {len(OFFSETS)} instruction entry sites, max {count} hits. "
            f"JSONL: {_active.outpath}\n"
            "No game memory writes. Resume with 'continue'; stop with 'pokopia-m28-stop'.\n")


class Stop(gdb.Command):
    def __init__(self):
        super().__init__("pokopia-m28-stop",gdb.COMMAND_USER)
    def invoke(self,arg,from_tty):
        global _active
        if _active:
            n=_active.hits
            out=str(_active.outpath)
            _active.stop_all()
            _active=None
            gdb.write(f"M28 trace disabled: {n} original runtime samples, file {out}\n")
        else:gdb.write("M28 trace is not active.\n")


class Status(gdb.Command):
    def __init__(self):
        super().__init__("pokopia-m28-status",gdb.COMMAND_USER)
    def invoke(self,arg,from_tty):
        c=_active
        if not c:gdb.write("M28 trace inactive.\n")
        else:gdb.write(f"M28 trace: active={c.enabled}, samples={c.hits}/{c.hit_limit}, "
                       f"main_base={hex(c.main_base)}, file={c.outpath}\n")


Start()
Stop()
Status()
gdb.write("M28 native read-only trace commands installed. "
          "Run 'help pokopia-m28-start' for usage.\n")
