"""Resolve declared publication derivatives without rewriting research inventories."""
from artifact_io import read, safe_path, sha


def publication_records(root, scope):
    core = read(root / 'artifacts/original-files.json')['files']
    manifest = read(root / 'artifacts/manifest.json')
    ledger = read(root / 'artifacts/publication-changes.json')
    source_manifest = read(root / 'artifacts/source-bundles.json')
    if ledger['schema'] != 1 or manifest.get('publication_revision') != ledger['publication_revision']:
        raise ValueError('Publication revision mismatch')
    originals = core + [r for b in source_manifest['bundles'] for r in b['files']]
    original_by_path = {r['path']: r for r in originals}
    if len(original_by_path) != len(originals):
        raise ValueError('Duplicate original path')
    changes = {}
    allowed_kinds = {'local_path_redaction', 'hwpx_author_metadata', 'standalone_documentation',
                     'public_copy_integrity_references', 'archive_interrupted_save'}
    for row in ledger['changes']:
        old = original_by_path.get(row['original_path'])
        safe_path(root, row['path'])
        if old is None or row['original_path'] in changes or row['kind'] not in allowed_kinds:
            raise ValueError('Unknown or duplicate publication change')
        if (old['sha256'], old['bytes']) != (row['original_sha256'], row['original_bytes']):
            raise ValueError('Publication change has a different research source')
        if row['kind'] == 'standalone_documentation' and not (
                row['path'].endswith('.md')
                or row['path'].endswith(('/build_report.py', '/evaluation.html', '/index.html', '/review-v1.html'))):
            raise ValueError('Documentation change targets a non-document file')
        if row['kind'] == 'archive_interrupted_save':
            if (row['sha256'], row['bytes']) != (old['sha256'], old['bytes']):
                raise ValueError('Archived temporary record changed')
        elif row['path'] != row['original_path']:
            raise ValueError('Undeclared relocation')
        changes[row['original_path']] = {k: row[k] for k in ('path', 'bytes', 'sha256')}
    exclusions = set()
    core_names = {r['path'] for r in core}
    for row in ledger['excluded']:
        old = original_by_path.get(row['path'])
        if (row['path'] in exclusions or row['path'] in changes or row['path'] not in core_names
                or old != {k: row[k] for k in ('path', 'bytes', 'sha256')}
                or row['bytes'] != 0 or row['reason'] != 'empty_worker_log'
                or not row['path'].endswith('/worker.log')):
            raise ValueError('Invalid publication exclusion')
        exclusions.add(row['path'])
    records = [changes.get(r['path'], r) for r in core if r['path'] not in exclusions]
    original_bundles = {b['id']: b for b in source_manifest['bundles']}
    if len(original_bundles) != len(source_manifest['bundles']):
        raise ValueError('Duplicate original bundle')
    if {b['id'] for b in manifest['bundles']} != set(original_bundles) or len(manifest['bundles']) != len(original_bundles):
        raise ValueError('Publication bundle set changed')
    for row in ledger['bundle_additions']:
        safe_path(root, row['path'])
        if row['bundle'] not in original_bundles or row['path'] in original_by_path:
            raise ValueError('Invalid bundle addition')
    all_destinations = list(records)
    for bundle in manifest['bundles']:
        expected = [changes.get(r['path'], r) for r in original_bundles[bundle['id']]['files']]
        expected += [{k: r[k] for k in ('path', 'bytes', 'sha256')}
                     for r in ledger['bundle_additions'] if r['bundle'] == bundle['id']]
        if sorted(bundle['files'], key=lambda r:r['path']) != sorted(expected, key=lambda r:r['path']):
            raise ValueError('Bundle files differ from declared publication changes')
        all_destinations.extend(expected)
        if scope == 'all' or (scope == 'runtime' and bundle['id'] == 'runtime-data'):
            records.extend(expected)
    if len({r['path'] for r in all_destinations}) != len(all_destinations):
        raise ValueError('Duplicate publication destination')
    correction = manifest.get('correction_release')
    if correction:
        inventory = safe_path(root, correction['inventory'])
        if sha(inventory) != correction['inventory_sha256']:
            raise ValueError('Correction inventory checksum differs')
        data = read(inventory)
        if data['release_tag'] != manifest['release_tag']:
            raise ValueError('Correction release version differs')
        # Existing research/publication records cannot be silently replaced.
        baseline = {r['path']: r for r in all_destinations}
        listed = {r['path']: r for r in records}
        additional = data['files']
        if len({r['path'] for r in additional}) != len(additional):
            raise ValueError('Duplicate correction file')
        for row in additional:
            safe_path(root, row['path'])
            if row['path'] in baseline and baseline[row['path']] != row:
                raise ValueError('Correction overwrites a preserved record')
            if row['path'] not in listed:
                records.append(row)
                listed[row['path']] = row
        bundle_ids = set(original_bundles)
        destinations = set(baseline) | set(listed)
        for bundle in manifest.get('supplemental_bundles', []):
            if bundle['id'] in bundle_ids:
                raise ValueError('Duplicate supplemental bundle')
            bundle_ids.add(bundle['id'])
            for row in bundle['files']:
                safe_path(root, row['path'])
                if row['path'] in destinations:
                    raise ValueError('Supplemental destination conflicts')
                destinations.add(row['path'])
                if scope == 'all':
                    records.append(row)
    elif manifest.get('supplemental_bundles'):
        raise ValueError('Supplemental data has no correction inventory')
    return records, {'publication_revision': ledger['publication_revision'],
                     'declared_changes_or_relocations': len(changes),
                     'excluded_empty_logs': len(exclusions),
                     'original_inventories_preserved': True}
