'use strict';
const $ = id => document.getElementById(id);
const query = new URLSearchParams(location.search);
const route = ['chunks','reviews','pages','runs'].includes(location.pathname.slice(1)) ? location.pathname.slice(1) : 'chunks';
const S = {run:query.get('run')||'',mode:route,offset:0,total:0,nonce:'',running:false,selection:null,seq:0,sourceSeq:0,initialized:false,polling:false,view:'text',pageQuery:null,sourceLoader:null};
const names = {prose:'본문',pmcs_item:'PMCS 항목',pmcs_context:'PMCS 공통 설명',table_row:'표 행',manual_table_row:'표 행',heading:'제목',reviewed_region:'검토한 영역',diagnostic_box:'진단 질문',condition_box:'조건 박스',flow_annotation:'흐름도 보조 문자',procedure_step:'절차',figure_label:'그림 표기'};
const categories = {TABLE_STRUCTURE:'표 구조',STRUCTURE_BOUNDARY:'항목·조건 경계',OCR_REGION_STRUCTURE:'이미지 문자 구조',LAYER_ALIGNMENT:'추출층 대응',SELECTION_CONFLICT:'채택 규칙 충돌',UNASSIGNED_TEXT:'미배정 구간',TOKEN_BUDGET:'청크 길이',TABLE_PARENT_CONDITION:'표의 상위 조건',CROSS_REGION_TEXT:'여러 영역이 섞인 줄',EXTRACTION_ERROR_CONFIRMED:'확인된 추출 오류',SYMBOL_EXTRACTION_REVIEW:'누락된 기호',LAYOUT_PROFILE_REJECTED:'구조 규칙의 예외',ADDITIONAL_TABLE_STRUCTURE:'추가 발견한 표',BOX_CONTEXT_REVIEW:'박스의 적용 맥락',CONDITION_ASSOCIATION_UNRESOLVED:'조건의 적용 대상',FLOW_ANNOTATION_REVIEW:'흐름도 보조 문자'};
const dispositions = {INCLUDED:'포함',DUPLICATE_ALTERNATIVE:'대안 추출 중복',EXCLUDED_BY_SCOPE:'범위 밖',EXCLUDED_NON_TEXT:'비본문',LAYOUT_ONLY:'서식',NEEDS_REVIEW:'검토 필요'};
const titles = {chunks:['청크 탐색','검색용 텍스트와 원문 위치를 확인합니다.'],pages:['원문 페이지','PDF 페이지별로 처리한 내용을 확인합니다.'],reviews:['검토 목록','구간 선택과 구조를 확정하기 전에 확인할 항목입니다.'],runs:['생성·검증','고정된 입력 자료로 corpus를 생성하고 검증합니다.']};
const number = n => Number(n||0).toLocaleString('ko-KR');
function element(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
function showError(error){$('alert').textContent=error.message||String(error);$('alert').hidden=false;}
async function api(path,params={},method='GET'){
  const options={method,headers:{}};let url=path;
  if(method==='GET')url+='?'+new URLSearchParams(params);
  else{options.headers={'Content-Type':'application/json','X-Corpus-Token':S.nonce};options.body=JSON.stringify(params);}
  const response=await fetch(url,options);const data=await response.json();
  if(!response.ok)throw new Error(data.error||'요청 실패 ('+response.status+')');
  return data;
}
function linkTo(mode,run=S.run){return '/'+mode+(run?'?'+new URLSearchParams({run}):'');}
function updateLinks(){
  for(const a of document.querySelectorAll('[data-route]'))a.href=linkTo(a.dataset.route);
  $('review-link').href=linkTo('reviews');$('job-link').href=linkTo('runs');
  document.querySelector('.brand').href=linkTo('chunks');
}
function renderHistory(runs){
  $('run-history').replaceChildren();
  for(const run of runs){
    const tr=element('tr',undefined,run.name===S.run?'current':'');
    tr.append(element('td',run.name),element('td',number(run.chunks)),element('td',run.status==='INVALID'?'검증 실패':run.status==='READY'?'준비됨':'검토 필요'));
    const action=element('td');const button=element('button',run.name===S.run?'선택됨':'선택');
    button.disabled=run.name===S.run;button.onclick=()=>changeRun(run.name).catch(showError);action.append(button);tr.append(action);$('run-history').append(tr);
  }
}
async function changeRun(run){
  S.run=run;S.offset=0;$('runs').value=run;resetSelection();updateLinks();
  const url=new URL(location.href);url.searchParams.set('run',run);history.replaceState(null,'',url);
  await Promise.all([loadSummary(),loadList()]);
  renderHistory(S.runs||[]);
}
async function refreshState(){
  if(S.polling)return;S.polling=true;
  try{
    const state=await api('/api/state');const wasRunning=S.running;
    S.nonce=state.nonce;S.running=state.job.running;S.runs=state.runs;
    const runKey=state.runs.map(r=>r.name).join('|');
    if($('runs').dataset.key!==runKey){
      $('runs').replaceChildren();
      for(const run of state.runs){const o=element('option',run.name);o.value=run.name;$('runs').append(o);}
      $('runs').dataset.key=runKey;
      if(!state.runs.some(r=>r.name===S.run))S.run=state.runs[0]?.name||'';
      $('runs').value=S.run;updateLinks();renderHistory(state.runs);
      if(S.run){await loadSummary();await loadList();}
      else{$('result-count').textContent='생성한 결과 없음';$('empty').querySelector('p').textContent='생성·검증 메뉴에서 corpus를 생성하세요.';$('empty').querySelector('small').textContent='';}
    }
    $('build').disabled=S.running;$('verify').disabled=S.running||!S.run;
    $('progress').hidden=!S.running;$('job-link').hidden=!S.running;
    $('stage').textContent=state.job.stage;$('percent').textContent=(state.job.percent||0)+'%';$('job-percent').textContent=(state.job.percent||0)+'%';$('progressbar').value=state.job.percent||0;
    if(!S.running&&state.job.error)showError(state.job.error);
    if(S.initialized&&wasRunning&&!S.running&&state.job.result){
      if(state.job.kind==='build')await changeRun(state.job.run);
      else if(state.job.run===S.run)await loadSummary(state.job.result);
      $('job-result').textContent=state.job.kind==='build'?'새 결과를 생성했습니다.':'검증을 마쳤습니다.';
      if(state.job.result.mechanical_status!=='PASS')$('job-result').textContent='검증 오류가 있습니다. 아래 검사 결과를 확인하세요.';
      $('job-result').hidden=false;
    }
    S.initialized=true;
  }catch(e){showError(e);}
  finally{S.polling=false;}
}
async function loadSummary(freshAudit=null){
  const run=S.run;const data=await api('/api/summary',{run});if(run!==S.run)return;
  const a=freshAudit||data.audit;S.summary=data;
  $('nav-reviews').textContent=number(a.review_count);
  $('page-count').textContent=S.mode==='chunks'?number(a.chunks)+'개 청크':S.mode==='pages'?number(a.scope_pages)+'쪽':S.mode==='reviews'?number(a.review_count)+'개 항목':'';
  $('audit-status').textContent=a.mechanical_status==='PASS'?(data.code_matches?'통과':'생성 당시 통과'):'실패';
  $('corpus-status').textContent=a.corpus_ready_for_index?'준비됨':'검토 필요';
  $('chunks-count').textContent=number(a.chunks)+'개';$('review-link').textContent=number(a.review_count)+'개 보기';
  $('audit-description').textContent=number(a.checks)+'개 검사 · 문자 보존, 출처 연결, 채택 규칙 및 길이 확인';
  $('stale-notice').hidden=data.code_matches;
  $('audit-errors').hidden=!a.errors.length;$('error-list').textContent=JSON.stringify(a.errors,null,2);
  $('scope-setting').textContent='제1·2장 · PDF '+data.config.scope_pdf_pages.join('–')+'쪽 ('+number(a.scope_pages)+'쪽)';
  $('token-setting').textContent='최대 '+data.config.max_tokens+' token · 같은 구조단위의 본문 '+data.config.body_overlap_tokens+' token 중첩';
  $('environment-setting').textContent='Python '+data.environment.python+' · tokenizers '+data.environment.tokenizers+' · 입력 '+data.input_count+'개 고정';
}
async function loadList(){
  if(!S.run||S.mode==='runs')return;const seq=++S.seq;const mode=S.mode;
  const params={run:S.run,q:$('search').value,page:$('page-filter').value,offset:S.offset};
  if(mode==='chunks')params.kind=$('kind').value;
  if(mode==='reviews')params.code=$('review-code').value;
  const result=await api('/api/'+mode,params);if(seq!==S.seq)return;
  S.total=result.total;$('result-count').textContent=number(result.total)+'개 결과';
  $('range').textContent=result.total?(number(S.offset+1)+'–'+number(S.offset+result.items.length)):'';
  $('previous').disabled=S.offset===0;$('next').disabled=S.offset+50>=result.total;$('list').replaceChildren();
  if(!result.items.length){$('list').append(element('p','검색 결과가 없습니다.','empty'));return;}
  for(const item of result.items){
    const id=mode==='pages'?'PDF '+item.pdf_page:item.id;
    const button=element('button');button.type='button';button.dataset.id=id;
    const title=element('div',undefined,'item-title');
    title.append(element('span',mode==='reviews'?(categories[item.code]||item.code):id));
    const pages=mode==='chunks'?item.pdf_pages:[item.pdf_page];
    title.append(element('span',mode==='pages'?(item.printed_page||''):pages.join(', ')+'쪽','item-page'));button.append(title);
    const preview=mode==='chunks'?item.preview:mode==='reviews'?item.detail:(item.blank_page?'빈 페이지':Object.entries(item.character_dispositions).map(([k,v])=>(dispositions[k]||k)+' '+number(v)+'자').join(' · '));
    button.append(element('div',preview,'item-preview'));
    button.append(element('div',mode==='chunks'?(names[item.kind]||item.kind)+' · '+item.token_count+' token':mode==='reviews'?item.id:'페이지 처리 기록','item-tags'));
    button.onclick=()=>choose(item).catch(showError);
    if(S.selection===id)button.classList.add('selected');$('list').append(button);
  }
  if(!S.selection)await choose(result.items[0]);
}
async function choose(item){
  const id=S.mode==='pages'?'PDF '+item.pdf_page:item.id;S.selection=id;
  for(const button of $('list').querySelectorAll('button'))button.classList.toggle('selected',button.dataset.id===id);
  if(S.mode==='chunks')await selectChunk(id);else selectOther(item);
}
function showView(view){
  S.view=view;
  for(const b of document.querySelectorAll('[data-view]')){
    b.setAttribute('aria-selected',String(b.dataset.view===view));b.tabIndex=b.dataset.view===view?0:-1;
    $('view-'+b.dataset.view).hidden=b.dataset.view!==view;
  }
  if(view==='compare')renderPage();
  if(view==='source'&&S.sourceLoader)S.sourceLoader().catch(showError);
}
function setPages(pages,id=null){
  $('source-page').replaceChildren();
  for(const page of pages){const o=element('option',page+'쪽');o.value=page;$('source-page').append(o);}
  $('source-page').onchange=()=>showPage(Number($('source-page').value),id);
  $('source-help').hidden=!id;showPage(pages[0],id);
}
function showPage(page,id=null,part=null){
  S.pageQuery={page,run:S.run};if(id)S.pageQuery.id=id;if(part!==null)S.pageQuery.part=part;
  if(S.view==='compare')renderPage();
}
function renderPage(){
  if(!S.pageQuery)return;
  const url='/api/page.png?'+new URLSearchParams(S.pageQuery);
  if($('source-image').getAttribute('src')!==url)$('source-image').src=url;
  $('image-link').href=url;$('image-view-link').href=url;$('source-image').alt='원본 교범 PDF '+S.pageQuery.page+'쪽';
}
async function selectChunk(id){
  const run=S.run;const result=await api('/api/chunk',{run,id});if(run!==S.run||S.selection!==id)return;
  const c=result.chunk;$('empty').hidden=true;$('selection').hidden=false;$('source-tab').hidden=false;
  $('detail-type').textContent=names[c.kind]||c.kind;$('detail-title').textContent=c.id;
  $('detail-meta').textContent='PDF '+c.pdf_pages.join(', ')+'쪽 · 인쇄면 '+c.printed_pages.join(', ')+' · '+c.token_count+' token';
  $('text').textContent=c.text;$('compare-text').textContent=c.text;$('compare-label').textContent='검색 텍스트';$('copy').hidden=false;
  $('item-notes').replaceChildren();
  const codes=[...new Set(result.reviews.map(r=>categories[r.code]||r.code))];
  if(codes.length)$('item-notes').append(element('p','이 페이지의 검토 항목: '+codes.join(', ')));
  for(const issue of c.source_issues||[])$('item-notes').append(element('p',issue.detail||issue.description||issue.note||JSON.stringify(issue)));
  $('item-notes').hidden=!$('item-notes').children.length;
  $('metadata').textContent=JSON.stringify({unit_id:c.unit_id,body_start:c.body_start,body_end:c.body_end,overlap_tokens:c.overlap_tokens,text_sha256:c.text_sha256,reviews:result.reviews,source_issues:c.source_issues},null,2);
  setPages(c.pdf_pages,id);$('source-span').replaceChildren();
  result.mapping.parts.forEach((p,i)=>{if(p.kind==='source'){const o=element('option',p.source.record_id+' · '+p.source.start+'–'+p.source.end);o.value=i;$('source-span').append(o);}});
  S.sourceLoader=async()=>{
    const seq=++S.sourceSeq;const part=$('source-span').value;
    const data=await api('/api/source',{run,id,part});
    if(seq!==S.sourceSeq||S.run!==run||S.selection!==id||$('source-span').value!==part)return;
    $('after-text').textContent=data.source.text;$('before-text').textContent=data.before_spans.join('\n');
    $('source-meta').textContent='PDF '+data.source.pdf_page+'쪽 · 보정 레코드 '+data.source.record_id+' · 위치 정밀도: '+(data.source.coordinate_precision==='line_or_cell'?'줄·셀':'보정 구간');
  };
  $('source-span').onchange=()=>{const part=Number($('source-span').value);const p=result.mapping.parts[part];$('source-page').value=p.source.pdf_page;showPage(p.source.pdf_page,id,part);S.sourceLoader().catch(showError);};
  showView(S.view);
}
function selectOther(item){
  ++S.sourceSeq;S.sourceLoader=null;
  $('empty').hidden=true;$('selection').hidden=false;$('source-tab').hidden=true;$('copy').hidden=true;
  $('detail-type').textContent=S.mode==='reviews'?'검토 항목':'원문';
  $('detail-title').textContent=S.mode==='reviews'?(categories[item.code]||item.code):'PDF '+item.pdf_page+'쪽';
  $('detail-meta').textContent='PDF '+item.pdf_page+'쪽'+(item.id?' · '+item.id:' · 인쇄면 '+(item.printed_page||'없음'));
  $('text').textContent=S.mode==='reviews'?item.detail+'\n\n'+(item.source_refs||[]).map(s=>s.text).join('\n\n'):Object.entries(item.character_dispositions).map(([k,v])=>(dispositions[k]||k)+'  '+number(v)+'자').join('\n');
  $('compare-text').textContent=$('text').textContent;$('compare-label').textContent=S.mode==='reviews'?'확인할 내용':'처리 내역';
  $('item-notes').hidden=true;setPages([item.pdf_page]);
  showView(S.mode==='pages'?'compare':S.view==='source'?'text':S.view);
}
function resetSelection(){
  S.selection=null;S.sourceLoader=null;S.pageQuery=null;++S.seq;++S.sourceSeq;
  $('selection').hidden=true;$('empty').hidden=false;
}
function filter(){S.offset=0;resetSelection();loadList().catch(showError);}
$('page-title').textContent=titles[route][0];$('page-description').textContent=titles[route][1];document.title=titles[route][0]+' · HMMWV';
$('explorer').hidden=route==='runs';$('operations').hidden=route!=='runs';
for(const a of document.querySelectorAll('[data-route]'))if(a.dataset.route===route)a.setAttribute('aria-current','page');
$('kind').hidden=route!=='chunks';$('review-code').hidden=route!=='reviews';$('search').closest('label').hidden=route==='pages';
$('search').placeholder=route==='reviews'?'검토 내용 또는 ID 검색':'내용 또는 청크 ID 검색';
for(const [code,name] of Object.entries(categories)){const option=element('option',name);option.value=code;$('review-code').append(option);}
for(const b of document.querySelectorAll('[data-view]')){
  b.onclick=()=>showView(b.dataset.view);
  b.onkeydown=e=>{
    if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;
    e.preventDefault();const tabs=[...document.querySelectorAll('[data-view]')].filter(t=>!t.hidden);
    const index=tabs.indexOf(b);const next=e.key==='Home'?0:e.key==='End'?tabs.length-1:(index+(e.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
    showView(tabs[next].dataset.view);tabs[next].focus();
  };
}
let debounce;
for(const id of ['search','page-filter','kind','review-code'])$(id).addEventListener('input',()=>{clearTimeout(debounce);debounce=setTimeout(filter,220);});
$('filter-form').onsubmit=e=>{e.preventDefault();clearTimeout(debounce);filter();};
$('clear-filters').onclick=()=>{clearTimeout(debounce);for(const id of ['search','page-filter','kind','review-code'])$(id).value='';filter();};
$('previous').onclick=()=>{S.offset=Math.max(0,S.offset-50);resetSelection();loadList().catch(showError);};
$('next').onclick=()=>{S.offset+=50;resetSelection();loadList().catch(showError);};
$('runs').onchange=()=>changeRun($('runs').value).catch(showError);
for(const kind of ['build','verify'])$(kind).onclick=async()=>{
  try{$('alert').hidden=true;$('job-result').hidden=true;$('build').disabled=true;$('verify').disabled=true;await api('/api/'+kind,{run:S.run},'POST');await refreshState();}
  catch(e){showError(e);$('build').disabled=S.running;$('verify').disabled=S.running||!S.run;}
};
$('copy').onclick=async()=>{try{await navigator.clipboard.writeText($('text').textContent);$('copy').textContent='복사됨';setTimeout(()=>$('copy').textContent='텍스트 복사',1300);}catch(e){showError('텍스트를 선택한 뒤 Ctrl+C로 복사할 수 있습니다.');}};
$('source-image').onerror=()=>showError('원문 이미지를 불러오지 못했습니다. 앱 실행 상태를 확인해주세요.');
refreshState();setInterval(refreshState,2500);

