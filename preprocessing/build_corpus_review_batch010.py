"""Source-checked flowchart text. Graphic displays are not interpreted as prose."""
import json
import pymupdf
import correct_extraction as io

REGIONS={}
def region(p,n,b,t):REGIONS.setdefault(p,[]).append((n,b,t))

region(546,'header',[42,86,535,112],'TRANSMISSION SYSTEM\n(4L80-E)\nDIAGNOSTIC FLOWCHART')
for letter,wire,ys in [('A','765A',(120,158,206,270)),('B','763A',(363,402,450,512)),('C','764A',(554,593,642,705))]:
    title,q,action,ds=ys
    region(546,letter+'-title',[42,title,300,title+25],f'TRANSMISSION RANGE PRESSURE\nSWITCH, CIRCUIT PRESSURE SWITCH {letter}')
    region(546,letter+'-wire',[78,q+5,110,q+20],wire)
    region(546,letter+'-question',[148,q,362,q+48],f'Disconnect the transmission connector\nfrom transmission. Check continuity from\nJ1 pin {letter} to chassis ground at shunt.')
    region(546,letter+'-no',[448,q+3,485,q+34],'NO')
    region(546,letter+'-yes',[303 if letter=='A' else 263 if letter=='B' else 241,q+65,345 if letter=='A' else 303 if letter=='B' else 282,q+100],'YES')
    region(546,letter+'-repair',[414,action,528,action+48],f'Repair short to\nground in wire {wire},\n(para. 4-85).')
    region(546,letter+'-ds',[233 if letter=='A' else 190,ds,375 if letter=='A' else 332,ds+28],'Refer to DS maintenance.')

region(860,'header',[240,78,415,94],'Table 2-1. STE/ICE-R GO-Chain Tests.')
region(860,'figure-caption-ready',[401,134,525,171],'INDICATES VTM IS PROPERLY\nCONNECTED AND READY\nFOR TESTS')
region(860,'figure-caption-pass',[401,200,529,224],'INDICATES GO-CONDITION\nAFTER CONFIDENCE TESTS')
region(860,'labels',[175,101,370,323],'DCA\nCABLE\nW1\nP1\nPOWER SWITCH\nPUSH ON\nPULL OFF\nTEST SELECT\nTEST')
region(860,'title',[75,297,129,310],'GO-CHAIN')
region(860,'note',[165,325,369,365],'NOTE\nPerform all GO steps until a NO-GO condition exists,\nthen perform the NO-GO step indicated.')
region(860,'mode',[405,362,463,411],'DCA\nMODE')
region(860,'go1',[117,373,164,400],'GO1')
region(860,'caution',[131,412,319,477],'CAUTION\n• Do not connect or disconnect the VTM while\nthe vehicle is running.\n• Connect DCA cable to the VTM before\nconnecting to the diagnostic connector.')
region(860,'step1',[77,515,365,590],'1\nCONNECT VTM TO VEHICLE DIAGNOSTIC CONNECTOR:\n• PULL OFF the VTM power switch.\n• Connect DCA cable to the VTM.\n• Connect DCA cable to the vehicle.\n• PUSH ON the VTM power switch.\n• Verify that the display indicated .8.8.8.8 for approximately\n2 seconds and then changes to - - - - .')
region(860,'question1',[77,590,365,609],'• Does the VTM display .8.8.8.8 and then change to - - - - ?')
region(860,'yes',[169,614,205,646],'YES')
region(860,'no',[230,614,267,646],'NO')
region(860,'continue3',[113,661,219,685],'• Proceed to step 3.')
region(860,'next',[237,661,372,685],'• Proceed to following page.')
region(860,'figure-caption-time',[462,664,543,676],'AFTER 2 SECONDS')

