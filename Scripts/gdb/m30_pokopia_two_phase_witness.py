#!/usr/bin/env python3
"""M30 read-only GDB provenance collector for Pokopia 2.0.1.

Use in a GDB already attached to the correct AArch64 game process:
  source Scripts/gdb/m30_pokopia_two_phase_witness.py
  pokopia-m30-start 0xACTUAL_MAIN_BASE identity 100 m30_identity.jsonl
  continue
  pokopia-m30-stop
  pokopia-m30-start 0xACTUAL_MAIN_BASE kids 100 m30_kids.jsonl
  continue
  pokopia-m30-stop

Mode identity: main+0x1136A60 reads x22+8 (original u16 record),
               main+0x5FD168 references m_mainPokemonList.
Mode kids:     main+0xDD1B48 is KIDS type property enumeration entry,
               main+0xDD1B74 loads KIDS class descriptor hash.

Hardware breakpoints are requested; target support is NOT tested by CI.
Breakpoints, GDB and remote stubs can still cause timing/stop side effects.
No writes to game data. Read-only bounded samples of exactly known source
instructions; *not* a real species ID -> icon mapping.
"""
import datetime
import json
import struct
from pathlib import Path
import gdb

SHA="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
OFFSETS={
  "identity":{
    "three_u16_record_before_read":0x1136A60,
    "pokemon_list_string_reference":0x5FD168,
  },
  "kids":{
    "kids_property_descriptor_entry":0xDD1B48,
    "kids_property_descriptor_hash_read":0xDD1B74,
  }
}
REGISTERS=("pc","sp","x0","x1","x2","x3","x8","x9","x19","x20",
           "x21","x22","x23","x24","x25","x26","x30")
MAX_HITS=500
# Exact original NSO0 source words from pinned M25/M26 AArch64 evidence.
ORIGINAL_OPCODE={
    0x1136A60:0x794012C8,
    0x5FD168:0x912CD463,
    0xDD1B48:0x2A1F03E8,
    0xDD1B74:0xB863D92C,
}
_session=None

def h(n):
    return hex(n) if n is not None else None

def reg(name):
    try:return int(gdb.parse_and_eval("$"+name))
    except (gdb.error, ValueError, RuntimeError):return None

def thread_tag():
    try:
        t=gdb.selected_thread()
        if t is None:return None
        return [int(x) for x in t.ptid]
    except (gdb.error,ValueError,TypeError):return None

def mem(address,n):
    if address is None or not 0x10000<=address<0xFFFFFFFFFFFFFFFF-n:
        return {"read_ok":False,"reason":"NULL_OR_UNSAFE_ADDRESS"}
    try:
        b=bytes(gdb.selected_inferior().read_memory(address,n))
        return {"read_ok":True,"address":h(address),
                "size":n,"raw_hex":b.hex(),
                "decoded_u32_le":int.from_bytes(b,"little") if n==4 else None}
    except (gdb.error,MemoryError,RuntimeError) as ex:
        return {"read_ok":False,"address":h(address),"size":n,
                "reason":str(ex)[:120]}

