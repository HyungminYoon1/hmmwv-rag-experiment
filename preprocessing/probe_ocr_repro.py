"""Small independent OCR reproducibility diagnostic, not corpus generation."""
import os
os.environ['OMP_THREAD_LIMIT'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import pymupdf
from preprocess import BASE, line_records

config = json.loads((BASE / 'config.json').read_text(encoding='utf-8'))
with tempfile.TemporaryDirectory(prefix='kidet-ocr-') as tmp, pymupdf.open(BASE / config['input']) as doc:
    shutil.copyfile(BASE / config['ocr']['data'], Path(tmp) / 'eng.traineddata')
    for n in [220, 464, 659, 220, 464, 659]:
        page = doc[n-1]
        pix = page.get_pixmap(dpi=300, colorspace=pymupdf.csRGB, alpha=False)
        png_hash = hashlib.sha256(pix.tobytes('png')).hexdigest()
        tp = page.get_textpage_ocr(language='eng', dpi=300, full=True, tessdata=tmp)
        result = json.dumps(line_records(page, tp), sort_keys=True)
        print(json.dumps({'page': n, 'pixels': png_hash, 'ocr': hashlib.sha256(result.encode()).hexdigest()}), flush=True)
