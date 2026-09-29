"""Download only pinned tokenizer/OCR data; no generation-model weights."""
from pathlib import Path
import hashlib
import json
import urllib.request

BASE = Path(__file__).resolve().parent
REVISION = 'cdbee75f17c01a7cc42f958dc650907174af0554'
URLS = {
    'qwen-tokenizer/tokenizer.json': f'https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/resolve/{REVISION}/tokenizer.json',
    'qwen-tokenizer/tokenizer_config.json': f'https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/resolve/{REVISION}/tokenizer_config.json',
    'tessdata/eng.traineddata': 'https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/4.1.0/eng.traineddata',
}
HASHES = {
    'qwen-tokenizer/tokenizer.json': 'aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4',
    'qwen-tokenizer/tokenizer_config.json': 'a62ff0a2472a0fa1b8eaabcb57c59b58afa42a22831dc141400b6e0cf2b65ce3',
    'tessdata/eng.traineddata': '7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2',
}

def main():
    folder = BASE / 'assets'
    rows = []
    for name, url in URLS.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with urllib.request.urlopen(url, timeout=60) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != HASHES[name]:
                raise ValueError(f'Download hash mismatch: {name}')
            path.write_bytes(data)
        if hashlib.sha256(path.read_bytes()).hexdigest() != HASHES[name]:
            raise ValueError(f'Asset hash mismatch: {name}')
        rows.append({'file': name, 'url': url, 'bytes': path.stat().st_size,
                     'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest = folder / 'manifest.json'
    if manifest.exists():
        expected = json.loads(manifest.read_text(encoding='utf-8'))
        if expected['files'] != rows:
            raise ValueError('Asset hash mismatch against existing manifest')
    else:
        content = {'tokenizer_revision': REVISION, 'files': rows}
        manifest.write_bytes((json.dumps(content, ensure_ascii=False, indent=2) + '\n').replace('\n', '\r\n').encode('utf-8'))
    print(json.dumps(rows, ensure_ascii=False))

if __name__ == '__main__':
    main()
