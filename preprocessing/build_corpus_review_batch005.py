"""Freeze PDF-reviewed extraction repairs; replay still uses the original parser.

PDF 133 is an explicit region retranscription, not a claimed spelling-only edit.
Its original mixed OCR remains in units-before and in the cumulative ledger.
"""
from pathlib import Path
import copy
import json
import pymupdf
import correct_extraction as io

PARENT = io.BASE / 'corrections/batch-004/correction-log.json'
OUT = io.BASE / 'corrections/batch-005'

# Literal box text transcribed from PDF 133. No arrow is expanded into a sentence.
BOXES_133 = [
 ('header', [37,76,542,94], 'STARTABILITY\nDIAGNOSTIC FLOWCHART'),
 ('start', [210,83,309,114], 'START'),
 ('1-id', [164,126,197,143], '1'),
 ('1-known', [42,128,151,207], 'KNOWN INFO\nNOTHING'),
 ('1-possible', [42,207,152,291], 'POSSIBLE PROBLEMS\nSTARTER SYSTEM\nBATTERIES\nFUEL SYSTEM\nAIR INTAKE/EXHAUST\nGLOWPLUGS\nENG MECHANICAL'),
 ('1-question', [166,143,357,241], 'DOES THE ENGINE CRANK\nNORMALLY? (STARTER ENGAGES,\nCRANKS ENGINE AT LEAST\n100 RPM, STARTER DISENGAGES)'),
 ('1-options', [341,128,501,206], 'TEST OPTIONS\n1. LISTEN\n2. STE/ICE TEST 10 (Page 2-734)\n(FOR RPM)'),
 ('1-reason', [344,206,501,270], 'REASON FOR QUESTION\nIf the engine cranks normally,\nthe battery and starter are\ngood enough to start the engine.'),
 ('1-no', [208,264,227,280], 'NO'),
 ('1-exit', [247,252,340,296], 'GO TO\nSTARTER CIRCUIT,\nPage 2-261'),
 ('1-yes', [168,283,202,301], 'YES'),
 ('2-id', [165,321,199,337], '2'),
 ('2-known', [42,324,153,404], 'KNOWN INFO\nSTARTER SYSTEM OK\nBATTERIES OK\nENGINE NOT LOCKED'),
 ('2-possible', [42,403,153,486], 'POSSIBLE PROBLEMS\nFUEL SYSTEM\nINTAKE AIR/EXHAUST\nGLOWPLUGS\nCOMPRESSION'),
 ('2-question', [167,337,361,435], 'RUN THE FUEL SYSTEM\nTESTS. RETURN HERE.'),
 ('2-options', [342,322,502,399], 'TEST OPTIONS\nFUEL SYSTEM TESTS,\n(Page 2-95)'),
 ('2-reason', [344,398,502,465], "REASON FOR TESTS\nIf the fuel system doesn't\nwork, the vehicle won't\nstart"),
 ('3-id', [165,522,200,539], '3'),
 ('3-known', [42,524,155,606], 'KNOWN INFO\nENGINE NOT LOCKED\nBATTERIES OK\nSTARTING SYSTEM OK\nFUEL SYSTEM OK'),
 ('3-possible', [42,605,155,688], 'POSSIBLE PROBLEMS\nFUEL SYSTEM\nINTAKE AIR/EXHAUST\nCOMPRESSION'),
 ('3-question', [167,539,361,638], 'RUN THE INTAKE AIR/EXHAUST\nTESTS. RETURN HERE.'),
 ('3-options', [342,523,505,602], 'TEST OPTIONS\nINTAKE AIR/EXHAUST TESTS,\n(Page 2-137)'),
 ('3-reason', [346,601,504,671], 'REASON FOR TESTS\nThe intake air/exhaust system\ntests are easy to run and can\ncause starting problems.'),
 ('3-exit', [140,716,228,749], 'GO TO 4,\nPage 2-44'),
]


