"""Record the PDF crop decisions made during the v6 source review."""
from corpus.common import *

WORK=PACKAGE/'reports/rules-v6-work/alignment'


def main():
    rows=read_json(WORK/'items.json')
    represented={0,1,2,3,4,5,6,7,8,9,10,11,13,14,31,33,34,39,44,46,47,48,51,52,53,55,56,62,64,65,71,72,73,75,79,85,89,90,93,95,96,97,99,103,104,105,106,107,108,109,110,111,117,154,168,204}
    graphics={12,17,18,24,25,27,28,29,30,32,42,43,54,57,58,60,61,67,68,69,70,74,84,91,92,94,100,101,102,113,118,119,120,121,122,123,124,155,164,173,174,185,190,200,202,206,207,208,209,210,211,*range(129,153)}
    corrections={
        21:'SEE PARAGRAPH 2-26,',
        35:'SOLENOID\n1. STE/ICE-R TEST 91(Page 2-752)',
        36:'SOLENOID OK\nCONNECTOR FROM THE PCB.\n1. STE/ICE-R TEST 91 (Page 2-752)',
        37:'There is battery voltage at the PCB at all times.',
        38:'1. STE/ICE-R TEST 91 (Page 2-752)',
        40:'it for dirt and other contaminants. Replace',
        63:'STARTER CIRCUIT\nFROM 6, Page 2-266',
        66:'TEST 91\n(Page 2-752)',
        77:'Replace harness/or repair wiring, refer',
        86:'Replace fuel level sending unit and repair wiring,\nrefer to (para 4-28 and 4-85).',
        158:'front door, rear door, or rear\nFROM 8,',
        159:'Repair lead, refer to (para. 4-85).\n717C',
        160:'Repair lead connector, refer to',
        161:'Repair lead connector, refer to (para. 4-85).',
        162:'(Single Dome Lamp)\nSTART',
        163:'(Spotlight)',
        165:'(Interior Blackout Lamps)\nSTART',
        166:'(Aspirator)\nSTART',
        167:'(Front DC Outlet)\nSTART',
        169:'Replace rear DC outlet, refer to',
        170:'(M997 Only)\nSTART',
        172:'(M997 Only)',
        175:'Repair lead, refer to (para. 4-85).',
        178:'(Refer to Figs.14-16.)',
        182:'Repair lead connector, refer to',
        183:'(para. 4-85).',
        184:'(Refer to Figs. 14-16.)\nPage 2-622',
        189:'STE/ICE-R TEST 89,',
        191:'(Refer to Figs. 14-16.)\nPage 2-630',
        192:'(Refer to Figs. 15, 16.)',
        193:'Repair lead, refer to (para. 4-85).',
        194:'AMBULANCE\nFROM 6,',
        195:'AMBULANCE',
        196:'(Refer to Figs. 14-16.)',
        197:'Replace heater switch,',
        198:'(NBC Filter Blower)\nFROM 2,',
        199:'(Refer to Fig. 17.)\nPage 2-660',
        203:'STE/ICE-R TEST 81, PAGE 2-752',
        205:'then you have a fuel system problem. Remove fuel pres-\nsure transducer, refer to (para 4-26). Make sure the',
    }
    # These are reviewed, literal OCR text whose native layer contains only a
    # page/paragraph reference. They must not be discarded as duplicate prose.
    keep={15,16,19,20,22,23,26,41,45,49,50,59,76,78,80,81,82,83,87,88,98,112,114,115,116,125,126,127,128,153,156,157,171,176,177,179,180,181,186,187,188,201}
    assert represented|graphics|set(corrections)|keep==set(range(len(rows)))
    assert sum(map(len,[represented,graphics,corrections,keep]))==len(rows)
    result=[]
    for i,row in enumerate(rows):
        action='REPRESENT' if i in represented else 'GRAPHIC' if i in graphics else 'CORRECT' if i in corrections else 'KEEP'
        result.append({'number':i,'action':action,'after':corrections.get(i),**row,
          'source_check':'CODEX_PDF_VISUAL_CHECK','human_source_review':'NOT_PERFORMED',
          'image':(WORK/f'{i:03d}.png').relative_to(ROOT).as_posix(),
          'image_sha256':sha(WORK/f'{i:03d}.png')})
    write_json(WORK/'decisions.json',result)
    print('Recorded',len(result),'individual PDF decisions')


if __name__=='__main__':main()
