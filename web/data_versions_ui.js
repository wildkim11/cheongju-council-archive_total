// Insert inside the Stage47 app closure after the counts-update extension.
function dataVersionsPanel(){
 const meeting=release.audience.kind==='master'?textRegistry.commit.slice(0,7)+' · '+textRegistry.records.length+'건':'개인판 · 전체 회의록 미포함';
 return `<details class="panel" data-version-panel><summary><b>자료별 기준 버전</b> · 회의록 ${E46(meeting)} · 기초집계 ${E46(countsData.source_commit.slice(0,7))}</summary><p>기초집계: 집계 가능 ${countsData.eligible_rows}행 · 보류 ${countsData.held_rows}행</p><p>기존 의안·활동·관계망 분석 묶음: ${E46((release.source?.commit||'미확인').slice(0,7))}. 회의록·기초집계와 별도 버전입니다.</p><p>기존 분석과 대조 진단은 그 묶음의 기준 시점에 해당합니다. 최신 수집 상태나 해결 여부 전체를 뜻하지 않습니다.</p></details>`;
}
const overviewBeforeVersions=overview;overview=function(){return dataVersionsPanel()+overviewBeforeVersions();};
const commonBeforeVersions=commonPage;commonPage=function(){const old=commonBeforeVersions(),notice=state.tab==='sourcecheck'?'<div class="research-note warn" data-historical-diagnosis>아래 대조 진단은 기존 분석 묶음의 기준 시점 자료입니다. 최신 기초집계는 의원 프로필에서, 최신 보존 원문은 회의록에서 확인하세요.</div>':'';return dataVersionsPanel()+notice+old;};
