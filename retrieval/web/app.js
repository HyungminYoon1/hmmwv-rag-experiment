"use strict";
const $ = (id) => document.getElementById(id);
const page = location.pathname === "/history" ? "history" : location.pathname === "/index" ? "index" : "search";
let currentResult = null;
let selectedChunk = null;
let searching = false;
let ready = false;
const kindNames = {
  prose:"본문", heading:"제목", reviewed_text_box:"텍스트", reviewed_region:"텍스트",
  manual_table_row:"표", table_row:"표", pmcs_item:"PMCS", pmcs_context:"PMCS",
  flow_annotation:"조건·연결", diagnostic_box:"진단", diagnostic_action:"조치",
  figure_labels:"그림 내 문자", figure_label:"그림 내 문자", procedure_step:"절차",
  test_card_section:"시험 카드"
};
function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}
async function api(path, options) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "요청을 처리하지 못했습니다.");
  return data;
}
function message(text) {
  $("message").textContent = text || "";
  $("message").hidden = !text;
}
function fillDefinitions(id, entries) {
  const root = $(id); root.replaceChildren();
  for (const [label, value] of entries) root.append(node("dt", label), node("dd", String(value)));
}
async function pollStatus() {
  try {
    const data = await api("/api/status");
    ready = data.ready;
    $("model-status").textContent = data.error ? "모델 준비 실패" : ready ? "검색 준비 완료" : "모델 준비 중";
    $("model-status").className = "status" + (data.error ? " failed" : ready ? " ready" : "");
    $("search-button").disabled = !ready || searching;
    $("corpus-count").textContent = `${data.pages.toLocaleString()}쪽 · ${data.chunks.toLocaleString()}개 청크`;
    if (data.error) throw new Error("검색 모델을 불러오지 못했습니다. 실행 환경을 확인해주세요.");
    if (!ready) setTimeout(pollStatus, 2000);
  } catch (error) {
    $("page-error").textContent = error.message;
    $("page-error").hidden = false;
  }
}
function closeSource() {
  selectedChunk = null;
  $("source-panel").hidden = true;
  $("workspace").classList.remove("with-source");
  document.querySelectorAll(".result").forEach((row) => row.classList.remove("selected"));
}
function showSource(chunk) {
  selectedChunk = chunk;
  $("source-title").textContent = chunk.id + " · PDF 원문";
  $("source-caption").textContent = "표시된 영역에서 근거를 확인하세요.";
  $("source-page").replaceChildren(...chunk.pdf_pages.map((number) => {
    const option = node("option", number); option.value = number; return option;
  }));
  $("source-panel").hidden = false;
  $("workspace").classList.add("with-source");
  document.querySelectorAll(".result").forEach((row) => row.classList.toggle("selected", row.dataset.id === chunk.id));
  updateImage();
  if (window.innerWidth <= 1100) $("source-panel").scrollIntoView({behavior:"smooth", block:"start"});
}
function updateImage() {
  if (!selectedChunk) return;
  const url = `/api/page.png?id=${encodeURIComponent(selectedChunk.id)}&page=${encodeURIComponent($("source-page").value)}`;
  $("source-image").src = url;
  $("full-image").href = url;
}
function renderResults(data) {
  currentResult = data;
  $("question").value = data.question;
  $("empty-state").hidden = true;
  $("result-area").hidden = false;
  $("results-title").textContent = `검색 결과 ${data.items.length}개`;
  $("search-time").textContent = `${(data.timing_ms.retrieval_total / 1000).toFixed(2)}초`;
  closeSource();
  $("results").replaceChildren();
  for (const chunk of data.items) {
    const card = node("article", undefined, "result"); card.dataset.id = chunk.id;
    const top = node("div", undefined, "result-top");
    top.append(node("span", String(chunk.rank).padStart(2,"0"), "rank"), node("span", chunk.id, "chunk-name"));
    top.append(node("span", kindNames[chunk.kind] || "원문", "kind"));
    const score = node("span", `유사도 ${chunk.score.toFixed(4)}`, "score");
    score.title = "정규화한 질문·청크 벡터의 내적입니다. 정답 확률이 아닙니다.";
    top.append(score);
    const bottom = node("div", undefined, "result-bottom");
    let locations = `PDF ${chunk.pdf_pages.join(", ")}쪽`;
    if (chunk.printed_pages.length) locations += ` · 교범 ${chunk.printed_pages.join(", ")}`;
    bottom.append(node("span", locations, "pages"));
    const button = node("button", "원문 보기 ↗", "source-button"); button.type = "button";
    button.setAttribute("aria-label", chunk.id + " 원문 보기");
    button.addEventListener("click", () => showSource(chunk));
    bottom.append(button);
    card.append(top, node("pre", chunk.text, "chunk-text"), bottom);
    $("results").append(card);
  }
}
async function submitSearch(event) {
  event.preventDefault();
  if (searching || !ready) return;
  searching = true; message("");
  $("search-button").disabled = true;
  $("search-button").querySelector("span").textContent = "검색 중…";
  try {
    const result = await api("/api/search", {method:"POST", headers:{"Content-Type":"application/json", "X-Retrieval-Request":"1"}, body:JSON.stringify({question:$("question").value})});
    renderResults(result);
    history.replaceState(null,"",`/?record=${encodeURIComponent(result.id)}`);
  } catch (error) { message(error.message); }
  finally { searching = false; $("search-button").disabled = !ready; $("search-button").querySelector("span").textContent = "검색"; }
}
async function historyPage() {
  const data = await api("/api/history");
  if (!data.items.length) { $("history-list").append(node("p", "아직 저장된 검색 기록이 없습니다.", "history-empty")); return; }
  for (const row of data.items) {
    const link = node("a", undefined, "history-row"); link.href = "/?record=" + encodeURIComponent(row.id);
    link.append(node("span", row.question, "history-question"), node("span", new Date(row.created_at).toLocaleString("ko-KR", {month:"2-digit", day:"2-digit", hour:"2-digit", minute:"2-digit"}), "history-date"), node("span", (row.timing_ms.retrieval_total/1000).toFixed(2) + "초", "history-time"));
    $("history-list").append(link);
  }
}
async function informationPage() {
  const data = await api("/api/info");
  fillDefinitions("corpus-info", [["자료", "HMMWV 정비교범"], ["판본", "1996 · Change 2 (2004)"], ["검색 범위", "제1·2장 · PDF 31–863쪽"], ["청크", `${data.status.chunks.toLocaleString()}개`], ["고정본", data.status.corpus]]);
  fillDefinitions("retrieval-info", [["임베딩", data.config.model_id], ["실행 환경", "CPU · float32"], ["검색 방식", "Dense · FAISS IndexFlatIP"], ["검색 개수", "상위 5개"], ["벡터 차원", "1,024 · L2 정규화"], ["입력 잘림", `${data.tokens.truncated_count}건`]]);
  fillDefinitions("benchmark-info", [["문항 구성", "단일 근거 20 · 다중 근거 30 · 답변불가 10"], ["현재 상태", "질문 보존 완료 · 정답 근거와 청크 대응표 검증 예정"], ["성능 평가", "아직 실행하지 않음"]]);
  fillDefinitions("version-info", [["모델 revision", data.config.model_revision], ["인덱스", data.status.index], ["인덱스 명세 SHA-256", data.status.index_manifest_sha256], ["corpus 명세 SHA-256", data.status.corpus_manifest_sha256], ["Python", data.environment.python], ["라이브러리", Object.entries(data.environment.packages).map(([name,version]) => `${name} ${version}`).join(" / ")], ["재순위화·질의 재작성", "미사용"]]);
}
$("search-form").addEventListener("submit", submitSearch);
$("question").addEventListener("keydown", (event) => { if ((event.ctrlKey || event.metaKey) && event.key === "Enter") $("search-form").requestSubmit(); });
$("close-source").addEventListener("click", closeSource);
$("source-page").addEventListener("change", updateImage);
$("source-image").addEventListener("error", () => message("PDF 원문을 불러오지 못했습니다."));
$("export").addEventListener("click", () => {
  if (!currentResult) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(currentResult,null,2)], {type:"application/json"}));
  const link = node("a"); link.href = url; link.download = currentResult.id + ".json"; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
document.querySelectorAll("nav a[data-page]").forEach((link) => { if(link.dataset.page === page) {link.classList.add("active"); link.setAttribute("aria-current","page");} });
$(page + "-page").hidden = false;
document.title = ({search:"교범 검색", history:"검색 기록", index:"검색 자료"})[page] + " · HMMWV";
pollStatus();
(async () => {
  if (page === "history") await historyPage();
  if (page === "index") await informationPage();
  const record = new URLSearchParams(location.search).get("record");
  if (page === "search" && record) renderResults(await api("/api/record?id=" + encodeURIComponent(record)));
})().catch((error) => { $("page-error").textContent = error.message; $("page-error").hidden = false; });