def build():
    if OUT.exists():
        raise ValueError('Use a fresh correction batch, never overwrite a frozen one')
    ledger = json.loads(PARENT.read_text(encoding='utf-8'))
    original = {r['id']: r for r in io.source_records(io.check_inputs(ledger))}
    patches = []
    def add(rid, before, after, box, reason, kind='EXTRACTION_CORRECTION'):
        raw = original[rid]['text']
        assert raw.count(before) == 1, (rid, before)
        start = raw.index(before)
        patches.append({'id':f'FIX-V5-{len(patches)+1:04d}', 'record_id':rid,
                        'pdf_page':original[rid]['pdf_page'], 'start':start, 'end':start+len(before),
                        'before':before, 'after':after, 'bbox':box, 'render_clip':box,
                        'reason':reason, 'kind':kind,
                        'source_check':'CODEX_PDF_VISUAL_CHECK', 'human_review':'NOT_PERFORMED'})
    add('P0133:ocr', original['P0133:ocr']['text'], '\n\n'.join(b[2] for b in BOXES_133),
        [35,75,545,754], '박스 간 문장이 섞이고 문자가 크게 오독된 페이지를 PDF의 개별 박스별로 다시 전사했다. 화살표 경로는 문장으로 만들지 않았으며 NO/YES는 별도 표식으로 보존했다.',
        'PDF_REGION_RETRANSCRIPTION')
    for number,spaces,y in [(1,12,349),(5,10,417)]:
        old=f'{number}. Position shift lever in'+(' '*spaces)
        add('P0517:native',old,f'{number}. Position shift lever in "Ⓓ" ',[142,y-4,578,y+14],
            'PDF의 따옴표 안 원형 D 기호를 Unicode CIRCLED LATIN CAPITAL LETTER D(Ⓓ)로 복원했다. 일반 D와 구별하며 overdrive라는 설명을 새로 추가하지 않았다.')
    add('P0517:ocr','in "©" (overdrive)','in "Ⓓ" (overdrive)',[142,345,578,365],
        '저작권 기호로 오독한 원형 D를 PDF와 대조하여 복원했다.')
    add('P0517:ocr','in ‘and with','in "Ⓓ" and with',[142,413,578,433],
        '5번 절차의 원형 D와 주변 따옴표·공백을 PDF와 대조하여 복원했다.')
    add('P0124:native','LUBRlCATlON','LUBRICATION',[75,364,198,378],
        '대문자 제목 I가 소문자 l로 추출된 두 문자를 PDF에서 확인했다.')
    for name,value,y in [('DRIVETRAIN','2-79',674),('AMBULANCE ELECTRICAL','2-497',687.5),
                         ('AMBULANCE MECHANICAL','2-693',701),('WINCH','2-715',714.5),
                         ('DCA TROUBLESHOOTING','2-723',728)]:
        add('P0124:native',name,name+'\n'+value,[74,y-2,318,y+12],
            'PDF에는 존재하지만 body 추출에서 빠진 PAGE 열의 값을 같은 행에 복원했다. 2-79를 포함하여 인쇄값을 그대로 보존했다.',
            'MISSING_PRINTED_CELL')
    OUT.mkdir(parents=True);(OUT/'evidence').mkdir()
    for p in ledger['corrections']:
        dest=OUT/p['evidence_crop'];dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes((PARENT.parent/p['evidence_crop']).read_bytes())
    with pymupdf.open(io.ROOT/ledger['inputs']['pdf']['path']) as pdf:
        for p in patches:
            rel=f"evidence/{p['id']}.png"
            pdf[p['pdf_page']-1].get_pixmap(clip=pymupdf.Rect(p['render_clip']),dpi=180,alpha=False).save(OUT/rel)
            p.update(evidence_crop=rel,evidence_sha256=io.sha(OUT/rel))
    ledger['corrections'] += patches
    ledger['batch']='batch-005-corpus-source-review'
    ledger['parent']={'path':PARENT.relative_to(io.ROOT).as_posix(),'sha256':io.sha(PARENT),
                      'preserved_corrections':len(ledger['corrections'])-len(patches)}
    ledger['additional_review']={'date':'2026-09-24','pages':[124,133,517],
         'evaluated_questions_read':False,'glyph_policy':'Circled D is encoded as U+24B9, distinct from D.',
         'region_retranscription_pages':[133],'source_anomalies_preserved':['PDF 124: 2-11','PDF 124: 2-79','PDF 124: 21 system tests versus 22 rows']}
    io.validate_ledger(list(original.values()),ledger)
    (OUT/'correction-log.json').write_bytes(io.json_bytes(ledger))
    (OUT/'page-133-regions.json').write_bytes(io.json_bytes(BOXES_133))
    print(json.dumps({'added':len(patches),'cumulative':len(ledger['corrections'])}))


if __name__ == '__main__': build()
