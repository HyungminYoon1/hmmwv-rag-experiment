"""Download exact locked public weights without overwriting the original locks."""
import argparse
import json
from urllib.parse import quote

from artifact_io import ROOT, fetch, read, safe_path


def targets(kind, metadata_only=False):
    records = []
    if kind in ('bge', 'all'):
        cfg = read(ROOT / 'retrieval/config.json')
        lock = read(safe_path(ROOT, cfg['model_lock']))
        if lock['revision'] != cfg['model_revision'] or lock['model_id'] != cfg['model_id']:
            raise ValueError('BGE configuration and model lock disagree')
        for name, digest in lock['files'].items():
            if metadata_only and name.endswith(('.bin', '.safetensors')):
                continue
            url = 'https://huggingface.co/' + lock['model_id'] + '/resolve/' + lock['revision'] + '/' + quote(name)
            records.append((safe_path(ROOT, cfg['model_path'] + '/' + name), url, digest, None))
    if kind in ('qwen', 'all') and not metadata_only:
        lock = read(ROOT / 'experiment/models/model.lock.json')
        url = 'https://huggingface.co/' + lock['publisher'] + '/resolve/' + lock['revision'] + '/' + quote(lock['file'])
        records.append((safe_path(ROOT, 'experiment/models/' + lock['file']), url, lock['sha256'], lock['bytes']))
    return records


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', choices=['bge', 'qwen', 'all'], default='all')
    p.add_argument('--metadata-only', action='store_true', help='BGE metadata/tokenizer download test; not an inference-ready installation')
    args = p.parse_args()
    for path, url, digest, size in targets(args.model, args.metadata_only):
        state = fetch(url, path, digest, size)
        print(json.dumps({'file': path.relative_to(ROOT).as_posix(), 'status': state}), flush=True)


if __name__ == '__main__':
    main()
