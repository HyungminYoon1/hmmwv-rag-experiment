"""Download a pinned GGUF, verifying its published LFS digest."""
from pathlib import Path
import json
import urllib.request
from retrieval.common import sha, write_json

ROOT = Path(__file__).resolve().parent
REPO = 'bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF'
REVISION = 'ae44f08e1392f39c0e474af10c3ff8355c8b6688'
NAME = 'Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf'

def main():
    target = ROOT / 'models' / NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    url = f'https://huggingface.co/api/models/{REPO}/revision/{REVISION}?blobs=true'
    with urllib.request.urlopen(url, timeout=60) as response:
        info = json.load(response)
    row = next(x for x in info['siblings'] if x['rfilename'] == NAME)
    expected = row['lfs']['sha256']
    part = target.with_suffix('.gguf.part')
    if not target.exists():
        with urllib.request.urlopen(f'https://huggingface.co/{REPO}/resolve/{REVISION}/{NAME}', timeout=120) as src, part.open('wb') as dst:
            total = 0
            while block := src.read(4 * 1024 * 1024):
                dst.write(block)
                total += len(block)
                if total % (128 * 1024 * 1024) == 0:
                    try:
                        write_json(ROOT / 'reports/download-progress.json', {'received': total, 'expected': row['lfs']['size']})
                    except PermissionError:
                        pass  # A transient OneDrive lock must not interrupt the download.
        if sha(part) != expected:
            raise ValueError('Downloaded GGUF differs from published LFS SHA256')
        part.replace(target)
    if sha(target) != expected:
        raise ValueError('Model checksum mismatch')
    write_json(ROOT / 'models/model.lock.json', {
        'model': 'Qwen3-4B-Instruct-2507', 'quantization': 'Q4_K_M',
        'publisher': REPO, 'revision': REVISION, 'file': NAME,
        'sha256': expected, 'bytes': target.stat().st_size,
        'base_model': 'Qwen/Qwen3-4B-Instruct-2507',
        'provenance': 'Third-party GGUF quantization of the Qwen model; not an official Qwen GGUF release.'})
    print('MODEL_DOWNLOAD_PASS', target.stat().st_size, flush=True)

if __name__ == '__main__':
    main()