class Point(gdb.Breakpoint):
    def __init__(self,ctx,label,offset):
        super().__init__(f"*0x{ctx.base+offset:x}",
                         type=gdb.BP_HARDWARE_BREAKPOINT,
                         internal=False,temporary=False)
        self.silent=True
        self.ctx=ctx
        self.label=label
        self.offset=offset

    def stop(self):
        c=self.ctx
        if not c.enabled:return False
        pc=reg("pc")
        if pc != c.base+self.offset:
            c.write({"kind":"error","reason":"BREAKPOINT_PC_MISMATCH",
                     "actual_pc":h(pc),"expected_pc":h(c.base+self.offset)})
            c.close()
            return False
        values={n:reg(n) for n in REGISTERS}
        sample={"kind":"event","event":self.label,
                "phase":c.phase,"ordinal":c.samples+1,
                "timestamp_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "thread_ptid":thread_tag(),
                "original_main_offset":h(self.offset),
                "absolute_pc":h(pc),
                "return_lr_x30":h(values["x30"]),
                "registers":{n:h(v) for n,v in values.items() if n!="pc"},
                "current_instruction_original_code_read":mem(pc,4),
                "expected_original_instruction_word":h(ORIGINAL_OPCODE[self.offset]),
                "bounded_original_instruction_reads":{},
                "user_scenario":c.scenario,
                "same_game_instance_proven":False,
                "native_species_ID_proven":False,
                "native_KIDS_source_OID_proven":False}
        if self.label=="three_u16_record_before_read":
            # Original main+1136A60: ldrh w8,[x22,#8].
            # The preceding code also reads x22+4 and x22+6.
            address=values["x22"]
            sample["bounded_original_instruction_reads"]["x22_plus4_to_plus9"]=(
                mem(address+4,6) if address is not None else {"read_ok":False,"reason":"MISSING_X22"})
        elif self.label=="pokemon_list_string_reference":
            # Original m_mainPokemonList caller, with x19+0x26 flag.
            address=values["x19"]
            sample["bounded_original_instruction_reads"]["x19_plus26_byte"]=(
                mem(address+0x26,1) if address is not None else {"read_ok":False,"reason":"MISSING_X19"})
        elif self.label=="kids_property_descriptor_hash_read":
            # Original main+DD1B74: ldr w12,[x9,w3,sxtw #2].
            # The value is a PROPERTY DESCRIPTOR HASH, not a source OID!
            idx=(values["x3"]&0xFFFFFFFF) if values["x3"] is not None else None
            sample["descriptor_index_w3"]=idx
            ptr=values["x9"]
            if idx is not None and idx<=2 and ptr is not None:
                sample["bounded_original_instruction_reads"]["descriptor_hash_at_x9_plus_index"]=mem(ptr+4*idx,4)
            else:
                sample["bounded_original_instruction_reads"]["descriptor_hash_at_x9_plus_index"]=(
                    {"read_ok":False,"reason":"INDEX_OUTSIDE_OR_MISSING_DESCRIPTOR"})
        elif self.label=="kids_property_descriptor_entry":
            sample["descriptor_index_w3"]=(values["x3"]&0xFFFFFFFF) if values["x3"] is not None else None

        c.samples+=1
        c.write(sample)
        if c.samples>=c.limit:
            c.close()
            gdb.write(f"M30 sampling limit reached ({c.limit}) in phase {c.phase}.\n")
        return False

class Session:
    def __init__(self,base,phase,limit,file):
        self.base=base
        self.phase=phase
        self.limit=limit
        self.path=Path(file)
        self.scenario="UNLABELED"
        self.samples=0
        self.enabled=True
        self.points=[]
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.fp=self.path.open("w",encoding="utf-8")
        try:
            self.write({
                "kind":"header","schema":"M30_POKOPIA_2_0_1_NATIVE_WITNESS_V1",
                "source_game_version":"2.0.1",
                "source_main_sha256_claim":SHA,
                "actual_main_base_supplied_by_operator":h(base),
                "requested_hardware_breakpoints":True,
                "runtime_build_verified_by_target_bytes":False,
                "phase":phase,"limit":limit,
                "code_offsets":{k:h(v) for k,v in OFFSETS[phase].items()},
                "identity_binding_proven":False,
                "warning":"No native ID semantics inferred. A claimed source SHA is not a verified target SHA.",
            })
            for label,offset in OFFSETS[phase].items():
                self.points.append(Point(self,label,offset))
        except Exception:
            self.close()
            raise

    def write(self,value):
        if not self.fp.closed:
            self.fp.write(json.dumps(value,ensure_ascii=False)+"\n")
            self.fp.flush()

    def close(self):
        if not self.enabled:return
        self.enabled=False
        for bp in self.points:
            try:bp.enabled=False
            except (gdb.error,RuntimeError):pass
        if not self.fp.closed:self.fp.close()

def check_started():
    if _session is None or not _session.enabled:
        raise gdb.GdbError("No active M30 trace. Run pokopia-m30-start first.")
    return _session

