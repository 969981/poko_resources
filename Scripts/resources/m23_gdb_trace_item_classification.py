# Pokopia 2.0.1 guest ARM64 GDB. Read-only, auto-resuming.
# (gdb) source Scripts/resources/m23_gdb_trace_item_classification.py
# (gdb) pokopia_m23_start 0xMAIN_BASE /abs/exefs/main /abs/00983.bin /abs/m23.jsonl 500
# (gdb) continue
# (gdb) pokopia_m23_stop
# No game memory writes. Disk file hash is checked; guest mapped build identity
# must be verified separately, and unknown enum values remain UNKNOWN.
import gdb
import hashlib
import json
import shlex
import struct
from pathlib import Path

MAIN_SHA = "8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
ITEM_SHA = "2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f"
COUNT, HEADER, STRIDE = 4600, 64, 68
SITES = {
    0x2F238: "v1_call",  # x0 V1 object, x8 method
    0x2F258: "v2_tailcall",  # x0 V2 object, x8 vtable, x2 method, x1 ID
    0xE5AA60: "field_26_loop_a",  # x20 ID, x8 record candidate
    0x10289F4: "field_26_loop_b",  # x20 ID, x8 record candidate
    0xABBB64: "field_3a_predicate",  # x19 ID, x8 record candidate
}
SCHEMA = "M23_ITEM_CLASSIFICATION_GDB_V1"

# Operator tags separate experiments; they are NOT native gameplay enum proofs.
ALLOWED_PHASES = {"unlabeled", "inventory", "crafting", "construction", "materials"}


def reg(frame, name):
    return int(frame.read_register(name))


def read_u64(inferior, addr):
    if not addr:
        raise ValueError("NULL_OBJECT")
    return struct.unpack("<Q", bytes(inferior.read_memory(addr, 8)))[0]


def caller_stack(frame, base, limit=8):
    """Read-only guest ARM64 stack sample, bounded to avoid expensive traces."""
    frames = []
    cursor = frame
    for _ in range(limit):
        if cursor is None:
            break
        try:
            pc = int(cursor.pc())
            frames.append({"pc": hex(pc), "candidate_main_rva": hex(pc - base)})
            cursor = cursor.older()
        except Exception:
            break
    return frames


class ProbeBreakpoint(gdb.Breakpoint):
    def __init__(self, owner, rva):
        super().__init__(f"*0x{owner.base+rva:x}", type=gdb.BP_BREAKPOINT, internal=True)
        self.silent = True
        self.owner, self.rva = owner, rva

    def stop(self):
        p = self.owner
        if p.disabled:
            return False
        p.hits += 1
        event = {"schema": SCHEMA, "seq": p.hits, "event": SITES[self.rva],
                 "rva": hex(self.rva), "phase": p.phase,
                 "phase_evidence": "OPERATOR_DECLARED_NOT_NATIVE_UI_IDENTITY"}
        try:
            f = gdb.newest_frame()
            inferior = gdb.selected_inferior()
            t = gdb.selected_thread()
            event["thread_ptid"] = list(t.ptid) if t else []
            event["guest_call_stack"] = caller_stack(f, p.base)
            if self.rva == 0x2F238:
                obj, method = reg(f, "x0"), reg(f, "x8")
                vtable = read_u64(inferior, obj)
                slot_target = read_u64(inferior, vtable + 0x38)
                event.update(item_id_candidate=reg(f, "x19") & 0xffff,
                             v1_object=hex(obj), v1_vtable=hex(vtable),
                             v1_method=hex(method),
                             v1_method_from_vtable_slot=hex(slot_target),
                             v1_vtable_slot_agrees=(method == slot_target),
                             v1_method_candidate_rva=hex(method - p.base),
                             status="DYNAMIC_V1_TARGET__CLASS_UNVERIFIED")
            elif self.rva == 0x2F258:
                obj, vt, method = reg(f, "x0"), reg(f, "x8"), reg(f, "x2")
                actual_vtable = read_u64(inferior, obj)
                slot_target = read_u64(inferior, actual_vtable + 0x30)
                event.update(item_id_candidate=reg(f, "x1") & 0xffff,
                             v2_object=hex(obj), v2_vtable=hex(vt),
                             v2_actual_vtable=hex(actual_vtable),
                             v2_method=hex(method),
                             v2_method_from_vtable_slot=hex(slot_target),
                             v2_vtable_slot_agrees=(vt == actual_vtable and method == slot_target),
                             v2_method_candidate_rva=hex(method - p.base),
                             status="DYNAMIC_V2_TARGET__LOADER_UNVERIFIED")
            else:
                item_id = reg(f, "x19" if self.rva == 0xABBB64 else "x20") & 0xffff
                ptr = reg(f, "x8")
                event.update(item_id=item_id, record_ptr=hex(ptr),
                             fallback_record_candidate=hex(p.base + 0x35B6128))
                if not 0 <= item_id < COUNT:
                    event["status"] = "ID_OUT_OF_RANGE"
                elif not ptr:
                    event["status"] = "NULL_POINTER"
                else:
                    mem = bytes(inferior.read_memory(ptr, STRIDE))
                    original = p.table[HEADER+item_id*STRIDE:HEADER+(item_id+1)*STRIDE]
                    event.update(runtime_record_hex=mem.hex(),
                                 runtime_record_sha256=hashlib.sha256(mem).hexdigest(),
                                 source_record_sha256=hashlib.sha256(original).hexdigest(),
                                 source_raw_kind_u8=original[0x26],
                                 runtime_raw_kind_u8=mem[0x26],
                                 source_name_index=struct.unpack_from("<H", original, 0x22)[0],
                                 runtime_name_index=struct.unpack_from("<H", mem, 0x22)[0],
                                 source_group_39=original[0x39],
                                 runtime_group_39=mem[0x39],
                                 source_group_3a=original[0x3a],
                                 runtime_group_3a=mem[0x3a],
                                 differing_bytes=sum(a != b for a, b in zip(original, mem)),
                                 status=("FULL_68_BYTE_MATCH" if mem == original
                                         else "LAYOUT_DIFF_OR_UNRELATED"))
                    if mem == original:
                        p.exact_ids.add(item_id)
        except Exception as exc:
            p.errors += 1
            event.update(status="READ_ERROR", reason=str(exc)[:400])
            if p.errors <= 5:
                gdb.write("[M23] " + str(exc) + "\n")
        p.out.write(json.dumps(event, ensure_ascii=False) + "\n")
        p.out.flush()
        if p.hits >= p.limit:
            p.disable()
        return False  # Always auto-resume.


