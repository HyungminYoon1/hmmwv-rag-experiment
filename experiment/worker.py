"""Formal retrieval IPC. The original development guard remains unchanged."""
import json,sys,time
from retrieval.service import SearchService

def main():
    service=SearchService(); service.load_model()
    print(json.dumps({'ready':True,'status':service.status()}),flush=True)
    for line in sys.stdin:
        request=json.loads(line)
        if request.get('stop'):break
        try:
            # Only the runner supplies exact, manifest-pinned formal questions.
            question=request['question']
            if not isinstance(question,str) or not question.strip():raise ValueError('Empty question')
            start=time.perf_counter()
            vector=service.encoder.encode([question]); embedded=time.perf_counter()
            items=service.index.search_vector(vector); end=time.perf_counter()
            print(json.dumps({'items':items,'embedding_ms':(embedded-start)*1000,
                'search_ms':(end-embedded)*1000},ensure_ascii=False),flush=True)
        except Exception as exc:
            print(json.dumps({'error':type(exc).__name__+': '+str(exc)},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
