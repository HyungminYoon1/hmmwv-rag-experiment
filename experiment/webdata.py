"""Read-only view data for the local experiment dashboard."""
import re
from .io import BASE,ROOT,read_json

def overview():
    runs=[]
    for p in (BASE/'runs').glob('*/manifest.json'):
        m=read_json(p);s=read_json(p.parent/'status.json')
        runs.append({'id':m['id'],'mode':m['mode'],'created_at':m['created_at'],**s})
    return {'runs':sorted(runs,key=lambda x:x['created_at'],reverse=True),
      'gold':read_json(BASE/'gold-v1/validation.json'),'config':read_json(BASE/'config.json')}

def gold_rows():return read_json(BASE/'gold-v1/questions.json')

def run_data(run_id):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,60}',run_id):raise ValueError('Invalid run')
    directory=BASE/'runs'/run_id
    rows=[]
    for path in sorted((directory/'attempts').glob('r1-*.json')):
        r=read_json(path)
        rows.append({'question_id':r['question_id'],'question':r['question'],'condition':r['condition'],
          'status':r['status'],'answer':(r['response'] or {}).get('response',''),
          'timing_ms':r['timing_ms'],'input_tokens':r.get('input_tokens_counted'),
          'chunks':[{'id':x['id'],'rank':x['rank'],'score':x['score'],'pdf_pages':x['pdf_pages']}
                for x in (r['retrieval'] or {}).get('items',[])]})
    return {'manifest':read_json(directory/'manifest.json'),'status':read_json(directory/'status.json'),
       'summary':read_json(directory/'summary.json') if (directory/'summary.json').exists() else None,'answers':rows}

def source_image(page):
    if not page.isdigit() or not 1<=int(page)<=890:raise ValueError('Invalid source page')
    cached=BASE/'evidence-review'/f'pdf-{int(page):04}.png'
    if cached.exists():return cached.read_bytes()
    import pymupdf
    config=read_json(ROOT/'preprocessing/output/corpus-v6-final/config.json')
    with pymupdf.open(ROOT/config['source_pdf']) as document:
        return document[int(page)-1].get_pixmap(dpi=115,alpha=False).tobytes('png')
