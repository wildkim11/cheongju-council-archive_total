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
