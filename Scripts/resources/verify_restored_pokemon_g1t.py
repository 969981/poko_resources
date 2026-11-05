#!/usr/bin/env python3
"""Audit all 29 Pokémon G1T aliases restored from original decoded FDATA blobs.

The alias path points at exactly the same Git blob as the source decoded file,
so no image data was rewritten. Do not confuse recognized G1T magic with
successful BC pixel/UV decoding, which is checked in a separate stage.
"""
from __future__ import annotations
import csv
import json
from collections import Counter
from pathlib import Path

from Scripts.resources.g1t_to_png import parse_g1t

ROOT = Path("UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native")
INDEX = Path("UnPack/2.0.1/Resources/Pokemon/pokemon_texture_index.csv")
REPORT = Path("UnPack/2.0.1/Resources/Pokemon/restore_29_g1t_report.json")

def main() -> None:
    with INDEX.open(encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["status"] == "MISSING_PHYSICAL_G1T"]
    if len(rows) != 29:
        raise ValueError(f"expected 29 previously missing references, got {len(rows)}")
    results=[]
    for row in rows:
        hashes = row["g1t_index_hash_candidates"].split("|")
        if len(hashes) != 1:
            raise ValueError(f"ambiguous index mapping: {row['texture_name']}")
        hash_ = hashes[0]
        matches = sorted(ROOT.glob(f"root_*_{hash_}.g1t"))
        result = {
            "texture_name": row["texture_name"],
            "texinfo_hash": row["texinfo_hash"],
            "g1t_hash": hash_,
            "restored_file": str(matches[0]) if matches else None,
            "file_size": matches[0].stat().st_size if matches else 0,
            "status": None, "error": None, "platform": None,
            "texture_entries": [], "expected_record_count": int(row["texinfo_record_count"])
        }
        if len(matches) != 1:
            result["status"]="NO_UNIQUE_ALIAS"
        else:
            try:
                raw=matches[0].read_bytes()
                if raw[:8]!=b"GT1G0600":
                    raise ValueError(f"wrong G1T magic: {raw[:8]!r}")
                platform, textures = parse_g1t(raw)
                result["platform"]=hex(platform)
                result["texture_entries"]=[
                    {"index":i, "format":hex(x["format"]),
                     "width":x["width"],"height":x["height"],
                     "payload_length":len(x["payload"])}
                    for i,x in enumerate(textures)]
                result["status"]="G1T_HEADER_AND_OFFSETS_PARSED"
            except (ValueError, OSError) as exc:
                result["status"]="UNPARSED_G1T_ALIAS"
                result["error"]=str(exc)
        results.append(result)
    summary={
        "original_missing_records":len(rows),
        "matched_blob_aliases":sum(x["restored_file"] is not None for x in results),
        "parseable_g1t_records":sum(x["status"]=="G1T_HEADER_AND_OFFSETS_PARSED" for x in results),
        "statuses":dict(Counter(x["status"] for x in results)),
        "results":results,
        "warning":"All aliases refer to original decoded FDATA blobs. Header success does NOT prove swizzle, UV crops or image identity. Other original G1T entries are audited separately."
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in summary.items() if k!="results"},ensure_ascii=False))
    for r in results:
        if r["status"]!="G1T_HEADER_AND_OFFSETS_PARSED":
            print(f"NOT PARSED: {r['texture_name']} hash={r['g1t_hash']} {r['error']}")
    if summary["matched_blob_aliases"] != 29:
        raise SystemExit("Not all decoded FDATA image aliases are present")
    if summary["parseable_g1t_records"] < 28:
        raise SystemExit("Fewer than 28 standard G1Ts parsed")


if __name__=="__main__":
    main()
