"""Download the pinned public model; search and indexing remain offline."""
from __future__ import annotations

from .common import ROOT, load_config, local_path, sha, write_json, read_json, check_files

FILES = ['1_Pooling/config.json', 'config.json', 'config_sentence_transformers.json',
         'modules.json', 'sentence_bert_config.json', 'sentencepiece.bpe.model',
         'special_tokens_map.json', 'tokenizer.json', 'tokenizer_config.json',
         'pytorch_model.bin', 'README.md']


def main():
    from huggingface_hub import hf_hub_download
    config = load_config()
    directory = local_path(config['model_path'])
    lock_path = local_path(config['model_lock'])
    if lock_path.exists():
        lock = read_json(lock_path)
        if lock['revision'] != config['model_revision']:
            raise ValueError('Existing model lock has another revision')
        check_files(directory, lock['files'])
        print('Pinned model already verified.', flush=True)
        return
    directory.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        print('Downloading: ' + name, flush=True)
        hf_hub_download(config['model_id'], name, revision=config['model_revision'],
                        local_dir=directory, token=False)
    lock = {'schema': 1, 'model_id': config['model_id'], 'revision': config['model_revision'],
            'source': f'https://huggingface.co/{config["model_id"]}/tree/{config["model_revision"]}',
            'files': {name: sha(directory / name) for name in FILES},
            'weight_loading': 'PyTorch weights_only=True; no remote code',
            'network_for_inference': False}
    write_json(lock_path, lock)
    print('Model downloaded and hashed: ' + str(directory.relative_to(ROOT)), flush=True)


if __name__ == '__main__':
    main()
