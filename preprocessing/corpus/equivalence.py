"""Whitespace-only equivalence with explicit source character witnesses.

Numbers, punctuation, case and negative/conditional words are never normalized.
Geometry proposes candidates; this module proves the actual text containment.
"""
from __future__ import annotations
import re


def normalized(text):
    chars=[]; positions=[]
    for match in re.finditer(r'\s+|\S',text):
        value=match.group()
        chars.append(' ' if value.isspace() else value)
        positions.append((match.start(),match.end()))
    left=0;right=len(chars)
    while left<right and chars[left]==' ':left+=1
    while right>left and chars[right-1]==' ':right-=1
    return ''.join(chars[left:right]),positions[left:right]


def norm(text):
    return normalized(text)[0]


def token_edge(char):
    # A numeric sign, decimal point, range or identifier separator is part of
    # the value, not a free punctuation boundary (10 must not match -10/10.0).
    return char.isalnum() or char in '._/+-−±°%'


def witness(store,source,targets):
    """Find the complete source text inside ordered literal target spans.

    Returns character refs, not a similarity score. Interior word matches are
    disallowed so a short number/identifier cannot match part of another value.
    """
    wanted=norm(source['text'])
    if not wanted:return None
    combined='';offsets=[]
    for target in targets:
        if combined:combined+='\n'
        a=len(combined);combined+=target['text'];offsets.append((a,len(combined),target))
    actual,positions=normalized(combined)
    cursor=0
    while True:
        at=actual.find(wanted,cursor)
        if at<0:return None
        end=at+len(wanted);cursor=at+1
        if at and token_edge(wanted[0]) and token_edge(actual[at-1]):continue
        if end<len(actual) and token_edge(wanted[-1]) and token_edge(actual[end]):continue
        a,b=positions[at][0],positions[end-1][1]
        refs=[]
        for x,y,target in offsets:
            lo,hi=max(a,x),min(b,y)
            if lo<hi:
                refs.append(store.ref(target['record_id'],target['start']+lo-x,target['start']+hi-x))
        valid=True
        for ref in refs:
            full=getattr(store,'records',{}).get(ref['record_id'],{}).get('text')
            if full is None:continue
            lo,hi=ref['start'],ref['end']
            if lo and token_edge(full[lo]) and token_edge(full[lo-1]):valid=False
            if hi<len(full) and token_edge(full[hi-1]) and token_edge(full[hi]):valid=False
        if valid and norm(' '.join(r['text'] for r in refs))==wanted:return refs


def proof(source,targets,kind='WHITESPACE_EQUIVALENT',rule_ids=None):
    return {'source':source,'targets':targets,'kind':kind,'rule_ids':list(rule_ids or []),
            'normalization':'whitespace-only-v1'}
