"""Frozen PDF transcriptions for the seven findings of the whole-OCR audit.

This program replays reviewed literals. It does not invoke OCR or an LLM.
Coordinates are PDF points; table cells are recorded independently of prose.
"""
import json
import pymupdf
import correct_extraction as io

REGIONS = {}
TABLES = []


def region(page, name, box, text):
    REGIONS.setdefault(page, []).append((name, box, text))


def table(page, name, headers, values, xs, ys):
    names = []
    for row, cells in enumerate(values, 1):
        fields = []
        for column, (header, text) in enumerate(zip(headers, cells)):
            key = f'{name}-{row}-{column+1}'
            region(page, key, [xs[column], ys[row-1], xs[column+1], ys[row]], text)
            fields.append((header, key))
        names.append(fields)
    TABLES.append({'page': page, 'name': name, 'rows': names})


region(408, 'header', [85, 93, 585, 107], 'REFERENCE INFORMATION\nGLOWPLUGS')
region(408, 'warning', [158, 187, 326, 271], 'WARNING\nDisconnect negative battery cable before\ndisconnecting and reconnecting protective\ncontrol box harness.\nThere is battery voltage at the PCB at all times.\nFailure to disconnect battery cable will result in\ndamage to equipment or injury to personnel.')
region(408, 'engine-labels', [437, 156, 530, 244], 'C B A\nF E D\nI H G')
region(408, 'engine-caption', [435, 251, 534, 279], 'Engine Connector Harness\nwith sockets "A" & "B"\nhighlighted.')
region(408, 'harness-labels', [199, 342, 311, 450], '3 4 5\n2 1 6')
region(408, 'harness-caption', [203, 451, 321, 472], 'Glowplug Controller Harness\nwith sockets 3 & 6 highlighted')
region(408, 'steice91', [403, 314, 594, 449], "0-4500 OHMS\nSTE/ICE-R TEST 91\n1. Connect RED clip and BLACK clip to the\nindicated test points in the question. RED to the\nfirst, BLACK to the second.\n2. Start Test 91, 0-4500 ohms.\n3. Displayed reading is in ohms. Less than 5 ohms\nis continuity. If the resistance is over 4500 ohms,\nSTE/ICE displays '9.9.9.9.'")
region(408, 'multimeter', [403, 457, 594, 602], 'CONTINUITY (RESISTANCE)\nMULTIMETER\n1. Set the voltmeter to an ohms scale of about\n1000 ohms.\n2. Connect the RED and BLACK leads to the\nconnections stated in the question.\n3. Be sure to read the correct scale. Less than\n5 ohms indicates continuity. For an open\ncircuit, the meter should peg full scale (needle\nall the way to the left).')
region(408, 'exception', [160, 522, 350, 575], 'NOTE\nYou will not be able to check the solid-state controller\nusing the pin-to-pin resistance check. The solid-state\ncontroller is identified by a green finish and a larger\ncase.')
region(408, 'replace', [159, 583, 338, 595], 'Replace glowplug controller, refer to (para 4-29).')
region(408, 'controller-labels', [205, 614, 313, 717], '4\n5 3\n6 2\n1')
region(408, 'controller-caption', [217, 723, 296, 733], 'Glowplug Controller')
region(408, 'pin-header', [404, 611, 593, 631], 'PIN-TO-PIN\nRESISTANCE')
table(408, 'pin', ['PIN 1', 'PIN 2', 'RESISTANCE'],
      [('1', '5', '130 Ω ± Ω'), ('2', '3', '0.40 Ω TO 0.75 Ω'),
       ('4', '5', '27 Ω ± 3 Ω'), ('2', '6', '.45 Ω MAXIMUM')],
      [404, 443, 481, 593], [631, 652, 678, 700, 728])

