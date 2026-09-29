import json,math,numpy as np
from pathlib import Path
base=Path(__file__).resolve().parents[1]/'runs/sol-formal-20260928-v1'
r=json.loads((base/'results/r1-M02-llm_only.json').read_text(encoding='utf-8'))['result']['stages']['relevancy_calculation_audit']
import hashlib
def fp(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()).hexdigest()
q=g=None
for f in (base/'embeddings').glob('*.json'):
 d=json.loads(f.read_text(encoding='utf-8'))
 if len(d['vectors'])==1 and fp(d['vectors'][0])==r['query_vector_hash']:q=d['vectors'][0]
 if fp(d['vectors'])==r['response_vectors_hash']:g=d['vectors']
repetitions=[]
refnormq=math.sqrt(math.fsum(x*x for x in q));refnormg=[math.sqrt(math.fsum(x*x for x in v)) for v in g];refdot=[math.fsum(x*y for x,y in zip(q,v)) for v in g]
errors=[]
for i in range(30000):
 qv=np.asarray(q).reshape(1,-1);gv=np.asarray(g).reshape(3,-1)
 denom=np.linalg.norm(gv,axis=1)*np.linalg.norm(qv,axis=1);dot=np.dot(gv,qv.T).reshape(-1)
 qnorm=np.linalg.norm(qv,axis=1);gnorm=np.linalg.norm(gv,axis=1)
 cosine=dot/denom
 repetitions.append(cosine.tolist())
 expected=[x/(y*refnormq) for x,y in zip(refdot,refnormg)]
 delta=max(abs(qnorm[0]-refnormq),max(abs(x-y) for x,y in zip(gnorm,refnormg)),max(abs(x-y) for x,y in zip(dot,refdot)),max(abs(x-y) for x,y in zip(cosine,expected)))
 if delta>1e-10 and len(errors)<4:errors.append({'iteration':i,'qnorm':qnorm.tolist(),'gnorm':gnorm.tolist(),'dot':dot.tolist(),'denom':denom.tolist(),'cosine':cosine.tolist(),'delta':delta,'q_alignment':qv.ctypes.data%64,'g_alignment':gv.ctypes.data%64})
print(json.dumps({'numpy':np.__version__,'iterations':30000,'errors':errors,'reference':{'qnorm':refnormq,'gnorm':refnormg,'dot':refdot}}))
