"""Export one consistent MongoDB application database to a private JSON.gz file."""
import argparse
import gzip
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile

from bson import json_util

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/api'))

from app.core.config import load_environment, validate_mongodb_uri
from app.core.mongo_connection import create_mongo_client, mongo_failure


def write_snapshot(database, client, output):
    def encode(value):
        return json_util.dumps(value, json_options=json_util.CANONICAL_JSON_OPTIONS,
                               ensure_ascii=False, separators=(',', ':'))

    collections = sorted(database.list_collections(), key=lambda info: info['name'])
    metadata = {'format': 'funilo-mongo-extended-json-v1', 'database': database.name,
                'exported_at': datetime.now(timezone.utc).isoformat()}
    output.write(encode(metadata)[:-1] + ',"collections":[')
    counts = {}
    with client.start_session(snapshot=True) as session:
        for info in collections:
            name = info['name']
            if counts:
                output.write(',')
            indexes = list(database[name].list_indexes()) if info['type'] != 'view' else []
            output.write(encode({'info': info, 'indexes': indexes})[:-1] + ',"documents":[')
            count = 0
            if info['type'] != 'view':
                with database[name].find({}, session=session, batch_size=250) as cursor:
                    for document in cursor:
                        if count:
                            output.write(',')
                        output.write(encode(document))
                        count += 1
            counts[name] = count
            output.write(']}')
    output.write('],"counts":' + json.dumps(counts, ensure_ascii=False) + '}\n')
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    temporary = None
    stage = 'configuration'
    try:
        if args.output.exists():
            raise FileExistsError
        uri = load_environment().get('MONGODB_URI', '').strip()
        validate_mongodb_uri(uri)
        stage = 'read'
        with create_mongo_client(uri) as client:
            database = client.get_default_database()
            if database.name in {'admin', 'config', 'local'}:
                raise ValueError('An application database is required')
            with tempfile.NamedTemporaryFile(dir=args.output.parent, prefix='.mongo-export-',
                                             delete=False) as file:
                temporary = Path(file.name)
                with gzip.open(file, 'wt', encoding='utf-8') as output:
                    counts = write_snapshot(database, client, output)
        os.link(temporary, args.output)
        print(json.dumps({'collections': len(counts), 'documents': sum(counts.values()),
                          'activities': counts.get('activities', 0),
                          'activity_revisions': counts.get('activity_revisions', 0)}))
        return 0
    except FileExistsError:
        print('Output already exists; choose a new path.', file=sys.stderr)
        return 1
    except OSError:
        print('Unable to write the private export file.', file=sys.stderr)
        return 1
    except Exception as error:
        print(mongo_failure(error, stage), file=sys.stderr)
        return 1
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    sys.exit(main())
