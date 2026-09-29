"""Source-image review decisions. Serial numbers refer to the frozen 557-row list.

This is a recorded Codex visual review, not a human or automatic semantic review.
No decisions are inferred for entries absent from DECISIONS.
"""
DECISIONS = {}


def note(numbers, category, reason):
    for number in numbers:
        assert number not in DECISIONS, number
        DECISIONS[number] = dict(category=category, reason=reason, edits=[])


def fix(number, layer, replacements=None, text=None, reason='PDF 원문에서 확인한 문자로 복원'):
    assert number not in DECISIONS, number
    DECISIONS[number] = dict(category='TEXT_CORRECTION', reason=reason,
                            edits=[dict(layer=layer, replacements=replacements, text=text)])


def revise(number, category, reason, edits=None):
    assert number in DECISIONS
    DECISIONS[number] = dict(category=category, reason=reason, edits=edits or [])


fix(1, 'ocr', [('¢ ', '• '), ('HI)', 'III)')])
fix(2, 'ocr', [('* ', '• '), ('section I)', 'section III)')])
fix(3, 'ocr', [('e Detailed', '• Detailed')])
fix(4, 'ocr', [('¢ ', '• '), ('II and II)', 'II and III)')])
fix(5, 'ocr', [('e Mandatory', '• Mandatory')])
for n in (6,7,8,29,30,31):
    fix(n, 'ocr', [('Z ', 'Ž ')], reason='PDF에 실제로 인쇄된 Ž를 보존한다. 이를 문법상 목록 기호로 임의 변경하지 않는다.')
note([9,10,23,32,35,38,51], 'SEPARATE_NATIVE_LABEL',
     '원문 번호 또는 제목은 본문 왼쪽에 별도 조판되어 있다. OCR은 같은 행으로 묶었다. 번호·제목의 native 별도 블록과 연결해 보존하며 본문에 중복 삽입하지 않는다.')
note([11,12,13,14,15,16,17,19], 'OCR_CROSS_REGION_MERGE',
     'OCR 행이 왼쪽 설명문과 오른쪽 축소 그림의 글자를 합쳤다. 왼쪽 설명문은 native 구간을 채택하고 혼합 OCR 행은 독립 문장으로 채택하지 않는다. 그림은 별도 영역으로 보존한다.')
fix(18, 'ocr', [('. Turn to chapter', '2. Turn to chapter')])
fix(20, 'ocr', [('must do to', 'you must do to')])
fix(21, 'ocr', [('Before beginning', '1. Before beginning')])
fix(22, 'ocr', [('The ten basic', '2. The ten basic')])
fix(24, 'ocr', [('section II.', 'section III.')])
fix(25, 'ocr', [('e Manual', '• Manual')])
fix(26, 'ocr', [('e¢ Equipment', '• Equipment')])
fix(27, 'ocr', [('e General', '• General')])
fix(28, 'ocr', [('step |', 'step 1')])
fix(33, 'ocr', [('xii_', 'xii')])
for n in (34,36,37):
    fix(n, 'ocr', [('$250', 'S250')])
note([39,48,50,52,53,54,55,56], 'FIGURE_CALLOUT',
     '원문 왼쪽 원 안의 대문자는 그림의 참조 문자다. OCR의 괄호 표기는 도형을 일반 텍스트로 읽은 것이다. 본문과 별도의 그림 참조로 유지하며 소문자 OCR 해석을 근거로 쓰지 않는다.')
