"""PDF-reviewed box retranscriptions; every replacement remains in the ledger."""
import json
import pymupdf
import correct_extraction as io


REGIONS = {
217: [
 ('header',[45,82,550,99],'FUEL SYSTEM\nDIAGNOSTIC FLOWCHART'),
 ('start',[228,79,316,115],'M\nFROM C1,\nPage 2-110'),
 ('M1-id',[172,131,206,147],'M1'),
 ('M1-known',[49,130,159,211],'KNOWN INFO\nENGINE CRANKS\nNO VOLTAGE AT ADVANCE\nSOLENOID.'),
 ('M1-possible',[49,211,159,294],'POSSIBLE PROBLEMS\nPCB\nCOLD ADVANCE SWITCH\nWIRING'),
 ('M1-question',[175,148,364,242],'WITH ROTARY SWITCH IN "RUN"\nPOSITION, DO YOU HAVE\nBATTERY VOLTAGE AT WIRE 5A\nAT THE ALTERNATOR OUTPUT?'),
 ('M1-options',[349,135,511,212],'TEST OPTIONS\n1. STE/ICE-R TEST 89 (Page 2-750)\n2. MULTIMETER'),
 ('M1-reason',[349,214,511,284],'REASON FOR QUESTION\nWith rotary switch in run posi-\ntion, W5A is connected to battery\nvoltage through the PCB and it\nsupplies power to the cold advance\nswitch.'),
 ('M1-no',[215,266,233,282],'NO'),
 ('M1-exit',[252,256,341,299],'RUN\nALTERNATOR\nDIAGNOSTICS'),
 ('M1-yes',[176,287,208,306],'YES'),
 ('M2-id',[174,326,206,343],'M2'),
 ('M2-known',[48,328,159,408],'KNOWN INFO\nPCB OK\nENGINE CRANKS\nNO VOLTAGE AT ADVANCE\nSOLENOID'),
 ('M2-possible',[48,408,159,491],'POSSIBLE PROBLEMS\nCOLD ADVANCE SWITCH\nWIRING'),
 ('M2-question',[175,345,367,438],'DISCONNECT WIRE 569C AT COLD\nADVANCE SWITCH. WITH ROTARY\nSWITCH IN "RUN" POSITION, DO\nYOU HAVE BATTERY VOLTAGE\nAT WIRE 569C?'),
 ('M2-options',[347,332,507,408],'TEST OPTIONS\n1. STE/ICE-R TEST 89\n(Page 2-750)\n2. MULTIMETER'),
 ('M2-reason',[366,409,507,474],'REASON FOR QUESTION\nIf you have no voltage here then\nthe problem may be the cold\nadvance switch'),
 ('M2-no',[213,459,232,478],'NO'),
 ('M2-exit',[250,445,347,492],'REPAIR 569C/\nREPLACE\nHARNESS'),
 ('M2-yes',[172,488,203,505],'YES'),
 ('M3-id',[171,529,203,544],'M3'),
 ('M3-known',[46,529,159,610],'KNOWN INFO\nPCB OK\nENGINE CRANKS\nNO VOLTAGE AT ADVANCE\nSOLENOID'),
 ('M3-possible',[46,610,159,692],'POSSIBLE PROBLEMS\nCOLD ADVANCE SWITCH\nWIRING'),
 ('M3-question',[172,547,363,642],'RECONNECT WIRE 569C.\nDISCONNECT WIRE 569B FROM\nCOLD ADVANCE SWITCH WITH\nROTARY SWITCH IN "RUN"\nPOSITION. DO YOU HAVE BATTERY\nVOLTAGE AT SWITCH LEAD?'),
 ('M3-options',[347,532,507,608],'TEST OPTIONS\n1. STE/ICE-R TEST 89\n(Page 2-750)\n2. MULTIMETER'),
 ('M3-reason',[366,610,507,678],"REASON FOR QUESTION\nIf you don't have voltage here then\nthe problem is the switch."),
 ('M3-no',[210,664,229,680],'NO'),
 ('M3-exit',[246,652,335,697],'REPLACE\nCOLD ADVANCE\nSWITCH'),
 ('M3-yes',[170,678,200,695],'YES'),
 ('M3-continue',[133,713,239,754],'REPAIR 569B/\nREPLACE\nHARNESS')],
262: [
 ('header',[43,81,549,103],'ENGINE COOLING\nDIAGNOSTIC FLOWCHART'),
 ('start',[218,89,312,119],'FROM C4,\nPage 2-176'),
 ('C5-id',[169,134,202,150],'C5'),
 ('C5-known',[46,133,157,216],"KNOWN INFO\nFAN DRIVE OK\nFAN WON'T DISENGAGE\nCONTROL VALVE OK"),
 ('C5-possible',[46,216,157,296],'POSSIBLE PROBLEMS\nTIME DELAY MODULE\nWIRING\nHYDRAULIC SYSTEM'),
 ('C5-question',[172,153,360,247],'DISCONNECT THE 4-WIRE\nCONNECTOR ON THE TIMER.\nIS THERE CONTINUITY FROM\nWIRE 93B ON THE HARNESS SIDE\nOF THE 4-WAY CONNECTOR\nTO ENGINE GROUND?'),
 ('C5-options',[345,138,502,216],'TEST OPTIONS\n1. STE/ICE-R TEST 91 (Page 2-752)\n2. MULTIMETER'),
 ('C5-reason',[347,217,502,279],'REASON FOR QUESTION\nThe need to test the ground\nconnection of the time delay\nmodule and control valve.'),
 ('C5-no',[214,270,231,288],'NO'),
 ('C5-exit',[250,262,337,301],'REPLACE\nWIRING\n(93B)'),
 ('C5-yes',[174,297,207,312],'YES'),
 ('C6-id',[170,330,201,343],'C6'),
 ('C6-known',[46,330,157,409],"KNOWN INFO\nFAN DRIVE OK\nFAN WON'T DISENGAGE\nCONTROL VALVE OK"),
 ('C6-possible',[46,409,157,491],'POSSIBLE PROBLEMS\nTIME DELAY MODULE\nWIRING\nHYDRAULIC SYSTEM'),
 ('C6-question',[172,347,360,439],'RECONNECT THE 4-WIRE\nCONNECTOR. IS THERE ABOUT\n580Ω FROM WIRE 93B ON THE\nTIMER SIDE OF THE 2-WIRE\nCOUPLING TO ENGINE\nGROUND?'),
 ('C6-options',[344,332,503,409],'TEST OPTIONS\n1. STE/ICE-R TEST 91 (Page 2-752)\n2. MULTIMETER'),
 ('C6-reason',[347,411,501,474],'REASON FOR QUESTION\nThis measurement will help to tell\nyou if the time delay module is OK.'),
 ('C6-no',[210,463,227,479],'NO'),
 ('C6-exit',[248,448,334,493],'REPLACE\nTIME DELAY\nMODULE'),
 ('C6-yes',[169,489,199,505],'YES'),
 ('C7-id',[166,530,200,545],'C7'),
 ('C7-known',[45,530,157,610],"KNOWN INFO\nFAN DRIVE OK\nFAN WON'T DISENGAGE\nCONTROL VALVE OK"),
 ('C7-possible',[45,610,157,692],'POSSIBLE PROBLEMS\nTIME DELAY MODULE\nWIRING\nHYDRAULIC SYSTEM'),
 ('C7-question',[170,549,359,642],'IS THERE CONTINUITY FROM\nWIRE 458B IN THE 4-WIRE\nCONNECTOR HARNESS TO WIRE\n458B AT THE FAN TEMPERATURE\nSWITCH?'),
 ('C7-options',[344,531,503,609],'TEST OPTIONS\n1. STE/ICE-R TEST 91 (page 2-752)\n2. MULTIMETER'),
 ('C7-reason',[347,609,503,677],'REASON FOR QUESTION\nThis measurement will help to tell\nif the time delay module is OK.'),
 ('C7-no',[205,662,224,678],'NO'),
 ('C7-exit',[246,653,333,695],'REPLACE\nTIME DELAY\nMODULE'),
 ('C7-yes',[166,677,198,691],'YES'),
 ('C7-continue',[138,712,235,740],'GO TO C8,\nPage 2-180')],
289: [
 ('header',[52,80,552,106],'ALTERNATOR\nDIAGNOSTIC FLOWCHART'),
 ('start',[222,91,320,123],'From B3,\nPage 2-204'),
 ('B4-id',[181,137,214,152],'B4'),
 ('B4-known',[60,136,169,216],'KNOWN INFO\nALTERNATOR OUTPUT\nNOT CORRECT\nFIELD VOLTAGE OK'),
 ('B4-possible',[60,216,170,299],'POSSIBLE PROBLEMS\nALTERNATOR'),
 ('B4-question',[184,153,377,248],'RECONNECT WIRE 568. TRY\nADJUSTING ALTERNATOR.\nIS THE ALTERNATOR OUTPUT\nVOLTAGE ADJUSTABLE TO 27-29\nVOLTS?'),
 ('B4-options',[358,140,518,215],'TEST OPTIONS\nAdjusting procedure on right\nhand page using STE/ICE-R\ntests 10 and 89 (pages 2-734\nand 2-750).'),
 ('B4-reason',[372,217,518,277],'REASON FOR QUESTION\nThe alternator may just need to\nbe adjusted.'),
 ('B4-no',[225,260,244,278],'NO'),
 ('B4-exit',[262,258,354,297],'REPLACE\nALTERNATOR\n(para 4-2)'),
 ('B4-yes',[183,276,215,293],'YES'),
 ('B5-id',[183,314,216,330],'B5'),
 ('B5-question',[184,332,377,396],'AFTER ADJUSTING 60 AMP\nPRESTOLITE ALTERNATOR, GO\nTO STEP 6, PAGE 2-198 AND\nCONTINUE TESTING.')]
}


