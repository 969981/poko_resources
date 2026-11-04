"""Read-only real small-file regression for a sparse Pokopia 2.0.1 checkout.

This validates entire IDX, both RDX/RDB catalogs, and one real FDATA zlib record.
It deliberately does not claim that missing FDATA in a sparse checkout are absent
from the game, and does not publish decoded game bytes.
"""
import argparse
import hashlib
from pathlib import Path
from .core import (FormatError, decode_kt_payload, parse_idx, parse_rdb,
                   parse_rdx, read_idrk, save_json, sha256_file)


def verify(source: Path, output: Path) -> dict:
    romfs = source / 'romfs'
    kt = romfs / 'motor_asset_re' / 'KIDS_PLATFORM_OUNCE'
    idx_file = romfs / 'LI_C0_R.IDX'
    idx = parse_idx(idx_file.read_bytes())
    if len(idx) != 12298 or len(idx) * 32 != idx_file.stat().st_size:
        raise FormatError('LINKDATA_UNEXPECTED_RECORD_COUNT')
    report = {'scope': 'sparse real-index smoke, not full source inventory',
              'idx_sha256': sha256_file(idx_file),
              'idx_records': len(idx),
              'idx_flag_0': sum(x.flag == 0 for x in idx),
              'idx_flag_1': sum(x.flag == 1 for x in idx),
              'idx_empty': sum(x.stored_size == 0 for x in idx),
              'catalogs': {}}
    for catalog in ('root', 'system'):
        rdx_file = kt / f'{catalog}.rdx'
        rdb_file = kt / f'{catalog}.rdb'
        rdx = parse_rdx(rdx_file.read_bytes())
        entries, hdr = parse_rdb(rdb_file.read_bytes(), catalog, rdx)
        report['catalogs'][catalog] = {
            'rdx_sha256': sha256_file(rdx_file),
            'rdb_sha256': sha256_file(rdb_file),
            'rdx_entries': len(rdx), 'rdb_records': len(entries),
            'header': hdr,
        }
    sample = kt / '0x4b13d561.fdata'
    with sample.open('rb') as f:
        if f.read(8) != b'PDRK0000':
            raise FormatError('SAMPLE_BAD_PDRK')
        header, _meta = read_idrk(f, 1184, sample.stat().st_size)
        if (header.packed_size, header.unpacked_size, header.name_hash,
            header.type_hash) != (88, 96, 0xf79cb076, 0x20a6a0bb):
            raise FormatError('SAMPLE_BAD_IDRK_HEADER')
        packed = f.read(header.packed_size)
        decoded = decode_kt_payload(packed, header)
    if not decoded.startswith(b'_DOK0000'):
        raise FormatError('SAMPLE_BAD_KIDSOBJDB_MAGIC')
    report['sample'] = {
        'source': '0x4b13d561.fdata',
        'source_sha256': sha256_file(sample),
        'record_offset': 1184, 'record_size': header.entry_size,
        'packed_size': len(packed), 'unpacked_size': len(decoded),
        'packed_sha256': hashlib.sha256(packed).hexdigest(),
        'decoded_sha256': hashlib.sha256(decoded).hexdigest(),
        'decoded_magic': decoded[:8].decode('ascii'),
        'status': 'DECOMPRESSED_VERIFIED',
    }
    save_json(output / 'real_index_smoke.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('2.0.1'))
    parser.add_argument('--output', type=Path, default=Path('_meta/2.0.1/smoke'))
    args = parser.parse_args()
    report = verify(args.source, args.output)
    print('IDX:', report['idx_records'], 'root RDB:', report['catalogs']['root']['rdb_records'],
          'system RDB:', report['catalogs']['system']['rdb_records'],
          'FDATA verified:', report['sample']['status'])


if __name__ == '__main__':
    main()
