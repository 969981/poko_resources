#!/usr/bin/env python3
"""Rank G1T atlas candidate PNG layouts against pinned PokoHex reference icons.

This is a heuristic only. Small distance does not prove native pixel identity.
Reads images produced by crop_native_item_atlas.py and NEVER replaces final icons.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import median
from PIL import Image, ImageChops, ImageStat


def distance(candidate: Path, reference: Path) -> float:
    with Image.open(candidate) as a_file, Image.open(reference) as b_file:
        a, b = a_file.convert("RGBA"), b_file.convert("RGBA")
    a = a.resize(b.size, Image.Resampling.LANCZOS)
    alpha_diff = ImageStat.Stat(ImageChops.difference(
        a.getchannel("A"), b.getchannel("A"))).mean[0] / 255
    scores = [alpha_diff]
    for rgb in [(0, 0, 0), (255, 255, 255)]:
        bg_a = Image.new("RGB", b.size, rgb)
        bg_b = Image.new("RGB", b.size, rgb)
        bg_a.paste(a, mask=a.getchannel("A"))
        bg_b.paste(b, mask=b.getchannel("A"))
        scores.append(sum(ImageStat.Stat(ImageChops.difference(bg_a, bg_b)).mean)
                      / (3 * 255))
    return round(sum(scores) / len(scores), 8)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidates", type=Path, default=Path("atlas-preview"))
    p.add_argument("--references", type=Path, default=Path("UnPack/2.0.1/Resources/Items/Icons"))
    p.add_argument("--out", type=Path, default=Path("atlas-preview"))
    args = p.parse_args()
    rows = []
    for manifest in sorted(args.candidates.rglob("atlas_candidate_manifest.csv")):
        orientation = manifest.parent.name
        with manifest.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("status") != "CROPPED_UNVERIFIED":
                    continue
                item = int(row["item_id"])
                reference = args.references / f"item_{item:04d}.png"
                candidate = Path(row["png_path"])
                if not (candidate.exists() and reference.exists()):
                    continue
                score = distance(candidate, reference)
                rows.append({"item_id": item, "orientation": orientation,
                             "layer": row["layer"], "layout": row["layout"],
                             "score": score, "candidate": candidate.as_posix(),
                             "reference": reference.as_posix()})
    args.out.mkdir(parents=True, exist_ok=True)
    columns = ["item_id", "orientation", "layer", "layout", "score", "candidate", "reference"]
    with (args.out / "layout_score_by_item.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r:(r["item_id"],r["orientation"],r["layout"])))
    groups=defaultdict(list)
    for row in rows:
        groups[(row["orientation"], row["layout"])].append(row["score"])
    ranked = [{"orientation": orientation, "layout": layout, "sample_count": len(scores),
               "median_distance": round(median(scores), 8),
               "mean_distance": round(sum(scores) / len(scores), 8)}
              for (orientation,layout),scores in groups.items()]
    ranked.sort(key=lambda x: x["median_distance"])
    result = {
        "reference": "PokoHex pinned PNGs, separately sourced from original Pokopia",
        "comparisons": len(rows),
        "layout_candidates": ranked,
        "warning": "Scores can prefer incorrect layouts if resampling, alpha, reference revisions or UV origin differ. Manual inspection still required."
    }
    (args.out / "layout_rankings.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