note([40], 'DETAIL_REVIEW', '제목 우측 글자가 겹치고 native/OCR 모두 일부 손상됨. 확대 및 문자 좌표 재검토 필요.')
fix(41, 'ocr', [('L 1-13.', '1-13.'), (' |', '')])
fix(42, 'ocr', [('a 1-13.', '1-13.')])
note([43], 'SEPARATE_NATIVE_LABEL', '표 번호 Table 1-1.은 제목 앞에 실제 인쇄되어 있다. OCR의 제목 일부 행과 native 전체 제목을 비교한 차이이므로 native 전체 제목을 보존한다.')
fix(44, 'native', text='1-20. COOLING SYSTEM OPERATION', reason='PDF 제목의 실제 단어와 번호를 기준으로 잘못 들어간 글자 사이 공백을 제거한다.')
fix(45, 'ocr', [('L 1-23.', '1-23.')])
fix(46, 'native', text='1-23.1. GENERATING SYSTEM OPERATION (100 AMPERE DUAL VOLTAGE ALTERNATOR)', reason='PDF 제목을 대조해 잘못 들어간 글자 사이 공백을 제거한다. OCR의 ATERNATOR 누락은 채택하지 않는다.')
fix(47, 'native', text='1-23.2. GENERATING SYSTEM OPERATION (200 AMPERE DUAL VOLTAGE ALTERNATOR)', reason='PDF 제목을 대조해 잘못 들어간 글자 사이 공백을 제거한다.')
fix(49, 'native', text='SUSPENSION SYSTEM OPERATION', reason='원문의 단어 OPERATION에 삽입된 글자 사이 공백을 제거한다. 별도 번호 블록은 그대로 둔다.')
note([57,59], 'TYPOGRAPHIC_DIFFERENCE', '원문의 Section I/II 표제와 내용은 native에 보존되어 있다. 대소문자·로마숫자 획 모양의 OCR 차이이며 native를 채택한다.')
fix(58, 'ocr', [('unit. pe', 'unit.')], reason='문장 뒤의 pe는 원문 사각형 테두리를 잘못 읽은 것이므로 제거한다.')
note([60,61,62,63,64,65,66,67,68,70,71,72,73,74,75,76,77,79,80,81,82,83,84], 'TABLE_COLUMN_MERGE',
     '원본 표의 세로 구분선과 셀을 대조했다. OCR이 서로 다른 열의 문장을 같은 행으로 합쳤다. 검증된 PMCS 셀 구조를 채택하며 혼합 OCR 행을 문장으로 이어 붙이지 않는다.')
fix(69, 'ocr', [('3 Nem', '3 N·m')], reason='원문 토크 단위 N·m의 가운데점을 e로 오인한 OCR을 복원한다.')
fix(78, 'ocr', [('81 Nem', '81 N·m')], reason='원문 토크 단위 N·m의 가운데점을 e로 오인한 OCR을 복원한다.')

note([85,86,87,88,89,90,91,92,93,94,97,98,99,100,104,105,106,107,108,110,111,112,117,118,119,120,121,124,125,126],
     'TABLE_COLUMN_MERGE', '원문 세로 구분선으로 다른 셀임을 확인했다. OCR은 같은 높이의 여러 열을 한 문장으로 합쳤다. 검증된 PMCS 셀 구조를 채택하고 혼합 OCR 행은 문장 근거로 채택하지 않는다.')
fix(95, 'ocr', [('IT for', 'II for')])
fix(96, 'ocr', [('47 Nem', '47 N·m')])
fix(101, 'native', text='(22-24 N•m)', reason='원문 수치 22-24의 글자 사이에 삽입된 공백을 제거한다.')
DECISIONS[101]['edits'].append(dict(layer='ocr', replacements=[('Nem','N·m')], text=None))
for n in (102,103):
    fix(n, 'ocr', [('eFill', '•Fill')])
fix(109, 'ocr', [('81 Nem', '81 N·m')])
for n in (113,114,115,122,123):
    fix(n, 'ocr', [('Nem', 'N·m')])
fix(116, 'ocr', [('reeommended', 'recommended')])

note(list(range(127,136)), 'TABLE_COLUMN_MERGE',
     '원본 표의 세로 구분선과 각 셀을 확인했다. OCR은 여러 열의 내용을 같은 행으로 묶었다. 검증된 PMCS 셀 구조를 채택한다.')
for n in (136,137,138):
    fix(n, 'ocr', [('e Use','• Use'), ('e Fill','• Fill')])
note([139,143,144,145,146,147,148,150,154,157,158,160,164], 'OCR_CROSS_REGION_MERGE',
     '원문에서 서로 떨어진 표제·흐름도·그림 영역이 OCR 한 행에 합쳐져 있다. 각 native 영역은 보존하고 혼합 OCR 행을 하나의 문장으로 채택하지 않는다.')
