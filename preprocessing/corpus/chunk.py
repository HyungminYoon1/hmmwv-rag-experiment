"""Bounded, character-preserving windows using the pinned local tokenizer."""
from __future__ import annotations
from functools import lru_cache
from tokenizers import Tokenizer


class ChunkingError(ValueError):
    pass


class Chunker:
    def __init__(self, tokenizer_path, max_tokens=500, overlap=100):
        if not (0 < overlap < max_tokens):
            raise ValueError('Require 0 < overlap < max_tokens')
        self.tokenizer = Tokenizer.from_file(str(tokenizer_path))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        self.max_tokens, self.overlap = max_tokens, overlap

    @lru_cache(maxsize=32768)
    def count(self, text):
        return len(self.tokenizer.encode(text, add_special_tokens=False).ids)

    def end_for_budget(self, prefix, body, start):
        remaining=body[start:]
        if self.count(prefix+remaining) <= self.max_tokens:
            return len(body)
        # Offsets identify real Python-character boundaries, not partial UTF-8 bytes.
        encoded=self.tokenizer.encode(remaining, add_special_tokens=False)
        budget=max(1, self.max_tokens-self.count(prefix))
        end=start+encoded.offsets[min(budget,len(encoded.offsets))-1][1]
        end=max(start+1, min(end,len(body)))
        # Token counts of concatenations are not assumed additive or monotonic.
        while end > start and self.count(prefix+body[start:end]) > self.max_tokens:
            end-=1
        if end <= start:
            raise ChunkingError('Prefix leaves no room for the next character')
        while end < len(body) and self.count(prefix+body[start:end+1]) <= self.max_tokens:
            end+=1
        return end

    def overlap_start(self, body, start, end):
        # Scan suffixes shortest-first. This implements the actual minimal
        # character suffix rule even for non-monotonic BPE prefix behavior.
        for candidate in range(end-1, start-1, -1):
            tokens=self.count(body[candidate:end])
            if tokens >= self.overlap:
                if candidate == start:
                    raise ChunkingError('Overlap consumes the whole previous body; no forward progress')
                return candidate,tokens
        raise ChunkingError('Body budget is smaller than the required overlap')

    def split(self, body, prefix=''):
        if not body.strip():
            return []
        if self.count(prefix) >= self.max_tokens:
            raise ChunkingError('Required title/conditions exhaust the token budget')
        windows=[]; start=0; previous_end=0; overlap_tokens=0
        while start < len(body):
            end=self.end_for_budget(prefix,body,start)
            if end <= previous_end:
                raise ChunkingError('Window adds no new source characters')
            text=prefix+body[start:end]
            windows.append({'body_start':start,'body_end':end,'text':text,
                            'token_count':self.count(text),'overlap_tokens':overlap_tokens,
                            'overlap_chars':max(0,previous_end-start)})
            if end==len(body):
                break
            start,overlap_tokens=self.overlap_start(body,start,end)
            previous_end=end
        return windows
