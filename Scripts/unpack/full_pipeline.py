"""M0 -> M1 -> M2 full local/runner orchestrator (read-only input).

Restores only in scratch, validates every archive, and writes only metadata
reports when --verify-only is set. Do NOT upload extracted game resources.
"""
import argparse
import os
import re
import shutil
import subprocess
import traceback
from pathlib import Path

from .core import save_json
from .inventory import audit
from .ktrdb import run as run_kt
from .linkdata import run as run_link

PART = re.compile(r'^(.*)\.7z\.(\d{3,})$', re.I)


def _archive_size(sevenzip: str, first: Path) -> int:
    listing = subprocess.run([sevenzip, 'l', '-slt', str(first)], check=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, errors='replace').stdout
    sizes = [int(x) for x in re.findall(r'(?m)^Size = ([0-9]+)\r?$', listing)]
    if not sizes:
        raise RuntimeError(f'7ZIP_SIZE_UNAVAILABLE: {first}')
    return sizes[-1]


def build_plan(source: Path, sevenzip: str) -> tuple[list[dict], list[Path]]:
    if not source.is_dir():
        raise FileNotFoundError(source)
    groups, direct = {}, []
    for path in sorted(source.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(source).as_posix()
        if relative.lower().startswith('romfs/movie_asset/'):
            continue
        match = PART.match(path.name)
        if match:
            groups.setdefault((path.parent, match.group(1)), []).append((int(match.group(2)), path))
        else:
            direct.append(path)
    archives = []
    for (parent, stem), numbered in sorted(groups.items()):
        numbered.sort()
        numbers = [n for n, _p in numbered]
        if numbers != list(range(1, len(numbers) + 1)):
            raise RuntimeError(f'VOLUME_SEQUENCE_GAP: {parent}/{stem}: {numbers}')
        first = numbered[0][1]
        target = (parent / stem).relative_to(source)
        archives.append({'first': first, 'parts': [p for _, p in numbered],
                         'target': target, 'size': _archive_size(sevenzip, first)})
    return archives, direct


def restore_one(src: Path, destination: Path, size: int, sevenzip: str) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sevenzip, 't', '-y', str(src)], check=True)
    subprocess.run([sevenzip, 'x', '-y', '-aoa', str(src), f'-o{destination.parent}'], check=True)
    if not destination.is_file() or destination.stat().st_size != size:
        raise RuntimeError(f'RESTORE_SIZE_MISMATCH:{destination}:{size}')
    return destination


def run(source: Path, work: Path, output: Path, sevenzip: str, verify_only: bool) -> dict:
    if not verify_only:
        raise ValueError('Only --verify-only is supported by this full orchestration; use direct extractors for payload exports')
    if shutil.which(sevenzip) is None:
        raise FileNotFoundError(f'7-Zip binary not found: {sevenzip}')
    source = source.resolve()
    work.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    result = {'scope': 'all tracked input files except romfs/movie_asset',
              'input_source': str(source), 'state': 'STARTED', 'stages': {}}
    save_json(output / 'pipeline_status.json', result)
    try:
        manifest = audit(source, output / 'm0', hash_files=True, test_7z=False)
        result['stages']['inventory'] = manifest
        archives, direct = build_plan(source, sevenzip)
        if not archives:
            raise RuntimeError('NO_ARCHIVES_FOUND')
        targets = {p.relative_to(source).as_posix() for p in direct}
        for entry in archives:
            target_name = entry['target'].as_posix()
            if target_name in targets:
                raise RuntimeError(f'RESTORE_PATH_COLLISION:{target_name}')
            targets.add(target_name)
        link_archives = [p for p in archives if p['target'].name == 'LD_C0_R.BIN']
        if len(link_archives) != 1:
            raise RuntimeError(f'LINKDATA_ARCHIVE_COUNT:{len(link_archives)}')
        kt_archives = [p for p in archives if p not in link_archives]
        peak_bytes = max(sum(p['size'] for p in kt_archives), link_archives[0]['size'])
        free = shutil.disk_usage(work.parent.resolve()).free
        reserve = 1024**3
        result['disk_preflight'] = {'free_bytes': free, 'estimated_peak_output_bytes': peak_bytes,
                                    'reserve_bytes': reserve,
                                    'notes': 'Input checkout already occupies disk; scratch output is not uploaded'}
        save_json(output / 'pipeline_status.json', result)
        if free < peak_bytes + reserve:
            raise RuntimeError(f'INSUFFICIENT_DISK:free={free}:required={peak_bytes + reserve}')
        restored = work / '2.0.1'
        if restored.exists():
            raise FileExistsError(f'Workspace already exists, will not overwrite: {restored}')
        restored.mkdir(parents=True)
        for fp in direct:
            dest = restored / fp.relative_to(source)
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                dest.symlink_to(fp)
            except OSError:
                shutil.copy2(fp, dest)
        # LINKDATA can be verified and removed before restoring the heavier KT resources.
        link_entry = link_archives[0]
        restored_bin = restore_one(link_entry['first'], restored / link_entry['target'],
                                   link_entry['size'], sevenzip)
        link_report = run_link(restored / 'romfs' / 'LI_C0_R.IDX', restored_bin,
                               output / 'm1', start=0, limit=None,
                               dry_run=False, decode=True, resume=False, verify_only=True)
        result['stages']['linkdata'] = link_report
        restored_bin.unlink()
        save_json(output / 'pipeline_status.json', result)
        for entry in kt_archives:
            restore_one(entry['first'], restored / entry['target'], entry['size'], sevenzip)
            result['stages']['archive_restore_completed'] = result['stages'].get('archive_restore_completed', 0) + 1
            save_json(output / 'pipeline_status.json', result)
        kt_root = restored / 'romfs' / 'motor_asset_re' / 'KIDS_PLATFORM_OUNCE'
        kt_report = run_kt(kt_root, output / 'm2', extract=True, decode=True, limit=None,
                           dry_run=False, resume=False, verify_only=True)
        result['stages']['ktrdb'] = kt_report
        result['state'] = 'COMPLETE_WITH_CLASSIFIED_RECORD_RESULTS'
    except Exception as exc:
        result.update(state='FAILED', error=f'{type(exc).__name__}:{exc}', traceback=traceback.format_exc())
        save_json(output / 'pipeline_status.json', result)
        raise
    save_json(output / 'pipeline_status.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, default=Path('2.0.1'))
    p.add_argument('--work', type=Path, default=Path('_work/pokopia-2.0.1-full'))
    p.add_argument('--output', type=Path, default=Path('_meta/2.0.1/full'))
    p.add_argument('--sevenzip', default='7z')
    p.add_argument('--verify-only', action='store_true', required=True)
    args = p.parse_args()
    result = run(args.source, args.work, args.output, args.sevenzip, args.verify_only)
    print('Full M0/M1/M2 validation finished:', result['state'])


if __name__ == '__main__':
    main()
