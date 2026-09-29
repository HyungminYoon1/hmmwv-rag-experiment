"""One image, one fresh OCR process. Writes JSON only; no network or LLM."""
import os
os.environ['OMP_THREAD_LIMIT'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['DOTPRODUCT'] = 'generic'
import argparse
import json
from pathlib import Path
import tesserocr


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('image', type=Path)
    parser.add_argument('tessdata')
    parser.add_argument('--width', type=float)
    parser.add_argument('--dpi', type=int, default=300)
    parser.add_argument('--psm', type=int, default=3)
    parser.add_argument('--include-words', action='store_true',
                        help='Preserve TSV word boxes and exact line-text offsets in a sidecar.')
    args = parser.parse_args()
    if not tesserocr.tesseract_version().startswith('tesseract 5.5.2\n'):
        raise RuntimeError('This profile requires the pinned Tesseract 5.5.2 build.')
    with tesserocr.PyTessBaseAPI(path=args.tessdata, lang='eng',
                              oem=tesserocr.OEM.LSTM_ONLY, psm=args.psm) as api:
        for name in ('classify_enable_learning', 'classify_enable_adaptive_matcher', 'tessedit_parallelize'):
            if not api.SetVariable(name, '0'):
                raise RuntimeError(f'OCR setting was not accepted: {name}')
        if api.GetStringVariable('dotproduct') != 'generic':
            raise RuntimeError('The fixed generic dot-product implementation is required.')
        api.SetImageFile(str(args.image))
        api.SetSourceResolution(args.dpi)
        api.Recognize()
        tsv = api.GetTSVText(0).splitlines()
        keys = ['level', 'page_num', 'block_num', 'par_num', 'line_num', 'word_num',
                'left', 'top', 'width', 'height', 'conf', 'text']
        if tsv and tsv[0].startswith('level\t'):
            tsv = tsv[1:]
        words = [dict(zip(keys, line.split('\t', 11))) for line in tsv]
        width = int(words[0]['width'])
        scale = args.width / width if args.width else 72 / args.dpi
        groups = {}
        for w in words:
            if w['level'] != '5' or not w.get('text', '').strip():
                continue
            key = (int(w['block_num']), int(w['par_num']), int(w['line_num']))
            groups.setdefault(key, []).append(w)
        lines = []
        for (block, paragraph, number), group in groups.items():
            x0 = min(int(w['left']) for w in group)
            y0 = min(int(w['top']) for w in group)
            x1 = max(int(w['left']) + int(w['width']) for w in group)
            y1 = max(int(w['top']) + int(w['height']) for w in group)
            lines.append({'bbox': [round(v * scale, 4) for v in (x0, y0, x1, y1)],
                          'text': ' '.join(w['text'] for w in group),
                          'block': block, 'line': paragraph * 10000 + number,
                          'fonts': ['TesseractOCR'], 'direction': [1, 0],
                          'word_confidences': [float(w['conf']) for w in group]})
            if args.include_words:
                offset = 0
                entries = []
                for w in group:
                    left, top = int(w['left']), int(w['top'])
                    entries.append({'text': w['text'], 'start': offset,
                                    'end': offset + len(w['text']),
                                    'bbox': [round(v * scale, 4) for v in
                                             (left, top, left + int(w['width']), top + int(w['height']))],
                                    'block': block, 'paragraph': paragraph, 'line': number,
                                    'word': int(w['word_num']), 'confidence': float(w['conf'])})
                    offset += len(w['text']) + 1
                assert all(lines[-1]['text'][w['start']:w['end']] == w['text'] for w in entries)
                lines[-1]['words'] = entries
        print(json.dumps({'lines': lines, 'text': api.GetUTF8Text().strip()}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