region(474, 'header', [75, 86, 578, 99], 'REFERENCE INFORMATION\nINSTRUMENTS CIRCUIT')
region(474, 'connector-location', [145, 206, 315, 226], 'The connector is located above the driveshaft\ntoward the rear of the vehicle.')
region(474, 'steice91', [375, 122, 566, 261], "0-4500 OHMS\nSTE/ICE-R TEST 91\n1. Connect RED clip and BLACK clip to the\nindicated terminals in the question. RED to the\nfirst, BLACK to the second.\n2. Start Test 91, 0-4500 ohms.\n3. Displayed reading is in ohms. Less than\n5 ohms is continuity. If the resistance is over\n4500 ohms, STE/ICE displays '9.9.9.9.'")
region(474, 'multimeter', [375, 268, 566, 414], 'CONTINUITY (RESISTANCE)\nMULTIMETER\n1. Set the voltmeter to an ohms scale of about\n1000 ohms.\n2. Connect the RED and BLACK leads to the\nconnections stated in the question.\n3. Be sure to read the correct scale. Less than\n5 ohms indicates continuity. For an open circuit,\nthe meter should peg full scale (needle all the\nway to the left).')
region(474, 'figure-labels', [147, 291, 324, 515], 'FUEL GAUGE\n28A\n58H\n58C\n27J\n58D\n58J\n58B\n58A\nFUEL LEVEL SENDING UNIT\nREAR OF LEFT CYLINDER HEAD')
region(474, 'gauge-header', [151, 583, 327, 602], 'GAUGE READING\nOHMS')
table(474, 'gauge', ['GAUGE READING', 'OHMS'], [('FULL', '35'), ('HALF', '16'), ('EMPTY', '0')],
      [151, 252, 327], [605, 618, 628, 641])

region(502, 'header', [40, 91, 537, 104], 'LIGHTS\nTURN SIGNAL SWITCH')
region(502, 'figure-caption', [297, 121, 440, 133], 'SWITCH DIAGRAM ("OFF" POSITION)')
region(502, 'figure-labels', [119, 136, 462, 382], 'H\nF\nG\nD\nA E C B\nA E D C B G F H')
region(502, 'connections-header', [127, 399, 456, 426], 'SUMMARY OF CONNECTIONS:\nTERMINAL\nCONNECTION\nWIRE NUMBER')
table(502, 'connections', ['TERMINAL', 'CONNECTION', 'WIRE NUMBER'], [
    ('A', 'RIGHT FRONT TURN SIGNAL', '460A'), ('B', 'LEFT FRONT TURN SIGNAL', '461A'),
    ('C', 'LEFT REAR TURN SIGNAL/STOP LAMP', '22-461A'), ('D', 'LIGHT SWITCH TERMINAL "C"', '22A'),
    ('E', 'RIGHT REAR TURN SIGNAL', '22-460A'), ('F', 'HAZARD/TURN SIGNAL FLASHER TERM. "B"', '325B'),
    ('G', 'LIGHT SWITCH TERMINAL "J" (24 VOLTS)', '467B'), ('H', 'HAZARD/TURN SIGNAL FLASHER TERM. "A"', '325A')],
    [127, 184, 401, 457], [438, 453, 469, 485, 501, 517, 533, 549, 565])
region(502, 'caution', [190, 582, 400, 614], 'CAUTION\nDISCONNECT NEGATIVE BATTERY CABLE PRIOR TO\nMAKING CONTINUITY MEASUREMENTS.')

