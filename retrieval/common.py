"""Artifact IO and paths; no model or HTTP dependencies."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
import importlib.metadata

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parent


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def text_sha(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def read_jsonl(path: Path):
    with path.open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write_text(path: Path, value: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='\r\n') as stream:
        stream.write(value.replace('\r\n', '\n'))


def write_json(path: Path, value):
    temporary = path.with_name(path.name + '.tmp')
    write_text(temporary, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    temporary.replace(path)


def write_jsonl(path: Path, values):
    write_text(path, ''.join(json.dumps(v, ensure_ascii=False, sort_keys=True) + '\n' for v in values))


def load_config():
    return read_json(PACKAGE / 'config.json')


def local_path(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError('Path must stay inside this project')
    return path


def check_files(base: Path, files: dict[str, str]):
    for name, expected in files.items():
        path = (base / name).resolve()
        if not path.is_relative_to(base.resolve()):
            raise ValueError(f'Invalid artifact path: {name}')
        if not path.is_file() or sha(path) != expected:
            raise ValueError(f'File integrity check failed: {name}')


def environment():
    from .cpu_affinity import process_affinity
    packages = ['torch', 'sentence-transformers', 'transformers', 'tokenizers',
                'huggingface-hub', 'numpy', 'faiss-cpu', 'PyMuPDF']
    return {'python': platform.python_version(), 'platform': platform.platform(),
            'process_cpu_affinity': process_affinity(),
            'packages': {p: importlib.metadata.version(p) for p in packages}}


def pipeline_hashes():
    names = ['common.py', 'source.py', 'model.py', 'build.py', 'index.py', 'cpu_affinity.py', 'config.json']
    return {name: sha(PACKAGE / name) for name in names}
