"""Read-only checks of the existing loopback app and the final corpus."""
import json
from urllib.request import urlopen
from urllib.parse import urlencode
from corpus.common import PACKAGE,write_json


def main():
    base='http://127.0.0.1:8765';run='corpus-v6-final'
    def api(path,**params):
        with urlopen(base+'/api/'+path+'?'+urlencode(params),timeout=60) as response:return json.load(response)
    assert api('health')['application']=='kidet-corpus'
    summary=api('summary',run=run)
    assert summary['code_matches'] and summary['audit']['corpus_ready_for_index']
    assert summary['audit']['chunks']==8344 and summary['audit']['scope_pages']==833
    assert api('reviews',run=run)['total']==0
    assert api('pages',run=run)['total']==833
    checked=[]
    for pn,term in [(50,'THRU GUIDES'),(201,'worn'),(224,'MUFFLER'),(361,'40 volts'),(479,'WIRING'),(832,'Confidence Test')]:
        result=api('chunks',run=run,page=pn,q=term);assert result['total']>0,(pn,term)
        detail=api('chunk',run=run,id=result['items'][0]['id'])
        assert not detail['chunk']['review_ids'] and detail['chunk']['token_count']<=500
        index=next(i for i,p in enumerate(detail['mapping']['parts']) if p['kind']=='source')
        source=api('source',run=run,id=detail['chunk']['id'],part=index)
        assert source['source']['pdf_page']==pn and source['before_spans']
        checked.append({'pdf_page':pn,'query':term,'matching_chunks':result['total'],'source_mapping_returned':True})
    with urlopen(base+'/api/page.png?page=201',timeout=60) as response:
        assert response.headers['Content-Type']=='image/png'
        assert response.read(8)==b'\x89PNG\r\n\x1a\n'
    result={'status':'PASS','run':run,'corpus_ready_for_index':True,'code_matches':True,
      'code_match_scope':'Disk code compared with generation manifest; not proof of server module reload.',
      'server_restarted':False,'restart_status':'Automatic approval review rejected restart; read-only verification used.',
      'chunks':8344,'scope_pages':833,'active_reviews':0,'sample_checks':checked,
      'source_pdf_image_response':'PASS','scope':'LIVE_LOCAL_READ_ONLY_HTTP_API','visual_browser_review_performed':False}
    write_json(PACKAGE/'reports/rules-v6-freeze/runtime.json',result);print(result)


if __name__=='__main__':main()