note([140,151,152,153,156,159,161,162,163,167,168], 'SEPARATE_NATIVE_LABEL',
     '원문에는 줄바꿈, 번호 또는 서로 다른 글꼴의 이어지는 구간이 있다. native 행과 OCR 행의 경계가 달라 생긴 비교 차이로 판정한다. 주변 native 블록을 보존해 연결하고 중복 문장을 삽입하지 않는다.')
fix(141, 'ocr', [('PROCEOURES','PROCEDURES')])
fix(142, 'ocr', text='2-17. STARTABILITY TESTS')
fix(149, 'ocr', text='2-19. COOLING SYSTEM TESTS')
fix(155, 'ocr', [('HMMWYV','HMMWV')])
fix(165, 'ocr', text='1. Connect RED clip to the indicated')
fix(166, 'ocr', text='1. Connect a tee into the fuel line')

note([169,170], 'SEPARATE_NATIVE_LABEL', '원문 단계 번호 3./4.는 본문과 떨어진 native 구간이며 OCR에서 합쳐졌다. 번호와 본문을 모두 보존한다.')
note([171,172,173,175,176,178,179,180,182,184,185,186,187,188,189,190,191,192,193,194,195,196,197,199,200,209,210],
     'OCR_CROSS_REGION_MERGE', '원문에서 좌우 표제·절차·그림 영역이 구분되어 있는데 OCR은 이를 한 행으로 묶었다. 각 native 영역을 채택하고 혼합 OCR 행은 하나의 문장으로 쓰지 않는다.')
fix(174, 'ocr', [('o teat for', 'To teat for')], reason='원문의 To를 복원한다. 원문에 실제 인쇄된 teat는 test로 임의 교정하지 않는다.')
fix(177, 'ocr', [('AIR_INTAKE','AIR INTAKE')])
fix(181, 'ocr', text='5. Wait for the GO message. Crank the engine.')
fix(183, 'ocr', text='1. Start and idle engine.')
fix(198, 'ocr', [('analo','analog')])
note(list(range(201,209)), 'TABLE_ROW_ALIGNMENT',
     '원문은 ENGINE RPM과 APPROXIMATE OIL PRESSURE 두 열의 표다. OCR은 같은 행의 대응 값을 한 줄로 묶었고 native는 셀별로 나눴다. 셀 값 자체는 원본과 대조하여 같은 행 관계로 보존한다.')

note([211,212,213,214,216,218,220,221,222,223,224,225,226,227,228,229,230,231,232,233,234,236,237,238,239,241,242,244,246,248,249,250,251],
     'OCR_CROSS_REGION_MERGE', '원문 좌우 표제·설명·그림 또는 다음 NOTE 영역이 별개임을 확인했다. native 영역을 각각 보존하고 OCR의 혼합 행은 하나의 문장으로 채택하지 않는다.')
fix(215, 'ocr', [('Nem','N·m')], reason='원문 토크 단위의 가운데점을 복원한다. 원문의 단위 환산 수치는 변경하지 않는다.')
fix(217, 'ocr', [('screw EO','screw E0')])
fix(219, 'ocr', [('connection EO','connection E0')])
fix(235, 'ocr', [('LE BLACK','BLACK')], reason='문장 앞 가로·세로 테두리를 LE로 읽은 OCR 잡음을 제거한다.')
fix(240, 'ocr', text='3. Inspect and clean wires and connection points.')
fix(243, 'ocr', [('equipment. i','equipment.')], reason='우측 개정 표시 막대를 문자 i로 읽은 잡음을 제거한다.')
fix(245, 'ocr', [('Failure to i','Failure to')], reason='우측 개정 표시 막대를 문자 i로 읽은 잡음을 제거한다.')
fix(247, 'ocr', [('290.','29C.')])
fix(252, 'ocr', [('millionms','milliohms')])

fix(253, 'ocr', [('millionms','milliohms')])
note([254,255,256,257,259,260,261,262,263,264,265,266,267,268,269,270,271,272,276,277,278,285,286,287,289,290,291,292,293,294],
     'OCR_CROSS_REGION_MERGE', '원본의 좌우 영역·테두리·그림·별도 제목이 OCR 한 행에 혼합되었다. 원문 문자 위치에 따라 native 영역을 각각 보존하고 혼합 OCR 행은 문장 근거에서 제외한다.')
