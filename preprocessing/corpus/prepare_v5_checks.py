"""Independent PDF facts: do not derive expected values from generated units."""
from .common import PACKAGE, read_json, write_json


def main():
    rules=PACKAGE/read_json(PACKAGE/'config.json')['rules_path']
    checks=read_json(PACKAGE/'rules/v4/table-assertions.json')
    expected={
        'P0408:pin':(['PIN 1','PIN 2','RESISTANCE'],[
            ['1','5','130 Ω ± Ω'],['2','3','0.40 Ω TO 0.75 Ω'],['4','5','27 Ω ± 3 Ω'],['2','6','.45 Ω MAXIMUM']]),
        'P0474:gauge':(['GAUGE READING','OHMS'],[['FULL','35'],['HALF','16'],['EMPTY','0']]),
        'P0502:connections':(['TERMINAL','CONNECTION','WIRE NUMBER'],[
            ['A','RIGHT FRONT TURN SIGNAL','460A'],['B','LEFT FRONT TURN SIGNAL','461A'],
            ['C','LEFT REAR TURN SIGNAL/STOP LAMP','22-461A'],['D','LIGHT SWITCH TERMINAL "C"','22A'],
            ['E','RIGHT REAR TURN SIGNAL','22-460A'],['F','HAZARD/TURN SIGNAL FLASHER TERM. "B"','325B'],
            ['G','LIGHT SWITCH TERMINAL "J" (24 VOLTS)','467B'],['H','HAZARD/TURN SIGNAL FLASHER TERM. "A"','325A']]),
        'P0575:answers':(['B6','B7','B8','COMPONENT TO REPLACE'],[
            ['NO','NO','NO','POWER STEERING PUMP'],['NO','NO','YES','SEE NOTE\nBELOW'],
            ['NO','YES','NO','SEE NOTE\nBELOW'],['NO','YES','YES','RUN ENGINE COOLING\nTEST (PARA 2-19)'],
            ['YES','NO','NO','POWER STEERING PUMP'],['YES','NO','YES','HYDRO-BOOSTER'],
            ['YES','YES','NO','DS LEVEL\nSTEERING GEAR'],['YES','YES','YES','NO FAULTS']])}
    for table,(headers,rows) in expected.items():
        checks['counts'][table]=len(rows)
        for i,row in enumerate(rows,1):
            for field,value in zip(headers,row):
                checks['field_checks'].append({'key':f'{table}:row:{i}','field':field,'expected':value})
    checks['required_context'] += [
        {'key_prefix':'P0408:pin:','contains':['solid-state controller','green finish','larger\ncase.','Glowplug Controller'],
         'excludes':['MULTIMETER','0-4500 OHMS']},
        {'key_prefix':'P0474:gauge:','contains':['INSTRUMENTS CIRCUIT','FUEL GAUGE'], 'excludes':['STE/ICE-R TEST 91']},
        {'key_prefix':'P0502:connections:','contains':['TURN SIGNAL SWITCH','DISCONNECT NEGATIVE BATTERY CABLE'],
         'excludes':['OFF']},
        {'key_prefix':'P0575:answers:','contains':['STEERING SYSTEM','second and third cases','for all cases, check',
         'HARD OR ABNORMAL','B9','LOOK AT THE CHART'], 'excludes':['NO FAULTS']}]
    write_json(rules/'table-assertions.json',checks)
    boxes=read_json(PACKAGE/'rules/v4/box-assertions.json')
    boxes['units'] += [
        {'key':'P0474:steice91','required_body':['Start Test 91','indicated terminals'],
         'forbidden_body':['58H','58C','driveshaft','GAUGE READING']},
        {'key':'P0408:replace','required_context':['solid-state controller','larger\ncase.'],
         'required_body':['para 4-29']},
        {'key':'P0547:branch:L1:NO','required_context':['(4L80-E)','RESISTANCE TOO LOW','J1 pin e to J1 pin c.','NO'],
         'forbidden_context':['RESISTANCE TOO HIGH','pin L.'],
         'required_body':['short from wire 923A','359A/B/C/D'], 'expected_metadata':{'branch_label':'NO','parent_question':'P0547:question:L1'}},
        {'key':'P0547:branch:H2:NO','required_context':['RESISTANCE TOO HIGH','pin L.','YES','pin M.','NO'],
         'forbidden_context':['RESISTANCE TOO LOW','chassis ground'], 'required_body':['Repair wire 359A/B/C/D'],
         'expected_metadata':{'branch_label':'NO','parent_question':'P0547:question:H2'}},
        {'key':'P0547:branch:L2:YES','required_context':['RESISTANCE TOO LOW','J1 pin e to J1 pin c.','chassis ground.','YES'],
         'required_body':['Refer to DS maintenance.']},
        {'key':'P0574:question:B7','required_body':['IS THE HYDRO-BOOSTER','Depress brake pedal'],
         'required_context':['HARD OR ABNORMAL'], 'forbidden_body':['CENTER ITSELF']},
        {'key':'P0612:question:19','required_body':['TB TERMINAL 1?','TB TERMINAL 2?','STE/ICE-R TEST 89'],
         'required_context':['All Dome Lamps','With Ambulance','Rear Step','Closed (Refer to Fig. 11.)','FUSES OK'],
         'forbidden_body':['TB TERMINAL 27']},
        {'key':'P0612:question:17','required_body':['No voltage wound indicate a'],
         'forbidden_body':['No voltage would indicate a']},
        {'key':'P0612:branch:17:NO','required_body':['REPLACE LEAD 660 D'],
         'required_context':['IS THERE BATTERY VOLTAGE','AT FUSE BLOCK?','NO'],
         'forbidden_body':['6600'], 'expected_metadata':{'branch_label':'NO'}},
        {'key':'P0612:branch:18:NO','required_body':['REPLACE BLOWN FUSES'],
         'required_context':['LEAD 660 D OK','ARE FUSES OK?','NO'], 'forbidden_context':['FUSES OK\nPOSSIBLE']},
        {'key':'P0612:branch:19:NO','required_body':['LEAD 712','LEAD 711'],
         'required_context':['FUSES OK','TB TERMINAL 1?','TB TERMINAL 2?','NO']},
        {'key':'P0613:steice89','required_body':['STE/ICE-R TEST 89','reading is in volts.'],
         'forbidden_body':['voits','SPARE FUSE','TERMINAL BOARD']},
        {'key':'P0829:B1-reference','required_body':['If it fails again','return to this question and answer "YES".'],
         'required_context':['B1','REMOVE THE TACHOMETER'], 'forbidden_body':['W5 cable','oil pump drive could']},
        {'key':'P0829:B2-reference','required_body':['W5 cable','oil pump drive could be too worn'],
         'required_context':['B2','IN THE TK MODE.'], 'forbidden_body':['Remove tachometer','Vehicle DCA faulty.']},
        {'key':'P0828:question:B3','required_body':['DID THE ORIGINAL DCA TEST','answer "NO"'],
         'forbidden_body':['Vehicle DCA faulty.']},
        {'key':'P0828:branch:B3:NO','required_body':['SEE NOTE TO','Vehicle DCA faulty.'],
         'required_context':['GIVE A CORRECT RESULT?','NO'], 'expected_metadata':{'branch_label':'NO'}},
        {'key':'P0828:branch:B3:YES','required_body':['NO FAULTS'],
         'forbidden_body':['Vehicle DCA faulty.'], 'expected_metadata':{'branch_label':'YES'}}]
    write_json(rules/'box-assertions.json',boxes)
    edges=[]
    for pn,steps in [(612,['17','18','19']),(828,['B1','B2','B3'])]:
        for i,step in enumerate(steps):
            q=f'P{pn:04d}:question:{step}'
            edges.append([q,'NO',f'P{pn:04d}:branch:{step}:NO'])
            edges.append([q,'YES',f'P{pn:04d}:question:{steps[i+1]}' if i<2 else f'P{pn:04d}:branch:{step}:YES'])
    for step,nxt in [('B7','B8'),('B8','B9')]:
        q='P0574:question:'+step; reminder='P0574:branch:'+step+':NO'
        edges += [[q,'NO',reminder],[reminder,None,'P0574:question:'+nxt],[q,'YES','P0574:question:'+nxt]]
    for step in ['L1','L2','H1','H2']:
        q='P0547:question:'+step
        edges.append([q,'NO','P0547:branch:'+step+':NO'])
        edges.append([q,'YES','P0547:question:'+step[0]+'2' if step.endswith('1') else 'P0547:branch:'+step+':YES'])
    write_json(rules/'flow-assertions.json',{'source':'Separately checked PDF branch destinations','edges':edges})
    print('Frozen independent checks: 74 table cells and 17 additional box/condition facts')


if __name__=='__main__':main()
