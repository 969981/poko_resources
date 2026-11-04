"""Evidence-ranked native extension index for Pokopia 2.0.1.

M3 magic fingerprints and RDB type_hash are independent evidence.
External KTID mappings originated in eArmada8/yumia_fdata_tools
(yumia_mod_lib.py); unvalidated Pokopia cross-game use is labelled inferred.
No binary data copied, extension guessed, or decoded assets changed here.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
from collections import Counter
from pathlib import Path

from .core import save_csv, save_json

ROOT = Path("UnPack/2.0.1")
EXTERNAL_REFERENCE = "https://github.com/eArmada8/yumia_fdata_tools/blob/main/yumia_mod_lib.py"

# Lowercase type-hash bytes as printed by the native RDB parser.
KT_TYPES = {
    "0bd05b27": "mit", "0d34474d": "srst", "17614af5": "g1mx",
    "1fdcaa40": "kidstask", "20a6a0bb": "kidsobjdb",
    "27bc54b7": "rigbin", "4d0102ac": "g1em", "4f16d0ef": "kts",
    "5153729b": "mtl", "54738c76": "g1co", "5599aa51": "kscl",
    "563bdef1": "g1m", "56d8deda": "sid", "5c3e543c": "swg",
    "6fa91671": "g1a", "757347e0": "bpo", "786dcd84": "g1n",
    "79c724c2": "g1p", "7bcd279f": "g1s", "9cb3a4b6": "oidex",
    "a027e46b": "mov", "a8d88566": "g1cox", "afbec60c": "g1t",
    "b097d41f": "g1e", "b0a14534": "sgcbin", "b1630f51": "kidsrender",
    "bbd39f2d": "srsa", "bbf9b49d": "grp", "be144b78": "ktid",
    "bf6b52c7": "name", "d7f47fb1": "efpl", "dbcb74a9": "oid",
    "f20de437": "texinfo", "1ab40ae8": "oid", "56efe45c": "grp",
    "e6a3c3bb": "oidex", "8e39aa37": "ktid", "b340861a": "mtl",
    "ed410290": "kts", "82945a44": "lsqtree", "f13845ef": "sclshape",
    "5b2970fc": "ktf2", "32ac9403": "g1fpose", "133d2c3b": "sid",
    "2bcc0c02": "g1frani", "6dbd6ea6": "mit", "1a6300fd": "g1es",
    "ad57ebba": "g1t_new",
}

MAGIC_TYPES = {
    "KIDSOBJDB_SIGNATURE": "kidsobjdb", "G1M_MODEL_CONTAINER": "g1m",
    "G1T_TEXTURE_CONTAINER": "g1t", "G1A_ANIMATION_CONTAINER": "g1a",
    "FLATBUFFERS_SCHEMA_BFBS": "bfbs", "BNTX_TEXTURE_CONTAINER": "bntx",
    "DDS_TEXTURE": "dds", "PNG_IMAGE": "png", "SQLITE_DATABASE": "sqlite",
    "KTX_TEXTURE": "ktx", "RIFF_WAVE_AUDIO": "wav", "ZIP_CONTAINER": "zip",
    "GZIP_COMPRESSED": "gz", "ELF_BINARY": "elf",
}

# Some native format families intentionally use a shared magic.
COMPATIBLE = {frozenset(("g1m", "g1mx")), frozenset(("g1t", "g1t_new"))}


def judge(type_hash: str, signature: str):
    by_hash = KT_TYPES.get((type_hash or "").lower())
    by_magic = MAGIC_TYPES.get(signature)
    if by_hash and by_magic:
        if by_hash == by_magic or frozenset((by_hash, by_magic)) in COMPATIBLE:
            return "." + by_hash, "MAGIC_AND_TKID", by_hash, by_magic
        return "", "HASH_MAGIC_CONFLICT", by_hash, by_magic
    if by_magic:
        return "." + by_magic, "MAGIC_CONFIRMED", "", by_magic
    if by_hash:
        return "." + by_hash, "EXTERNAL_TKID_INFERRED", by_hash, ""
    return "", "UNKNOWN_NATIVE_FORMAT", "", ""


def git(*args) -> str:
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8")


def read_manifest_index() -> dict[str, dict]:
    names = git("ls-tree", "-r", "--name-only", "HEAD", "--",
                str(ROOT / "romfs")).splitlines()
    paths = sorted(x for x in names if x.endswith("/_manifest.csv"))
    if len(paths) < 29:
        raise ValueError("MISSING_SOURCE_MANIFESTS: " + str(len(paths)))
    index = {}
    for path in paths:
        csv_blob = git("show", "HEAD:" + path)
        link = path.endswith("/LD_C0_R.BIN/_manifest.csv")
        for row in csv.DictReader(io.StringIO(csv_blob)):
            if row.get("publish_status") != "PUBLISHED":
                continue
            rid = row["record_id"]
            key = "link:" + str(int(rid)) if link else rid
            if key in index:
                raise ValueError("DUPLICATE_MANIFEST_ID:" + key)
            index[key] = row
    return index


def run(source=ROOT / "_reports/m3_signatures.csv", output=ROOT / "_reports", manifest_index=None):
    output, source = Path(output), Path(source)
    if manifest_index is None:
        manifest_index = read_manifest_index()
    with source.open("r", newline="", encoding="utf-8-sig") as f:
        m3rows = list(csv.DictReader(f))
    rows = []
    status = Counter()
    extensions = Counter()
    seen = set()
    for m in m3rows:
        rid = m.get("record_id", "")
        if rid in seen:
            raise ValueError("DUPLICATE_M3_ID:" + rid)
        seen.add(rid)
        entry = manifest_index.get(rid)
        if m.get("status") == "EMPTY_INDEX":
            if entry:
                raise ValueError("EMPTY_LINK_WITH_PUBLISHED_OUTPUT:" + rid)
            continue
        if not entry:
            raise ValueError("M3_ENTRY_WITHOUT_PUBLISHED_FILE:" + rid)
        ext, grade, mapped, magic = judge(m.get("type_hash", ""), m.get("signature", ""))
        rows.append({
            "record_id": rid, "source_path": entry.get("source_path", ""),
            "name_hash": m.get("name_hash", ""),
            "type_hash": m.get("type_hash", ""),
            "unpacked_size": m.get("unpacked_size", ""),
            "output_path": entry.get("output_path", ""),
            "output_sha256": entry.get("output_sha256", ""),
            "native_extension_hint": ext,
            "evidence_grade": grade,
            "type_hash_hint": mapped, "magic_hint": magic,
            "signature": m.get("signature", ""),
            "head_64_hex": m.get("head_64_hex", ""),
            "m3_probe_status": m.get("status", "")
        })
        status[grade] += 1
        extensions[ext or "<unknown>"] += 1
    if len(rows) != len(manifest_index) or set(manifest_index) != {r["record_id"] for r in rows}:
        raise ValueError(f"M3_TYPE_INDEX_COVERAGE_MISMATCH:{len(rows)}:{len(manifest_index)}")
    save_csv(output / "m3_resource_type_index.csv", sorted(rows, key=lambda row: row["record_id"]))
    save_csv(output / "m3_type_hint_conflicts.csv", [r for r in rows if r["evidence_grade"] == "HASH_MAGIC_CONFLICT"])
    result = {
        "published_records": len(rows), "status_counts": dict(status),
        "extension_hint_counts": dict(extensions),
        "external_type_hash_reference": EXTERNAL_REFERENCE,
        "identity_note": "Type hashes derive from original RDB; external KTID meanings are hypotheses until independently confirmed for Pokopia.",
        "no_asset_copy": True,
        "unknown_or_conflicted_records": status["UNKNOWN_NATIVE_FORMAT"] + status["HASH_MAGIC_CONFLICT"],
        "semantic_conversion_complete": False
    }
    save_json(output / "m3_resource_type_index_summary.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, default=ROOT / "_reports/m3_signatures.csv")
    p.add_argument("--output", type=Path, default=ROOT / "_reports")
    args = p.parse_args()
    run(args.source, args.output)


if __name__ == "__main__":
    main()
