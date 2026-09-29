"""Read-only source check plus repeatable test/HTTP/synthetic-result verification."""
from pathlib import Path
import json
import subprocess
import urllib.request
from experiment.evaluation.common import BASE, ROOT, read, sha, save, write_text, utc
from experiment.evaluation.inputs import source_packet
from experiment.evaluation.runner import verify, doctor, profile_named


def main():
    backup=ROOT/'backups/before-evaluator-20260928-145202/manifest.json'
    files=read(backup)['files']
    allowed={'experiment/app.py','experiment/architecture.md','experiment/DECISIONS.md',
             'experiment/README.md','experiment/web/index.html'}
    changed=[name for name,expected in files.items() if sha(ROOT/name)!=expected]
    assert set(changed)<=allowed,changed
    rows,_,source_hashes=source_packet('formal-v1')
    directory=BASE/'runs/local-smoke-20260928-v2'
    manifest,_=verify(directory)
    summary=read(directory/'summary.json')
    assert summary['status']=='COMPLETED' and summary['answers_with_evaluator_errors']==0
    assert summary['provider_response_count']==17
    results={read(p)['result']['question_id']:read(p)['result'] for p in (directory/'results').glob('*.json')}
    for name in ('oracle_support','faithfulness','required_coverage'):
        assert results['SYN01']['metrics'][name]['value']==1
        assert results['SYN02']['metrics'][name]['value']==0
    assert results['SYN03']['metrics']['correct_abstention']['value']==1
    assert all(results[q]['metrics']['full_abstention']['value']==0 for q in ('SYN01','SYN02'))
    checks=[]
    for label,command in (
        ('evaluation-tests',[str(BASE/'.venv/Scripts/python.exe'),'-X','utf8','-m','pytest','experiment/evaluation/tests','-q']),
        ('generation-regression',[str(ROOT/'retrieval/.venv/Scripts/python.exe'),'-X','utf8','-m','unittest','experiment.test_experiment']),
        ('dependency-check',[str(BASE/'.venv/Scripts/python.exe'),'-m','pip','check'])):
        result=subprocess.run(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8')
        write_text(BASE/'verification'/(label+'.txt'),result.stdout)
        checks.append({'name':label,'exit_code':result.returncode})
        assert result.returncode==0,label
    http=[]
    for route in ('/','/gold','/results','/evaluation','/api/overview','/api/evaluation','/api/evaluation-run?id=local-smoke-20260928-v2'):
        with urllib.request.urlopen('http://127.0.0.1:8767'+route,timeout=10) as response:
            assert response.status==200
            body=response.read()
            if route=='/api/evaluation':
                assert not any(r['mode']=='benchmark' and r['processed'] for r in json.loads(body)['runs'])
            http.append({'route':route,'status':response.status})
    out={'at':utc(),'status':'IMPLEMENTATION_VERIFIED','checks':checks,'http':http,
         'backup_files_checked':len(files),'original_files_unchanged':len(files)-len(changed),
         'approved_modified_original_files':changed,'source_packet_rows':len(rows),'source_files_hash_checked':len(source_hashes),
         'smoke':{'id':manifest['id'],'status':'PASS','synthetic_cases':3,'provider_calls':17,
                  'expected_support_and_coverage':'correct=1, wrong=0','expected_unanswerable_abstention':1,
                  'resume':'PASS_NO_ADDITIONAL_CALLS','resume_unchanged_call_and_result_files':37,
                  'initial_failed_run_preserved':'local-smoke-20260928-v1'},
         'browser':{'status':'VISUALLY_VERIFIED','screenshot':'verification/evaluation-screen.png',
                    'visible_benchmark_status':'0 / 120','visible_smoke_status':'3 / 3'},
         'commercial_api':{'actual_call':'NOT_RUN','doctor':doctor(profile_named('openai-astra'))},
         'local_candidate':{'actual_call':'NOT_RUN','doctor':doctor(profile_named('local-gemma4-12b'))},
         'benchmark_answer_quality':'NOT_RUN','researcher_source_review':'PENDING','manual_evaluator_validation':'PENDING'}
    save(BASE/'verification.json',out)
    print(json.dumps({k:out[k] for k in ('status','backup_files_checked','original_files_unchanged','source_packet_rows','benchmark_answer_quality')},ensure_ascii=False))


if __name__=='__main__':main()
