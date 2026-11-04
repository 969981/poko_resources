"""M1: LINKDATA IDX audit and optional raw/zlib extraction from a restored BIN."""
import argparse
import hashlib
import sys
from dataclasses import asdict
from pathlib import Path
from .core import FormatError, decode_linkdata_payload, parse_idx, save_csv, save_json


def run(idx_path: Path, bin_path: Path | None, output: Path, start: int, limit: int | None,
        dry_run: bool, decode: bool, resume: bool, verify_only: bool = False) -> dict:
    entries = parse_idx(idx_path.read_bytes())
    if bin_path and not bin_path.is_file():
        raise FileNotFoundError(f'Restore the BIN first: {bin_path}')
    bin_size = bin_path.stat().st_size if bin_path else None
    rows = []
    total_processed = 0
    with bin_path.open('rb') if bin_path else _NoFile() as inp:
        for entry in entries:
            row = asdict(entry)
            row['status'] = 'INDEXED' if entry.stored_size else 'EMPTY'
            row['error'] = ''
            row['output_sha256'] = ''
            row['decoded_sha256'] = ''
            row['raw_head64_hex'] = ''
            if bin_size is not None and entry.offset + entry.stored_size > bin_size:
                row.update(status='INVALID_RANGE', error='offset+stored_size exceeds BIN')
            eligible = entry.index >= start and (limit is None or total_processed < limit)
            if eligible and entry.stored_size and row['status'] != 'INVALID_RANGE':
                total_processed += 1
                if not bin_path:
                    row['status'] = 'BIN_NOT_PROVIDED'
                elif dry_run:
                    row['status'] = 'DRY_RUN_LOCATED'
                else:
                    raw_file = output / 'raw' / f'{entry.index:05d}.bin'
                    if not verify_only:
                        raw_file.parent.mkdir(parents=True, exist_ok=True)
                    inp.seek(entry.offset)
                    blob = inp.read(entry.stored_size)
                    if len(blob) != entry.stored_size:
                        row.update(status='TRUNCATED_READ', error='short read')
                    else:
                        if not verify_only:
                            if not resume or not raw_file.exists() or raw_file.stat().st_size != len(blob) or hashlib.sha256(raw_file.read_bytes()).digest() != hashlib.sha256(blob).digest():
                                raw_file.write_bytes(blob)
                        row['status'] = 'EXTRACTED'
                        row['raw_head64_hex'] = blob[:64].hex()
                        row['output_sha256'] = hashlib.sha256(blob).hexdigest()
                        if decode:
                            try:
                                decoded = decode_linkdata_payload(blob, entry.unpacked_size, entry.flag)
                                dest = output / 'decoded' / f'{entry.index:05d}.bin'
                                if not verify_only:
                                    dest.parent.mkdir(parents=True, exist_ok=True)
                                    if not (resume and dest.is_file() and dest.stat().st_size == len(decoded) and hashlib.sha256(dest.read_bytes()).digest() == hashlib.sha256(decoded).digest()):
                                        dest.write_bytes(decoded)
                                row['decoded_sha256'] = hashlib.sha256(decoded).hexdigest()
                                row['status'] = 'DECOMPRESSED'
                            except FormatError as exc:
                                row['status'] = 'DECODE_FAILED'
                                row['error'] = str(exc)
            rows.append(row)
    report = {'idx_file': str(idx_path), 'idx_records': len(entries),
              'flag_0': sum(e.flag == 0 for e in entries), 'flag_1': sum(e.flag == 1 for e in entries),
              'empty': sum(e.stored_size == 0 for e in entries), 'bin_provided': bin_size is not None,
              'bin_bytes': bin_size, 'selected_nonempty_records': total_processed,
              'statuses': {key: sum(x['status'] == key for x in rows) for key in sorted({x['status'] for x in rows})},
              'note': 'Rows not selected by --start/--limit are index-only and should not be counted as extraction failures.'}
    save_csv(output / 'linkdata_entries.csv', rows)
    save_json(output / 'linkdata_report.json', report)
    return report


class _NoFile:
    def __enter__(self): return None
    def __exit__(self, *args): return False


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--idx', type=Path, default=Path('2.0.1/romfs/LI_C0_R.IDX'))
    p.add_argument('--bin', type=Path, default=None, help='Restored LD_C0_R.BIN (optional for index-only mode)')
    p.add_argument('--output', type=Path, default=Path('UnPack/2.0.1/LINKDATA'))
    p.add_argument('--start', type=int, default=0)
    p.add_argument('--limit', type=int, default=None)
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--decode', action='store_true')
    p.add_argument('--resume', action='store_true')
    p.add_argument('--verify-only', action='store_true', help='Validate and hash each record without writing game payloads')
    args = p.parse_args(argv)
    print(run(args.idx, args.bin, args.output, args.start, args.limit, args.dry_run, args.decode, args.resume, args.verify_only))
    return 0


if __name__ == '__main__':
    sys.exit(main())