note([258,279,280,281,282,283,284], 'SEPARATE_NATIVE_LABEL',
     '원문 번호 또는 줄바꿈 구간이 native에서는 나뉘고 OCR에서는 묶여 있다. 원문에 존재하는 주변 블록을 보존하며 번호·문장을 새로 중복 삽입하지 않는다.')
fix(273, 'ocr', [('millionms','milliohms')])
fix(274, 'ocr', [('voltrneter','voltmeter')])
fix(275, 'native', [('max. I','max.')], reason='문장 끝의 I는 원본 우측 상자 테두리이며 문장의 일부가 아니다.')
fix(288, 'ocr', [('ohmss','ohms')], reason='원본 상자 테두리에 붙어 중복 인식된 s를 제거한다.')

note([295,296,297,298,299,300,301,302,303,306,307,308,309,310,315,327], 'OCR_CROSS_REGION_MERGE',
     '서로 다른 본문·배선도·흐름도·표제의 위치를 원본과 대조했다. OCR의 혼합 행을 문장으로 쓰지 않고 각각의 native 영역을 보존한다.')
for n in (304,305):
    fix(n, 'native', [('INSTRUMENTS CIRCUIT','INSTRUMENTS CIRCUITS')], reason='원문 표제 끝의 복수형 S가 native 추출에서 누락되었다.')
for n in (311,312):
    fix(n, 'ocr', text='@native', reason='원문 핀 식별 문자와 따옴표를 native 구간 및 원문 이미지에 맞춰 복원한다.')
for n in (313,314):
    fix(n, 'native', [('G IF','• IF')], reason='원문의 둥근 목록 기호가 G로 매핑된 native 추출 오류를 복원한다.')
for n in range(316,327):
    fix(n, 'ocr', text='@native', reason='원문 단계 번호가 OCR에서 누락되었다. 원문과 일치하는 native 행의 번호와 문장을 복원한다.')
fix(328, 'ocr', [('e Milky','• Milky')])
fix(329, 'ocr', text='@native', reason='원문의 Paragraph 2-33 of this 참조 구간에서 추가 0과 붙은 단어 경계를 바로잡는다.')
note([330], 'SEPARATE_NATIVE_LABEL', '원문 표제의 실제 줄바꿈 위치와 두 추출층의 행 경계가 다르다. 앞뒤 표제 블록을 보존한다.')
for n in range(331,337):
    fix(n, 'native', [('G ','• '), ('c Conditions','• Conditions')], reason='원문의 둥근 목록 기호를 G/c로 잘못 매핑한 native 추출을 복원한다.')

for n in list(range(337,379)) + list(range(380,393)):
    fix(n, 'native', [('G ','• '), ('c The','• The'), ('. All','• All'), ('s Trans','• Trans')],
        reason='PDF에 실제 인쇄된 둥근 목록 기호가 G/c/s/마침표로 매핑되었다. 해당 기호만 복원하고 원문의 기술 수치·단어는 유지한다.')
fix(379, 'ocr', [('OFP','OFF')])
for n in (393,394,395):
    fix(n, 'ocr', [('e Vehicle','• Vehicle'), ('e Trans','• Trans'), ('e All','• All')])
note([396,397,398,399,400,401,402,403,404,406], 'FLOWCHART_BRANCH',
     'No는 원본 흐름도 연결선의 분기 조건이며 Go to pg는 타원 안의 이동 지시다. 문장 누락이 아니다. 두 영역과 연결 관계를 구분해서 보존하며 No Go라는 일반 문장으로 사용하지 않는다.')
fix(405, 'native', [('¡','→')], reason='원문 High Temp와 Low Resist. 사이의 오른쪽 화살표가 ¡로 추출되었다. 방향을 원문대로 복원한다.')
note([407,408,409,410,413,414,417], 'OCR_CROSS_REGION_MERGE',
     '원본의 다른 흐름도 상자·연결선·그림 참조 또는 좌우 표제가 한 OCR 행으로 합쳐졌다. native 영역을 각각 보존하고 혼합 OCR 행을 문장 근거로 채택하지 않는다.')
fix(411, 'ocr', [('connecior','connector')])
fix(412, 'ocr', [('Kohms Q.','Kohms Ω.')])
note([415,416,418,419,420], 'SEPARATE_NATIVE_LABEL',
     '원문 단계 A/B/D/E/(1) 참조는 본문과 떨어진 native 구간이고 OCR은 같은 행으로 묶었다. 주변 번호 블록을 함께 보존한다.')

