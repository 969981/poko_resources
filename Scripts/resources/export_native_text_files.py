#!/usr/bin/env python3
"""Export Pokopia 2.0.1 M7 native LINKDATA tables to auditable UTF-8 text.

One physical TXT line = one zero-based native record ID, first form only.
The JSONL sidecar retains all native forms, raw metadata and offsets.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

try:
    from .recover_native_text_ids import LANGS, parse
except ImportError:
    from recover_native_text_ids import LANGS, parse

ANCHORS = (2323, 2350, 3304, 4645)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def txt_escape(value: str) -> str:
    """Escape physical newlines, not in-game text tags."""
    return (value.replace('\\', '\\\\').replace('\r', '\\r')
            .replace('\n', '\\n').replace('\t', '\\t'))


def load_groups(path: Path, starts: set[int] | None) -> list[dict]:
    with path.open(encoding='utf-8-sig', newline='') as f:
        groups = list(csv.DictReader(f))
    selected = [g for g in groups if starts is None or int(g['start_entry']) in starts]
    found = {int(g['start_entry']) for g in selected}
    if starts is not None and found != starts:
        raise ValueError(f'M7 groups missing: {sorted(starts - found)}')
    for g in selected:
        s = int(g['start_entry'])
        if int(g['end_entry']) != s + 8:
            raise ValueError(f'Not a 9-file group: {s}')
        if g.get('locale_order') != ','.join(LANGS):
            raise ValueError(f'Unexpected M7 locale order: {s}')
    return sorted(selected, key=lambda g: int(g['start_entry']))


def load_inventory(path: Path) -> dict[int, dict]:
    with path.open(encoding='utf-8-sig', newline='') as f:
        return {int(r['entry']): r for r in csv.DictReader(f)}


def export_group(group: dict, decoded: Path, dest: Path,
                 inventory: dict[int, dict]) -> dict:
    start = int(group['start_entry'])
    out = dest / f'table_{start:05d}'
    tables = []
    for number in range(start, start + 9):
        original = decoded / f'{number:05d}.bin'
        data = original.read_bytes()
        parsed, status = parse(data, number, original.as_posix())
        if status != 'PARSED' or parsed is None:
            raise ValueError(f'M7 parser rejected {original}: {status}')
        reference = inventory.get(number)
        if (not reference or reference.get('status') != 'PARSED'
                or reference.get('sha256') != digest(data)):
            raise ValueError(f'M7 inventory SHA/status mismatch: {number}')
        if (parsed.count != int(group['record_count'])
                or parsed.forms != int(group['forms'])):
            raise ValueError(f'M7 shape mismatch: {number}')
        if tables and parsed.key() != tables[0].key():
            raise ValueError(f'M7 structural key mismatch: {number}')
        tables.append(parsed)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        'table_start': start, 'table_end': start + 8,
        'record_count': tables[0].count, 'forms_per_record': tables[0].forms,
        'locale_order': list(LANGS), 'category': group.get('category') or 'UNKNOWN',
        'evidence_grade': group['evidence_grade'],
        'text_id_semantics': 'ZERO_BASED_NATIVE_TABLE_RECORD_ORDINAL',
        'sources': {}, 'outputs': {},
        'notes': [
            'TXT: one physical line per text ID, form 0 only; empty records stay empty.',
            'TXT escapes backslash, actual newline, CR, and tab. Game tags are preserved.',
            'All original forms and byte offsets are losslessly retained in *.forms.jsonl.',
            'M7 structural alignment does not prove a scene/quest/UI caller relationship.',
        ],
    }
    for lang, table in zip(LANGS, tables):
        lines = [txt_escape(row[0][0]) for row in table.rows]
        txt_data = ('\n'.join(lines) + '\n').encode('utf-8')
        txt_path = out / f'{lang}.txt'
        txt_path.write_bytes(txt_data)
        forms_path = out / f'{lang}.forms.jsonl'
        with forms_path.open('w', encoding='utf-8', newline='\n') as f:
            for i, (values, offsets, metadata) in enumerate(table.rows):
                f.write(json.dumps({
                    'text_id': i, 'forms': list(values),
                    'absolute_byte_offsets': list(offsets),
                    'raw_metadata_u32': list(metadata),
                }, ensure_ascii=False, separators=(',', ':')) + '\n')
        manifest['sources'][lang] = {
            'entry': table.entry, 'decoded_path': table.path,
            'sha256': table.sha, 'native_record_width': table.width,
        }
        manifest['outputs'][lang] = {
            'txt': txt_path.name, 'txt_sha256': digest(txt_data),
            'all_forms_jsonl': forms_path.name,
            'all_forms_jsonl_sha256': digest(forms_path.read_bytes()),
            'lines': len(lines),
            'nonempty_first_form': sum(bool(v) for v in lines),
        }
    (out / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {
        'start_entry': start, 'end_entry': start + 8,
        'record_count': tables[0].count, 'forms': tables[0].forms,
        'evidence_grade': group['evidence_grade'], 'category': manifest['category'],
        'directory': out.as_posix(),
    }


def run(decoded: Path, groups_csv: Path, inventory_csv: Path,
        dest: Path, starts: set[int] | None) -> dict:
    groups = load_groups(groups_csv, starts)
    inventory = load_inventory(inventory_csv)
    report = {
        'status': 'NATIVE_TEXT_EXPORTED_WITH_M7_PROVENANCE',
        'source': 'Pokopia 2.0.1 decoded LINKDATA / M7',
        'groups_exported': len(groups), 'locale_count': len(LANGS),
        'table_groups': [], 'full_game_coverage': 'NOT_CLAIMED',
        'category_mapping': 'ONLY_WHERE_ORIGINALLY_PROVEN',
    }
    for group in groups:
        report['table_groups'].append(export_group(group, decoded, dest, inventory))
    dest.mkdir(parents=True, exist_ok=True)
    (dest / 'text_export_report.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    base = Path('UnPack/2.0.1')
    p.add_argument('--decoded-root', type=Path,
                   default=base / 'romfs/LD_C0_R.BIN/decoded')
    p.add_argument('--groups', type=Path,
                   default=base / 'Resources/Localization/M7/nine_language_groups.csv')
    p.add_argument('--inventory', type=Path,
                   default=base / 'Resources/Localization/M7/native_table_inventory.csv')
    p.add_argument('--dest', type=Path,
                   default=base / 'Resources/Localization/TextExports')
    choice = p.add_mutually_exclusive_group()
    choice.add_argument('--start-entry', type=int, action='append',
                        help='Repeat for groups; default: 2323,2350,3304,4645')
    choice.add_argument('--all-groups', action='store_true',
                        help='Explicit opt-in; requires every group source file')
    args = p.parse_args()
    starts = None if args.all_groups else set(args.start_entry or ANCHORS)
    print(json.dumps(
        run(args.decoded_root, args.groups, args.inventory, args.dest, starts),
        ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
