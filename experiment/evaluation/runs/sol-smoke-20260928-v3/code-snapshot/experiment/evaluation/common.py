"""Evaluation artifacts and credentials-safe diagnostics (UTF-8, CRLF)."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import uuid
import time

BASE = Path(__file__).resolve().parent
EXPERIMENT = BASE.parent
ROOT = EXPERIMENT.parent
SECRET_NAMES = ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GOOGLE_API_KEY')


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(Path(path).read_bytes())


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def fingerprint(value):
    return digest(canonical(value).encode('utf-8'))


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def redact(value):
    if isinstance(value, str):
        for name in SECRET_NAMES:
            secret = os.environ.get(name)
            if secret:
                value = value.replace(secret, '[REDACTED]')
        return re.sub(r'\bsk-[A-Za-z0-9_-]{12,}', '[REDACTED]', value)
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, dict):
        return {k: ('[REDACTED]' if k.lower() in ('api_key', 'authorization', 'secret', 'access_token') else redact(v))
                for k, v in value.items()}
    return value


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = text.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\r\n')
    path.write_bytes(text.encode('utf-8'))


def save(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    write_text(tmp, json.dumps(redact(value), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n')
    for attempt in range(10):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            if attempt==9:
                raise EvaluationError('LOCAL_ARTIFACT_IO_ERROR') from None
            time.sleep(min(0.05 * (2 ** attempt),0.5))


def valid_id(value):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,80}', value):
        raise ValueError('Invalid artifact ID')
    return value


def safe_error(error):
    # SDK error strings can echo request headers or credentials. Never persist them.
    result = {'type': type(error).__name__}
    status = getattr(error, 'status_code', None)
    if isinstance(status, int):
        result['http_status'] = status
    if isinstance(error, EvaluationError):
        result['code'] = error.code
    return result


class EvaluationError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code

