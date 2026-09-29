"""Local model interface. This module does not read gold labels or question types."""
import json, re, urllib.request
from tokenizers import Tokenizer
from jinja2 import Environment
from .io import BASE, ROOT, read_json

def api(path, payload=None, timeout=15):
    config=read_json(BASE/'config.json')
    request=urllib.request.Request(config['ollama_url']+path,
        data=json.dumps(payload).encode('utf-8') if payload is not None else None,
        headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=timeout) as response:
        return json.load(response)

def context_text(items):
    return '\n\n'.join(f'[{c["id"]}] TM 9-2320-280-20-1 | PDF {",".join(map(str,c["pdf_pages"]))} | Printed {",".join(c["printed_pages"])}\n{c["text"]}' for c in items)

def evaluation_copy(answer):
    ids=re.findall(r'\[C[0-9]{6}\]',answer)
    return re.sub(r'\[C[0-9]{6}\]','',answer),ids

class Generator:
    def __init__(self):
        self.config=read_json(BASE/'config.json')
        self.tokenizer=Tokenizer.from_file(str(ROOT/self.config['tokenizer']))
        self.tokenizer.no_truncation(); self.tokenizer.no_padding()
        self.template=Environment().from_string(read_json(ROOT/self.config['tokenizer_config'])['chat_template'])
        self.prompt=(BASE/'prompt.txt').read_text(encoding='utf-8').strip()

    def prepare(self,question,context):
        if not isinstance(question,str) or not question.strip(): raise ValueError('Empty question')
        content=self.prompt.format(question=question,context=context)
        raw=self.template.render(messages=[{'role':'user','content':content}],add_generation_prompt=True,tools=None)
        tokens=len(self.tokenizer.encode(raw,add_special_tokens=False).ids)
        if tokens+self.config['options']['num_predict']>self.config['options']['num_ctx']:
            raise ValueError('Input plus reserved output exceeds context; truncation is forbidden')
        return {'model':self.config['model'],'prompt':raw,'raw':True,'stream':False,
                'keep_alive':-1,'options':self.config['options']},tokens

    def generate(self,payload):
        return api('/api/generate',payload,self.config['timeout_seconds'])

    def resident(self):
        models=api('/api/ps')['models']
        match=[x for x in models if x.get('name',x.get('model'))==self.config['model']]
        if len(match)!=1:raise RuntimeError('Generation model is not resident')
        m=match[0]
        if m.get('size_vram',0)<=0:raise RuntimeError('Expected GPU model residency')
        return m