class Start(gdb.Command):
    """pokopia-m30-start MAIN_BASE identity|kids [MAX_HITS] [OUTPUT.jsonl]"""
    def __init__(self):super().__init__("pokopia-m30-start",gdb.COMMAND_USER)
    def invoke(self,arg,from_tty):
        global _session
        a=gdb.string_to_argv(arg)
        if len(a)<2 or len(a)>4:
            raise gdb.GdbError("Usage: pokopia-m30-start 0xACTUAL_MAIN_BASE identity|kids [100] [witness.jsonl]")
        try:
            base=int(a[0],0)
            n=int(a[2],0) if len(a)>=3 else 100
        except ValueError as ex:raise gdb.GdbError("Invalid numeric main base or event limit") from ex
        phase=a[1]
        if phase not in OFFSETS:raise gdb.GdbError("Phase must be identity or kids")
        if base<0x10000 or base&3:raise gdb.GdbError("Main load base must be valid and aligned")
        if n<1 or n>MAX_HITS:raise gdb.GdbError("Max events must be 1..500")
        if _session:_session.close()
        output=a[3] if len(a)==4 else f"m30_{phase}_witness.jsonl"
        _session=Session(base,phase,n,output)
        gdb.write(f"M30 {phase}: two hardware breakpoints requested; log={output}.\n"
                  "GDB runtime support is NOT guaranteed. Press continue to sample.\n")

class Mark(gdb.Command):
    """pokopia-m30-mark SCENARIO_LABEL (operator action annotation only)"""
    def __init__(self):super().__init__("pokopia-m30-mark",gdb.COMMAND_USER)
    def invoke(self,arg,from_tty):
        c=check_started()
        label=arg.strip()
        if not label or len(label)>72 or not all(x.isascii() and (x.isalnum() or x in "_-.") for x in label):
            raise gdb.GdbError("Scenario label: 1-72 chars of ASCII letters/numbers/_-., no spaces")
        c.scenario=label
        c.write({"kind":"operator_marker","label":label,
                 "timestamp_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 "same_game_instance_proven":False})
        gdb.write(f"M30 scenario marker: {label}\n")

class RawPair(gdb.Command):
    """pokopia-m30-pair SLOT KEY_ADDR VALUE_ADDR (operator-supplied, unproven address provenance)"""
    def __init__(self):super().__init__("pokopia-m30-pair",gdb.COMMAND_USER)
    def invoke(self,arg,from_tty):
        c=check_started()
        args=gdb.string_to_argv(arg)
        if len(args)!=3:raise gdb.GdbError("Usage: pokopia-m30-pair SLOT KEY_ADDR VALUE_ADDR")
        try:slot,kaddr,vaddr=map(lambda x:int(x,0),args)
        except ValueError as ex:raise gdb.GdbError("Invalid slot or address") from ex
        if not 0<=slot<3543 or kaddr&3 or vaddr&3:
            raise gdb.GdbError("Slot range 0..3542; u32 addresses must be aligned")
        c.write({"kind":"operator_raw_pair_candidate",
                 "scenario":c.scenario,"original_kids_array_slot_claim":slot,
                 "operator_supplied_address_provenance":False,
                 "captured_pc":h(reg("pc")),"thread_ptid":thread_tag(),
                 "key_u32_raw":mem(kaddr,4),"source_oid_u32_raw":mem(vaddr,4),
                 "same_instance_link_proven":False,
                 "game_species_ID_verified":False})
        gdb.write("M30 raw pair candidate recorded. It does not prove a game-ID lookup.\n")

class Stop(gdb.Command):
    def __init__(self):super().__init__("pokopia-m30-stop",gdb.COMMAND_USER)
    def invoke(self,arg,from_tty):
        global _session
        if _session:
            gdb.write(f"M30 closed: {_session.samples} events; file {_session.path}\n")
            _session.close()
            _session=None
        else:gdb.write("M30 not running.\n")

Start()
Mark()
RawPair()
Stop()
gdb.write("M30 original identity/KIDS two-phase witness tool loaded.\n")
