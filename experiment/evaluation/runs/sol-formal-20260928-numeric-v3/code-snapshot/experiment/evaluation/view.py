"""Read-only stdlib view adapter; does not import Ragas or instantiate a judge."""
from .common import BASE, EXPERIMENT, read, valid_id
from .report import completed


def overview():
    runs=[read(p) for p in (BASE/'runs').glob('*/summary.json')]
    return {'benchmark_answers':read(EXPERIMENT/'runs/formal-v1/evaluation-inputs/manifest.json')['answers'],
            'runs':sorted(runs,key=lambda r:r['created_at'],reverse=True),
            'configured_profiles':[{'id':p.stem,**{k:read(p).get(k) for k in ('provider','model','smoke_only')}}
                                   for p in sorted((BASE/'profiles').glob('*.json'))]}


def run_data(run_id):
    directory=BASE/'runs'/valid_id(run_id)
    manifest=read(directory/'manifest.json')
    return {'summary':read(directory/'summary.json'),'results':completed(directory,manifest)}
