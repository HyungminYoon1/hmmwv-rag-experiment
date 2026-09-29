"""Recompute the declared AR formula from frozen questions/vectors, with zero model calls."""
import argparse
from copy import deepcopy
from decimal import Decimal, localcontext
import math
from pathlib import Path
from experiment.evaluation.common import BASE, ROOT, read, save, sha, fingerprint, utc, valid_id
from experiment.evaluation.runner import verify
from experiment.evaluation.report import summarize


def reference_cosines(query, vectors):
    qnorm = math.sqrt(math.fsum(x*x for x in query))
    assert qnorm > 0
    floats = [math.fsum(x*y for x,y in zip(query, vector)) /
              (qnorm * math.sqrt(math.fsum(y*y for y in vector))) for vector in vectors]
    with localcontext() as context:
        context.prec = 50
        qd = [Decimal.from_float(float(x)) for x in query]
        qn = sum((x*x for x in qd), Decimal(0)).sqrt()
        decimals = []
        for vector in vectors:
            gd = [Decimal.from_float(float(x)) for x in vector]
            gn = sum((y*y for y in gd), Decimal(0)).sqrt()
            dot = sum((x*y for x,y in zip(qd,gd)), Decimal(0))
            decimals.append(dot/(qn*gn))
    differences = [abs(x-float(y)) for x,y in zip(floats,decimals)]
    assert max(differences) <= 1e-10
    return floats, [str(x) for x in decimals], max(differences)