region(861,'header',[191,77,413,93],'Table 2-1. STE/ICE-R GO-Chain Tests. (Cont’d)')
region(861,'go1',[64,111,115,137],'GO1')
region(861,'mode',[332,101,387,151],'DCA\nMODE')
region(861,'light-question',[74,159,176,180],'• Does display light up?')
region(861,'light-no',[99,187,137,222],'NO')
region(861,'light-yes',[168,187,203,222],'YES')
region(861,'partial-display',[257,181,428,244],'• If only a portion of .8.8.8.8 or ---- is\ndisplayed, a display module may be\nburned out. Refer to TM 9-4910-\n571-12&P for module replacement.\n• Return to step 1.')
region(861,'step2',[45,237,234,307],'2\nDISPLAY DOES NOT LIGHT UP\nPROCEED AS FOLLOWS:\n• PULL OFF power switch.\n• Check and clean all battery connections\nand interconnecting cables.\n• PUSH ON the power switch.')
region(861,'question2',[45,307,234,332],'• Does the VTM display .8.8.8.8 and then\nchange to - - - - ?')
region(861,'q2-yes',[72,342,104,376],'YES')
region(861,'q2-no',[134,342,166,376],'NO')
region(861,'continue3',[43,397,150,422],'• Proceed to step 3.')
region(861,'no-power',[192,346,341,397],'• No power for VTM, connect to\na known good battery to see if\nproblem is the vehicle or the\nVTM.')
region(861,'battery-test',[192,418,411,468],'• PULL OFF the power switch.\n• Use power cable W5 to connect to\na known good battery.\n• PUSH ON the power switch.')
region(861,'battery-question',[192,468,411,496],'• Does the VTM display .8.8.8.8 and\nthen change to ----?')
region(861,'battery-yes',[212,507,247,540],'YES')
region(861,'battery-no',[272,507,306,540],'NO')
region(861,'cable-action',[339,507,498,562],'• Proceed to TM 9-4910-571-12&P for\nfault isolation of cable W1.\n• If cable is bad, replace cable.\n• If cable is good, replace STE/ICE-R.')
region(861,'charge',[191,572,413,634],'• Check the vehicle battery electrolyte level.\n• Clean vehicle battery terminals.\n• Check vehicle battery specific gravity\n(para. 4-79).\n• Charge vehicle battery (TM 9-6140-200-14).')
region(861,'return',[190,646,412,696],'• Return to step 1.\n• If problem repeats, look for broken or loose\nconnections in DCA wiring from battery or in\ncable W1.')

# Page 862's already corrected title is outside this new patch.
region(862,'go1',[93,114,138,140],'GO1')
region(862,'mode',[369,102,424,153],'DCA\nMODE')
region(862,'step3',[76,156,284,184],'3\nRUN CONFIDENCE TEST:\n• Dial 66 into TEST SELECT and press TEST.')
region(862,'question3',[76,184,284,208],'• Does the VTM display and hold 0066?')
region(862,'q3-yes',[137,215,169,248],'YES')
region(862,'q3-no',[203,215,236,248],'NO')
region(862,'retry',[334,166,472,257],'• PULL OFF the power switch.\n• PUSH ON the VTM power\nswitch.\n• Verify that the display indi-\ncates .8.8.8.8 for approxi-\nmately 2 seconds and then\nchange to ----.\n• Re-dial 66 and press TEST.')
region(862,'retry-question',[334,257,472,287],'• Does the VTM display and\nhold 0066?')
region(862,'retry-yes',[349,299,382,334],'YES')
region(862,'retry-no',[416,299,449,334],'NO')
region(862,'replace',[431,349,567,374],'• STE/ICE-R is bad. Replace.')
region(862,'display-check',[94,341,267,387],'• Dial 99 into TEST SELECT and press\nTEST.\n• Look for this display.')
region(862,'display-labels',[142,412,334,631],'1\n2\nBLANK\n3\n4\nBLANK')
region(862,'table-header',[400,448,521,472],'TEST NO.\nTEST')
region(862,'table66',[400,472,450,506],'66')
region(862,'table-confidence',[450,472,521,506],'CONFIDENCE\nTEST')
region(862,'note',[100,641,289,701],'NOTE\nAt this point in the test, several numbers will\nappear on the display. Wait for readout\ndisplay of PASS.')
region(862,'next',[88,713,224,738],'• Proceed to following page.')