class Probe:
    def __init__(self, base, table, out, limit):
        self.base, self.table, self.limit = base, table, limit
        self.disabled = False
        self.hits, self.errors = 0, 0
        self.phase = "unlabeled"
        self.exact_ids = set()
        self.out = out.open("w", encoding="utf-8", buffering=1)
        self.out.write(json.dumps({
            "schema": SCHEMA, "event": "session",
            "main_base": hex(base),
            "source_main_file_sha256": MAIN_SHA,
            "source_item_table_sha256": ITEM_SHA,
            "main_executable_mapped_identity_verified": False,
            "warning": "Disk inputs verified; guest mapped main identity is not independently attested."
        }) + "\n")
        self.breakpoints = [ProbeBreakpoint(self, rva) for rva in SITES]

    def disable(self):
        if self.disabled:
            return
        self.disabled = True
        for bp in self.breakpoints:
            bp.enabled = False
        self.out.close()
        gdb.write(f"[M23] {self.hits} hits, {len(self.exact_ids)} distinct exact IDs, "
                  f"{self.errors} read errors; audit JSONL offline.\n")


class Start(gdb.Command):
    def __init__(self):
        super().__init__("pokopia_m23_start", gdb.COMMAND_USER)
        self.probe = None

    def invoke(self, args, from_tty):
        a = shlex.split(args)
        if len(a) not in (4, 5):
            raise gdb.GdbError("Usage: pokopia_m23_start 0xMAIN_BASE /abs/main /abs/00983.bin /abs/m23.jsonl [max_hits=500]")
        base = int(a[0], 0)
        limit = int(a[4]) if len(a) == 5 else 500
        if base <= 0 or base % 4096 or not 5 <= limit <= 10000:
            raise gdb.GdbError("Invalid guest base or hit limit")
        main, table = Path(a[1]).read_bytes(), Path(a[2]).read_bytes()
        if hashlib.sha256(main).hexdigest() != MAIN_SHA:
            raise gdb.GdbError("Original 2.0.1 ExeFS main hash mismatch")
        if (hashlib.sha256(table).hexdigest() != ITEM_SHA or
            len(table) != HEADER+COUNT*STRIDE or
            struct.unpack_from("<II", table) != (COUNT, 3)):
            raise gdb.GdbError("Original 2.0.1 00983.bin hash/layout mismatch")
        if self.probe:
            self.probe.disable()
        dest = Path(a[3])
        dest.parent.mkdir(parents=True, exist_ok=True)
        self.probe = Probe(base, table, dest, limit)
        gdb.write("[M23] Auto-resuming, read-only V1/V2 and classification field probes armed.\n")


class Stop(gdb.Command):
    def __init__(self, start):
        super().__init__("pokopia_m23_stop", gdb.COMMAND_USER)
        self.start = start

    def invoke(self, args, from_tty):
        if self.start.probe:
            self.start.probe.disable()
        else:
            gdb.write("[M23] No active probe\n")


class Phase(gdb.Command):
    """Set an operator-declared experiment phase; does not alter guest memory."""
    def __init__(self, start):
        super().__init__("pokopia_m23_phase", gdb.COMMAND_USER)
        self.start = start

    def invoke(self, args, from_tty):
        label = args.strip().lower()
        if label not in ALLOWED_PHASES:
            raise gdb.GdbError("Phase must be: " + ", ".join(sorted(ALLOWED_PHASES)))
        p = self.start.probe
        if not p or p.disabled:
            raise gdb.GdbError("No active M23 probe; call pokopia_m23_start first")
        p.phase = label
        p.out.write(json.dumps({"schema": SCHEMA, "event": "phase",
                                "phase": label, "seq": p.hits,
                                "evidence": "OPERATOR_DECLARED_NOT_NATIVE_UI_IDENTITY"}) + "\n")
        p.out.flush()
        gdb.write("[M23] Experiment phase: " + label + "\n")


_start = Start()
_stop = Stop(_start)
_phase = Phase(_start)
