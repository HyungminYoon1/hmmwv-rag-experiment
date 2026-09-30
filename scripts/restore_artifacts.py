"""Restore immutable data from local ZIPs or a GitHub Release base URL."""
import argparse
import json
from pathlib import Path
from urllib.parse import quote

from artifact_io import ROOT, fetch, read, restore_bundle


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT)
    source = p.add_mutually_exclusive_group()
    source.add_argument('--asset-dir', type=Path)
    source.add_argument('--base-url', help='HTTPS GitHub Release download directory; no trailing filename')
    p.add_argument('--bundle', action='append', help='Bundle ID from artifacts/manifest.json; default: all')
    args = p.parse_args()
    root = args.root.resolve()
    manifest = read(root / 'artifacts/manifest.json')
    bundles = manifest['bundles'] + manifest.get('supplemental_bundles', [])
    selected = set(args.bundle or [b['id'] for b in bundles])
    if selected - {b['id'] for b in bundles}:
        p.error('Unknown bundle name')
    for bundle in bundles:
        if bundle['id'] not in selected:
            continue
        asset_dir = args.asset_dir or (root.parent / 'release-assets')
        archive = asset_dir / bundle['filename']
        if args.base_url:
            archive = root / '.artifact-cache' / bundle['filename']
            url = args.base_url.rstrip('/') + '/' + quote(bundle['filename'])
            fetch(url, archive, bundle['sha256'], bundle['bytes'])
        elif not archive.is_file():
            if bundle.get('url'):
                archive = root / '.artifact-cache' / bundle['filename']
                fetch(bundle['url'], archive, bundle['sha256'], bundle['bytes'])
            else:
                raise FileNotFoundError('Place ' + bundle['filename'] + ' in --asset-dir or specify --base-url')
        print(json.dumps(restore_bundle(root, archive, bundle), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
