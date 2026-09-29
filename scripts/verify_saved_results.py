"""Run the original source/arithmetic verifier, saving a separate local report."""
import importlib.util
import json
import sys
from artifact_io import ROOT


def main():
    sys.path.insert(0, str(ROOT))
    source = ROOT / 'experiment/revisions/20260929-v2/verify_results.py'
    spec = importlib.util.spec_from_file_location('preserved_results_verifier', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original_report = source.parent / 'verification.json'
    output = ROOT / 'validation/local/saved-results-verification.json'
    def save_report(path, value):
        if path.resolve() != original_report.resolve():
            raise ValueError('Unexpected verifier write')
        output.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
        output.write_bytes(text.replace('\n', '\r\n').encode('utf-8'))
    # Redirect its one report write; all checks and original inputs are unchanged.
    module.save = save_report
    module.verify()


if __name__ == '__main__':
    main()
