"""Pinned BGE-M3 dense encoder. No network requests during inference."""
from __future__ import annotations

import os
from .common import local_path, read_json, check_files


def configure_runtime(config):
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    import torch
    import faiss
    torch.set_num_threads(config['cpu_threads'])
    if torch.get_num_interop_threads() != config['interop_threads']:
        torch.set_num_interop_threads(config['interop_threads'])
    torch.manual_seed(config['seed'])
    torch.use_deterministic_algorithms(True)
    torch.set_float32_matmul_precision('highest')
    faiss.omp_set_num_threads(config['cpu_threads'])


class DenseEncoder:
    def __init__(self, config, verify=True):
        if config['device'] != 'cpu' or config['dtype'] != 'float32':
            raise ValueError('This experiment requires CPU float32 embeddings')
        self.config = config
        self.lock = read_json(local_path(config['model_lock']))
        if (self.lock['model_id'], self.lock['revision']) != (config['model_id'], config['model_revision']):
            raise ValueError('Embedding model revision mismatch')
        if verify:
            check_files(local_path(config['model_path']), self.lock['files'])
        configure_runtime(config)
        import torch
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(
            str(local_path(config['model_path'])), device='cpu', local_files_only=True,
            trust_remote_code=False,
            model_kwargs={'torch_dtype': torch.float32, 'attn_implementation': config['attention'],
                          'use_safetensors': False, 'weights_only': True})
        self.model.float().eval()
        if self.model.get_sentence_embedding_dimension() != config['embedding_dimension']:
            raise ValueError('Unexpected embedding dimension')
        if self.model.max_seq_length != config['max_input_tokens']:
            raise ValueError('Unexpected model input limit')
        pooling = self.model[1]
        if not pooling.pooling_mode_cls_token or pooling.pooling_mode_mean_tokens:
            raise ValueError('The model must use CLS pooling')
        if any(p.device.type != 'cpu' or p.dtype != torch.float32 for p in self.model.parameters()):
            raise ValueError('Model dtype/device does not match the experiment')

    def token_lengths(self, texts):
        encoded = self.model.tokenizer(texts, add_special_tokens=True, truncation=False,
                                       padding=False, return_attention_mask=False,
                                       return_token_type_ids=False)
        return [len(ids) for ids in encoded['input_ids']]

    def encode(self, texts):
        import numpy as np
        import faiss
        if not texts or any(not isinstance(t, str) or not t.strip() for t in texts):
            raise ValueError('Embedding input must contain nonempty text')
        lengths = self.token_lengths(texts)
        if max(lengths) > self.config['max_input_tokens']:
            raise ValueError('Input exceeds the BGE-M3 token limit; truncation is disabled')
        # Encode plain text with the model's published CLS + Normalize modules.
        vectors = self.model.encode(texts, batch_size=self.config['document_batch_size'],
                                    show_progress_bar=False, convert_to_numpy=True,
                                    precision='float32', normalize_embeddings=False,
                                    device='cpu', prompt='')
        vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        if vectors.shape != (len(texts), self.config['embedding_dimension']):
            raise ValueError('Invalid embedding shape')
        if not np.isfinite(vectors).all() or (np.linalg.norm(vectors, axis=1) <= 0).any():
            raise ValueError('Invalid embedding values')
        faiss.normalize_L2(vectors)
        return vectors
