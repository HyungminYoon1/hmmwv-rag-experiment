"""Read-only checks for the recorded Windows/NVIDIA execution profile."""
import argparse
import json
import os
from pathlib import Path
import platform
import sys
import urllib.request
from artifact_io import ROOT, read


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ollama', action='store_true', help='Also check the already started local server/model; no generation')
    args = parser.parse_args()
    checks = {'windows': os.name == 'nt', 'python_3_11_9': platform.python_version() == '3.11.9'}
    info = {'python': platform.python_version(), 'platform': platform.platform()}
    config = read(ROOT / 'retrieval/config.json')
    checks['nvml_dll'] = Path('C:/Windows/System32/nvml.dll').is_file()
    if os.name == 'nt':
        sys.path.insert(0, str(ROOT))
        from retrieval.cpu_affinity import windows_cpu_sets
        rows = {r['logical']: r for r in windows_cpu_sets() if r['group'] == 0}
        selected = config['cpu_logical_processors']
        checks['configured_distinct_performance_cores'] = bool(rows) and set(selected) <= set(rows) and len({rows[i]['core'] for i in selected if i in rows}) == len(selected) and all(rows[i]['efficiency'] == max(r['efficiency'] for r in rows.values()) for i in selected if i in rows)
        info['selected_logical_cpus'] = selected
    for name in ['preprocessing/output/corpus-v6-final/manifest.json', 'retrieval/indexes/bge-m3-v1/manifest.json',
                 'retrieval/models/bge-m3-5617a9f/pytorch_model.bin', 'experiment/models/Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf']:
        checks[name] = (ROOT / name).is_file()
    if args.ollama:
        try:
            def get(path):
                with urllib.request.urlopen('http://127.0.0.1:11435' + path, timeout=5) as r:
                    return json.load(r)
            info['ollama_version'] = get('/api/version')['version']
            checks['ollama_0_34_1'] = info['ollama_version'] == '0.34.1'
            configured = read(ROOT / 'experiment/config.json')['model']
            tags = get('/api/tags')['models']
            checks['registered_model'] = any(r['name'] == configured for r in tags)
        except Exception as exc:
            checks['ollama_connection'] = False
            info['ollama_error_type'] = type(exc).__name__
    result = {'status': 'PASS' if all(checks.values()) else 'NOT_READY', 'checks': checks, 'environment': info,
              'scope': 'Recorded platform requirements; not a new experiment or model inference.'}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
