"""Read an existing save pair and benchmark only disposable transaction copies.

Does not construct ApplicationState, advance dates, import CS2 or modify the
source directory. Reports sizes/times, never player data or private settings.
"""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import tempfile
from time import perf_counter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--save-dir', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    with tempfile.TemporaryDirectory(prefix='career-save-benchmark-') as folder:
        target = Path(folder)
        os.environ.update(CS2CAREER_SAVE_DIR=str(target),
                          CS2CAREER_EXTENSION_DIR=str(target / 'extensions'), CS2CAREER_NO_GAME='1')
        from cs2career.storage import transaction, history
        from cs2career.storage.receipts import compact_row, MAX_ROW_BYTES, MAX_TOTAL_BYTES
        from cs2career.storage.immutable import freeze, snapshot_memo
        from cs2career.json_bytes import encode
        from types import SimpleNamespace
        values = {name:json.loads(history.portable_bytes(args.save_dir/name))
                  for name in ('career.json', 'season.json')}
        receipt_rows = values['career.json'].get('incident_state', {}).get('operation_receipts', [])
        receipt_sizes = [len(encode(row)) for row in receipt_rows]
        compact_sizes = [len(encode(compact_row(row))) for row in receipt_rows]
        # The shipped save predates central receipts. Also model 2,048 real
        # report-shaped responses using its largest saved match, on copies only.
        match_rows = [m for e in values['season.json'].get('history', []) for m in e.get('matches', [])]
        largest = max(match_rows, key=lambda m: len(encode(m)), default={})
        sample = dict(request_id='benchmark-only', fingerprint='0'*64, path='/api/3d/match/simulate',
                      created_at=1, result=dict(ok=True, result=largest))
        receipt_metrics = dict(count=len(receipt_rows), total_bytes=sum(receipt_sizes),
            max_bytes=max(receipt_sizes, default=0), compact_total_bytes=sum(compact_sizes),
            max_row_limit=MAX_ROW_BYTES, total_limit=MAX_TOTAL_BYTES,
            report_shaped_sample_bytes=len(encode(sample)),
            report_shaped_summary_bytes=len(encode(compact_row(sample))))
        field_bytes = {key:len(encode(value)) for key, value in values['season.json'].items()}
        start = perf_counter()
        snapshot = deepcopy(values)
        copy_ms = (perf_counter()-start)*1000
        del snapshot
        values['season.json']['history'] = [freeze(row) for row in values['season.json'].get('history', [])]
        start = perf_counter()
        snapshot = deepcopy(values, snapshot_memo(SimpleNamespace(history=values['season.json']['history'])))
        shared_copy_ms = (perf_counter()-start)*1000
        del snapshot
        sizes = {name:len(encode(value)) for name, value in values.items()}
        rounds = []
        for _ in range(3):
            calls = {name:0 for name in values}
            def serialize(name):
                calls[name] += 1
                value = values[name]
                if name == 'season.json': value = history.pack(target, value)
                return encode(value)
            start = perf_counter()
            with transaction.batch():
                for _ in range(11):
                    for name in values:
                        transaction.save(target/name, lambda name=name: serialize(name))
            rounds.append(dict(milliseconds=round((perf_counter()-start)*1000, 1), serializers=calls))
        archived = json.loads((target/'season.json').read_text('utf-8'))
        assert history.expand(target, archived) == values['season.json']
        print(json.dumps(dict(source_bytes=sizes, season_field_bytes=field_bytes,
            receipt_metrics=receipt_metrics,
            rollback_snapshot_ms=round(copy_ms, 1), sealed_history_snapshot_ms=round(shared_copy_ms, 1), repeated_save_calls_per_file=11,
            commits=rounds, active_bytes={name:(target/name).stat().st_size for name in values},
            archive_bytes=sum(p.stat().st_size for p in (target/'history').glob('*.gz')),
            full_history_roundtrip=True, source_modified=False), indent=2))


if __name__ == '__main__':
    main()
