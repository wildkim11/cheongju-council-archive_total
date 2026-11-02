# 청주시의회 통합 아카이브 — 새 채팅 인수인계 (2026-11-02)

## 0. 이 문서의 지위
- 새 채팅에서 작업을 재개할 때 **GitHub 실제 데이터·코드·리포트와 대조한 인수인계 기준점**이다.
- 조사 기준 시각: 2026-11-02 (KST). 시작 기준 개발 브랜치 commit: `6bebd763762629efa0e6a951da898082a0be2989` (`data: assemble integrated meeting archive stage C`).
- 저장소: `wildkim11/cheongju-council-archive_total`
- 작업 브랜치: `feature/archive-foundation` / 보존할 기본 브랜치: `main` (확인 당시 초기 커밋 `54e8cd0...`).
- 다른 저장소 `wildkim11/cheongju-council-minutes`는 **건드리지 않는다**.
- 본 아카이브는 공식 자료의 원본 사실·버전·출처 보존을 담당한다. 평가, 의원 순위, Q코드, 이벤트 분류, P1~P7 등 분석적 판단은 별도 의정분석기에서 처리한다.

## 1. 필수 원칙
1. 기존 수집물·원본·해시·출처 링크·이력·임시본을 삭제, 초기화, 덮어쓰기하지 않는다. 정식본으로 대체되는 임시본은 `superseded`로 보존한다.
2. 회의록 상태값: `provisional`, `published`, `superseded`. 공식 회기·대수 목록이 대수 귀속의 기준이며 연도만으로 대수를 추정하지 않는다.
3. 의원 신원은 대수별 공식 식별자와 증빙을 사용한다. 같은 이름만으로 서로 다른 대수·기관의 인물을 자동 병합하지 않는다. `identity_candidates`는 판단 후보이며 자동 승격하지 않는다.
4. 현직 명부에 없다는 이유만으로 사퇴·교체 전 위원회 재임 이력을 삭제하지 않는다.
5. 인물 사진은 공식 출처의 대표사진 1장 원칙. 대용량 PDF/HWP·첨부 및 포토의정 사진은 우선 링크·메타데이터만 저장한다.
6. 정기 자동수집은 아직 비활성 상태. 검증 뒤 가동 여부 결정. 공식 서버 실수집에서는 macOS 러너가 검증되어 있으며 Ubuntu는 타임아웃 이력이 있다.

## 2. 2026-11-02 실제 확인된 상태
### Stage A: PASS
- 분석기 export 최신 manifest 기준: 의원 원천 행 `people=435`, `tenures=435`, 위원회 상태 26, 위원회 소속 207, 연구단체 5, 연구단체 참여 65, 정당 소속 44, 지역구 소속 167.
- 원래 Stage A 집계는 people/tenures 434였으나, **후속 Stage B/C export manifest는 435**다. 최신 지표를 기준으로 하며 증가 1건의 출처는 후속 QA에서 확인한다.

### Stage B: PASS
- 의안/결의 3,394건 (1대 1,098 / 2대 1,020 / 3대 1,141 / 4대 135).
- 발의자 관계 11,158행, 동일 대수 정확 일치 11,158, unresolved 0, ambiguous 0.
- 의원발의 893건 중 25건은 의안 상세의 발의자 명단이 부족해 **회의록 기반 fallback 검증 필요**. 이름을 추정해 채우지 않는다.
- 5분발언 606, 시정질문 85, 서면질문 16, 건의·결의 게시판 72, 보도자료 914, 토론회 20, 포토의정 메타데이터 6,606.
- 보도자료 1건은 본문 미노출 상태로 출처·제목·날짜만 보존. 포토의정 바이너리 일괄 미러링은 하지 않음.

### Stage C: 회의록 초기 수집·정규 인덱스 생성 확인
- 공식 대수 목록 2,339건: 통합 1대 663 / 2대 771 / 3대 855 / 4대 50.
- `published=2,333`, `provisional=6`.
- 개별 대수별 `bodies_checked` 합계 2,339; `archive/meetings/cheongju_integrated/term-*/`에 개별 MD 원문 파일이 있으며 `indexes/integrated/meetings.json`와 `exports/analyzer/meetings.jsonl` 생성됨.
- Stage C 조립 리포트: `reports/integrated-sync.json`, `history_rows=0` (초기 집합).
- 연도별 목록은 2,326건으로, 대수별 목록 2,339건보다 **13건 적음**. 대수 목록에만 있는 ID: 1212, 1573, 180, 1848, 1900, 2257, 2258, 2659, 2951, 3315, 3652, 508, 896. 이를 곧바로 수집 누락으로 간주하지 말고 각 공식 목록의 기준 차이를 검증한다.
- CI의 본문 확인 완료는 ‘비어 있지 않고 정상 파싱됨’의 전수 인증과 구별한다. 후속 품질감사 필요.

### 배포/운영
- `feature/archive-foundation`에 Stage A/B/C 데이터가 저장되어 있음.
- `main` 병합하지 않았고 정기 스케줄 가동하지 않음.
- 저장소 크기는 GitHub 저장소 조회값 `size=98768`(KB 단위의 GitHub 보고값, 약 96.5 MiB)로 관측; 이 수치는 전체 Git 객체/실제 결제·용량 한도에 대한 결론이 아니다.

## 3. 즉시 이어갈 작업 (우선순위)
1. **Stage C 전수 검증 보고서**: 공식 2,339개 대수목록 ↔ 개별 `minutes-*.md` ↔ canonical index ↔ analyzer JSONL 간 ID·대수·공개상태·본문 길이·출처·해시를 1:1 대조한다. 중복 파일, 빈 본문, 파서 오류, 인덱스/파일 수 불일치, SHA-256 불일치, provisional/superseded 처리 등을 별도 원장으로 기록한다.
2. 공식 연도별 목록과 대수별 목록의 차이 13건의 원인을 증빙 가능한 자료로 분류한다. 대수 귀속은 공식 대수별 목록 우선.
3. 25건 의안 발의자 fallback 대조: 공식 회의록에서 발의자 목록이 실제로 확인되는 것만 링크하고 증빙 없는 동일이름 추론 금지.
4. Stage A `435 vs 434`의 1건 증가 사유 추적. 정당·재임 이력의 시간 정합성 및 사퇴 전 상태 보존 점검.
5. 검사 통과 후에만 **증분 수집·개정이력 추적·스케줄 가동** 설계 및 시험. 먼저 수동·격리 브랜치에서 테스트하며 기존 데이터와 `main`에 영향 없게 한다.
6. source-only JSONL을 기존 의정분석기로 연결할 때 원본 아카이브에서 평가 지표를 생성하지 않는다.

## 4. 읽을 파일 순서
1. `docs/FOUNDATION_STATUS_20261101.md` — Stage A/B 및 소스별 검증 기록
2. `reports/integrated-initial-term-{1,2,3,4}.json` — 회의록 원천 단계
3. `reports/integrated-sync.json` — 회의록 초기 통합과 13건 목록 차이
4. `indexes/integrated/meetings.json` + `archive/meetings/cheongju_integrated/` — 회의록 실제 자료
5. `exports/analyzer/manifest.json` + `exports/analyzer/meetings.jsonl` — downstream export
6. `reports/bill-proposer-repair.json` + `reports/bill-proposer-identity-links.json` — 25건 fallback 과제
7. `.github/workflows/populate-stage-c-meetings.yml`, `scripts/collect_integrated_minutes.py`, `scripts/validate_archive.py` — 수집·검증 코드

## 5. 상태 구분 주의
- ‘파일 생성 확인’, ‘리포트 수치 확인’, ‘본문 전수 품질검증 PASS’, ‘자동수집 운영 시작’은 서로 다른 단계다.
- **확인됨**: 개발 브랜치 원천·인덱스·export 존재 및 수치 일치, Stage C 데이터 publish 커밋.
- **미확인/후속**: 파일 단위 전수 해시 검증, 본문 품질 QA 상세, 13건 공식 목록 차이 원인, 25건 발의자 보완, 증분수집 운영 인증.
- 이 문서 작성만으로 자동수집이나 QA가 완료되었다고 주장하지 않는다.


