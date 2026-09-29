"""Check declared public copies and restored data without models or API calls."""
import argparse
import json
from pathlib import Path

from artifact_io import ROOT, read, safe_path, sha
from publication_records import publication_records


def verify(root, scope):
    try:
        records, publication = publication_records(root, scope)
    except (ValueError, KeyError, FileNotFoundError, TypeError) as exc:
        return {'status': 'FAIL', 'scope': scope, 'checked_files': 0,
                'errors': [{'error': 'INVALID_PUBLICATION_RECORDS', 'type': type(exc).__name__}]}
    errors = []
    for row in records:
        path = safe_path(root, row['path'])
        if not path.is_file():
            errors.append({'path': row['path'], 'error': 'MISSING'})
        elif path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
            errors.append({'path': row['path'], 'error': 'CHANGED'})
    return {'status': 'FAIL' if errors else 'PASS', 'scope': scope,
            'checked_files': len(records), 'publication': publication, 'errors': errors}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--scope', choices=['core', 'runtime', 'all'], default='all')
    args = p.parse_args()
    result = verify(args.root.resolve(), args.scope)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
