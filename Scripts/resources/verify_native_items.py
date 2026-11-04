#!/usr/bin/env python3
"""Compare nine PokoHex item-name languages with native Pokopia 2.0.1 LINKDATA."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import struct
from pathlib import Path

LANGS = {"en":4454, "jp":4453, "de":4457, "es":4458, "fr":4455,
         "it":4456, "ko":4460, "zhs":4461, "zht":4459}
COUNT, NAME_COUNT, SHIFT = 4600, 3001, 192

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def items(path: Path) -> list[int]:
    blob = path.read_bytes()
    if len(blob) != 64 + COUNT * 68 or struct.unpack_from("<II", blob) != (COUNT, 3):
        raise ValueError(f"Invalid v3 item table: {path}")
    return [struct.unpack_from("<H", blob, 64 + i * 68 + 34)[0]
            for i in range(COUNT)]

def names(path: Path, item_indices: list[int]) -> list[str]:
    blob = path.read_bytes()
    if len(blob) < 64 + NAME_COUNT * 32 or struct.unpack_from("<II", blob) != (NAME_COUNT, 2):
        raise ValueError(f"Invalid v2 name table: {path}")
    output = [""] * COUNT
    output[0] = "(Empty)"
    for i in range(1, COUNT):
        name_id = item_indices[i]
        if name_id == 0 or name_id >= NAME_COUNT:
            continue
        offset_field = 64 + name_id * 32
        start = offset_field + struct.unpack_from("<I", blob, offset_field)[0]
        if not 64 + NAME_COUNT * 32 <= start < len(blob):
            raise ValueError(f"Invalid name offset: {path}, item {i}")
        end = blob.find(b"\x00", start)
        if end == -1:
            raise ValueError(f"Unterminated name: {path}, item {i}")
        output[i] = blob[start:end].decode("utf-8")
    return output

def write_csv(path: Path, header: list[str], data: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(header)
        w.writerows(data)

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--decoded", type=Path,
                   default=Path("UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded"))
    p.add_argument("--text", type=Path,
                   default=Path("UnPack/2.0.1/Resources/Items/Text"))
    p.add_argument("--out", type=Path,
                   default=Path("UnPack/2.0.1/Resources/Items/Native_2.0.1"))
    a = p.parse_args()
    table = a.decoded / "00983.bin"
    ids = items(table)
    result = {}
    diffs = []
    stats = {}
    sources = {"items": {"path": table.as_posix(), "sha256": digest(table), "entry":983},
               "languages": {}}
    for lang, original_id in LANGS.items():
        entry_id = original_id + SHIFT
        native_path = a.decoded / f"{entry_id:05d}.bin"
        actual = names(native_path, ids)
        reference = a.text / f"text_item_{lang}.txt"
        expected = reference.read_text(encoding="utf-8-sig").splitlines()
        if len(expected) != COUNT:
            raise ValueError(f"Wrong PokoHex text size: {reference} ({len(expected)})")
        result[lang] = actual
        for i, (found, wanted) in enumerate(zip(actual, expected)):
            if found != wanted:
                diffs.append([i, lang, found, wanted])
        mismatch = sum(x[1] == lang for x in diffs)
        stats[lang] = {"matched": COUNT - mismatch, "different": mismatch,
                       "native_nonempty": sum(bool(x) for x in actual)}
        sources["languages"][lang] = {
            "path": native_path.as_posix(), "entry": entry_id,
            "sha256": digest(native_path), "pokohex_sha256": digest(reference)}
        text_file = a.out / "Text" / f"text_item_{lang}.txt"
        text_file.parent.mkdir(parents=True, exist_ok=True)
        text_file.write_text("\n".join(actual) + "\n", encoding="utf-8")
    write_csv(a.out / "native_item_catalog.csv",
              ["item_id", "native_name_index", *LANGS],
              [[i, ids[i], *(result[lang][i] for lang in LANGS)] for i in range(COUNT)])
    write_csv(a.out / "differences_vs_pokohex.csv",
              ["item_id", "language", "native_2_0_1", "pokohex"], diffs)
    report = {"status": "MATCH" if not diffs else "MISMATCH",
              "item_slots": COUNT, "differences": len(diffs),
              "invalid_name_indices": sum(i >= NAME_COUNT for i in ids),
              "languages": stats, "source": sources,
              "scope": "Native item names only; no inferred material classes or icon-G1T links"}
    (a.out / "validation.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status":report["status"], "differences":len(diffs),
                      "languages":stats}, ensure_ascii=False))

if __name__ == "__main__":
    main()
