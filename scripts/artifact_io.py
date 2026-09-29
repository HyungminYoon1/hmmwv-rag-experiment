"""Small standard-library helpers for immutable research package assets."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def safe_path(root, relative):
    """Reject absolute paths, traversal, Windows streams and escaping symlinks."""
    if not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative:
        raise ValueError('Invalid artifact path')
    parts = PurePosixPath(relative)
    if parts.is_absolute() or '..' in parts.parts or relative != parts.as_posix():
        raise ValueError('Invalid artifact path')
    base = Path(root).resolve()
    target = (base / relative).resolve()
    if target == base or not target.is_relative_to(base):
        raise ValueError('Artifact path escapes the destination')
    return target


def fetch(url, target, expected_sha256, expected_bytes=None):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Downloads require an HTTPS URL without credentials')
    target = Path(target)
    if target.exists():
        if sha(target) == expected_sha256:
            return 'ALREADY_VERIFIED'
        raise ValueError('Existing file differs; choose a new destination: ' + target.name)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=target.name + '.', suffix='.part', dir=target.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(fd, 'wb') as dst, urllib.request.urlopen(url, timeout=120) as response:
            if urllib.parse.urlsplit(response.geturl()).scheme != 'https':
                raise ValueError('Download redirected away from HTTPS')
            shutil.copyfileobj(response, dst, 1024 * 1024)
        if expected_bytes is not None and temporary.stat().st_size != expected_bytes:
            raise ValueError('Downloaded file size differs: ' + target.name)
        if sha(temporary) != expected_sha256:
            raise ValueError('Downloaded checksum differs: ' + target.name)
        if target.exists():
            if sha(target) != expected_sha256:
                raise ValueError('Destination changed during download')
        else:
            temporary.rename(target)
        return 'DOWNLOADED_AND_VERIFIED'
    finally:
        temporary.unlink(missing_ok=True)


def restore_bundle(root, archive, bundle):
    archive = Path(archive)
    if archive.stat().st_size != bundle['bytes'] or sha(archive) != bundle['sha256']:
        raise ValueError('Archive checksum/size mismatch: ' + bundle['filename'])
    records = {r['path']: r for r in bundle['files']}
    if len(records) != len(bundle['files']):
        raise ValueError('Duplicate manifest destination')
    existing = 0
    # Verify all conflicts before creating any restored file.
    for relative, record in records.items():
        target = safe_path(root, relative)
        if target.exists():
            if not target.is_file() or sha(target) != record['sha256']:
                raise ValueError('Refusing to overwrite a different file: ' + relative)
            existing += 1
    stage_root = Path(root) / '.artifact-staging'
    stage_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='restore-', dir=stage_root) as stage, zipfile.ZipFile(archive) as z:
        members = z.infolist()
        names = [m.filename for m in members]
        if len(names) != len(set(names)) or set(names) != set(records):
            raise ValueError('ZIP entries differ from the artifact manifest')
        for member in members:
            safe_path(root, member.filename)
            if member.is_dir() or stat.S_ISLNK(member.external_attr >> 16):
                raise ValueError('Unsupported archive entry')
            record = records[member.filename]
            if member.file_size != record['bytes']:
                raise ValueError('ZIP member size differs')
            output = safe_path(stage, member.filename)
            output.parent.mkdir(parents=True, exist_ok=True)
            with z.open(member) as src, output.open('xb') as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
            if sha(output) != record['sha256']:
                raise ValueError('ZIP member checksum differs: ' + member.filename)
        # Every member is verified before any is installed.
        for relative, record in records.items():
            target = safe_path(root, relative)
            if target.exists():
                if sha(target) != record['sha256']:
                    raise ValueError('Destination changed during restoration: ' + relative)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            safe_path(stage, relative).rename(target)
    return {'bundle': bundle['id'], 'files': len(records), 'already_present': existing,
            'restored': len(records) - existing, 'status': 'PASS'}