region(547, 'header', [79, 92, 581, 117], 'DIAGNOSTIC FLOWCHART\nTRANSMISSION SYSTEM\n(4L80-E)')
region(547, 'title', [79, 124, 305, 138], 'TRANSMISSION TEMPERATURE SENSOR')
region(547, 'description', [78, 152, 582, 201], 'The transmission temperature sensor is a thermistor. The resistance decreases as the temperature\nincreases at 68°F (20°C) the resistance should be from 2980 to 4020 ohms, at 248°F (120°C) the\nresistance should be 90 to 111 ohms.')
region(547, 'low-title', [268, 222, 397, 237], 'RESISTANCE TOO LOW')
region(547, 'wire-label', [117, 252, 148, 266], '923A')
region(547, 'L1-question', [194, 244, 397, 290], 'Disconnect transmission connector\nfrom transmission. Check continuity\nfrom J1 pin e to J1 pin c.')
region(547, 'L1-no', [483, 238, 522, 270], 'NO')
region(547, 'L1-exit', [430, 286, 579, 330], 'Repair short from wire 923A\nto wire 359A/B/C/D,\n(para. 4-85).')
region(547, 'L1-yes', [343, 294, 382, 326], 'YES')
region(547, 'L2-question', [199, 337, 454, 365], 'Check continuity from J1 pin e to chassis ground.')
region(547, 'L2-no', [467, 341, 505, 372], 'NO')
region(547, 'L2-exit', [462, 383, 572, 418], 'Repair wire 923A,\n(para. 4-85).')
region(547, 'L2-yes', [343, 374, 382, 406], 'YES')
region(547, 'L2-continue', [322, 425, 465, 454], 'Refer to DS maintenance.')
region(547, 'high-title', [267, 521, 397, 537], 'RESISTANCE TOO HIGH')
region(547, 'H1-question', [104, 541, 414, 579], 'Disconnect transmission connector from transmission. Check\ncontinuity from J1 pin e to transmission connector pin L.')
region(547, 'H1-no', [472, 541, 510, 573], 'NO')
region(547, 'H1-exit', [431, 582, 583, 618], 'Repair short from wire 923A,\n(para. 4-85).')
region(547, 'H1-yes', [277, 585, 315, 617], 'YES')
region(547, 'H2-question', [112, 626, 434, 655], 'Check continuity from J1 pin c to transmission connector pin M.')
region(547, 'H2-no', [453, 622, 491, 654], 'NO')
region(547, 'H2-exit', [448, 666, 582, 701], 'Repair wire 359A/B/C/D,\n(para. 4-85).')
region(547, 'H2-yes', [276, 665, 314, 697], 'YES')
region(547, 'H2-continue', [197, 707, 338, 735], 'Refer to DS maintenance.')

region(574, 'header', [44, 79, 545, 93], 'STEERING SYSTEM\nDIAGNOSTIC FLOWCHART')
region(574, 'start', [226, 77, 311, 115], 'FROM B6,\nPage 2-468')
STEERING = [
    ('B7', 127, 209, 291, 127, 145, 241, 129, 206, 273,
     'IS THE HYDRO-BOOSTER\nWORKING PROPERLY?', 'TEST OPTIONS\nSEE INSTRUCTIONS AT RIGHT.',
     'REASON FOR QUESTION\nThe hydro-booster will affect the\noperation of the steering system.'),
    ('B8', 325, 404, 487, 324, 340, 436, 325, 401, 469,
     'TURN STEERING WHEEL\nSLIGHTLY TO LEFT OR RIGHT\nAND RELEASE WHEEL QUICKLY.\nTHE STEERING WHEEL SHOULD\nCENTER ITSELF. DOES THIS\nHAPPEN?', 'TEST OPTIONS\nTRY IT',
     'REASON FOR QUESTION\nThe steering gear is working\nproperly if this happens.'),
    ('B9', 525, 606, 690, 525, 543, 639, 526, 602, 674,
     'LOOK AT THE CHART TO THE\nRIGHT TO DETERMINE WHAT IS\nWRONG AND REPAIR IT AS\nDIRECTED.', 'TEST OPTIONS\nN/A', 'REASON FOR TESTS\nN/A')]