note([421,422,423,429,430,431,432,433,434,436,437,438], 'SEPARATE_NATIVE_LABEL',
     '원문의 단계 번호와 본문이 native에서 따로 추출되었다. OCR에는 번호가 같은 행에 있다. 기존 번호 블록을 보존하고 본문에 중복 삽입하지 않는다.')
note([424,425,426,427,428,435,439,440,441,442,443,444,445,446,447,448,449,450,451,452,454,457,458,459,460,461,462],
     'OCR_CROSS_REGION_MERGE', '원본의 본문과 옆 그림·표제·선이 OCR에서 혼합되었다. native 본문과 그림 영역을 각각 보존하고 해당 OCR 행을 독립 문장으로 채택하지 않는다.')
fix(453, 'ocr', [('(8 mm)','(3 mm)')], reason='원문 간극의 단위값은 3 mm다. OCR의 8 mm를 3 mm로 복원한다.')
for n in (455,456):
    fix(n, 'ocr', [('© ','o ')], reason='원문의 속이 빈 작은 원 목록 기호는 native의 o 표기로 유지한다. OCR의 저작권 기호 ©를 원문과 맞춘다.')

note([463,464,466,467,468,469,470,473,474,475,476,477,478,479,482,483,484,485,486,487,496,497],
     'SEPARATE_NATIVE_LABEL', '원본 참조 문구의 앞뒤 단어·괄호·줄바꿈이 native/OCR에서 서로 다른 구간으로 묶였다. 주변 native 블록과 참조 번호를 보존한다. 비교 행 길이 차이를 문장 누락으로 판단하지 않는다.')
DECISIONS[473]['edits'].append(dict(layer='ocr', replacements=[('tefer','refer')], text=None))
note([465,471,472,480,481,488,489,490,491,492,494,495,498], 'OCR_CROSS_REGION_MERGE',
     '원본에서 떨어진 표제·흐름도 노드·좌우 설명이 한 OCR 행으로 결합됐다. native 영역을 각각 보존하고 혼합 OCR 행을 문장으로 채택하지 않는다.')
note([493], 'DETAIL_REVIEW', '원문과 OCR의 or/of를 원문 확대 및 원시 문자열로 재확인한다.')
note(list(range(499,505)), 'TABLE_ROW_ALIGNMENT',
     '원문은 TEST TITLE, TEST NO., PAGE 표다. OCR은 같은 행의 세 열을 합쳤고 native는 셀 단위로 추출했다. 실제 대응 행을 확인했으므로 표의 행·열 관계로 보존한다.')

note(list(range(505,518)), 'TABLE_ROW_ALIGNMENT',
     '원문 테스트 목록 표에서 제목·시험번호·쪽수의 같은 행 관계를 확인했다. native는 셀별, OCR은 행별 추출이므로 표 구조로 보존한다. DC VOLTAGE의 원문 시험번호 39도 임의로 바꾸지 않는다.')
for n in range(518,541):
    fix(n, 'ocr', text='@native', reason='PDF 원문에 인쇄된 단계 번호가 OCR에서 누락되었다. native와 원문이 일치하는 번호와 해당 행을 복원한다. 원문의 da-energized 등 표현은 바꾸지 않는다.')
fix(541, 'ocr', [('VIM','VTM')])
note([542,543,544,545,546], 'TABLE_ROW_ALIGNMENT',
     'VTM Readout와 Interpretation 표의 서로 다른 열이다. .8.8.8.8 / .9.9.9.9 / PASS·FAIL 값과 설명의 대응 관계로 보존하며 코드 값을 설명 문장에 중복 삽입하지 않는다.')
fix(547, 'ocr', [('STEAICE','STE/ICE')])
note([548,549,551,552,553,554,555,556,557], 'SEPARATE_NATIVE_LABEL',
     '접지 도면의 FO-1~FO-9 식별자가 native에서는 별도 구간이고 OCR에서는 제목과 같은 행으로 묶였다. 원문 도면 번호와 제목을 함께 보존한다.')
