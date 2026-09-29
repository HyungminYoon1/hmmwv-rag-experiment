"""Run under retrieval/.venv; expose only pinned local BGE embeddings over stdio."""
import contextlib
import json
import sys
from .common import ROOT, read


def main():
    output = sys.stdout
    with contextlib.redirect_stdout(sys.stderr):
        from retrieval.model import DenseEncoder
        encoder = DenseEncoder(read(ROOT/'retrieval/config.json'))
    print(json.dumps({'status':'READY','revision':encoder.config['model_revision']}), file=output, flush=True)
    for line in sys.stdin:
        try:
            request = json.loads(line)
            with contextlib.redirect_stdout(sys.stderr):
                vectors = encoder.encode(request['texts']).tolist()
            reply = {'status':'OK', 'vectors':vectors}
        except Exception as error:
            reply = {'status':'ERROR','error_type':type(error).__name__}
        print(json.dumps(reply, allow_nan=False), file=output, flush=True)


if __name__ == '__main__':
    main()