for step, k0, k1, k2, ident, q0, q1, o0, o1, o2, question, options, reason in STEERING:
    region(574, step+'-id', [168, ident, 205, q0], step)
    region(574, step+'-known', [45, k0, 158, k1], 'KNOWN INFO\nHARD OR ABNORMAL\nSTEERING')
    region(574, step+'-possible', [45, k1, 158, k2], 'POSSIBLE PROBLEMS\nPOWER STEERING PUMP\nPOWER STEERING GEAR\nFAN DRIVE\nHYDRO-BOOSTER')
    region(574, step+'-question', [173, q0, 368, q1], question)
    region(574, step+'-options', [344, o0, 507, o1], options)
    region(574, step+'-reason', [349, o1, 507, o2], reason)
for step, ny, ey, yy in [('B7', 259, 252, 289), ('B8', 454, 446, 483)]:
    region(574, step+'-no', [210, ny, 233, ny+23], 'NO')
    region(574, step+'-exit', [252, ey, 337, ey+41], 'REMEMBER\nFOR END OF\nTEST')
    region(574, step+'-yes', [170, yy, 208, yy+20], 'YES')

region(575, 'header', [88, 101, 585, 115], 'REFERENCE INFORMATION\nSTEERING SYSTEM')
region(575, 'hydro-method', [160, 216, 427, 246], "Method for checking hydro-booster. Depress brake pedal several times to\nexhaust accumulator. Depress brake pedal and start engine. Brake pedal\nshould fall, then push back against operator's foot.")
region(575, 'answers-header', [165, 466, 419, 502], 'ANSWERS TO QUESTION:\nB6 B7 B8\nCOMPONENT\nTO REPLACE')
table(575, 'answers', ['B6', 'B7', 'B8', 'COMPONENT TO REPLACE'], [
    ('NO','NO','NO','POWER STEERING PUMP'), ('NO','NO','YES','SEE NOTE\nBELOW'),
    ('NO','YES','NO','SEE NOTE\nBELOW'), ('NO','YES','YES','RUN ENGINE COOLING\nTEST (PARA 2-19)'),
    ('YES','NO','NO','POWER STEERING PUMP'), ('YES','NO','YES','HYDRO-BOOSTER'),
    ('YES','YES','NO','DS LEVEL\nSTEERING GEAR'), ('YES','YES','YES','NO FAULTS')],
    [165, 208, 247, 293, 419], [502, 518, 544, 568, 598, 616, 633, 661, 680])
region(575, 'table-note', [162, 693, 429, 739], 'NOTE\nTo diagnose the second and third cases to one item, it is necessary\nto have a power steering analyzer. Additionally, for all cases, check\nthe hoses for the particular part to make sure they are OK.')

region(612, 'header', [42, 57, 541, 125], 'AMBULANCE\n(All Dome Lamps)\nWith Ambulance\nCompartment Front Door,\nRear Door, and Rear Step\nClosed (Refer to Fig. 11.)\nDIAGNOSTIC FLOWCHART')
region(612, 'start', [218, 78, 324, 116], 'FROM 16,\nPage 2-508')
AMBULANCE = [
    ('17', 129, 196, 273, 130, 147, 261, 130, 206, 270,
     'KNOWN INFO\nPREVIOUSLY CORRECTED\nINFORMATION',
     'POSSIBLE PROBLEMS\nLEAD 660 D\nBLOWN FUSES\nLEAD 712\nLEAD 711\nDAMAGED LEADS',
     'IS THERE BATTERY VOLTAGE IN\nCONTROL BOX AT FUSE BLOCK?',
     'TEST OPTIONS\n1. STE/ICE-R TEST 89, PAGE 2-750\n2. MULTIMETER',
     'REASON FOR QUESTION\nNo voltage would indicate a\ndamaged power supply lead,\nthus no power.'),
    ('18', 334, 383, 449, 321, 340, 453, 321, 397, 460,
     'KNOWN INFO\nLEAD 660 D OK',
     'POSSIBLE PROBLEMS\nBLOWN FUSES\nLEAD 712\nLEAD 711\nDAMAGED LEADS',
     'CHECK FUSE BLOCK IN CONTROL\nBOX. ARE FUSES OK?', 'TEST OPTIONS\nVISUAL',
     'REASON FOR QUESTION\nDamaged fuses causes the\npower circuit to be incomplete.'),
    ('19', 523, 585, 642, 511, 531, 646, 508, 584, 647,
     'KNOWN INFO\nLEAD 660 D OK\nFUSES OK', 'POSSIBLE PROBLEMS\nLEAD 712\nLEAD 711\nDAMAGED LEADS',
     'IS THERE BATTERY VOLTAGE IN\nCONTROL BOX AT:\nTB TERMINAL 1?\nTB TERMINAL 2?',
     'TEST OPTIONS\n1. STE/ICE-R TEST 89, PAGE 2-750\n2. MULTIMETER',
     'REASON FOR QUESTION\nNo power would indicate\ndamaged leads.')]
