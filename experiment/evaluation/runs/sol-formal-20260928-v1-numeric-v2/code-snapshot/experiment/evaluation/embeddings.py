"""Reuse frozen CPU embedding environment without installing Torch into evaluation."""
import json
import subprocess
import threading
import queue
import numpy as np
from ragas.embeddings.base import BaseRagasEmbedding
from .common import ROOT, read, save, fingerprint, EvaluationError


class LocalEmbeddings(BaseRagasEmbedding):
    def __init__(self, directory):
        super().__init__()
        self.directory = directory
        self.process = None
        self.queue = queue.Queue()
        self.log = None
        self.last_vectors = {}
        self.last_query_vector = None
        self.last_response_vectors = None

    def _line(self):
        try:
            line = self.queue.get(timeout=300)
        except queue.Empty:
            raise EvaluationError('EMBEDDING_WORKER_TIMEOUT') from None
        if not line:
            raise EvaluationError('EMBEDDING_WORKER_EXITED')
        result = json.loads(line)
        if result['status'] not in ('OK','READY'):
            raise EvaluationError('EMBEDDING_WORKER_ERROR')
        return result

    def _start(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        self.log = (self.directory/'worker.log').open('a',encoding='utf-8')
        self.process = subprocess.Popen(
            [str(ROOT/'retrieval/.venv/Scripts/python.exe'),'-X','utf8','-m','experiment.evaluation.embedding_worker'],
            cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
            text=True, encoding='utf-8', creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        def reader():
            for line in self.process.stdout:
                self.queue.put(line)
            self.queue.put('')
        threading.Thread(target=reader,daemon=True).start()
        if self._line()['revision'] != read(ROOT/'retrieval/config.json')['model_revision']:
            raise EvaluationError('EMBEDDING_REVISION_MISMATCH')

    def embed_texts(self, texts, **kwargs):
        if not texts or any(not t.strip() for t in texts):
            raise EvaluationError('EMPTY_EMBEDDING_INPUT')
        config = read(ROOT/'retrieval/config.json')
        key = fingerprint({'texts':texts,'revision':config['model_revision'],'dtype':'float32','batch':config['document_batch_size']})
        path = self.directory/(key+'.json')
        if path.exists():
            record = read(path)
            if record['request_hash'] != key or record['vectors_hash'] != fingerprint(record['vectors']):
                raise EvaluationError('EMBEDDING_CACHE_CHANGED')
            vectors = record['vectors']
        else:
            if self.process is None:
                self._start()
            self.process.stdin.write(json.dumps({'texts':texts},ensure_ascii=False)+'\n')
            self.process.stdin.flush()
            vectors = self._line()['vectors']
            save(path,{'request_hash':key,'texts':texts,'vectors':vectors,'vectors_hash':fingerprint(vectors),'revision':config['model_revision']})
        array = np.asarray(vectors)
        if array.shape != (len(texts),config['embedding_dimension']) or not np.isfinite(array).all() or (np.linalg.norm(array,axis=1)<=0).any():
            raise EvaluationError('INVALID_EMBEDDING_VECTORS')
        self.last_vectors.update(zip(texts,vectors))
        return vectors

    def embed_text(self,text,**kwargs):
        self.last_query_vector = self.embed_texts([text])[0]
        return self.last_query_vector

    async def aembed_text(self,text,**kwargs):
        return self.embed_text(text)

    async def aembed_texts(self,texts,**kwargs):
        self.last_response_vectors = self.embed_texts(texts)
        return self.last_response_vectors

    def close(self):
        if self.process:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=15)
        if self.log:
            self.log.close()

