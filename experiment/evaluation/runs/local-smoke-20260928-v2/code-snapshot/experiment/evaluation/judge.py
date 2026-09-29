"""Persistent per-stage attempts: at most three calls, including after resume."""
import asyncio
from pathlib import Path
from ragas.llms.base import InstructorBaseRagasLLM
from .common import EvaluationError, read, save, fingerprint, safe_error, utc
from .providers import SYSTEM, strict_schema


def save_attempt(path,record):
    record['record_hash']=fingerprint({k:v for k,v in record.items() if k!='record_hash'})
    save(path,record)


class Journal:
    def __init__(self, directory, transport, identity):
        self.directory = Path(directory)
        self.transport = transport
        self.identity = identity

    async def ask(self, key, prompt, model, validator=None):
        directory = self.directory / key
        request = {'prompt':prompt, 'system':SYSTEM, 'schema':strict_schema(model), 'identity':self.identity}
        request_hash = fingerprint(request)
        request_file = directory / 'request.json'
        if request_file.exists():
            if read(request_file)['request_hash'] != request_hash:
                raise EvaluationError('CACHED_REQUEST_MISMATCH')
        else:
            save(request_file, {'request_hash':request_hash, **request})
        existing = sorted(directory.glob('attempt-*.json'))
        for path in existing:
            record = read(path)
            if record.get('record_hash')!=fingerprint({k:v for k,v in record.items() if k!='record_hash'}):
                raise EvaluationError('CACHED_ATTEMPT_CONTENT_CHANGED')
            if record['request_hash'] != request_hash:
                raise EvaluationError('CACHED_ATTEMPT_MISMATCH')
            if record['status'] == 'OK':
                result = model.model_validate(record['parsed'], strict=True)
                if validator:
                    validator(result)
                return result
        for attempt in range(len(existing)+1, 4):
            path = directory / f'attempt-{attempt}.json'
            record = {'attempt':attempt, 'request_hash':request_hash, 'started_at':utc(), 'status':'STARTED'}
            save_attempt(path, record)
            try:
                response = await self.transport.send(prompt, model)
                record['provider'] = response
                save_attempt(path, record)
                if response.get('model_consistent') is False:
                    raise EvaluationError('RETURNED_MODEL_CHANGED')
                if not response['complete']:
                    raise EvaluationError('INCOMPLETE_PROVIDER_OUTPUT')
                result = model.model_validate_json(response['text'], strict=True)
                if validator:
                    validator(result)
                record.update(status='OK', parsed=result.model_dump(mode='json'), ended_at=utc())
                save_attempt(path, record)
                return result
            except Exception as error:
                record.update(status='EVAL_ERROR', error=safe_error(error), ended_at=utc())
                save_attempt(path, record)
                if isinstance(error,EvaluationError) and error.code=='RETURNED_MODEL_CHANGED':
                    raise
                if isinstance(error, EvaluationError) and error.code in ('API_KEY_NOT_CONFIGURED','CONSERVATIVE_CONTEXT_LIMIT_EXCEEDED'):
                    break
                if getattr(error, 'status_code', None) in (401,403,404):
                    break
                if attempt < 3:
                    await asyncio.sleep(min(attempt,2))
        raise EvaluationError('STAGE_ATTEMPTS_EXHAUSTED')


class StageLLM(InstructorBaseRagasLLM):
    def __init__(self, journal, prefix, validator=None):
        self.journal, self.prefix, self.validator = journal, prefix, validator
        self.count = 0
        self.outputs = []

    async def agenerate(self, prompt, response_model):
        self.count += 1
        result = await self.journal.ask(f'{self.prefix}-{self.count}', prompt, response_model, self.validator)
        self.outputs.append(result.model_dump(mode='json'))
        return result

    def generate(self, prompt, response_model):
        return asyncio.run(self.agenerate(prompt,response_model))

