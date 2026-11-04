"""Reconcile all source manifests against actual GitHub Git-tree blob metadata.

Does not download any binary game assets. Blob existence and byte size are
verified through GitHub Git Trees API (rather than 'git ls-tree -l', which may
lazy-fetch every large blob in a partial clone). SHA-256 fields are preserved
as publisher-generated checksums, not falsely reported as rehashed in CI.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import subprocess
import urllib.request
from collections import Counter
from pathlib import Path

from .core import save_csv, save_json

PREFIX = "UnPack/2.0.1/romfs/"


def git(*args):
    return subprocess.check_output(
        ["git", *args], text=True, encoding="utf-8", stderr=subprocess.PIPE
    )


def tree_sha(tree_path):
    try:
        return git("rev-parse", "--verify", f"HEAD:{tree_path}").strip()
    except subprocess.CalledProcessError:
        return None


def github_tree(repo, tree, token):
    if not repo or "/" not in repo:
        raise ValueError("GitHub repository required, e.g. owner/repo")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/git/trees/{tree}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "poko-resources-unpack-audit",
            "X-GitHub-Api-Version": "2022-11-28",
            **({"Authorization": "Bearer " + token} if token else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=90) as response:
        data = json.load(response)
    if data.get("truncated"):
        raise RuntimeError(f"GIT_TREE_TRUNCATED: {tree}")
    if "tree" not in data:
        raise RuntimeError(f"GIT_TREE_MISSING: {tree}")
    result = {}
    for item in data["tree"]:
        if item.get("type") == "blob":
            if not isinstance(item.get("size"), int):
                raise RuntimeError(f"GIT_TREE_BLOB_SIZE_MISSING: {item.get('path')}")
            result[item["path"]] = item["size"]
    return result


def read_git_manifest_history(path):
    merged = {}
    history = git("log", "--full-history", "--reverse", "--format=%H", "--", path).splitlines()
    for commit in history:
        try:
            contents = git("show", commit + ":" + path)
        except subprocess.CalledProcessError:
            continue
        for row in csv.DictReader(io.StringIO(contents)):
            record_id = row.get("record_id")
            if not record_id:
                continue
            prior = merged.get(record_id)
            # An earlier successful publication must not be replaced by a
            # later skip for the exact same source container.
            if (prior and prior.get("publish_status") in
                    ("PUBLISHED", "ALREADY_PRESENT_VERIFIED", "ALREADY_PRESENT_GIT_REFERENCE")
                    and row.get("publish_status") not in
                    ("PUBLISHED", "ALREADY_PRESENT_VERIFIED", "ALREADY_PRESENT_GIT_REFERENCE")
                    and prior.get("source_sha256") == row.get("source_sha256")):
                continue
            merged[record_id] = row
    return merged, len(history)


def run(output=Path("UnPack/2.0.1"), prefix=PREFIX, repo=None,
        github_token=None, tree_reader=github_tree):
    output = Path(output)
    repo = repo or os.environ.get("GITHUB_REPOSITORY", "")
    token = github_token if github_token is not None else os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise RuntimeError("GITHUB_TOKEN_REQUIRED_FOR_TREE_METADATA_VALIDATION")
    paths = set(git("ls-tree", "-r", "--name-only", "HEAD", "--",
                    str(output / "romfs")).splitlines())
    manifests = sorted(x for x in paths if x.startswith(prefix) and x.endswith("/_manifest.csv"))
    if not manifests:
        raise RuntimeError("NO_SOURCE_MANIFESTS_FOUND")
    stats = Counter()
    by_source = {}
    rewritten = {}
    for manifest in manifests:
        folder = manifest.removesuffix("/_manifest.csv")
        saved, nversions = read_git_manifest_history(manifest)
        size_map = {}
        for mode in ("decoded", "raw"):
            subfolder = folder + "/" + mode
            sha = tree_sha(subfolder)
            if not sha:
                continue
            blob_info = tree_reader(repo, sha, token)
            for name, size in blob_info.items():
                size_map[subfolder + "/" + name] = size
        verified, missing = 0, 0
        known_output_paths = set()
        for record in saved.values():
            if record.get("publish_status") not in (
                "PUBLISHED", "ALREADY_PRESENT_VERIFIED", "ALREADY_PRESENT_GIT_REFERENCE"
            ):
                continue
            expected = [str(output / p) for p in record.get("output_path", "").split(";") if p]
            known_output_paths.update(expected)
            recorded_bytes = int(record.get("output_bytes") or -1)
            valid = (bool(expected) and all(p in size_map for p in expected)
                     and sum(size_map[p] for p in expected) == recorded_bytes)
            if valid:
                record["publish_status"] = "PUBLISHED"
                verified += 1
                stats["published_bytes"] += recorded_bytes
            else:
                record["publish_status"] = "MISSING_OR_WRONG_SIZE_ON_GIT"
                record["decoder_error"] = (
                    record.get("decoder_error", "") + " HEAD tree presence/size mismatch"
                ).strip()
                missing += 1
        asset_paths = {p for p in paths if p.startswith(folder + "/") and
                       ("/decoded/" in p or "/raw/" in p)}
        unknown = sorted(asset_paths - known_output_paths)
        by_source[manifest] = {
            "manifest_records": len(saved),
            "published_with_verified_size": verified,
            "missing_or_wrong_size": missing,
            "unmanifested_output_files": len(unknown),
            "unmanifested_examples": unknown[:15],
            "manifest_versions": nversions,
            "size_source": "GitHub Git Trees API",
        }
        stats["manifest_records"] += len(saved)
        stats["published_verified_size"] += verified
        stats["missing_or_wrong_size"] += missing
        stats["unmanifested_output_files"] += len(unknown)
        rewritten[manifest] = [saved[k] for k in sorted(saved)]

    for manifest, rows in rewritten.items():
        save_csv(Path(manifest), rows)
    report = {"overall": dict(stats), "sources": by_source,
              "size_source": "GitHub Git Trees API; no binary asset download",
              "sha256_note": "SHA-256 is from the extractor, not rehashed in this verification job"}
    save_json(output / "_reports" / "manifest_reconciliation.json", report)
    print(json.dumps(report["overall"], ensure_ascii=False, indent=2), flush=True)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=Path("UnPack/2.0.1"))
    p.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    args = p.parse_args()
    run(args.output, repo=args.repo)


if __name__ == "__main__":
    main()
