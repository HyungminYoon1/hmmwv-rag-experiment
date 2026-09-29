"""UTF-8/CRLF artifacts with bounded retry for Windows sharing violations."""
from pathlib import Path
import json, time, uuid
from retrieval.common import ROOT, read_json, read_jsonl, sha, text_sha, write_text
BASE = Path(__file__).resolve().parent

def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    write_text(tmp, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    for attempt in range(20):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            if attempt == 19: raise
            time.sleep(.1)

def utc():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