## 6. 2026-11-02 Stage C 후속 전수검증 완료 (인수인계 갱신)
- 검증 코드: \`scripts/audit_stage_c.py\`; 회귀 테스트: \`tests/test_audit_stage_c.py\`; 읽기 전용 Actions: \`.github/workflows/audit-stage-c.yml\`.
- 검증 보고서: \`docs/STAGE_C_OFFLINE_AUDIT_20261102.md\`.
- 최종 재실행: https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41357430900
- **Stage C 저장자료 무결성: PASS. 오류 0건, 경고 0건.**
- 확인된 파일 2,339, 파일 SHA-256 일치 2,339, 공식본문 정규화 SHA-256 일치 2,339, 분석기 회의록 JSONL 2,339행 일치, 전체 analyzer export 22개 파일의 SHA-256 일치.
- 대수별 파일: 1대 663, 2대 771, 3대 855, 4대 50. published 2,333; provisional 6.
- 기존 경고 1건 (\`minutes-2886\`)은 \`(개의되지 않음)\` 원문을 합법적으로 짧은 본문으로 인식하지 못한 검증 규칙의 오탐이었다. 검사 규칙만 수정하고 재실행하여 경고 0이 됐으며 원문은 변경하지 않았다.
- **공식 대수별/연도별 목록 차이 13건**은 모두 제목 속 회기 종료일보다 실제 회의일이 나중인 회의다. 12건 의회운영위원회, 1건 특별위원회. 원인 확정 전에는 공식 대수별 목록을 유지하고 임의 삭제/날짜 변경하지 않는다.
- **검증의 범위는 저장된 GitHub 스냅샷의 무결성**이며, 공식 홈페이지 현재 원본과의 실시간 글자 단위 대조 및 과거에 누락된 임의의 외부 항목 존재 여부는 별도 과제다.
- 후속 우선순위: ① 13건 공식 연도별 트리 차이 원인 조사, ② 회의록 근거로 의원발의 명단 미노출 25건 보완, ③ 신원/이력 정합성 QA, ④ 격리된 증분수집 시험, ⑤ 조건 충족 시 정기 수집 가동 검토. \`main\` 병합은 보류.


## 7. 2026-11-02 의원발의 명단 복원 17건 완료 (최종 추가)
- 상세 보고서: \`docs/BILL_PROPOSER_FALLBACK_STATUS_20261102.md\`.
- 공식 회의록 직접증거 원장: \`reports/bill-minutes-proposer-evidence.json\`.
- 일회성 반영 검증서: \`reports/bill-minutes-promotion.json\`.
- 재검증 PASS 및 개발 브랜치 게시: https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41359269974
- 이전 의원발의 명단 미확인 25건 중 **17건**이 공식 회의록의 완전한 대표·공동발의 명단에 의해 증빙됨. 자료 반영 완료.
- 발의자 관계 **250행 증가**: 전체 11,158 -> 11,408. 동일 대수 신원 11,408 해결, unresolved 0, ambiguous 0.
- 의원발의 총 893건 중 명단 확보 885건, **미확인 8건**. 잔여 내부번호: **1308, 1458, 1960, 2083, 2258, 2364, 2637, 3255**.
- Stage C 회의록 2,339건 불변. 승격 전후 전체 저장자료 SHA-256 검사 PASS. \`main\` 미병합, 자동수집 비활성.
- **새로 확인된 기존 데이터 품질 문제**: 기관발의 유형인데 사람 이름이 연결된 기존 **5건 44행**. 내부번호: **375, 2177, 2180, 3265, 3266**. 이전 보고서가 0으로 기록했으나 실제 저장자료가 달랐다. 이번 복원 과정에서 **새 기관발의-개인 연결은 0**이므로 기존 5건은 삭제하지 않고 별도 전수 QA 대상으로 격리 표시함.
- 소비측의 의원 공동발의 분석에는 위 44행을 그대로 의원발의 관계로 간주하지 말 것. 원문 관계유형을 확인한 후 격리·수정 방식을 결정한다.
- \`promote-verified-bill-rosters.yml\`의 자동 재실행은 비활성화했다. 현재 \`promote_verified_bill_rosters.py\`는 2026-11-02의 25건/17건 베이스라인을 전제로 하는 일회성 마이그레이션이다.
- 다음 우선순위: ① 남은 8건 원문·의안접수대장 재확인, ② 기관발의 5건/44행의 진짜 관계유형 정정, ③ 해당 데이터 품질 확인 뒤 증분수집 검증·통합 분석기 연결.


## 8. [최신] 2026-11-02 의안 1960 추가 복원·기관발의 44행 분석 격리
**이 절은 앞쪽에 기록된 25건/8건 및 11,158/11,408행 수치를 최신 기준으로 대체한다.**
- 상세 보고서: `docs/BILL_RECONCILIATION_FINAL_20261102.md`.
- 의안 내부번호 **1960**(제2대 제66회): 2021-10-19 공식 농업정책위원회 회의록 `minutes-2530`에서 박노학 대표발의 + 공동발의 12명, **전체 13명**을 직접 확인하고 개발 브랜치의 의안·관계·export에 반영했다. 원문 회의록·기존 raw 필드는 유지.
- 원인: 회의록 제목의 `ㆍ`(U+318D)와 의안 제목의 `·`(U+00B7)가 달랐음. 검색 정규화 로직과 회귀 테스트를 보완했고 원문 문자는 수정하지 않았다.
- 실행: https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41363218233 / 검증서 `reports/bill-1960-official-roster-promotion.json` (PASS).
- **최신 의원발의 893건 중 명단 확보 886건, 명단 미확인 7건**: 내부번호 `1308,1458,2083,2258,2364,2637,3255`. 미확인 공동발의자 이름을 추정하지 않는다.
- **전체 raw 발의자 관계 11,421행** 중 의원발의 관계 **11,377행**, 기관발의 분류 충돌 **44행(5건)**.
- 기관발의 5건: `375(위원장·1행),2177(의장·6행),2180(시장·12행),3265(위원장·12행),3266(위원장·13행)`. 원본 개인 인명관계를 삭제하지 않고, 두 분석용 뷰로 무손실 분할.
- **의원별 발의 실적용으로 반드시 `exports/analyzer/bill_proposers_member_only.jsonl` (11,377행)을 사용한다.** 원시 `bill_proposers.jsonl` (11,421행)은 44행 오염 가능성이 있어 그대로 의원 통계에 사용하지 않는다. 기관형 문서에서 발견된 이름은 `bill_proposers_institutional_type_quarantine.jsonl` (44행)에 보존. 증빙: `reports/bill-proposer-safe-export.json`, `exports/analyzer/manifest.json`.
- 안전 뷰 배포 실행: https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41363446723 (PASS).
- 모든 작업은 **개발 브랜치**에만 적용. `main` 미병합, 정기 자동수집 비활성. Stage C 회의록 2,339건 변경 없이 무결성 PASS.
- 후속 우선순위: ① 잔여 7건 공식 입법예고·의안 접수원문 조회, ② 기관발의 5건 내 인명의 실제 역할 검증, ③ 구버전 분석기의 안전 뷰 소비처 적용 확인, ④ 다른 아카이브 품질 검사 후 증분수집의 격리 운영 시험.


## 9. [최신] 2026-11-02 의안 공식 첨부 심화 검증 (원본 변경 없음)
- 검증 보고서: \`docs/BILL_OFFICIAL_ATTACHMENT_FOLLOWUP_20261102.md\`.
- 원문 공식 상세 **12건 모두 실시간 재조회 성공**(미확인 의원발의 7 + 기관발의 5). 파일 메타데이터·원문 SHA-256은 Actions artifact에 보존: https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41364205009.
- **2258 의안181**: 2019-04-12 청주시의회 입법예고와 HWP 원문 직접 다운로드 성공(19,456바이트, SHA-256 \`a666cc1b2b7ffc62fb962b85aca5c4ef0fdd1b3c9b099b9b8b3d3c373d8b6db7\`). 공식 첨부파일명에 **김미자 의원 외 10명**으로 총 11명 확인. **HWP 본문에는 공동발의 10명의 실명이 없어 여전히 완전 명단 미확인**. 증빙 https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41364356702.
- **3255 의안1042**: 2025-11-12 의원발의, 2025-11-17 철회. 2025-11-13 공고(2025-101호)의 입법예고 HWP 존재를 별도 입법예고 자료에서 확인했지만 실제 첨부 원문은 확보하지 못함. 회의록의 “이상조 의원 등 발의 의원 전원의 철회 요구”는 전체 발의자 명단 근거가 아님. **2024년 동일 제목의 시장 제출 의안과 혼동하지 않는다**.
- 3255 공식 입법예고 공개 목록 최대 24페이지 추가 탐색에서 해당 게시물 링크가 발견되지 않았으나, 이는 목록 조회 한계일 수 있으므로 '삭제됨' 단정 불가. 결과 https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41364642987.
- **최신 명단 미확인 의원발의는 여전히 7건**, 원시 발의자 관계 11,421행, 안전한 의원발의 관계 11,377행, 기관유형 인명 격리 44행 모두 **변경 없음**.
- 후속은 공식 원안·접수대장·발의 서명부의 원천 확인. 원천 메타데이터만으로 누락된 공동발의자 이름을 채우거나 원본 인명관계를 삭제하지 않는다.


## 10. [최신] 2026-11-02 미확인 의안 7건 공식자료 제출요구용 목록 확정
- **실제 자료제출은 하지 않았다.** 원천 확보가 필요한 7건의 **대수·회기·의안번호·발의일·명단 누락 범위** 및 기관발의 5건의 역할 검증 요구를 하나로 정리한 문서: \`docs/BILL_SOURCE_RECORDS_REQUEST_20261102.md\`.
- **3255**: 2025년 제98회 내부번호 3255/의안번호 1042의 공개 입법예고 원본을 찾기 위해 2025-11-13 근접 게시물 공식 fidx **20477~20494(18개)**를 제한적으로 직접 조회했으나 **의안명과 2025년 날짜가 함께 일치하는 원본 게시물 0건**, 다운로드 가능한 HWP 0건. 이는 **게시물이 원래 없었다거나 삭제됐음을 증명하지 않는다**. 원안 서명부는 의회사무국에 확인 필요. read-only macOS Actions https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41366747257.
- 전체 미확인 의원발의: 1308(2대44회/의안221), 1458(2대40회/140), 2083(2대70회/991), 2258(2대42회/181), 2364(3대79회/218), 2637(3대87회/489), 3255(3대98회/1042).
- **기존 수치 불변**: 총 의원발의 893, 완전명단 886, 미확인 7; 발의자 원시관계 11,421, 의원발의 분석용 11,377, 기관유형 격리 44.
- 그 외 앞 절의 확인·예외/보존 원칙 및 개발 브랜치 한정 정책을 유지한다.


## 11. [최신] Stage A 434 vs 435 인물 원천 행수 차이 해결
- 상세: \`docs/STAGE_A_PERSON_COUNT_RECONCILIATION_20261102.md\`; read-only 검증 \`scripts/audit_stage_a_people_count.py\`, 테스트 \`tests/test_stage_a_people_count.py\`.
- 434 = 현재 제4대 44 + 제1~3대 역사명부 123 + 통합 전 청주시 187 + 통합 전 청원군 80.
- 추가 1 = 제4대 공식 역사명부 전용 **최영중** \`mcode=4200\`, 원본 \`archive/people/history/cheongju_integrated_term4_departed_people.json\` 및 짝 재임이력 1건. **현재 435 인물 원천 기록/435 재임이력과 정확히 일치**.
- 개인 식별 상태 \`candidate_unmerged\`; **435는 실존하는 서로 다른 고유 자연인 435명이라는 뜻이 아니다**. 다른 대수 같은 이름은 신원 근거 없이는 자동 병합 금지.
- 공식 원천 보고서·실제 JSON·analyzer manifest 교차검증 **PASS**: https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41367113137. 공식 원천파일 변경 없음.
- 남은 현안은 ① 발의자 명단 미확인 7건(의회사무국 원안/서명부 자료 요청 초안 준비), ② 기관형 문서에 저장된 인명 44행 원문 역할 확인, ③ 공식 대수/연도 목록 차이 13건 원인, ④ 증분수집의 격리 시험. \`main\` 병합 및 정기 자동수집 여전히 보류.


## 12. [최신] Stage C 공식 대수별/연도별 목록 차이 13건 유형 규명
- 심화 보고서: `docs/YEAR_TERM_TREE_DIFF_QA_20261102.md`.
- 코드/테스트: `scripts/audit_official_tree_discrepancy.py`, `tests/test_official_tree_discrepancy.py`.
- **개발 브랜치에 영구 저장한 재현 가능한 분석 원장:** `reports/integrated-year-term-discrepancy-probe.json`.
- 기존 공식 목록 스냅샷 **2,339건** 전수 분석, 회기 시작/종료일 파싱 실패 0건.
- 회기 종료일보다 실제 회의일이 늦은 전체 **121건** 중 **같은 해 개최 108건은 대수별·연도별 두 목록 모두에 있음**, **연도가 바뀐 13건은 대수별 목록에만 있음**. 추가적인 `only_year`는 0건. 13건은 2014~2024년 12월에 끝난 회기의 회의록인데, 실제 개최는 다음 해 1~2월이며 27~49일 차이.
- 13건 ID: `180,508,896,1212,1573,1848,1900,2258,2257,2659,2951,3315,3652` (이것은 **회의록 schSn**, 의안 내부번호와 별개).
- 공식 회의록 원본/해시 보존. 회기 귀속은 대수별 공식 트리, 기록의 실제 날짜/연도는 개최일로 관리. **내부 연도별 트리 생성조건은 아직 공식 확인되지 않았으므로 원인을 확정하지 않는다**.
- 저장자료 비교검증 CI PASS: https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41369346819.
- 검증 원장 영구 저장 CI PASS: https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41369481983.
- **실시간 전체 트리 재탐색 시도는 FAIL(공식 서버 연결 시간 초과)**: https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41368923499. 저장자료 전수 QA PASS와 실시간 재조회 실패를 구분. 공식 서버 안정화 뒤 요청 단위 작은 재탐색 필요.
- 미해결 다른 현안: ① 발의자 명단 미확인 7건 공식 원안/서명부 확보(자료제출요구안 `docs/BILL_SOURCE_RECORDS_REQUEST_20261102.md`), ② 기관형 문서 인명관계 44행의 실제 역할 확인, ③ 증분수집을 격리 환경에서 설계·시험.
- `main` 및 기존 `wildkim11/cheongju-council-minutes` 미변경. 정기 수집 비활성.


## 13. [최신] 증분수집 격리 시뮬레이션 및 실운영 하드 차단 (2026-11-02)
- 최신 증분수집 격리보고서: `docs/INCREMENTAL_SYNC_ISOLATION_SAFETY_20261102.md`.
- **재현 가능 QA 원장(개발 브랜치에 저장):** `reports/incremental-sync-isolation-diagnostics.json`, `release_decision=BLOCKED_UNSAFE_TO_OPERATE`, 잔여 release blocker **3개**.
- 검증 CI: https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41371942115 (**성공**: 전체 unittest, 격리 7시나리오, Stage C 전체 원본/해시 QA, 프로젝트 원본 무변경 검증).
- 기존 수집기 `scripts/collect_integrated_minutes.py`의 위험을 synthetic fixture로 재현: ① 신규 수집은 정상·원본 불변, ② 공식 서버 타임아웃은 쓰기 전 중단, ③ 같은 ID 공개상태만 변경하면 원본 헤더 불일치, ④ 같은 ID 본문 수정이면 기존 MD 덮어쓰기, ⑤ 디스크 오류 중간 복사로 인덱스/파일 부분 불일치, ⑥ 두 provisional ID -> 같은 published ID 매핑, ⑦ 파생 출력·대수 shard 갱신 누락.
- **조치 완료:** 부적절한 many-to-one provisional 대체 차단 및 published 후계만 허용; staging 사전 백업 + Python 예외 시 바이트 단위 롤백; 새 canonical 인덱스와 동기화된 `exports/analyzer/*` / `indexes/integrated/current_term_{1..4}.json` 생성, 기존 `initial_term_*` 불변; Stage C audit가 최신 current shard를 우선 검사.
- **위험 반영 차단:** 동일 ID의 상태/제목/날짜 변경 또는 본문 개정은 이력 보존 기능이 없어 **쓰기 전 오류로 중단**(`SAME_ID_METADATA_REVISION_REQUIRES_VERSION_HISTORY` / `SAME_ID_BODY_REVISION_REQUIRES_VERSION_HISTORY`). 아직 실제 임시→정식 동일-ID 전환을 지원하지 않는다.
- **실운영 실행 방지:** 실제 저장소 ROOT에서 `run_sync("incremental")` 또는 `run_sync("full")`는 공식 네트워크 요청 이전에 `LIVE_ARCHIVE_INCREMENTAL_SYNC_DISABLED`로 거부한다. 운영 스케줄은 계속 OFF.
- **최신 잔여 차단조건 3개:** ① 동일 ID 공개상태/메타데이터 이력 안전한 보존, ② 동일 ID 본문 개정의 버전별 원본 안전보존, ③ 프로세스 강제종료/전원장애 시 다중파일 일관성 보장 및 복구시험. Python 예외 롤백 통과가 크래시 원자성을 뜻하지 않는다.
- **현재 검증은 오프라인 임시 데이터 7개 시나리오 + 기존 실제 아카이브의 read-only Stage C 검사**다. 청주시의회 공식 서버 HTTP 접속 0회, 운영 원본 수집/갱신 없음. `main`, 독립 `cheongju-council-minutes` 미변경.
- 현행 보고서는 '운영 준비 완료'로 읽으면 안 된다. 다음은 snapshot version history + crash recovery 설계·격리 검증이며, 전체 2,339건을 반영하는 리허설 전까지 운영 잠금 해제 금지.


## 14. [최신] 원본 변경이력+SIGKILL 복구 개발 및 2,339건 복사본 전체 리허설
- 기준 상세보고서: `docs/INCREMENTAL_VERSION_CRASH_RESULTS_20261102.md`.
- 이 절은 앞의 §13에서 “동일 ID 이력 미구현”이라고 적은 상태를 **최신 변경 사항으로 대체**한다. 다만 운영 루트 수집 해제나 실시간 자동 증분수집 인증을 뜻하지 않는다.
- **개발 브랜치에 구현**:
  1. `scripts/collect_integrated_minutes.py` 같은 ID `provisional → published` 전환 및 동일 ID 본문 수정 시 이전 MD 바이트를 `archive/meetings/cheongju_integrated/_revisions/minutes-XXXX/<prior_file_sha256>.md`에 불변 보존하고, 이전/다음 인덱스 상태·SHA·변경 필드를 `indexes/integrated/meeting_revisions.json`에 기록. 3회 연속 변경·본문 복귀도 tested.
  2. `scripts/audit_stage_c.py`가 개정 원본 SHA/바이트·이력 chain·현재 인덱스 연결 검증.
  3. `scripts/sync_transaction.py` 디스크 write-ahead journal: 완전한 원본 백업과 신규 파일을 저널로 봉인, fsync + 원자적 `os.replace`로 개별 파일 반영. 미완료 시 재시작 후 **rollback**, 커밋 표식 뒤 강제 종료 시 **commit finalize**. 완료·복구된 저널은 원자적으로 다른 이름으로 분리한 뒤 삭제해 삭제 중 크래시 시 활성 저널이 손상되지 않도록 함. `fcntl.flock` 로컬 실행 잠금.
  4. 실제 **SIGKILL** 별도 subprocess 강제 종료: 저널 준비 직후 / 일부 파일 반영 직후 / 커밋 직후, 손상 백업 복구 거부, 락 충돌, 경로 이탈 검증 등 회귀시험.
- 전체 unittest 및 원본 Stage C QA 포함 검증: https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41375340219 (당시 PASS), SIGKILL 신호로 강화한 뒤 회귀 PASS https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41375676225.
- **실제 원본 2,339건 전체를 임시 폴더로 복사**해 오프라인으로 가상 회의록 하나 추가(최종 복사본 2,340행): 기존 2,339 원본 SHA 동일, 기존 provisional 6건 원문을 로컬에서만 재사용, 2,340행 Stage C 전수 감사와 분석기 출력 동기화 PASS. 100% **가상 증분**, 공식 HTTP 0회, 원본 아카이브/실제 의안 인덱스 불변. CI https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41375525361.
- **QA 자료**: `scripts/rehearse_incremental_full_snapshot.py`, `tests/test_sync_transaction_crash.py`, `scripts/compose_incremental_release_gate.py`, `reports/incremental-revision-crash-release-gate.json` 및 `reports/incremental-full-snapshot-rehearsal.json`(최종 발행 후 이용).
- 기존 원본수는 **2,339**, 공식 신규 1건 추가가 아니며, 리허설에서만 2,340.
- **실운영 수집은 계속 HARD BLOCKED**: `run_sync("full"|"incremental", ROOT)`는 네트워크 전에 거부. 원본 회의록의 날짜·대수 변경으로 canonical 파일 경로 이동이 필요한 경우 별도 migration 구현 전까지 `SAME_ID_PATH_CHANGE_REQUIRES_VERSIONED_MIGRATION` 오류로 거부. 물리적 전원장애·네트워크 파일시스템은 SIGKILL 검증과 별개로 미검증.
- 다음 승인·후속: 날짜/회기 경로 이동을 원본 손실 없이 이력으로 안전하게 처리하는 테스트, 청주시의회 서버의 **요청량 제한 읽기전용** 소규모 재조회 및 파서 QA, 운영 루트 잠금 해제 판단은 사용자 단일 승인 후. `main`, 기존 `wildkim11/cheongju-council-minutes` 변경 없음. 스케줄 OFF.


## 15. [최신] 회의록 동일 ID의 연도·대수·경로 이동, 불변 원문 및 SIGKILL 복구
- **최신 상세보고서:** `docs/CROSS_YEAR_PATH_MIGRATION_QA_20261102.md`.
- 기존 제14절의 `SAME_ID_PATH_CHANGE_REQUIRES_VERSIONED_MIGRATION` 차단은 개발 브랜치에서 **기능 구현 및 오프라인 격리검증으로 대체됐다**. 현재 실운영 ROOT 차단과 스케줄 OFF는 그대로다.
- 수집기 `scripts/collect_integrated_minutes.py`: 이전 `term-N/YYYY/minutes-X.md`에서 새로운 `term-M/YYYY/minutes-X.md`로 동일 source ID가 이동할 때, 구본 SHA를 확인하고 `_revisions/minutes-X/<old_sha>.md`와 이력 원장에 이전 정확한 바이트·메타데이터 보존. 옛 canonical 파일은 staging에서 제거하고 **명시적 삭제 목록**으로 트랜잭션에 전달. source ID가 바뀌면 이 처리로 묶지 않음.
- `scripts/sync_transaction.py`: 저널에 파일 추가·수정과 **구 canonical 경로 삭제(new_exists=false, old_sha256)**를 함께 기록. 복사 중 실패나 SIGKILL로 미완료된 경우 구 경로·구 SHA·기존 인덱스 모두 복원. 이미 committed된 경우 새 경로 SHA를 검증하고 구 경로 부재를 확인. 허용된 삭제는 `archive/meetings/cheongju_integrated/term-N/YYYY/minutes-X.md` 패턴만.
- 단위 회귀: `tests/test_incremental_sync_isolation.py` (동일 ID 연도/대수 변경 및 이전 원본 보존, 같은 대수 연도변경, 연결 실패 시 원본 불변), `tests/test_sync_transaction_crash.py` (구 경로 삭제 직후 실제 SIGKILL 후 복구, 커밋 후 SIGKILL, 무단 삭제 차단 등).
- **2,339건 전체 복사본 시험 CI PASS:** https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41377032467. 가상 회의록 1건의 `term-3/2025` → `term-4/2026`만 이동. 현재 파일 **2,339건 유지**, 나머지 **2,338건 원본 SHA 불변**, 이전 1건 정확한 바이트 `_revisions` 보존, 옛 경로 없음, 새 canonical 존재, 개정 원장 1건, 전체 Stage C QA **2,339건+개정 1건 PASS**, 분석기 2,339행 일치.
- 기계검증 코드: `scripts/rehearse_cross_year_migration_full_snapshot.py`. 공식 서버 HTTP **0회**, 실제 GitHub 원본/인덱스/대수 변경 **0건**. 가상 변경을 현실의 공식 날짜 재분류로 오해 금지.
- **기계검증 원장**: `reports/synthetic-cross-year-migration-full-2339-qa.json` (일회성 CI를 통해 개발 브랜치에 저장; 성공 실행 확인 후 출처로 사용).
- **운영 미승인:** 실제 ROOT `run_sync("full"/"incremental")`는 네트워크 이전에 거부; 자동 실행 OFF. 실시간 소량 읽기전용 원천 검증·물리적 전원차단/네트워크 저장소 내구성은 별도이며 현재 성공했다고 주장하지 않는다.
- `main` 및 독립 `wildkim11/cheongju-council-minutes` 미변경. 다음은 실서버 소량 읽기전용 검증과 의회사무국에만 존재하는 발의자 원안 확보.


## 16. [최신] 공식 회의록 서버의 소량 읽기전용 접속 검증 (2026-11-02)
- **상세 결과:** `docs/OFFICIAL_READONLY_CONNECTIVITY_QA_20261102.md`. 현재 결론은 `LIVE_SOURCE_VALIDATION_NOT_COMPLETED`. 이는 운영 수집기의 파싱 오류나 보존 원본 손상 확정이 아니라 **검증을 시도한 GitHub 클라우드 실행 환경에서 공식 서버와 TLS 접속에 실패했다**는 뜻이다.
- 1차 한도형 검증: `scripts/probe_official_readonly_limited.py`, `reports/official-limited-readonly-probe-20261102.json`. GET viewer `schSn=3999` 첫 요청에서 `SSLError: [SSL: SSLV3_ALERT_HANDSHAKE_FAILURE]`; 요청 **1회, 응답 0건**, 이후 `schSn=4019` 및 회기 트리 root 요청은 **미시도**, 재시도 0회. "SSLV3_ALERT"는 TLS 오류 코드 명칭이지 실제 SSL3 사용 증거 아님. 저장본은 `3999=published`, `4019=provisional`이지만 **실시간 공개상태와 본문 동일성은 확인 못함**. QA CI https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41377991597.
- 2차 TLS-only 원인 범위 확인: `scripts/diagnose_official_tls_path_readonly.py`, `reports/official-readonly-tls-diagnostic-20261102.json`. `councilrec.cheongju.go.kr`와 `council.cheongju.go.kr` 각각 1회 TLS 접속 시 **TimeoutError**, 총 TLS 연결 2회/HTTP **0회**, 인증서 검증 비활성화 없음. QA CI https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41378195345.
- 공식 사이트와 회기 검색 페이지는 공개 검색색인에서 보이지만, 검색 캐시는 실제 동적 PHP 페이지의 실시간 응답·본문을 증명하지 않는다. 웹에서 해당 ID 페이지 직접 열기도 캐시 미스. **서버 전체 장애를 확정하지 말 것**.
- 보존 아카이브 기존 **2,339건은 불변**. 공식 서버에서 신규 회의록을 수집하거나 기존 본문을 갱신한 적 없음. 개발 브랜치에 소량 읽기전용 코드·QA 원장·보고서만 추가. `main`, 독립 `wildkim11/cheongju-council-minutes` 불변. 실운영 `run_sync` 하드 잠금 및 자동 실행 OFF.
- 후속은 기관이 허용한 다른 네트워크에서 **한 건짜리 읽기전용 접속 확인**부터 수행할 것. 성공 전에는 조회범위를 확대하지 않고 TLS 보안 검증을 약화시키지도 않는다. 연결 뒤에도 본문·상태 변경은 보존자료와 별도 대조·검토하고 자동반영 금지.


## 17. [최신] ChatGPT Work 클라우드 브라우저에서도 공식 상세페이지 3999 본문 확보 실패
- **사용자 제공 관찰 결과** (브라우저 내부 실행 로그를 이 개발 세션에서 독립 검증한 것은 아님): Work 클라우드 브라우저에서 `https://councilrec.cheongju.go.kr/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn=3999`까지 이동했으나 `upstream connect error … connection timeout`, 새로고침 1회 후에도 동일 오류. **본문 미표시**.
- 제목·일자·실시간 공개상태·원문 일부 모두 추출/검증 **불가**. URL 탐색 성공을 회의록 내용 확인으로 오해하지 말 것. 사용자 설명상 기존 저장자료 수정 없음.
- 근거 분리 원장: `reports/official-work-browser-readonly-3999-user-report-20261102.json`; 종합 보고서: `docs/OFFICIAL_READONLY_CONNECTIVITY_QA_20261102.md` 제7절.
- 종합: GitHub Runner에서도 공식 서버 TLS 연결 오류/시간초과였고, ChatGPT Work도 본문 표시 실패. **청주시의회 서버 전체 장애·차단 정책·기존 아카이브 변경**을 단정하지 않는다. 소량 실시간 원문 대조 불가 판정 유지.
- 다음 단계: **기관의 허가된 로컬/내부망 PC에서 단일 ID 3999 읽기전용 접속을 확인**하고 결과에 따라 후속 원문 대조 범위를 결정. 네트워크/접근정책 우회 또는 TLS 보안 무력화 금지. `run_sync` 운영 하드 잠금과 정기 자동수집 OFF 유지, `main` 및 기존 회의록 아카이브 불변.


## 18. [최신·기존 접속장애 판정 갱신] macOS 원본 수집기 TLS로 공식 회의록 3999·4019 및 대수목록 root 실시간 조회 성공
- **상세:** `docs/MACOS_ORIGINAL_TLS_LIVE_SOURCE_SUCCESS_20261102.md`.
- macOS `python ssl.create_default_context()` 방식 초기 읽기전용 시험: `3999` SSL handshake 실패, HTTP 0건. 증거 `reports/official-macos-readonly-probe-20261102.json` / https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41390168265.
- **원본 수집기와 같은 TLS 설정** (`collect_integrated_minutes.TLS`: 인증서 검증 활성, 최소 TLS1.2, `set_ciphers("DEFAULT")`)으로 macOS `3999` 실제 HTTP 200, HTML 322,974바이트, 본문 파싱 및 기존 저장 SHA-256 **완전 일치**. 증거 `reports/official-macos-original-tls-3999-20261102.json` / https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41390349243.
- 동일 설정의 macOS 추가 시험: `4019` HTTP 200, 본문 파싱 및 기존 저장본 SHA-256 **완전 일치**. 공식 대수목록 `SvcMntsTreeGnrtn.php` 조회용 최상위 POST HTTP 200, JSON 대수 1~4 모두 파싱 성공. 증거 `reports/official-macos-original-tls-4019-tree-20261102.json` / https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41390508185.
- **제16·17절 및 앞선 '모든 클라우드에서 본문 추출 불가' 판정은 최신 실증으로 정정**: 동일 공식 서버에서 macOS 기존 수집기 TLS로 상세 본문·목록 조회 가능함. 과거 Ubuntu·Work·macOS 기본 TLS 실패도 당시 관찰 사실로 유지. 단, 서로 다른 실행 시점/러너였으므로 TLS 암호군 설정만을 단독 원인으로 확정하지는 않음.
- 저장된 `3999=published`, `4019=provisional` 상태는 **기존 인덱스의 수집 시점 사실**. `4019` 실시간 공개상태는 회기별 세부 트리 아직 재조회하지 않아 **미검증**.
- 총 공식 실시간 GET 2회 + 목록 최상위 조회용 POST 1회, 재시도 0회. 원문 2건 해시 일치, 루트 대수 4개 확인. 기존 2,339건·인덱스·exports 수정 0. `main` 및 별도 `cheongju-council-minutes` 불변. 운영 `run_sync` 하드 잠금과 정기 자동수집 OFF.
- 다음 단계: 이 원본 TLS 컨텍스트를 정식 소량 진단기에서 재사용하고 제4대 106회 좁은 트리로 `4019`의 실시간 `var09`만 제한적 조회, 이후 **격리 환경**에서 증분 변경 후보를 검증. **실운영 자동갱신은 아직 미승인.**


## 19. [최신] 임시 회의록 6건 공식 상태 전수 확인 및 변경후보 0건 (2026-11-02)
- **최신 상세 검증:** `docs/SIX_PROVISIONAL_OFFICIAL_LIVE_STATUS_QA_20261102.md`. 이 절은 앞의 제18절에서 `4019` 실시간 공개상태가 미검증이라고 한 상황을 최신 공식 조회 결과로 대체한다.
- macOS 원본 수집기 TLS 컨텍스트(`set_ciphers("DEFAULT")`, 서버 인증서 검증 유지)에서 공식 대수별 목록을 루트→제4대 회기→제105·106회 위원회→정확히 네 해당 위원회까지 한정 조회. **총 8회 공식 목록 조회, 각 요청 재시도 0회, 기존 수집 파일 변경 0건.**
- 공식 위원회 회의록 노드 `var12`와 `var09`로 **6개 모두 실시간 상태 확인**: `4017=N`, `4018=N`, `4019=N`, `4020=N`, `4021=N`, `4022=N`. 기존 저장 상태 `provisional`과 6건 모두 동일하며 **확인된 전환 후보 0건**.
- 단계별 공식 응답 원장: `reports/official-term4-branch-discovery-20261102.json` (제4대 루트/회기, PASS, CI https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41391542744); `reports/official-term4-target-sessions-20261102.json` (105·106회 위원회, PASS, CI https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41391710745); `reports/official-six-provisional-status-20261102.json` (4개 위원회·6개 `var09`, PASS, CI https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41391894216).
- 오프라인 변경판정 `scripts/evaluate_provisional_official_changes.py`, `tests/test_provisional_official_change_candidates.py`, 보고 `reports/official-six-provisional-change-candidates-20261102.json`, CI https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41392066334. **실자료는 6건 불변·검토 후보 0건**, 별도 가상시험에서 `4019:N→Y`를 주입하면 자동 적용 대신 본문·원본 이력 확인 후보 1건을 생성함. 가상시험 결과를 공식 상태로 오인하지 말 것.
- **범위 제한:** 이것은 기존 임시 6건의 현재 공개상태 검증이지 전체 공식 신규 회의록·모든 수정 이력의 전수 재조회가 아님. 4개 관련 위원회 외 새로 생긴 회의록 존재 여부는 미확인.
- 전체 기존 회의록 **2,339건 원본·인덱스·export 변경 없음**, 전체 원본 무결성 PASS. `main` 및 별도 저장소 불변, 실운영 `run_sync` HARD LOCKED, 정기 자동수집 OFF.
- 다음: **공식 전체 목록을 당장 재수집하지 말고**, 변경 탐지를 위한 조회범위/자원상한·실패복구 기준을 설계해 macOS 격리 복사본에서 검증. 운영 활성화에는 사용자 단일 승인 필요.


## 20. [최신] 제4대 전체 공식 회의록 목록 실시간 재조회 — 미수집 ID 2건 4024·4025 및 본문 검증 완료
- **최신 상세 QA:** `docs/TERM4_NEW_MEETING_IDS_LIVE_DISCOVERY_20261102.md`. 이 절은 제19절의 임시본 6건 상태 확인 후 다음 과제인 **신규 ID 후보 탐지**를 실제 서버에서 수행한 결과.
- GitHub macOS + 원본 수집기 TLS(`set_ciphers("DEFAULT")`, 인증서 검증 유지): 공식 대수별 트리 **제4대 전 회기 4개(103~106회), 위원회 26개 분기, 개별 leaf 52개**에 대해 총 **32회 읽기전용 조회**, 재시도 0회, 모든 하위 분기 완료/에러 0. 기존 `indexes/integrated/meetings.json`의 전체 2,339 ID 집합과 비교: 제4대 기존 **50건 전부 동일**, 새 `schSn=4024`, `schSn=4025` **2건**. 제4대 기존 상태·제목·일자·위원회/URL 변경 0, 미발견된 기존 제4대 ID 0. 공식 신설/게시 시각은 불명; '저장본에 없고 현재 공식목록에 있음'을 정확히 표현. 공식 목록 조회 QA: https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41393348557, `reports/official-term4-new-meeting-id-discovery-20261102.json`.
- **4024:** 제106회 도시건설위원회 제1호, 개최 2026-10-14, 공식 상태 `N` 임시, 공식 상세 HTTP 200, HTML 263,445바이트, 본문 77,681자, 정규화 본문 SHA `818fa74efdb62b563d5ba4ce8c23a47e5c9811113e0b3e493f82fe3ee5b6545d`.
- **4025:** 제106회 의회운영위원회 제1호, 개최 2026-10-12, 공식 상태 `N` 임시, 공식 상세 HTTP 200, HTML 59,398바이트, 본문 12,887자, 정규화 본문 SHA `56a6503293a26f9cec67d6170dfaa5fa93b0047cacbb5438c55fd192592f3eba`.
- 두 새 ID는 공식 HTML 추출/임시 안내까지 실제 확인. 각각 GET 1회, 재시도 0회. 조회 QA https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41393659913, `reports/official-term4-new-meeting-body-check-20261102.json`. HTML·본문 자체를 이번 아카이브에는 발행하지 않고 QA 원장에 해시만 보존.
- 안전 코드는 `scripts/probe_official_term4_new_meeting_ids_macos.py`, `scripts/probe_official_new_term4_bodies_macos.py`; 테스트 `tests/test_official_term4_new_meeting_ids.py`, `tests/test_official_new_term4_bodies.py`. API 호출 예산 제4대 전부 80회 상한/실제 32, 본문 2회 상한/실제 2. 회기/위원회 분기가 불완전하면 누락을 삭제로 처리하지 않는 fail-closed 판정.
- **중요 운영 현황:** 기존 보존본 **2,339건 그대로**, 제4대 원본 **50건 그대로**. 공식 최신 제4대 **52건**과의 차이 2건은 **검토 후보**일 뿐 원본 추가 0건. 실제 2,341건 아카이브 작성/Stage C 검증을 이번에 성공했다고 주장하지 않는다. `main`과 독립 `cheongju-council-minutes` 변경 없음, 운영 `run_sync` 하드 잠금/스케줄 OFF.
- 다음 단계: 정식 수집 자동화 적용 전 **임시 루트에 기존 2,339건을 복사**하고 공식 4024·4025 새 원문을 재조회하여 기존 SHA와 대조한 뒤 추가·원본 불변·Stage C 2,341행/이력·충돌복구 **격리 리허설**. 그 이전에는 실제 원본 갱신 금지. 제1~3대 기존 회의록의 최신성은 이번 작업 범위 밖.


## 21. [최신] 공식 신규 4024·4025를 실제 원문으로 2,341건 격리 복사본에 증분 추가·복구 검증 PASS
- 상세 QA `docs/REAL_TWO_NEW_2341_FULL_COPY_QA_20261102.md`, 기계검증 `reports/official-real-two-new-2341-full-copy-rehearsal-20261102.json`. macOS 전체 리허설 Actions https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41395286199 **PASS**.
- 공식 2026 연도별 목록에서 `4024,4025` 모두 `var09=N` 재확인, GET 2회로 실제 공식 원문 재수신, 직전 라이브 SHA와 완전 일치. 4024 본문 정규화 SHA `818fa74efdb62b563d5ba4ce8c23a47e5c9811113e0b3e493f82fe3ee5b6545d`, 4025 `56a6503293a26f9cec67d6170dfaa5fa93b0047cacbb5438c55fd192592f3eba`.
- **2,339건 전체 정확한 바이트 복사본**에만 기존 `collect_integrated_minutes.run_sync("incremental",temp_root)`를 활용. 실제 서버에서 새로 읽은 본문 2건 외 기존 임시 6건은 저장된 Markdown에서 SHA 검사 후 mock 재생했고 별도 라이브 조회로 주장하지 않음.
- 결과 **격리 복사본 2,341건**: 기존 2,339 원본 파일 해시 **전부 불변**, 새 2건 공식 본문 해시 일치, 신규 정규화 본문 SHA 및 Markdown 파일 SHA **2,341/2,341 PASS**, term 663/771/855/**52**, published **2,333**, provisional **8**, 분석기 `meetings.jsonl` **2,341행**, export manifest 해시 **24/24 PASS**, Stage C **경고 0·오류 0**.
- **두 번째 별도 원본 복사본**에서 업데이트 저널 7파일의 2파일 설치 직후 SIGKILL 종료. `sync_transaction.recover_pending`이 `rolled_back_uncommitted`로 복구. 이전 **2,339건 원본 SHA**·인덱스·분석기 JSONL/manifest **정확한 기존 바이트 복원**, Stage C 재검증 PASS. 정전·NFS 검증은 아님.
- **실제 GitHub 아카이브는 여전히 2,339건**. 임시 두 복사본 모두 폐기. 신규 원문 4024/4025 실운영 원본 추가 없음. 개발 브랜치에는 안전 리허설 코드·테스트·본문 해시 및 QA 보고서만 보존. `main`, 독립 `wildkim11/cheongju-council-minutes` 변경 없음.
- 운영 `run_sync("incremental"/"full",ROOT)` 하드 잠금 및 자동 스케줄 OFF. 기존 2,339건과 두 신규 ID를 실제 운영 저장소에 합치거나 자동수집을 가동하려면 **별도의 사용자 명시적 승인** 필요.
- 후속 우선순위: 실제 정식 무인 증분 운영의 **안전한 요청 예산, 중복/재수집 주기, 새 본문 변경·임시→정식 전환 이력 보존, 전체 회기·연도 목록 커버리지와 장애 알림** 설계 및 격리 QA. 이번 PASS가 원본 자동 배포 승인이라는 해석은 금지.


## 22. [최신] macOS 통합 공식 증분 감시 개발 및 제4대 신규 4026 추가 발견, 합성 상태·본문 복합변동 전수 QA PASS
- **통합 상세:** `docs/OFFICIAL_AUTOMATED_INCREMENTAL_MONITOR_PRE_RELEASE_20261102.md`.
- macOS 본 수집기 원본 TLS 설정으로 `scripts/monitor_official_incremental_preflight.py` 실행. **공식 제4대 회의록 목록 53건**, 기존 보존본 제4대 50건과 차이 **신규 4024·4025·4026 세 건**. 4026은 제106회 행정안전위원회 제1호(2026-10-13), 현행 공식 `var09=N` 임시, 실제 본문 파싱 성공, 정규화 SHA `c63e097c11c05b89e80d7865816552353838e4914c9244727f1d42b8cd601536`. 4024·4025도 재조회 성공/이전 본문 SHA 일치. **신규 자료의 공식 게시 시각은 미검증**.
- 공식 목록 요청 **33회**, 본문 GET **17회** (기존 임시본 6·기존 정식 표본 8·새 자료 3). 기존 본문 **14건 SHA 전부 일치**, 공식 상태·메타데이터 변경 0, 오류 0, 재시도 0. 이는 **제4대 목록 전량 + 기존 본문 일부 표본**에 한정되며 1~3대 전체 공식 현재 목록 또는 본문 2,339건 실시간 동일성 전수검증이 아님.
- 모니터 실증 CI https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41397894568, 원장 `reports/official-incremental-monitor-readonly-latest.json`. macOS 원본 수집기 TLS/서버 인증서 검증 유지. 트리 최대 80/본문 최대 20요청, 12초 타임아웃/요청, 재시도 0. 새 ID/기존 본문 변경/임시→정식/메타데이터 후보 검토 보고, 장애·불완전 트리 실패차단 및 Actions 경고·오류·요약·아티팩트 준비.
- **동적 기준 수량 지원:** 기존 단발 제4대 탐지의 2,339·제4대 50 고정은 `baseline_policy="initial"`로 계속 유지하고, 발전한 아카이브(예: 2,341건)를 읽는 감시에서는 `baseline_policy="current"` 사용하도록 코드·무네트워크 단위시험 추가.
- **정식본 내용만 수정된 상황의 격리 반영 보완:** `collect_integrated_minutes.run_sync(mode,temp_root,force_body_ids={meeting_id})`에서 별도 본문 SHA 변경후보를 재조회 대상으로 포함할 수 있게 확장. 알 수 없는 ID는 거부, 실운영 ROOT의 `LIVE_ARCHIVE_INCREMENTAL_SYNC_DISABLED`는 먼저 작동하므로 우회 불가.
- **합성 복합변동 전체 원본 복사본 QA:** 실제 변경 사실이 아닌 오프라인 가상 `4019` 임시→정식 `N→Y`, `3999` 정식본 메타데이터 불변·본문만 변경을 2,339건 전체 복사본에 적용. 나머지 2,337건 SHA 불변, 이전 두 원본 바이트 별도 불변 리비전·이력 2건, 변경 후 2,339건 SHA 전수 및 분석기 2,339행 PASS, 정식 2,334·임시 5, Stage C 오류 0. **실제 서버 변경을 뜻하지 않음**. CI https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41398476676, 원장 `reports/synthetic-status-and-published-body-drift-2339-full-copy-20261102.json`, 스크립트 `scripts/rehearse_synthetic_status_and_body_drift_full_copy.py`.
- **알림/주기 개발상태:** 제안 정기 실행 오전 **07:30 KST**, 그러나 **schedule OFF**, 워크플로는 **수동 workflow_dispatch만** 유지; 실패 시 Actions 실패/오류, 변경 후보 시 경고 주석·요약·JSON 보고 가능. 외부 이메일·메신저 푸시 실제 발송 연결은 미검증. 보고는 `reports/`만 기록하고 원본·인덱스·export 수정 0.
- **중요 잔여 과제:** 새 4026의 공식 연도별 목록 교차조회, 신규 3건으로 구성된 **2,342건 전체 격리 임포트**(종전 2,341건 리허설에 4026은 없음), 1~3대 전체 공식 대수별 목록의 신규/수정 감시 범위, 장기간 무인실행 안전관리와 통보 수신 설정. 자동수집/실운영 원본 반영은 여전히 **별도 사용자 승인 전 금지**.
- **현재 원본:** 통합 회의록 2,339건 원래 바이트 및 SHA 유지, `main` 및 독립 `wildkim11/cheongju-council-minutes` 불변, 프로덕션 `run_sync` 잠금 유지. 테스트 복사본은 폐기.


## 23. [최신] 공식 2026 연도별 목록 4024·4025·4026 모두 임시본 확인, 실제 2,342건 격리 증분수집 및 SIGKILL 원복 PASS

- **최신 상세 QA:** docs/REAL_THREE_NEW_2342_FULL_COPY_QA_20261102.md. 이 절은 제22절의 4026 연도별 목록·2,342건 격리 검증 미완료 상태를 최신 실증으로 갱신한다.
- macOS 기존 성공 TLS 설정으로 공식 **2026년 연도별 목록**을 읽기전용 탐색한 결과 **4024·4025·4026 전부 존재**, var09=N(임시). 공식 서버 요청 **9회**, 재시도 0, 오류 0. CI https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41400610405, reports/official-year2026-three-new-ids-presence-20261102.json.
- 세 회의록 상세페이지 **각 1회 새로 GET**, HTTP 200, 전부 기존 실시간 해시와 일치. 4024 본문 SHA 818fa74efdb62b563d5ba4ce8c23a47e5c9811113e0b3e493f82fe3ee5b6545d / 4025 56a6503293a26f9cec67d6170dfaa5fa93b0047cacbb5438c55fd192592f3eba / 4026 c63e097c11c05b89e80d7865816552353838e4914c9244727f1d42b8cd601536.
- **2,339건 원본을 임시 두 복사본에 복제**, 첫 복사본의 기존 증분수집기를 mock 공식 목록과 실자료 세 본문으로 구동. 임시본 기존 6건 본문은 저장 Markdown에서 SHA 검증 후 mock 재생(새 실시간 조회로 주장하지 않음). **격리 2,342건** (정식 2,333·임시 9, 대수별 663/771/855/53) Stage C PASS, **파일 SHA 2,342건/본문 SHA 2,342건**, 기존 원본 2,339건 바이트 불변, 분석기 meetings.jsonl **2,342행**, 내보내기 24개 SHA 전부 검증, 오류·경고 0.
- **SIGKILL 복구:** 두 번째 복사본에서 8개 변경 대상 파일 중 2개 설치 직후 프로세스를 강제 중단. 미완료 트랜잭션 저널을 rolled_back_uncommitted로 복원, **2,339건 전체 원본 SHA와 기존 인덱스·분석기 바이트 모두 복구**. 복구 후 Stage C PASS.
- 실증 CI https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41401069874. 기계검증 reports/official-real-three-new-2342-full-copy-rehearsal-20261102.json. 코드 scripts/rehearse_real_three_new_2342_full_copy_macos.py, 무네트워크 방어 시험 tests/test_real_three_new_2342_isolated_rehearsal.py.
- **운영 아카이브는 실제 여전히 2,339건**. 두 임시 복사본 삭제. 신규 원문 세 건 정식 반영 0건, main 및 독립 회의록 저장소 변경 0, 실운영 run_sync full/incremental 하드 잠금 유지, 자동 스케줄 OFF.
- 남은 출시 조건: 제1~3대 최신 목록 감시 범위·요청상한, 연속 자동실행/장기 실패 후 백필, 오류 알림 실제 전송, 사용자 명시 승인 없는 자동 원본 반영을 절대 허용하지 않는 출시 정책 확인.


## 24. [중요 범위 정정] '통합 청주시의회 제1~4대'와 통합 전 구 청주시·청원군의회는 별도 아카이브

- 범위 및 인수인계: `docs/PRE_INTEGRATION_CITY_COUNTY_INCLUSION_AND_RELEASE_SCOPE_20261102.md`.
- 이 프로젝트에는 세 기관을 `config/council_scopes.json`에 독립적으로 등록: `cheongju_integrated` / `cheongju_old_city` / `cheongwon_old_county`. 대수 번호와 source_id는 기관 간 혼합 금지.
- **현재 원본 회의록 2,339건/실자료 2,342건 격리 검증은 통합 이후 청주시의회에만 해당.** 방금 macOS에서 검증한 제1~3대 회기 순환 조회도 **통합 이후 제1~3대**만 해당. 통합 전 시의회·군의회 회의록 원문은 `archive/meetings` 안에 아직 없다.
- 통합 전 구 청주시 의원 명부: 공식 제4~9대 자료에서 187 재임행 후보, 대표지역 표시 187행. 구 청원군: 공식 제1~6대 자료에서 80 재임행 후보, 대표지역 표시 0행. 각각 `reports/cheongju_old_city-historical-members.json`, `reports/cheongwon_old_county-historical-members.json`; **재임행은 고유 인물 수가 아님**. 의원 명부 일부 확보를 회의록·발언·의안 데이터 완수로 오인 금지.
- `scripts/assess_official_autonomous_release_gates.py`의 판정은 `release_council_scope=cheongju_integrated`로 명시. `preintegration_legacy_minutes_included=false`, `all_three_council_scopes_analyzer_release_authorized=false`를 항상 표시하며 별도 레거시 출처 검증 전 전범위 출시 불허.
- 향후 구 청주시·청원군의 공식 회의록·의안 목록/뷰어 식별 및 가용기간 조사 → 기관별 최초 원문 백필/해시·미확인 범위 보존 → 각 기관 독립 변경감시 → 시간별 의원 속성/발언 연결 → 변은영 기준판 바탕 통합분석기 진입. 동명 인물을 이름만으로 결합하지 않음.
- 기존 무인 운영 QA용 `official-autonomous-readonly-operations-staged.yml`은 통합 이후 청주시의회만 읽고, 예약 스케줄 OFF 및 실제 수집기 ROOT 잠금 유지.


## 25. [최신] 통합 전 청주시·청원군 **실제 공식 원문 수집 경로 검증** — 12대수·437회기·실자료 5건 격리 저장 QA PASS

- **상세 공식 검증보고서:** `docs/PREINTEGRATION_OFFICIAL_SOURCE_437_SESSIONS_AND_FIVE_BODY_QA_20261102.md`. 앞의 제24절에서 통합 전 원문 출처를 미확인으로 기록했던 부분을 최신 **실서버 접속/본문 추출 성공**으로 갱신. 단, 정식 전량 원문 아카이브는 여전히 미구축.
- 청주시의회 공식 홈페이지 링크에서 구 청주시 `/content/cityMinutes/prevsession.html`, 구 청원군 `/content/gunMinutes/prevsession.html` 확인. **macOS 원본 TLS 검증** 환경에서 두 HTML 모두 GET HTTP 200. 페이지에서 서로 독립한 `/minuteschj/`·`/minuteschw/` JS를 확인. 공식 `svc.mnts.tree.js`에서 `SvcMntsTreeGnrtn.php` POST 호출, `jquery.treeview.async.svc.mnts.js`에서 `SvcMntsViewer.php?schSn=<공식 ID>` GET을 독립 확인. 이관 전까지 항상 `council_scope`를 보존.
- 두 기관 공식 최상위 대수 ROOT 각각 **6개**: 구 청주시 제4~9대(1991~2014) / 구 청원군 제1~6대(1991~2014). `reports/official-preintegration-root-trees-readonly-20261102.json`.
- 공식 12개 대수 각각의 하위 회기 목록 **12회 직접 POST**, 오류/재시도 0: 구 청주시 44/27/38/40/41/36 = **226회기**, 구 청원군 47/25/36/34/35/34 = **211회기**, **합계 437회기**. 이것은 **회의록 건수 아님**. `reports/official-preintegration-12-terms-sessions-readonly-20261102.json`.
- **공식 자료 품질 이슈:** 구 청원군 제1대 최상위 설명문은 제001~040회, 하위 공식 회기 노드는 **1~47회 총 47건**. 상위 설명만을 근거로 41~47회를 버리지 말고 별도 원천 확인/누락 QA 실시. 실제 공식 12대수 세션 count와 다른 표시를 임의로 맞추지 말 것.
- 구 청주시 제9대 제329회 본회의 3건(`4349,4354,4355`), 구 청원군 제6대 제211회 본회의 2건(`3163,2581`)을 공식 분기에서 확인. 공식 상세본문을 기관별로 총 5건 실제 GET, HTTP200/본문 파싱/정규화 SHA-256/임시파일 저장·읽기복원 모두 PASS. 검증 기록 `reports/official-preintegration-five-bodies-isolated-pilot-20261102.json`; macOS 실증 https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41408694408. 소스 5건 원문은 **임시 저장 후 삭제**, 정식 archive에는 아직 추가 0건.
- **공개상태 의미 미확정:** 과거 공식 목록 `var09=N`이지만 직접 검증한 구 의회 본문에는 통합 이후 시스템의 임시회의록 안내 문구가 발견되지 않음. 따라서 이 값을 임의로 `provisional`로 승격시키지 않고 `source_tree_publication_code=N` 및 `normalized_publication_status=null`, `eligible_for_public_analyzer=false` 상태로 격리. 근거 없이는 '모든 2014년 자료가 임시본'이라고 주장 금지.
- 안전한 scope 계약 `scripts/legacy_minutes_scope_contract.py` 및 `tests/test_legacy_minutes_scope_contract.py`: 구 청주시/군의회 및 통합 시의회의 독립 term/ID 공간, 공식 URL 범위, 공개상태 미검증 차단, 이름만으로 의원 동일인 통합 금지. 동일 숫자 공식 source_id라도 기관별 회의록은 별개.
- 후속: 공식 **437회기 각각 위원회→개별 leaf 전체 탐색**으로 원문 대상 건수·가용성/누락 원장 구축 → 12대수 체크포인트·복구 가능한 초도 백필을 **기관별 격리 스냅샷**에서 실행 → 상태코드 의미 및 본문/인물연결 QA → 정식 아카이브 반영. 현재 통합 회의록 원본 **2,339건 그대로**, `main` 불변, 정기 무인 수집·운영 반영 OFF.


## 26. [최신] 대수별·연도별 회의록 불일치 13건 공식 웹 트리 실시간 전수 검증 완료
- 상세: `docs/MEETING_YEAR_TREE_ROLLOVER_FINDING_20261102.md` (이 절은 제12절의 실시간 전수조회 실패 상태를 최신 결과로 대체).
- 전체 저장자료 대조: 대수별 목록 2,339 / 연도별 목록 2,326 / 대수별 전용 13. 회기 종료 후 위원회 개최 121건 중 **같은 해 개최 108건은 두 트리에 모두 있고**, **전년도 12월 회기의 다음 해 1~2월 개최 13건은 대수별에만 존재**. 기존 ID 변경 없음. 비교 CI https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41421036637.
- 기존 macOS 수집기와 동일한 TLS 암호설정 `sslctx.set_ciphers("DEFAULT")` 적용: 공식 트리 root·표본 8건, 상세뷰어 180/1848/3652 3건 **모두 실시간 조회 성공** ( https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41421027454 ). 이전 41368923499 전체 재조회 타임아웃을 서버의 영구 접속불가로 해석하지 않는다.
- **원본 ID 13건을 공식 `SvcMntsTreeYear.php`와 `SvcMntsTreeGnrtn.php` 각각 회기·위원회 leaf까지 제한적으로 직접 대조**: 대수별에는 **13/13 모두 존재**, 연도별에는 **13/13 모두 누락**(해당 위원회 leaf에서 제외 11건, 위원회 분기 자체 제외 2건: 1848·2951). 요청 **60회**, 네트워크 실패 **0건**. exact `committee_code` 탐색으로 `C101` 의회운영위원회와 `J101` 행정사무감사 명칭 혼동 방지. CI https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41421849139; 결과물 artifact `official-13-year-rollover-tree-paths`.
- **이제 확인된 사실**은 두 공식 트리에서 13건이 실제로 다르게 색인된다는 것. 강한 연관인 '전년도 회기/차년도 개최'는 전수 관찰로 확정됐지만 **공식 내부 서버 SQL·프로그램 분기 구현 원인은 직접 보지 못했으므로 단정 불가**. 실무적으로 '공식 연도별 트리 인덱싱 누락 13건'으로 표기하고 본문 원본·대수·개최일·정식/임시 상태는 변경하지 않는다.
- 원본 `archive/meetings/*`, 실무 export, 의원/의안 원천 데이터 **이 조사에서는 수정 없음**. `main`과 독립 저장소 미변경, 정기 스케줄 OFF. 2026-11-02 당시 최신 운영 아카이브 2,339건 및 별도 격리 검증 2,342건 구분 유지.
