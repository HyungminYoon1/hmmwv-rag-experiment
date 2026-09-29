"""Repair additional confirmed failures found by independent layout sampling."""
import json
import pymupdf
from build_corpus_review_batch012 import main as apply_boxes
import correct_extraction as io


def main():
    out=io.BASE/'corpus/reports/rules-v6-work/profile-text-corrections';out.mkdir(exist_ok=True)
    data=[
      (549,[346,134,504,211],'TEST OPTIONS\nTEST PARKING BRAKE USING\nPROCEDURE ON RIGHT'),
      (720,[350,134,509,273],'TEST OPTIONS\nVISUAL\nREASON FOR QUESTION\nHeat lever must be in proper\nposition for heater fuel pump\noperation.'),
      (720,[44,195,154,297],'HEAT LEVER POSITION\nCONTROL LEVER\nPOSITION\nHEATER SWITCH\nPOSITION\nFUSE\nBATTERY\nCABLE 660\nLEAD 798\nFUEL PUMP'),
      (720,[44,387,153,482],'CONTROL LEVER\nPOSITION\nHEATER SWITCH\nPOSITION\nFUSE\nBATTERY\nCABLE 660\nLEAD 798\nFUEL PUMP'),
      (720,[352,400,509,465],'REASON FOR QUESTION\nControl lever msut be in proper\nposition for heater fuel pump\noperation.'),
      (720,[351,515,510,591],'TEST OPTIONS\nVISUAL'),
      (720,[354,591,510,654],'REASON FOR QUESTION\nHeater switch must be in\nproper position for heater fuel\npump operation.'),
      (728,[45,148,153,179],'LEAD 660 B OK\nLEAD 722 OK\nLEAD 722 A OK'),
      (728,[45,194,153,321],'HEATER CONTINUITY\nSWITCH\nLEAD 722 B\nHEATER FRESH AIR\nSWITCH\nLEAD 722 C\nHEATER SWITCH\nLEAD 723 D\nROLLOVER SWITCH\nLEAD 723 C\nLEAD 723B\nLEAD 723 A\nFUEL PUMP'),
      (728,[353,210,508,274],'REASON FOR QUESTION\nNo power would indicate a\nswitch malfunction.'),
      (728,[174,341,363,453],'IS THERE BATTERY VOLTAGE IN\nENVIRONMENTAL CONTROL BOX\nAT HEATER FRESH AIR DOOR\nCONTINUITY SWITCH?'),
      (728,[47,605,158,714],'HEATER FRESH AIR\nSWITCH\nLEAD 722 C\nHEATER SWITCH\nLEAD 723 D\nROLLOVER SWITCH\nLEAD 723 C\nLEAD 723 B\nLEAD 723A\nFUEL PUMP'),
      (743,[375,180,570,284],'0-45 DC VOLTS\nSTE/ICE-R TEST 89\n1. Connect RED clip to the indicated test point,\nBLACK clip to negative or ground.\n2. Start Test 89, DC volts.\n3. Displayed reading is in volts.')]
    ledger=json.loads((io.BASE/'corrections/batch-012/correction-log.json').read_text(encoding='utf-8'))
    candidates=[];decisions={}
    with pymupdf.open(io.ROOT/ledger['inputs']['pdf']['path']) as doc:
        for i,(pn,box,text) in enumerate(data):
            key=f'P{pn:04d}-S{i:02d}';audit=json.loads((io.BASE/f'ocr-structure-review-20260924/full-audit-e/page-{pn:04d}.json').read_text())
            words=[w for w in audit['words'] if w.get('raw_start') is not None and box[0]<=(w['bbox'][0]+w['bbox'][2])/2<=box[2] and box[1]<=(w['bbox'][1]+w['bbox'][3])/2<=box[3]]
            words.sort(key=lambda w:w['raw_start'])
            img=out/(key+'.png');doc[pn-1].get_pixmap(clip=pymupdf.Rect(box),dpi=180,alpha=False).save(img)
            candidates.append({'id':key,'pdf_page':pn,'bbox':box,'old_words':words,'image':img.relative_to(io.ROOT).as_posix(),'image_sha256':io.sha(img)})
            decisions[key]={'decision':'TRANSCRIBE','text':text}
    (out/'candidates.json').write_bytes(io.json_bytes(candidates));(out/'review-decisions.json').write_bytes(io.json_bytes({'decisions':decisions}))
    apply_boxes(io.BASE/'corrections/batch-012/correction-log.json',io.BASE/'corrections/batch-013',out,'V13')


if __name__=='__main__':main()