region(863,'header',[191,77,404,88],'Table 2-1. STE/ICE-R GO-Chain Tests. (Cont’d)')
region(863,'go1',[43,112,93,136],'GO1')
region(863,'mode',[336,99,376,142],'DCA\nMODE')
region(863,'caption-pass',[150,178,215,200],'PROMPTING\nMESSAGE')
region(863,'question-pass',[56,214,210,240],'• Does the VTM display PASS?')
region(863,'pass-yes',[81,270,113,304],'YES')
region(863,'pass-no',[152,270,186,304],'NO')
region(863,'confidence-note',[258,156,539,252],'NOTE\nThe VTM can fail Confidence Test if a bad transducer is connected\nto it. If the VTM fails Confidence Test when powered by W1 (DCA\nmode), remove all cable from the VTM and connect only W5, then\nclip W5 to the vehicle batteries. If it passes Confidence Test this\nway, there is a bad transducer in the vehicle’s DCA. If it fails, the\nVTM has failed internally. Repeat TM 9-4910-571-12&P.')
region(863,'repeat3',[214,278,358,298],'• Repeat step 3.')
region(863,'repeat3-question',[214,298,358,317],'• Does the VTM display PASS?')
region(863,'repeat3-yes',[231,327,263,361],'YES')
region(863,'repeat3-no',[309,327,343,361],'NO')
region(863,'replace3',[367,367,501,392],'• STE/ICE-R is bad. Replace.')
region(863,'step4',[58,423,343,489],'4\nENTER VEHICLE IDENTIFICATION NUMBER (VIN):\n• Dial 60 into TEST SELECT and press TEST.\n• When UEH appears, dial vehicle identification number (21) into\nTEST SELECT and press TEST.\n• VIN entered should appear on the display.')
region(863,'vin-note',[406,399,532,482],'NOTE\nIf message E010 appears,\neither wrong number is\nentered or VTM is connect-\ned to wrong DCA con-\nnecter.')
region(863,'question-vin',[58,504,233,530],'• Does the VTM display the number 21?')
region(863,'vin-yes',[81,546,115,580],'YES')
region(863,'vin-no',[152,546,186,580],'NO')
region(863,'caption-vin',[297,546,370,570],'PROMPTING\nMESSAGE')
region(863,'repeat4',[94,593,276,613],'• Repeat step 4.')
region(863,'repeat4-question',[94,613,276,633],'• Does the VTM display the number 21?')
region(863,'repeat4-yes',[118,650,150,684],'YES')
region(863,'repeat4-no',[191,650,225,684],'NO')
region(863,'replace4',[276,650,411,675],'• STE/ICE-R is bad. Replace.')
region(863,'continue',[58,693,243,719],'• Proceed to troubleshooting procedures.')


def main():
    parent=io.BASE/'corrections/batch-009/correction-log.json';out=io.BASE/'corrections/batch-010'
    if out.exists():raise ValueError('Use a new batch')
    ledger=json.loads(parent.read_text(encoding='utf-8'))
    original={r['id']:r for r in io.source_records(io.check_inputs(ledger))}
    out.mkdir();(out/'evidence').mkdir()
    for p in ledger['corrections']:(out/p['evidence_crop']).write_bytes((parent.parent/p['evidence_crop']).read_bytes())
    spans=[];added=[]
    with pymupdf.open(io.ROOT/ledger['inputs']['pdf']['path']) as pdf:
        for pn,regions in REGIONS.items():
            rid=f'P{pn:04d}:ocr';raw=original[rid]['text'];start=0
            if pn==862:start=raw.index('\n\n')+2
            assert not any(p['record_id']==rid and p['end']>start for p in ledger['corrections'])
            after='\n\n'.join(t for _,_,t in regions);clip=[35,60,pdf[pn-1].rect.width-25,pdf[pn-1].rect.height-25]
            patch={'id':f'FIX-V10-{pn:04d}','record_id':rid,'pdf_page':pn,'start':start,'end':len(raw),
                   'before':raw[start:],'after':after,'bbox':clip,'render_clip':clip,
                   'reason':'PDF 대조로 문장 혼합·탈락·오독을 보정하고 질문, 조건, 분기 표식, 조치 영역을 분리했다. 그림의 선과 계기 표시 도형은 문장으로 해석하지 않았다.',
                   'kind':'PDF_REGION_RETRANSCRIPTION','source_check':'CODEX_PDF_VISUAL_CHECK','human_review':'NOT_PERFORMED',
                   'layout_only_not_transcribed':['document running header','printed page footer','arrow line OCR artifacts','seven-segment display drawing']}
            name='evidence/'+patch['id']+'.png';pdf[pn-1].get_pixmap(clip=pymupdf.Rect(clip),dpi=180,alpha=False).save(out/name)
            patch.update(evidence_crop=name,evidence_sha256=io.sha(out/name));added.append(patch)
            offset=start
            for name,box,text in regions:
                spans.append({'name':name,'record_id':rid,'pdf_page':pn,'start':offset,'end':offset+len(text),
                              'text':text,'bbox':box,'review':'CODEX_PDF_LAYOUT_REVIEW','human_review':'NOT_PERFORMED',
                              'evidence':{'file':(out/patch['evidence_crop']).relative_to(io.ROOT).as_posix(),'sha256':patch['evidence_sha256']}})
                offset+=len(text)+2
    ledger['parent']={'path':parent.relative_to(io.ROOT).as_posix(),'sha256':io.sha(parent),'preserved_corrections':len(ledger['corrections'])}
    ledger['corrections']+=added;ledger.update(batch='batch-010-flow-text-and-condition-repair',date='2026-09-24')
    io.validate_ledger(list(original.values()),ledger)
    (out/'correction-log.json').write_bytes(io.json_bytes(ledger));(out/'source-regions.json').write_bytes(io.json_bytes(spans))
    print({'new_patches':len(added),'cumulative':len(ledger['corrections']),'regions':len(spans)})

if __name__=='__main__':main()