for step, k0, k1, k2, ident, q0, q1, o0, o1, o2, known, possible, question, options, reason in AMBULANCE:
    region(612, step+'-id', [169, ident, 206, q0], step)
    region(612, step+'-known', [42, k0, 157, k1], known)
    region(612, step+'-possible', [42, k1, 157, k2], possible)
    region(612, step+'-question', [172, q0, 366, q1], question)
    region(612, step+'-options', [344, o0, 506, o1], options)
    region(612, step+'-reason', [349, o1, 506, o2], reason)
for step, ny, ex, yy, text in [
    ('17', 265, [240, 264, 341, 317], 289, 'REPLACE LEAD 660 D'),
    ('18', 464, [250, 458, 368, 508], 476, 'REPLACE BLOWN FUSES'),
    ('19', 653, [253, 647, 368, 704], 672, 'REPLACE LEAD 712\nAND/OR LEAD 711')]:
    region(612, step+'-no', [209, ny, 234, ny+20], 'NO')
    region(612, step+'-exit', ex, text)
    region(612, step+'-yes', [168, yy, 212, yy+20], 'YES')
region(612, '19-continue', [142, 706, 242, 759], 'GO TO 20,\nPage 2-512')

# Only the two test cards are changed on page 613. Its complex wiring diagram
# remains verbatim in the frozen OCR and explicitly requires separate review.
region(613, 'steice89', [366, 167, 562, 269], '0-45 DC VOLTS\nSTE/ICE-R TEST 89\n1. Connect RED clip to the indicated test point,\nBLACK clip to negative or ground.\n2. Start test 89, DC volts.\n3. Displayed reading is in volts.')
region(613, 'multimeter', [366, 278, 562, 388], 'BATTERY VOLTAGE\nMULTIMETER\n1. Set the voltmeter to a DC volts scale of at least\n40 volts.\n2. Connect the RED lead to positive and the\nBLACK lead to negative.\n3. Be sure to read the correct scale.')

