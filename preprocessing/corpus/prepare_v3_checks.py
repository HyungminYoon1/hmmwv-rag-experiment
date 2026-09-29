"""Freeze independently transcribed PDF facts used by the v3 audit."""
from .common import ROOT,BASE,PACKAGE,read_json,read_jsonl,write_json,write_jsonl


def main():
    rules=PACKAGE/'rules/v3'
    audit=read_json(BASE/'audit/corrected-v6-a.json')
    if audit['status']!='PASS':raise ValueError('The new source must pass the correction audit first')
    config=read_json(PACKAGE/'config.json')
    config.update(corrected_source='preprocessing/output/corrected-v6-a',
                  correction_ledger='preprocessing/corrections/batch-006/correction-log.json')
    write_json(PACKAGE/'config.json',config)
    source={r['id']:r for r in read_jsonl(BASE/'output/corrected-v6-a/units-corrected.jsonl')}
    pmcs=read_jsonl(rules/'pmcs-structure.jsonl')
    for r in pmcs:
        if r['row_id']=='P0097-T2_1-R01':r['fields']['PROCEDURES']=source[r['row_id']+':PROCEDURES']['text']
    write_jsonl(rules/'pmcs-structure.jsonl',pmcs)
    issues=read_jsonl(rules/'source-issues.jsonl')
    for issue in issues:
        if issue['id']=='OD_SYMBOL':
            issue.update(status='SYMBOL_RECOVERED_BY_BATCH006',description='PDF의 원형 D를 Ⓓ로 복원했다. batch-006의 전후 문자·원문 이미지 기록을 참조한다.')
    extra=[{'id':'PRINTED_REFERENCE_2_11','pdf_page':124,'status':'SOURCE_IDENTIFIER_PRESERVED',
            'description':'4L80-E 행의 PAGE는 원문에 2-11로 인쇄되어 있다. 예상 쪽번호로 바꾸지 않았다.'},
           {'id':'PRINTED_REFERENCE_2_79','pdf_page':124,'status':'SOURCE_IDENTIFIER_PRESERVED',
            'description':'DRIVETRAIN 행의 PAGE는 원문에 2-79로 인쇄되어 있다. 원문값을 복원하고 그대로 보존했다.'},
           {'id':'SYSTEM_TEST_COUNT','pdf_page':124,'status':'SOURCE_COUNT_INCONSISTENCY',
            'description':'설명에는 21 SYSTEM LEVEL TESTS라고 적혀 있으나 표에는 22개 행이 있다. 설명과 표를 모두 원문대로 보존했다.'}]
    existing={i['id'] for i in issues};issues.extend(i for i in extra if i['id'] not in existing)
    write_jsonl(rules/'source-issues.jsonl',issues)
    checks=read_json(PACKAGE/'rules/v2/table-assertions.json')
    checks['counts'].update({'P0123:foldouts':22,'P0124:top':5,'P0124:system':22,'P0573:idle':3})
    # Values entered from the PDF independently of generated table output.
    labels=['FUEL','AIR INTAKE/EXHAUST','COMPRESSION/MECHANICAL','ENGINE COOLING','ENGINE LUBRICATION',
        'ALTERNATOR','PROTECTIVE CONTROL BOX/\nDISTRIBUTION BOX','BATTERY CIRCUIT','STARTER CIRCUIT',
        'GLOWPLUGS (PROTECTIVE\nCONTROL BOX)','GLOWPLUGS (DISTRIBUTION BOX)','INSTRUMENTS','LIGHTS',
        'TRANSMISSION (3L80)','TRANSMISSION (4L80-E)','BRAKES','STEERING','DRIVETRAIN',
        'AMBULANCE ELECTRICAL SYSTEM','AMBULANCE MECHANICAL SYSTEM','WINCH SYSTEM','DCA TROUBLESHOOTING']
    paragraphs=['2-22','2-23','2-24','2-25','2-26','2-27','2-28','2-29','2-30','2-31','2-31.1',
                '2-32','2-33','2-34','2-35','2-36','2-37','2-38','2-39','2-40','2-41','2-42']
    foldouts=['FO-1','FO-2','FO-3','FO-4','FO-5','FO-6','','FO-7','FO-8','FO-9','','FO-10','FO-11',
              'FO-12','','FO-13','FO-14','FO-15','','','','FO-16']
    def fact(key,field,value):checks['field_checks'].append({'key':key,'field':field,'expected':value})
    for i,(label,para,foldout) in enumerate(zip(labels,paragraphs,foldouts),1):
        for f,value in [('SYSTEM LEVEL TESTS',label),('PARAGRAPH',para),('FOLDOUT NUMBER',foldout)]:
            fact(f'P0123:foldouts:row:{i}',f,value)
    page_refs=['2-95','2-137','2-143','2-155','2-187','2-194','2-227','2-251','2-261','2-303',
               '2-318.1','2-319','2-389','2-399','2-11','2-445','2-459','2-79','2-497','2-693','2-715','2-723']
    system_labels=labels[:]
    system_labels[9]='GLOWPLUGS (PCB)';system_labels[18]='AMBULANCE ELECTRICAL'
    system_labels[19]='AMBULANCE MECHANICAL';system_labels[20]='WINCH'
    for i,(label,value) in enumerate(zip(system_labels,page_refs),1):
        fact(f'P0124:system:row:{i}','SYSTEM LEVEL TESTS',label);fact(f'P0124:system:row:{i}','PAGE',value)
    for i,(label,value) in enumerate(zip(['ENGINE STARTING','ENGINE RUNNING','COOLING','LUBRICATION','ELECTRICAL'],
                                         ['2-41','2-47','2-57','2-65','2-71']),1):
        fact(f'P0124:top:row:{i}','TOP LEVEL TESTS',label);fact(f'P0124:top:row:{i}','PAGE',value)
    for i,(engine,rpm) in enumerate([('6.2L engine','650±25 RPM'),('6.5L engine','700±25 RPM'),('6.5L detuned\nengine','700±25 RPM')],1):
        fact(f'P0573:idle:row:{i}','Engine',engine);fact(f'P0573:idle:row:{i}','Idle speed',rpm)
    checks['required_context'].append({'key_prefix':'P0573:idle:',
         'contains':['18. Check for proper engine idle speeds','190° F to 230° F.', 'engine cooling system'],
         'excludes':['CONTROL VALVE','BYPASS HOSE']})
    write_json(rules/'table-assertions.json',checks)
    units=[
      {'key':'P0133:question:1','required_body':['100 RPM','STE/ICE TEST 10 (Page 2-734)'],
       'required_context':['KNOWN INFO\nNOTHING'],'forbidden_body':['NOES','STENCE']},
      {'key':'P0133:question:2','required_body':['RUN THE FUEL SYSTEM\nTESTS. RETURN HERE.'],
       'required_context':['STARTER SYSTEM OK','ENGINE NOT LOCKED']},
      {'key':'P0133:question:3','required_body':['RUN THE INTAKE AIR/EXHAUST'],
       'required_context':['FUEL SYSTEM OK']},
      {'key':'P0287:question:B2','required_body':['STOP ENGINE. DISCONNECT WIRE','1. STE/ICE-R TEST 89 (Page 2-750)'],
       'forbidden_context':['KNOWN INFO','POSSIBLE PROBLEMS'],'forbidden_body':['CONNECT WIRE 568A AND 568. TURN']},
      {'key':'P0287:question:B3','required_body':['CONNECT WIRE 568A AND 568. TURN','1. STE/STE-R TEST 89'],
       'forbidden_context':['KNOWN INFO','POSSIBLE PROBLEMS']},
      {'key':'P0287:unlinked-condition:3','required_body':['KNOWN INFO','ALTERNATOR'], 'forbidden_body':['WIRING']},
      {'key':'P0328:question:7','required_context':['KNOWN INFO\nNOTHING','PARKING BRAKE SWITCH BAD']},
      {'key':'P0336:question:20','required_body':['(ENGINE RUNNING)'], 'required_context':['IGNITION SWITCH OK']},
      {'key':'P0389:pcb-replacement','required_context':['Disconnect negative battery cable before'],
       'required_body':['Replace PCB','Replace distribution box']},
      {'key':'P0389:multimeter','required_body':['1000 ohms.','Less than'],
       'forbidden_context':['Disconnect negative battery','WARNING']},
      {'key':'P0389:steice91','required_body':['0-4500 OHMS','“9.9.9.9.”'],
       'forbidden_context':['Disconnect negative battery','WARNING']},
      {'key':'P0517:road','required_body':['1. Position shift lever in "Ⓓ"','5. Position shift lever in "Ⓓ"','9. Hard shifting'],
       'required_context':['Road Test Procedure','(4L80-E)'],'forbidden_body':['Procedure for checking transmission fluid']},
      {'key':'P0573:step:22','required_body':['1300 psi or higher'],
       'required_context':['Do not leave analyzer valve fully closed for more than 5 seconds.','190° F to 230° F.','engine cooling system'],
       'forbidden_body':['BYPASS HOSE','CONTROL VALVE','HOSE CLAMP']},
      {'key':'P0849:procedure','required_context':['Run Confidence Test.','Make sure the circuit','or component being tested is shut off.'],
       'required_body':['-225 to 225','1. Connect test probe cable W2. Attach P1 to J4.']},
      {'key':'P0849:applications','required_body':['• Continuity checks','• Resistance measurements','• Switch and relay functions']},
      {'key':'P0124:explanation:system','required_body':['LEVEL TESTS BUT YOU CAN GO'],
       'required_context':['THERE ARE 21 SYSTEM LEVEL TESTS.']}
    ]
    write_json(rules/'box-assertions.json',{'source':'Independent PDF screen checks of selected regions',
         'units':units,'complete_native_profile_pages':[165,197,287,328,336,583]})
    write_json(rules/'finding-resolutions.json',{'completed':[
         {'pages':[97,124,133,517,849],'action':'Logged extraction corrections in batches 005 and 006'},
         {'pages':[123,124,573],'action':'52 additional literal table rows and complete independent field assertions'},
         {'pages':[389,517,573,849],'action':'Separate procedures/panels and explicit condition/warning scopes'}],
         'partial':[{'pages':[287],'action':'Question/test boxes separated; left boxes preserved independently; no inferred link'},
                    {'profile':'native flowchart boxes','action':'62 pages mechanically separated; individual context review remains'}],
         'global_corpus_ready':False,'evaluation_questions_read':False})
    print('v6 source and v3 independent check facts prepared')


if __name__=='__main__':main()