note([550], 'DETAIL_REVIEW', '원문 도면 캡션의 Location/Locations를 확대 확인한다.')

# Second look: enlarged source images and embedded character positions.
revise(40, 'TEXT_CORRECTION',
       '제목의 PLA와 TES는 같은 기준선에 있으며 A/T가 겹쳐 인쇄되어 있다. PDF 내부 문자 순서와 확대 이미지를 함께 확인해 PLATES로 연결하고 글자 사이 공백을 제거한다. 새 단어를 추정 생성하지 않는다.',
       [dict(layer='native', before_text="1 - 1 3 . L O C ATION AND CONTENTS OF WARNING, CAUTION, AND DATA PLA\nT E S\n( C o n t ' d )",
             text="1-13. LOCATION AND CONTENTS OF WARNING, CAUTION, AND DATA PLATES\n(Cont'd)",
             render_clip=[50,70,560,110])])
for n in (46,47):
    DECISIONS[n]['reason'] = 'PDF 제목에서 L과 T의 x좌표가 겹쳐 OCR은 L을 놓쳤다. PDF 내부의 A/L/T/E/R/N/A/T/O/R 문자 순서와 확대 이미지를 확인해 제목을 복원한다.'
    DECISIONS[n]['edits'].append(dict(layer='ocr', replacements=[('ATERNATOR','ALTERNATOR')], text=None))
DECISIONS[49]['edits'].append(dict(layer='native', before_text='1 - 3 0 .', text='1-30.'))
revise(493, 'TEXT_CORRECTION', '확대 원문은 or이며 OCR의 of를 교정한다.',
       [dict(layer='ocr', replacements=[(' of ',' or ')], text=None)])
revise(550, 'TEXT_CORRECTION', '확대 원문 캡션은 단수 Location이다. native 추출의 추가 s를 제거한다.',
       [dict(layer='native', replacements=[('Locations','Location')], text=None)])

# Some flowcharts have native reference-number overlays and image-only prose.
# Their longer, visually checked OCR lines must not be discarded in favor of
# the short native reference alone.
for n in [151,152,153,330,464,466,467,468,469,470,473,474,475,476,477,478,479,482,483,484,485,486,487,496,497]:
    old=DECISIONS[n]
    revise(n, 'IMAGE_TEXT_WITH_NATIVE_REFERENCE',
           '원본 설명문의 대부분은 그림이고 native에는 참조 번호 등 일부만 들어 있다. 확대 원문과 대조한 OCR 설명 구간을 보존하고 native 참조 번호를 연결한다. native만 채택하면 주변 설명이 누락된다.', old['edits'])
DECISIONS[485]['edits'].append(dict(layer='ocr', replacements=[('para,','para.')], text=None))
DECISIONS[486]['edits'].append(dict(layer='ocr', text='(para. 4-126 or 4-127).'))
for n,label in [(39,'A'),(48,'A'),(50,'A'),(52,'A'),(53,'G'),(54,'H'),(55,'I'),(56,'A')]:
    DECISIONS[n]['callout']={'shape':'circle','label':label,'source':'PDF_VISUAL_CHECK'}
    if n in (39,48,50,55,56):
        DECISIONS[n]['edits'].append(dict(layer='ocr', replacements=[('(a)',f'({label})')], text=None))
    DECISIONS[n]['reason']='원문 원 안의 대문자 참조와 설명문을 구분한다. 원 안의 문자를 별도 메타데이터로 기록하고, 잘못 인식된 OCR 문자만 복원한다. 괄호는 기존 OCR의 도형 표현이다.'
revise(57,'TEXT_CORRECTION','원문은 Section I.이며 OCR의 소문자와 세로 막대 인식을 복원한다.',
       [dict(layer='ocr',replacements=[('section |.','Section I.')],text=None)])
revise(59,'TEXT_CORRECTION','원문은 Section II.이며 OCR의 로마숫자와 대소문자를 복원한다.',
       [dict(layer='ocr',replacements=[('section Il.','Section II.')],text=None)])
for n in [313,314]+list(range(331,379))+list(range(380,393)):
    DECISIONS[n]['edits'][0]=dict(layer='native',leading_bullet='Gc.s')
    DECISIONS[n]['edits'].append(dict(layer='ocr',leading_bullet='*¢®©e«'))
