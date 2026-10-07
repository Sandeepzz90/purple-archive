"""Bootstrap local matching from labelled starter portraits, then check held-out photos."""
import json
import server
from local_sort import LocalSorter, LocalSortError


def main():
    engine = LocalSorter(server.DATA)
    with server.database() as db:
        originals = [dict(row) for row in db.execute("SELECT id,filename,member FROM media WHERE id LIKE 'seed-%' AND member!='all' ORDER BY member")]
        holdouts = [dict(row) for row in db.execute("SELECT id,filename,member FROM media WHERE id LIKE 'extra-%' AND member!='all' ORDER BY member")]
    for item in originals:
        try:
            engine.add_reference(server.DOWNLOAD / item['filename'], item['member'], item['id'])
            print(item['member'] + ': starter reference ready', flush=True)
        except LocalSortError as error:
            print(item['member'] + ': ' + str(error), flush=True)
    print('Status:', json.dumps(engine.status()), flush=True)
    if engine.status()['ready']:
        report = []
        for item in holdouts:
            result = engine.classify(server.DOWNLOAD / item['filename'])
            report.append({'id': item['id'], 'expected': item['member'], 'result': result})
            print('Held-out', item['member'], '→', result['members'], 'faces:', result['detected'], flush=True)
        (server.DATA / 'local_sort_validation.json').write_text(json.dumps(report, indent=2))
    engine.close()


if __name__ == '__main__':
    main()
