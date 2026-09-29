"""Check reviewed cell relationships against independently entered PDF facts."""
from collections import Counter
from .common import PACKAGE,read_json


def verify_table_contracts(rows,check):
    config=read_json(PACKAGE/'config.json')
    contract=read_json(PACKAGE/config.get('rules_path','rules/v2')/'table-assertions.json')
    by_key={r['key']:r for r in rows}
    counts=Counter(r['metadata']['table_id'] for r in rows)
    for table,count in contract['counts'].items():check(counts[table]==count,'TABLE_EXPECTED_ROWS',table)
    for fact in contract['field_checks']:
        row=by_key.get(fact['key'],{})
        actual=next((f['text'] for f in row.get('fields',[]) if f['name']==fact['field']),None)
        check(actual==fact['expected'],'TABLE_PDF_VALUE',fact['key']+':'+fact['field'])
    matrix=contract['matrix']
    for row_number,expected in enumerate(matrix['printed_x_columns_by_row'],1):
        cells=[r for r in rows if r['metadata']['table_id']==matrix['table_id'] and r['metadata']['row']==row_number]
        check(sorted(r['metadata']['column'] for r in cells)==list(range(1,matrix['columns']+1)),'MATRIX_COLUMNS',row_number)
        actual=[]
        for r in cells:
            value=next(f['text'] for f in r['fields'] if f['name']=='Mark')
            check(value in ('','x'),'MATRIX_BLANK_OR_X',r['key'])
            if value=='x':actual.append(r['metadata']['column'])
        check(sorted(actual)==expected,'MATRIX_CELL_ASSIGNMENT',row_number)
    for requirement in contract['required_context']:
        matches=[r for r in rows if r['key'].startswith(requirement['key_prefix'])]
        check(bool(matches),'TABLE_CONTEXT_ROWS',requirement['key_prefix'])
        for r in matches:
            context=' '.join(x['text'] for x in r['context_refs'])
            for term in requirement['contains']:check(term in context,'TABLE_REQUIRED_CONDITION',r['key']+':'+term)
            for term in requirement['excludes']:check(term not in context,'TABLE_WRONG_CONDITION',r['key']+':'+term)
