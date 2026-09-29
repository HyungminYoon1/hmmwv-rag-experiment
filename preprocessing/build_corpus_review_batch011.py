"""Correct the confirmed page-183 OCR failures and two page-615 word errors."""
import json
import pymupdf
import correct_extraction as io


def main():
    parent=io.BASE/'corrections/batch-010/correction-log.json';out=io.BASE/'corrections/batch-011'
    if out.exists():raise ValueError('Use a new batch')
    ledger=json.loads(parent.read_text(encoding='utf-8'));raw={r['id']:r for r in io.source_records(io.check_inputs(ledger))}
    audit=json.loads((io.BASE/'ocr-structure-review-20260924/full-audit-e/page-0183.json').read_text(encoding='utf-8'))
    rects={r['id']:r['bbox'] for r in audit['rectangles']};regs=[]
    def add(name,box,text):regs.append((name,box,text))
    add('header',[40,86,533,100],'FUEL SYSTEM\nDIAGNOSTIC FLOWCHART')
    add('start',[223,87,303,120],'START')
    texts={
      'B002':'KNOWN INFO','B003':'TEST OPTIONS\nVISUAL INSPECTION, SAMPLED\nWHILE CRANKING OR RUNNING.\nTHIS QUESTION ONLY CHECKS\nTHE SUPPLY OF FUEL IN THE\nTANK AND TESTS TO SEE IF IT IS\nGETTING TO THE INJECTOR\nPUMP. THIS IS NOT A TEST OF\nFUEL PRESSURE.',
      'B004':'NOTHING','B005':'IS THE FUEL SUPPLY AND\nQUALITY O.K.?','B006':'POSSIBLE PROBLEMS',
      'B007':'FUEL LINES\nFUEL FILTER\nFUEL PUMP\nFUEL SOLENOID\nINJECTION PUMP\nINJECTORS',
      'B008':'REASON FOR QUESTION\nWithout a supply of good fuel,\nnone of the components in the\nfuel system can be expected to\nwork properly.',
      'B010':'KNOWN INFO','B011':'TEST OPTIONS\nTRY STARTING THE ENGINE.',
      'B012':'DOES THE ENGINE START\nAND STAY RUNNING?',
      'B013':'FUEL AVAILABLE AND\nNOT CONTAMINATED','B014':'POSSIBLE PROBLEMS',
      'B015':'REASON FOR QUESTION\nIf it starts, you know that there is\nfuel available and the fuel\nsolenoid is working.',
      'B016':'COLD ADVANCE\nGLOWPLUGS\nFUEL LINES\nFUEL FILTER\nFUEL PUMP\nINJECTION PUMP\nFUEL SOLENOID\nRETURN CHECK VALVE',
      'B018':'KNOWN INFO','B019':'TEST OPTIONS\nTRY STARTING THE ENGINE\nWHILE ITS COLD.',
      'B020':'FUEL SOLENOID OK\nFUEL OK','B021':'DOES THE ENGINE START\nEASILY WHEN COLD?',
      'B022':'REASON FOR QUESTION\nProblem may be the cold\nadvance circuit.',
      'B023':'POSSIBLE PROBLEMS','B024':'COLD ADVANCE\nFUEL LINES\nFUEL FILTER\nFUEL PUMP\nINJECTION PUMP\nINJECTORS'}
    for name,text in texts.items():add(name,rects[name],text)
    for step,y,exit_y,yn_y,label,page in [(1,133,260,268,'A','2-104'),(2,330,455,462,'B','2-106'),(3,532,658,665,'C','2-110')]:
        add(f'{step}-id',[167,y,198,y+16],str(step));add(f'{step}-no',[207,yn_y,225,yn_y+18],'NO')
        add(f'{step}-yes',[168,yn_y+21,199,yn_y+41],'YES')
        add(f'{step}-exit',[249,exit_y,335,exit_y+40],f'GO TO {label},\nPage {page}')
    add('next',[139,727,225,756],'GO TO 4,\nPage 2-98')
    out.mkdir();(out/'evidence').mkdir()
    for p in ledger['corrections']:(out/p['evidence_crop']).write_bytes((parent.parent/p['evidence_crop']).read_bytes())
    added=[];regions=[]
    with pymupdf.open(io.ROOT/ledger['inputs']['pdf']['path']) as doc:
        def patch(rid,a,b,after,box,name):
            pn=raw[rid]['pdf_page'];pid='FIX-V11-'+name
            file='evidence/'+pid+'.png';doc[pn-1].get_pixmap(clip=pymupdf.Rect(box),dpi=180,alpha=False).save(out/file)
            p={'id':pid,'record_id':rid,'pdf_page':pn,'start':a,'end':b,'before':raw[rid]['text'][a:b],'after':after,
               'bbox':box,'render_clip':box,'kind':'PDF_REGION_RETRANSCRIPTION' if pn==183 else 'OCR_CHARACTER_ERROR',
               'reason':'PDF 확대 대조로 확인한 추출 오류를 보정했다. 원문 자체의 표현과 철자는 문법적으로 바꾸지 않았다.',
               'source_check':'CODEX_PDF_VISUAL_CHECK','human_review':'NOT_PERFORMED',
               'evidence_crop':file,'evidence_sha256':io.sha(out/file)}
            added.append(p);return p
        p=patch('P0183:ocr',0,len(raw['P0183:ocr']['text']),'\n\n'.join(t for _,_,t in regs),[35,78,550,763],'0183')
        p['layout_only_not_transcribed']=['document running header','printed page footer','arrow-line OCR artifacts','warning exclamation symbol']
        pos=0
        for name,box,text in regs:
            regions.append({'name':name,'record_id':'P0183:ocr','pdf_page':183,'start':pos,'end':pos+len(text),'text':text,'bbox':box,
               'review':'CODEX_PDF_LAYOUT_REVIEW','evidence':{'file':(out/p['evidence_crop']).relative_to(io.ROOT).as_posix(),'sha256':p['evidence_sha256']}});pos+=len(text)+2
        text=raw['P0615:ocr']['text']
        for old,new,box,name in [('STEACE-R','STE/ICE-R',[410,169,516,192],'0615-test'),('voits.','volts.',[375,244,494,262],'0615-volts')]:
            assert text.count(old)==1;a=text.index(old);patch('P0615:ocr',a,a+len(old),new,box,name)
    ledger['parent']={'path':parent.relative_to(io.ROOT).as_posix(),'sha256':io.sha(parent),'preserved_corrections':len(ledger['corrections'])}
    ledger['corrections']+=added;ledger.update(batch='batch-011-confirmed-ocr-text-repair',date='2026-09-25')
    io.validate_ledger(list(raw.values()),ledger)
    (out/'correction-log.json').write_bytes(io.json_bytes(ledger));(out/'source-regions.json').write_bytes(io.json_bytes(regions))
    print({'new_patches':len(added),'cumulative':len(ledger['corrections']),'regions':len(regions)})

if __name__=='__main__':main()
