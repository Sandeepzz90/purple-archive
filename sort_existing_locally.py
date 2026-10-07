"""Apply conservative offline member matching to existing unassigned uploads."""
import json
from collections import Counter
import server


def main():
    engine = server.LOCAL_SORT
    if not engine.status()['ready']:
        raise RuntimeError('Prepare the reference portraits first.')
    with server.database() as db:
        rows = [dict(row) for row in db.execute("SELECT id,filename FROM media WHERE source='telegram' AND kind='image' AND member='all' ORDER BY created")]
    counts = Counter()
    matched = 0
    for number, row in enumerate(rows, 1):
        result = engine.classify(server.DOWNLOAD / row['filename'])
        server.set_setting('local-result:'+row['id'], json.dumps(result))
        if result['members']:
            with server.database() as db:
                changed = db.execute("UPDATE media SET member=? WHERE id=? AND member='all'", (','.join(result['members']), row['id'])).rowcount
            matched += changed
            counts.update(result['members'])
        if number % 10 == 0 or number == len(rows):
            print(f'Checked {number}/{len(rows)} · matched {matched}', flush=True)
    server.set_setting('local_sort_enabled', 'on')
    server.set_setting('local_initial_sort_complete', 'on')
    print(json.dumps({'checked': len(rows), 'matched': matched, 'uncertain': len(rows)-matched, 'member_assignments': dict(counts)}), flush=True)
    engine.close()


if __name__ == '__main__':
    main()