region(828, 'header', [47, 92, 548, 106], 'DCA TROUBLESHOOTING\nDIAGNOSTIC FLOWCHART')
region(828, 'start', [226, 90, 307, 125], 'B FROM 2,\nPage 2-724')
DCA = [
    ('B1', 139, 218, 301, 139, 157, 243, 139, 220, 269,
     'KNOWN INFO\nSTE/ICE-R OK\nCABLES OK\nTK OK USING PULSE\nTACHOMETER',
     'POSSIBLE PROBLEMS\nTACHOMETER\nVEHICLE SYSTEMS\nDCA',
     'REMOVE THE TACHOMETER\nFROM THE ENGINE AND\nINSPECT IT. IS IT OK?',
     'TEST OPTIONS\nVISUAL INSPECTION - CHECK\nFOR BROKEN WIRES OR\nCONNECTORS AND WORN\nPARTS. ALSO CHECK THE SLOT\nIN THE OIL PUMP DRIVE.',
     "REASON FOR QUESTION\nIf the tachometer is no good, you\ncan't expect good test results."),
    ('B2', 353, 432, 514, 353, 369, 454, 353, 432, 481,
     'KNOWN INFO\nVEHICLE TACHOMETER\nOK\nSTE/ICE-R OK', 'POSSIBLE PROBLEMS\nVEHICLE SYSTEMS\nDCA',
     'INSTALL THE TACHOMETER\nFROM THE TK KIT. RUN THE\nORIGINAL TEST WITH THE VTM\nIN THE TK MODE. IS THE\nVEHICLE OK?',
     'TEST OPTIONS\nSEE THE CHART ON THE\nFOLDOUT PAGE TO RUN THE\nTK VERSION OF THE\nTEST YOU WANT',
     'REASON FOR QUESTION\nYou want to know if the vehicle\nis OK.'),
    ('B3', 546, 626, 710, 546, 563, 642, 546, 625, 688,
     'KNOWN INFO\nVEHICLE OK\nSTE/ICE-R OK\nCABLES OK\nTK OK', 'POSSIBLE PROBLEMS\nDCA',
     'DID THE ORIGINAL DCA TEST\nGIVE A CORRECT RESULT?', 'TEST OPTIONS\nN/A',
     'REASON FOR QUESTION\nIf you got a substantially\ndifferent test result through\nthe DCA, then you have a DCA\nproblem.')]
for step, k0, k1, k2, ident, q0, q1, o0, o1, o2, known, possible, question, options, reason in DCA:
    region(828, step+'-id', [167, ident, 201, q0], step)
    region(828, step+'-known', [47, k0, 158, k1], known)
    region(828, step+'-possible', [47, k1, 158, k2], possible)
    region(828, step+'-question', [172, q0, 368, q1], question)
    region(828, step+'-options', [343, o0, 506, o1], options)
    region(828, step+'-reason', [349, o1, 506, o2], reason)
for step, nb, eb, yb, text in [
    ('B1', [209,270,231,292], [247,262,336,303], [167,299,202,320], 'REPLACE\nTACHOMETER'),
    ('B2', [195,455,218,478], [210,474,400,547], [167,512,202,532], 'VEHICLE PROBLEM.\nIF YOU CAME FROM ANOTHER\nPARAGRAPH, RETURN THERE AND FOLLOW\nTHE PATH CORRESPONDING TO A\nFAILURE OF THE TEST YOU\nWERE RUNNING'),
    ('B3', [209,653,231,675], [246,654,325,690], [169,675,204,695], 'SEE NOTE TO\nRIGHT')]:
    region(828, step+'-no', nb, 'NO')
    region(828, step+'-exit', eb, text)
    region(828, step+'-yes', yb, 'YES')
region(828, 'B3-continue', [148,713,232,744], 'NO FAULTS')

region(829, 'header', [74, 98, 573, 110], 'REFERENCE INFORMATION\nDCA TROUBLESHOOTING')
region(829, 'B1-reference', [137, 219, 344, 258], 'Remove tachometer, refer to (para 4-13). If you find the\ntachometer defective, replace it and return to where you\ncame from and rerun the original DCA test. If it fails again\nreturn to this question and answer "YES".')
region(829, 'B2-reference', [134, 427, 341, 476], "Make sure the STE/ICE-R is powered by the W5 cable.\nIf you don't find any faults in the vehicle, the slot in the\noil pump drive could be too worn to drive the tachometer.\nIf you see this, notify DS maintenance.")
region(829, 'B3-interpretation', [138, 584, 338, 615], 'You will have to decide if the DCA test result is wrong.\nIf the TK test gave a substantially different result than\nthe DCA test, answer "NO" to this question.')
region(829, 'B3-note', [138, 621, 339, 682], "NOTE\nVehicle DCA faulty. Use the STE/ICE-R in the TK mode\nfor the rest of your testing. See the chart on the foldout\npage for a way to run the rest of the DCA tests in the\nTK mode. Have DS maintenance repair the DCA when\nyou're finished.")


