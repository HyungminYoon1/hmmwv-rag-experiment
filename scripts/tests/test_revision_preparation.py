"""Run in the evaluation environment. Fixture-only preparation, zero API calls."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
PARENT = 'sol-formal-20260928-numeric-v3'


class RevisionPreparationTest(unittest.TestCase):
    def test_new_generation_is_bound_and_old_answer_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix='kidet-preparation-test-') as folder:
            fixture = Path(folder)
            for directory in ('experiment', 'experiment/evaluation', 'retrieval'):
                source = ROOT / directory
                target = fixture / directory
                target.mkdir(parents=True, exist_ok=True)
                for path in source.iterdir():
                    if path.is_file() and path.suffix in ('.py', '.json', '.txt'):
                        shutil.copy2(path, target / path.name)
            for directory in ('experiment/gold-v1', 'experiment/gold-v2', 'experiment/gold-v3', 'experiment/evaluation/profiles'):
                shutil.copytree(ROOT / directory, fixture / directory, ignore=shutil.ignore_patterns('pdf-pages'))
            decision = Path('experiment/revisions/20260929-v2/DECISIONS.md')
            (fixture / decision).parent.mkdir(parents=True)
            shutil.copy2(ROOT / decision, fixture / decision)
            shutil.copytree(ROOT / 'experiment/runs/formal-v1',
                            fixture / 'experiment/runs/fixture-generation')
            parent = fixture / 'experiment/evaluation/runs' / PARENT
            shutil.copytree(ROOT / 'experiment/evaluation/runs' / PARENT, parent)
            helper = fixture / 'scripts/prepare_revised_evaluation.py'
            helper.parent.mkdir()
            shutil.copy2(ROOT / 'scripts/prepare_revised_evaluation.py', helper)

            manifest = json.loads((parent / 'manifest.json').read_text(encoding='utf-8'))
            manifest['source_run'] = 'fixture-generation'
            (parent / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            environment = os.environ.copy()
            environment.pop('OPENAI_API_KEY', None)
            environment['PYTHONIOENCODING'] = 'utf-8'

            def command(*args):
                return subprocess.run([sys.executable, '-X', 'utf8', *args], cwd=fixture,
                                      env=environment, capture_output=True, text=True,
                                      encoding='utf-8', timeout=90)

            prepared = command(str(helper), '--id', 'fixture-revised', '--source-evaluation', PARENT)
            self.assertEqual(prepared.returncode, 0, prepared.stdout + prepared.stderr)
            destination = fixture / 'experiment/evaluation/runs/fixture-revised'
            result = json.loads((destination / 'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(result['source_run'], 'fixture-generation')
            self.assertEqual(result['gold_version'], 'gold-v3')
            packet = json.loads((destination / 'inputs.json').read_text(encoding='utf-8'))
            s16 = next(r for r in packet['rows'] if r['question_id'] == 'S16')
            self.assertEqual([e['id'] for e in s16['required_elements']], ['S16-A01'])
            self.assertTrue(any('runs/fixture-generation/attempts/' in path
                                for path in result['identity']['source_hashes']))
            self.assertFalse(any('runs/formal-v1/' in path for path in result['identity']['source_hashes']))
            verified = command('-m', 'experiment.evaluation.revision_runner', 'verify', '--id', 'fixture-revised')
            self.assertEqual(verified.returncode, 0, verified.stdout + verified.stderr)
            self.assertFalse((destination / 'calls').exists())
            self.assertFalse((destination / 'results').exists())

            historical = command(str(helper), '--id', 'fixture-gold-v2', '--source-evaluation', PARENT, '--gold-version', 'gold-v2')
            self.assertEqual(historical.returncode, 0, historical.stdout + historical.stderr)
            old_packet = json.loads((fixture / 'experiment/evaluation/runs/fixture-gold-v2/inputs.json').read_text(encoding='utf-8'))
            old_s16 = next(r for r in old_packet['rows'] if r['question_id'] == 'S16')
            self.assertEqual(len(old_s16['required_elements']), 2)

            parent_inputs = json.loads((parent / 'inputs.json').read_text(encoding='utf-8'))
            parent_inputs['rows'][0]['response'] += '\nDifferent answer fixture.'
            (parent / 'inputs.json').write_text(json.dumps(parent_inputs), encoding='utf-8')
            rejected = command(str(helper), '--id', 'fixture-rejected', '--source-evaluation', PARENT)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn('PARENT_ANSWERS_DIFFER', rejected.stderr)
            self.assertFalse((fixture / 'experiment/evaluation/runs/fixture-rejected').exists())


if __name__ == '__main__':
    unittest.main()