def main():
    parent=io.BASE/'corrections/batch-006/correction-log.json'
    out=io.BASE/'corrections/batch-007'
    if out.exists():raise ValueError('Use a new batch')
    ledger=json.loads(parent.read_text(encoding='utf-8'))
    original={r['id']:r for r in io.source_records(io.check_inputs(ledger))}
    out.mkdir();(out/'evidence').mkdir()
    for p in ledger['corrections']:(out/p['evidence_crop']).write_bytes((parent.parent/p['evidence_crop']).read_bytes())
    added=[]
    with pymupdf.open(io.ROOT/ledger['inputs']['pdf']['path']) as pdf:
        for pn,regions in REGIONS.items():
            rid=f'P{pn:04d}:ocr'
            assert not any(p['record_id']==rid for p in ledger['corrections'])
            before=original[rid]['text'];after='\n\n'.join(text for _,_,text in regions)
            patch={'id':f'FIX-V7-{pn:04d}','record_id':rid,'pdf_page':pn,'start':0,'end':len(before),
                   'before':before,'after':after,'bbox':[35,75,565,755],'render_clip':[35,75,565,755],
                   'reason':'PDF에서 질문·알려진 상태·가능 원인·시험 설명·분기 표식을 각각 대조하여 영역별로 재전사했다. 서로 다른 열이 합쳐진 읽기 순서와 누락된 단계 표식을 복원했으며 화살표의 뜻을 새 문장으로 생성하지 않았다.',
                   'kind':'PDF_REGION_RETRANSCRIPTION','source_check':'CODEX_PDF_VISUAL_CHECK','human_review':'NOT_PERFORMED',
                   'layout_only_not_transcribed':['document running header','printed page footer']}
            name='evidence/'+patch['id']+'.png'
            pdf[pn-1].get_pixmap(clip=pymupdf.Rect(patch['render_clip']),dpi=180,alpha=False).save(out/name)
            patch.update(evidence_crop=name,evidence_sha256=io.sha(out/name));added.append(patch)
            (out/f'page-{pn}-regions.json').write_bytes(io.json_bytes(regions))
    ledger['parent']={'path':parent.relative_to(io.ROOT).as_posix(),'sha256':io.sha(parent),'preserved_corrections':len(ledger['corrections'])}
    ledger['corrections']+=added;ledger['batch']='batch-007-region-retranscription';ledger['date']='2026-09-24'
    ledger['region_review']={'pages':list(REGIONS),'evaluation_questions_read':False,'arrow_prose_generated':False}
    io.validate_ledger(list(original.values()),ledger)
    (out/'correction-log.json').write_bytes(io.json_bytes(ledger))
    print(json.dumps({'added':len(added),'cumulative':len(ledger['corrections'])}))


if __name__=='__main__':main()
