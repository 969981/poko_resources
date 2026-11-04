"""M0: Read-only input inventory, volume continuity and optional archive integrity tests."""
import argparse
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from .core import sha256_file, save_csv, save_json

PART = re.compile(r'^(.*)\.7z\.(\d{3,})$', re.IGNORECASE)


def audit(source: Path, output: Path, hash_files: bool, test_7z: bool) -> dict:
    if not source.is_dir():
        raise FileNotFoundError(source)
    files = sorted(p for p in source.rglob('*') if p.is_file())
    rows, groups = [], defaultdict(list)
    for file in files:
        relative = file.relative_to(source).as_posix()
        if relative.lower().startswith('romfs/movie_asset/'):
            continue
        m = PART.match(file.name)
        if m:
            groups[(file.parent, m.group(1))].append((int(m.group(2)), file))
        rows.append({'path': relative, 'bytes': file.stat().st_size,
                     'sha256': sha256_file(file) if hash_files else '',
                     'kind': 'volume' if m else 'direct'})
    volume_rows = []
    failures = []
    for (directory, stem), parts in sorted(groups.items()):
        parts.sort()
        numbers = [number for number, _ in parts]
        continuous = numbers == list(range(1, len(numbers) + 1))
        first = parts[0][1]
        status = 'NOT_TESTED'
        if test_7z and continuous:
            sevenzip = shutil.which('7zz') or shutil.which('7z') or shutil.which('7za')
            if not sevenzip:
                status = '7Z_MISSING'
            else:
                result = subprocess.run([sevenzip, 't', '-y', str(first)], capture_output=True, text=True, errors='replace')
                status = 'OK' if result.returncode == 0 else f'7Z_EXIT_{result.returncode}'
        if not continuous or (test_7z and status != 'OK'):
            failures.append({'file': str(first.relative_to(source)), 'continuous': continuous, 'status': status})
        volume_rows.append({'base_path': str((directory / stem).relative_to(source)).replace('\\', '/'),
                            'volumes': len(parts), 'first': numbers[0], 'last': numbers[-1],
                            'total_compressed_bytes': sum(p.stat().st_size for _, p in parts),
                            'continuous': continuous, 'integrity_status': status})
    save_csv(output / 'inventory.csv', rows)
    save_csv(output / 'volumes.csv', volume_rows)
    report = {'input': str(source), 'files': len(rows), 'volume_sets': len(volume_rows),
              'continuity_ok': all(v['continuous'] for v in volume_rows),
              'hashes_computed': hash_files, 'tested_7z': test_7z,
              'validation_failures': failures,
              'note': 'No archives extracted by this inventory command.'}
    save_json(output / 'inventory_report.json', report)
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, default=Path('2.0.1'))
    p.add_argument('--output', type=Path, default=Path('_meta/2.0.1'))
    p.add_argument('--hash', action='store_true', help='Stream SHA256 over every file; expensive on large inputs')
    p.add_argument('--test-7z', action='store_true', help='Test all complete archives; no extraction')
    args = p.parse_args(argv)
    report = audit(args.source, args.output, args.hash, args.test_7z)
    print(report)
    return 1 if report['validation_failures'] else 0


if __name__ == '__main__':
    sys.exit(main())
