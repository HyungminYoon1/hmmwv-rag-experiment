"""Read-only current-release data; retain all historical evaluation records."""
from artifact_io import ROOT, read
from experiment import webdata
from experiment.evaluation import view

def current():
    return read(ROOT / 'experiment/current-release.json')

def evaluation_overview():
    data = view.overview()
    active = current()
    data['current'] = active
    for row in data['runs']:
        row['is_current'] = row['id'] == active['evaluation_run']
        row['is_historical'] = row['mode'] == 'benchmark' and not row['is_current']
    data['runs'].sort(key=lambda r: (r['is_current'], r['created_at']), reverse=True)
    return data

def evaluation_run(run_id):
    data = view.run_data(run_id)
    data['current'] = current()
    return data

def overview():
    data = webdata.overview()
    data['current'] = current()
    data['gold'] = read(ROOT / 'experiment' / current()['gold_version'] / 'validation.json')
    return data

def gold_rows(version=None):
    version = version or current()['gold_version']
    if version not in ('gold-v1', 'gold-v2', 'gold-v3'):
        raise ValueError('Unknown gold version')
    return read(ROOT / 'experiment' / version / 'questions.json')
