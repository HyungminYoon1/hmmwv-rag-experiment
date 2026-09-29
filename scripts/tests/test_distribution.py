"""Package contract checks; no model generation or paid evaluation."""
import hashlib
import http.client
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import artifact_io as assets
import download_models
from serve_results import make_server


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.root = self.base / 'project'
        self.root.mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def archive(self, items):
        path = self.base / 'data.zip'
        with zipfile.ZipFile(path, 'w') as handle:
            for name, data in items.items():
                handle.writestr(name, data)
        manifest = {'id': 'fixture', 'filename': path.name, 'bytes': path.stat().st_size,
                    'sha256': assets.sha(path), 'files': [
                        {'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                        for name, data in items.items()]}
        return path, manifest

    def test_restore_is_byte_exact_and_idempotent(self):
        archive, manifest = self.archive({'data/원문.txt': '교범\r\n'.encode(), 'a.bin': b'\x00\xff'})
        self.assertEqual(assets.restore_bundle(self.root, archive, manifest)['restored'], 2)
        self.assertEqual((self.root / 'data/원문.txt').read_bytes(), '교범\r\n'.encode())
        self.assertEqual(assets.restore_bundle(self.root, archive, manifest)['already_present'], 2)

    def test_existing_conflict_blocks_all_installation(self):
        archive, manifest = self.archive({'new.txt': b'new', 'existing.txt': b'original'})
        (self.root / 'existing.txt').write_bytes(b'researcher change')
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            assets.restore_bundle(self.root, archive, manifest)
        self.assertFalse((self.root / 'new.txt').exists())
        self.assertEqual((self.root / 'existing.txt').read_bytes(), b'researcher change')

    def test_member_hash_failure_installs_nothing(self):
        archive, manifest = self.archive({'a.txt': b'a', 'b.txt': b'b'})
        manifest['files'][1]['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'member checksum'):
            assets.restore_bundle(self.root, archive, manifest)
        self.assertFalse((self.root / 'a.txt').exists())

    def test_archive_tampering_is_rejected(self):
        archive, manifest = self.archive({'a.txt': b'a'})
        with archive.open('ab') as handle:
            handle.write(b'tampered')
        with self.assertRaisesRegex(ValueError, 'Archive checksum'):
            assets.restore_bundle(self.root, archive, manifest)

    def test_unlisted_zip_entry_is_rejected(self):
        archive, manifest = self.archive({'a.txt': b'a', 'unexpected.txt': b'extra'})
        manifest['files'].pop()
        with self.assertRaisesRegex(ValueError, 'ZIP entries'):
            assets.restore_bundle(self.root, archive, manifest)

    def test_traversal_and_windows_streams_are_rejected(self):
        for name in ('../outside.txt', '/outside.txt', 'C:/outside.txt', 'a/../../b',
                     'a\\b', 'a:stream', './a.txt', 'a//b'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                assets.safe_path(self.root, name)

    def test_download_hash_error_leaves_no_target_or_temp(self):
        response = io.BytesIO(b'wrong download')
        response.geturl = lambda: 'https://example.invalid/file'
        with patch('artifact_io.urllib.request.urlopen', return_value=response):
            with self.assertRaisesRegex(ValueError, 'checksum'):
                assets.fetch('https://example.invalid/file', self.root / 'model.bin', '0' * 64)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_verified_download_is_reused_without_network(self):
        target = self.root / 'model.bin'
        target.write_bytes(b'fixed')
        with patch('artifact_io.urllib.request.urlopen', side_effect=AssertionError('network')):
            self.assertEqual(assets.fetch('https://example.invalid/file', target, assets.sha(target)),
                             'ALREADY_VERIFIED')

    def test_non_https_or_credential_urls_are_rejected(self):
        for url in ('http://example.invalid/file', 'https://username:password@example.invalid/file'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                assets.fetch(url, self.root / 'target', '0' * 64)


class IntegrationTests(unittest.TestCase):
    def test_model_targets_follow_original_locks(self):
        rows = download_models.targets('all')
        self.assertEqual(len(rows), 12)
        self.assertTrue(all('/resolve/' in url and len(digest) == 64 for _, url, digest, _ in rows))
        qwen = [r for r in rows if r[0].suffix == '.gguf']
        self.assertEqual(len(qwen), 1)
        self.assertEqual(qwen[0][3], 2497280736)
        self.assertIn('ae44f08e1392f39c0e474af10c3ff8355c8b6688', qwen[0][1])

    def test_viewer_uses_requested_port_and_rejects_foreign_host(self):
        with make_server(0) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = http.client.HTTPConnection('127.0.0.1', server.server_address[1], timeout=30)
            try:
                connection.request('GET', '/evaluation')
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertIn(b'<!doctype html', response.read()[:100].lower())
                connection.request('GET', '/api/evaluation')
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                content = response.read().decode('utf-8')
                json.loads(content)
                self.assertIn('sol-revision-formal-20260929-v3', content)
                connection.request('GET', '/evaluation', headers={'Host': 'example.invalid'})
                response = connection.getresponse()
                self.assertEqual(response.status, 403)
                response.read()
            finally:
                connection.close()
                server.shutdown()
                thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