def main():
    parent = io.BASE/'corrections/batch-007/correction-log.json'
    out = io.BASE/'corrections/batch-008'
    if out.exists():
        raise ValueError('Use a new correction batch; do not overwrite frozen inputs')
    ledger = json.loads(parent.read_text(encoding='utf-8'))
    original = {r['id']: r for r in io.source_records(io.check_inputs(ledger))}
    out.mkdir(); (out/'evidence').mkdir()
    for p in ledger['corrections']:
        (out/p['evidence_crop']).write_bytes((parent.parent/p['evidence_crop']).read_bytes())
    added, spans = [], []
    with pymupdf.open(io.ROOT/ledger['inputs']['pdf']['path']) as pdf:
        for pn, regions in REGIONS.items():
            rid = f'P{pn:04d}:ocr'
            assert not any(p['record_id'] == rid for p in ledger['corrections'])
            raw = original[rid]['text']; a, b = 0, len(raw)
            if pn == 613:
                a = raw.index('0-45 DC VOLTS'); b = raw.index('\n\nSPARE FUSE')
            after = '\n\n'.join(text for _, _, text in regions)
            rect = pdf[pn-1].rect
            clip = [35, 55, rect.width-25, rect.height-25] if pn != 613 else [360,160,570,395]
            patch = {'id': f'FIX-V8-{pn:04d}', 'record_id': rid, 'pdf_page': pn,
                     'start': a, 'end': b, 'before': raw[a:b], 'after': after,
                     'bbox': clip, 'render_clip': clip,
                     'reason': 'PDF를 대조해 표의 셀, 질문·조건·분기, 참고 설명을 구분하여 재전사했다. 문자 오독과 누락을 보정하고 각 영역의 좌표를 기록했다. 배선도에서 연결 의미를 추론하거나 원문의 결함을 추정값으로 채우지 않았다.',
                     'kind': 'PDF_REGION_RETRANSCRIPTION', 'source_check': 'CODEX_PDF_VISUAL_CHECK',
                     'human_review': 'NOT_PERFORMED',
                     'layout_only_not_transcribed': [] if pn == 613 else ['document running header', 'printed page footer']}
            name = 'evidence/'+patch['id']+'.png'
            pdf[pn-1].get_pixmap(clip=pymupdf.Rect(clip), dpi=180, alpha=False).save(out/name)
            patch.update(evidence_crop=name, evidence_sha256=io.sha(out/name)); added.append(patch)
            offset = a
            for name, bbox, text in regions:
                spans.append({'name': name, 'pdf_page': pn, 'record_id': rid, 'start': offset,
                              'end': offset+len(text), 'text': text, 'bbox': bbox,
                              'review': 'CODEX_PDF_LAYOUT_REVIEW', 'human_review': 'NOT_PERFORMED',
                              'evidence': {'file': (out/patch['evidence_crop']).relative_to(io.ROOT).as_posix(),
                                           'sha256': patch['evidence_sha256']}})
                offset += len(text)+2
    ledger['parent'] = {'path': parent.relative_to(io.ROOT).as_posix(), 'sha256': io.sha(parent),
                        'preserved_corrections': len(ledger['corrections'])}
    ledger['corrections'] += added
    ledger.update(batch='batch-008-table-and-condition-repair', date='2026-09-24',
                  region_review={'pages': sorted(REGIONS), 'partial_page': 613,
                                 'evaluation_questions_read': False, 'arrow_prose_generated': False})
    io.validate_ledger(list(original.values()), ledger)
    (out/'correction-log.json').write_bytes(io.json_bytes(ledger))
    (out/'source-regions.json').write_bytes(io.json_bytes(spans))
    (out/'table-cell-map.json').write_bytes(io.json_bytes(TABLES))
    print(json.dumps({'added': len(added), 'cumulative': len(ledger['corrections']),
                      'regions': len(spans), 'table_rows': sum(len(t['rows']) for t in TABLES)}))


if __name__ == '__main__':
    main()