def recalculate(source_id, target_id):
    source = BASE/'runs'/valid_id(source_id)
    target = BASE/'runs'/valid_id(target_id)
    assert not target.exists(), 'Use a new derived run ID.'
    manifest, packet = verify(source)
    original_summary = read(source/'summary.json')
    assert original_summary['status'] in ('COMPLETED','COMPLETED_WITH_EVAL_ERRORS')
    assert original_summary['processed'] == original_summary['expected'] == len(packet['rows'])
    assert not (source/'run.lock').exists()
    assert 'numerical_recalculation' not in manifest['identity'], 'Derive once from raw evaluation.'
    sources = deepcopy(manifest['identity']['source_hashes'])
    for name in ('manifest.json','inputs.json','summary.json'):
        path=source/name;sources[path.relative_to(ROOT).as_posix()]=sha(path)
    records={}
    for path in sorted((source/'results').glob('*.json')):
        record=read(path);r=record['result']
        assert record['identity_hash']==manifest['identity_hash'] and record['result_hash']==fingerprint(r)
        records[r['attempt_key']]=record;sources[path.relative_to(ROOT).as_posix()]=sha(path)
    embeddings={}
    config=read(source/'code-snapshot/retrieval/config.json')
    for path in sorted((source/'embeddings').glob('*.json')):
        record=read(path)
        assert record['vectors_hash']==fingerprint(record['vectors'])
        assert record['request_hash']==fingerprint({'texts':record['texts'],'revision':config['model_revision'],'dtype':'float32','batch':config['document_batch_size']})
        assert record['revision']==config['model_revision']
        assert len(record['vectors'])==len(record['texts'])
        assert all(len(v)==config['embedding_dimension'] and all(math.isfinite(x) for x in v) for v in record['vectors'])
        embeddings[tuple(record['texts'])]=record
        sources[path.relative_to(ROOT).as_posix()]=sha(path)
    calls={}
    for request_path in sorted((source/'calls').rglob('request.json')):
        request=read(request_path)
        assert request['request_hash']==fingerprint({k:v for k,v in request.items() if k!='request_hash'})
        sources[request_path.relative_to(ROOT).as_posix()]=sha(request_path)
        stage=request_path.parent.relative_to(source/'calls').as_posix()
        for path in sorted(request_path.parent.glob('attempt-*.json')):
            record=read(path)
            assert record['record_hash']==fingerprint({k:v for k,v in record.items() if k!='record_hash'})
            assert record['request_hash']==request['request_hash']
            sources[path.relative_to(ROOT).as_posix()]=sha(path)
            if record['status']=='OK' and stage not in calls:
                calls[stage]=record['parsed']
    calculated=[];changes=[];max_difference=0.0
    for row in packet['rows']:
        key=row['attempt_key'];original=records[key]
        assert original['input_hash']==fingerprint(row)
        result=deepcopy(original['result'])
        if row['type']!='unanswerable' and row['generation_status']=='OK' and row['response'].strip():
            questions=[calls.get(key+'/relevancy-'+str(i)) for i in (1,2,3)]
            if all(questions):
                texts=tuple(q['question'] for q in questions)
                qrecord=embeddings.get((row['user_input'],));grecord=embeddings.get(texts)
                if qrecord and grecord:
                    flags=[q['noncommittal'] for q in questions]
                    assert all(flag in (0,1) for flag in flags)
                    floats,decimals,difference=reference_cosines(qrecord['vectors'][0],grecord['vectors'])
                    max_difference=max(max_difference,difference)
                    score=math.fsum(floats)/3*int(not all(flags))
                    previous={name:deepcopy(result['metrics'][name]) for name in ('ar_raw','ar_report')}
                    old_error=result['errors'].get('answer_relevancy')
                    assert old_error is None or old_error.get('code')=='RAGAS_ALGORITHM_MISMATCH', 'Unexpected error cannot be silently repaired.'
                    audit={'reference_implementation':'python_math_fsum_and_decimal50',
                           'score':score,'questions':questions,'flags':flags,'cosine_similarities':floats,
                           'decimal50_cosines':decimals,'maximum_implementation_difference':difference,
                           'query_vector_hash':fingerprint(qrecord['vectors'][0]),'response_vectors_hash':grecord['vectors_hash'],
                           'original_metrics':previous,'original_error':old_error,'model_calls':0}
                    result['stages']['relevancy_numeric_recalculation']=audit
                    for name in ('ar_raw','ar_report'):
                        result['metrics'][name]={'value':score,'status':'OK_NUMERIC_RECALCULATION'}
                    result['errors'].pop('answer_relevancy',None)
                    changes.append({'attempt_key':key,'old':previous,'new':score,'resolved_error':old_error,
                                    'difference_from_prior_report':None if previous['ar_report']['value'] is None else score-previous['ar_report']['value']})
        for name in result['metrics']:
            if name not in ('ar_raw','ar_report'):assert result['metrics'][name]==original['result']['metrics'][name]
        for name,stage in original['result']['stages'].items():
            assert result['stages'][name]==stage
        calculated.append((row,result))
    script=Path(__file__).resolve();sources[script.relative_to(ROOT).as_posix()]=sha(script)
    identity=deepcopy(manifest['identity']);identity['source_hashes']=sources
    identity['numerical_recalculation']={'source_evaluation':source_id,'source_identity_hash':manifest['identity_hash'],
        'implementation':'math.fsum cosine, validated with Decimal precision 50','script_sha256':sha(script),
        'threshold':1e-10,'apply_to':'all answerable rows with three valid cached questions and vectors','model_calls':0}
    derived=deepcopy(manifest);derived.update(id=target_id,created_at=utc(),identity=identity,identity_hash=fingerprint(identity),
        derivation='NUMERICAL_RECALCULATION_ONLY',source_evaluation=source_id)
    target.mkdir(parents=True)
    for name in identity['code']['files']:
        output=target/'code-snapshot'/name;output.parent.mkdir(parents=True,exist_ok=True)
        output.write_bytes((source/'code-snapshot'/name).read_bytes())
    output=target/'code-snapshot'/script.relative_to(ROOT);output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(script.read_bytes())
    save(target/'manifest.json',derived);save(target/'inputs.json',packet)
    for row,result in calculated:
        save(target/'results'/(row['attempt_key']+'.json'),{'identity_hash':derived['identity_hash'],'input_hash':fingerprint(row),
            'result_hash':fingerprint(result),'at':utc(),'original_result_sha256':sha(source/'results'/(row['attempt_key']+'.json')),'result':result})
    summary=summarize(target)
    save(target/'numerical-recalculation.json',{'source_evaluation':source_id,'derived_evaluation':target_id,
        'at':utc(),'model_calls':0,'recalculated_answers':len(changes),'maximum_implementation_difference':max_difference,
        'source_api_usage':original_summary['usage'],'source_provider_response_count':original_summary['provider_response_count'],
        'other_metrics_unchanged':True,'changes':changes})
    verify(target)
    return {'id':target_id,'status':summary['status'],'processed':summary['processed'],
            'recalculated_answers':len(changes),'model_calls':0,'maximum_implementation_difference':max_difference,
            'answers_with_evaluator_errors':summary['answers_with_evaluator_errors']}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',required=True);parser.add_argument('--id',required=True)
    args=parser.parse_args()
    import json
    print(json.dumps(recalculate(args.source,args.id),ensure_ascii=False,indent=2))
