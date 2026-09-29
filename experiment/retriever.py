"""One resident, isolated search process; JSON IPC and bounded waits."""
import json, queue, subprocess, sys, threading
from .io import BASE, ROOT

class Retriever:
    def __init__(self):
        self.errors=(BASE/'reports'/'worker-stderr.log').open('a',encoding='utf-8')
        self.proc=subprocess.Popen([sys.executable,'-X','utf8','-m','experiment.worker'],cwd=ROOT,
          stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.errors,text=True,encoding='utf-8',bufsize=1,
          creationflags=subprocess.CREATE_NO_WINDOW)
        self.lines=queue.Queue()
        def read():
            for line in self.proc.stdout:self.lines.put(line)
            self.lines.put(None)
        threading.Thread(target=read,daemon=True).start()
        self.initial=self.receive(240)
        if not self.initial.get('ready'):raise RuntimeError('Search worker did not become ready')
    @property
    def pid(self):return self.proc.pid
    def receive(self,timeout):
        line=self.lines.get(timeout=timeout)
        if line is None:raise RuntimeError('Search worker exited')
        data=json.loads(line)
        if data.get('error'):raise RuntimeError(data['error'])
        return data
    def search(self,question):
        self.proc.stdin.write(json.dumps({'question':question},ensure_ascii=False)+'\n');self.proc.stdin.flush()
        return self.receive(120)
    def close(self):
        if self.proc.poll() is None:
            self.proc.stdin.write('{"stop": true}\n');self.proc.stdin.flush()
            try:self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:self.proc.terminate();self.proc.wait(timeout=10)
        self.errors.close()
