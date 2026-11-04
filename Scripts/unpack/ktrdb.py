"""M2: root+system RDB/RDX inventory, platform FDATA lookup and optional raw extraction."""
import argparse
import hashlib
import sys
from dataclasses import asdict
from pathlib import Path
from .core import (FormatError, decode_kt_payload, find_fdata, parse_rdb, parse_rdx,
                   read_idrk, save_csv, save_json)


def run(base: Path, output: Path, extract: bool, decode: bool, limit: int | None,
        dry_run: bool, resume: bool, verify_only: bool = False, only_fdata: set[str] | None = None) -> dict:
    rdx_rows, rows, stats = [], [], {}
    processed = 0
    for catalog in ('root', 'system'):
        rdx_path, rdb_path = base / f'{catalog}.rdx', base / f'{catalog}.rdb'
        if not rdx_path.is_file() or not rdb_path.is_file():
            stats[catalog] = {'error': 'RDB_OR_RDX_NOT_PRESENT'}
            continue
        rdex = parse_rdx(rdx_path.read_bytes())
        entries, hdr = parse_rdb(rdb_path.read_bytes(), catalog, rdex)
        stats[catalog] = hdr
        resolved = {}
        for rd in rdex:
            fp = find_fdata(base, rd)
            resolved[rd.position] = fp
            rdx_rows.append({'catalog': catalog, **asdict(rd), 'filename': rd.filename,
                             'path': str(fp) if fp else '', 'status': 'CONTAINER_FOUND' if fp else 'NOT_PRESENT'})
        for en in entries:
            row = {'catalog': catalog, 'record_index': en.record_index, 'rdb_offset': en.rdb_offset,
                   'name_hash': f'{en.name_hash:08x}', 'type_hash': f'{en.type_hash:08x}',
                   'flags': f'{en.flags:08x}', 'footer_magic': f'{en.footer_magic:04x}',
                   'fdata_index': en.fdata_index, 'fdata_offset': en.fdata_offset,
                   'fdata_entry_size': en.fdata_entry_size, 'uncompressed_size': en.uncompressed_size,
                   'footer_extra_hex': en.footer_extra_hex,
                   'status': 'INDEXED', 'error': '', 'source_path': '', 'output_sha256': '', 'decoded_sha256': ''}
            rd = rdex[en.fdata_index]
            if en.footer_magic == 0x0c01:
                container = base / 'data' / f'0x{en.name_hash:08x}.file'
                mode = 'standalone_file'
            elif en.footer_magic == 0x0401:
                container = resolved[en.fdata_index]
                mode = 'fdata_idrk'
            else:
                container = None
                mode = 'unsupported_footer'
            if mode == 'unsupported_footer':
                row.update(status='UNSUPPORTED_FOOTER', error=f'0x{en.footer_magic:04x}')
            elif container is None or not container.is_file():
                row.update(status='CONTAINER_NOT_PRESENT', error=f'{mode}:{rd.filename}')
            else:
                row.update(status='LOCATED', source_path=str(container))
                if extract and (only_fdata is None or f'{rd.fdata_hash:08x}' in only_fdata) and (limit is None or processed < limit):
                    processed += 1
                    if dry_run:
                        row['status'] = 'DRY_RUN_LOCATED'
                    else:
                        try:
                            with container.open('rb') as fd:
                                if mode == 'fdata_idrk':
                                    header, _metadata = read_idrk(fd, en.fdata_offset, container.stat().st_size)
                                    if header.name_hash != en.name_hash or header.type_hash != en.type_hash:
                                        raise FormatError('IDRK_RDB_NAME_OR_TYPE_MISMATCH')
                                    if header.unpacked_size != en.uncompressed_size:
                                        raise FormatError('IDRK_RDB_UNPACKED_SIZE_MISMATCH')
                                    if header.entry_size != en.fdata_entry_size:
                                        raise FormatError('IDRK_RDB_STORED_SIZE_MISMATCH')
                                    if header.packed_size > 512 * 1024 * 1024:
                                        raise FormatError('IDRK_RECORD_EXCEEDS_MEMORY_LIMIT')
                                    blob = fd.read(header.packed_size)
                                    if len(blob) != header.packed_size:
                                        raise FormatError('IDRK_TRUNCATED_PAYLOAD')
                                else:
                                    if container.stat().st_size > 512 * 1024 * 1024:
                                        raise FormatError('STANDALONE_FILE_EXCEEDS_MEMORY_LIMIT')
                                    blob = fd.read()
                                    header = None
                            name = f'{catalog}_{en.record_index:06d}_{en.name_hash:08x}.{mode}.bin'
                            dest = output / 'raw' / name
                            raw_hash = hashlib.sha256(blob).hexdigest()
                            if not verify_only:
                                dest.parent.mkdir(parents=True, exist_ok=True)
                                if not (resume and dest.is_file() and dest.stat().st_size == len(blob) and hashlib.sha256(dest.read_bytes()).hexdigest() == raw_hash):
                                    dest.write_bytes(blob)
                            row.update(status='EXTRACTED', output_sha256=raw_hash)
                            if decode:
                                if mode == 'standalone_file':
                                    raise FormatError('STANDALONE_DECODE_UNVERIFIED_RAW_PRESERVED')
                                decoded = decode_kt_payload(blob, header)
                                out = output / 'decoded' / name
                                if not verify_only:
                                    out.parent.mkdir(parents=True, exist_ok=True)
                                    if not (resume and out.is_file() and out.stat().st_size == len(decoded) and hashlib.sha256(out.read_bytes()).hexdigest() == hashlib.sha256(decoded).hexdigest()):
                                        out.write_bytes(decoded)
                                row['decoded_sha256'] = hashlib.sha256(decoded).hexdigest()
                                row['status'] = 'DECOMPRESSED'
                        except (FormatError, OSError) as exc:
                            # Existing raw has not been deleted; failure explicitly reported.
                            row.update(status='DECODE_FAILED' if row['status'] == 'EXTRACTED' else 'EXTRACTION_FAILED', error=str(exc))
            rows.append(row)
    report = {'catalogs': stats, 'rdx_entries': len(rdx_rows), 'rdb_records': len(rows),
              'selected_for_extraction': processed,
              'statuses': {state: sum(row['status'] == state for row in rows) for state in sorted({r['status'] for r in rows})}}
    save_csv(output / 'rdb_records.csv', rows)
    save_csv(output / 'rdx_containers.csv', rdx_rows)
    save_csv(output / 'unresolved.csv', [r for r in rows if r['status'] in ('UNSUPPORTED_FOOTER', 'CONTAINER_NOT_PRESENT', 'EXTRACTION_FAILED', 'DECODE_FAILED')])
    save_json(output / 'ktrdb_report.json', report)
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', type=Path, default=Path('2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE'))
    p.add_argument('--output', type=Path, default=Path('UnPack/2.0.1/KTRDB'))
    p.add_argument('--extract', action='store_true', help='Enable writing record payloads (default index-only)')
    p.add_argument('--decode', action='store_true', help='Attempt verified KT framed zlib decoding')
    p.add_argument('--limit', type=int, default=None)
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--resume', action='store_true')
    p.add_argument('--verify-only', action='store_true', help='Only emit index records/hashes; do not save game payloads')
    p.add_argument('--only-fdata', action='append', default=[], help='Filter extraction by 8-digit hex FDATA hash; may repeat')
    args = p.parse_args(argv)
    print(run(args.base, args.output, args.extract or args.decode, args.decode, args.limit, args.dry_run, args.resume, args.verify_only, set(x.lower().removeprefix('0x') for x in args.only_fdata) if args.only_fdata else None))
    return 0


if __name__ == '__main__':
    sys.exit(main())
