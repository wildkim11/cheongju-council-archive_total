# 청주시의회 통합 회의록 증분수집 격리시험 및 운영 차단 검증 (2026-11-02)

## 1. 현재 결론

**운영 판정: \`BLOCKED_UNSAFE_TO_OPERATE\` — 아직 정기·수동 실운영 증분수집을 실행하면 안 된다.**

기존 2,339건의 아카이브 원본·인덱스·분석기 export는 변경하지 않았다. 이번 변경은 **개발 브랜치의 수집기 로직, 격리 시험, QA 원장, 테스트/보고서**에만 적용되었다.

**실제 공식 사이트 호출 0회**, 모든 신규/갱신/실패 시나리오는 임시 디렉터리와 HTTP mock에서만 실행했다. 시험을 정상 완료한 것은 **기존 코드에 있던 위험을 발견·일부 차단하거나 보완했다**는 의미이지 운영 가능 승인이나 실사이트 연동 성공을 의미하지 않는다.

## 2. 초기 재현 위험 5항목과 조치

| 초기 위험 | 기존 코드 재현 | 보완 후 상태 | 운영 시 주의 |
|---|---|---|---|
| 분석기 JSONL·대수별 shard가 canonical 인덱스보다 뒤처짐 | 신규 회의록 1건 추가 시 재현 | **격리 시험 통과**. staging 내 \`exports/analyzer/*\` 전체 재생성 + \`indexes/integrated/current_term_{1..4}.json\` 재생성, 기존 \`initial_term_*\` 보존 | 다음 단계에서 전체 2,339건 실제 스냅샷 복사 시험 필요 |
| 임시본 동일 ID가 published로 변경돼도 Markdown 헤더는 provisional인 상태 | 재현됨 | **위험 반영 차단**. 동일 ID에서 상태/제목/날짜/대수 등의 메타데이터가 변경되면 \`SAME_ID_METADATA_REVISION_REQUIRES_VERSION_HISTORY\` 예외 발생 | 과거 원문을 보존하며 정식본으로 변환하는 기능은 미구현 |
| 동일 ID의 공식 본문이 변경되면 원본 MD 덮어쓰기 | full 모드에서 재현됨 | **위험 반영 차단**. 기존 ID에서 정규화 본문 SHA가 달라지면 \`SAME_ID_BODY_REVISION_REQUIRES_VERSION_HISTORY\` 예외 발생 | 이전 버전 원문·SHA·개정일자 원장 설계 필요 |
| staging 검증 후 파일별 복사 중 오류가 나면 일부 새 MD만 남음 | 강제 복사 오류에서 재현됨 | **격리 시험 통과**. 변경된 대상 전체 선백업, 파일별 적용, 예외 시 바이트 단위 원복 및 신규 파일 삭제. 시험에서는 원복 전후 파일 SHA 집합 일치 | **비정상 강제종료/전원 상실에 대한 다중파일 원자성은 미확인** |
| 서로 다른 임시본 2개가 동일한 정식본 1개로 대체 | 재현됨 | **차단 완료**. many-to-one 대체관계 예외 처리, 대체 대상은 published여야 함 | 복수 후보·동명이안 수동 검증 방침 유지 |

## 3. 격리 테스트에서 실제 통과한 사례

1. 임시 아카이브에 신규 회의록 1건을 추가한 뒤 원래 회의록 Markdown의 SHA-256 불변, 신규 행·원문 존재 확인.
2. 원래 \`initial_term_4.json\` 1행은 유지하고 최신 \`current_term_4.json\` 2행 및 \`exports/analyzer/meetings.jsonl\` 2행이 canonical \`meetings.json\` 2행과 정확히 일치.
3. 가상 공식 서버에서 \`TimeoutError\`를 내면 \`RuntimeError\`로 중단하고 임시 원본의 모든 파일 SHA가 변하지 않음.
4. publish 중 canonical \`meetings.json\` 파일 복사를 **정확히 한 번** 강제 실패시켜도, 이미 임시로 복사됐던 새 MD가 제거되고 전체 시험 파일 SHA가 원상복구됨.
5. 동일 ID published 상태전환 또는 본문 개정은 이전 버전 이력 저장 기능이 없으므로 **파일 쓰기 전에 중단**. 데이터 불일치/원본 덮어쓰기 방지.
6. 서로 다른 두 provisional ID가 같은 published 후속 ID로 매핑되는 경우 수동검토 예외로 중단.
7. 기존 프로젝트 실경로에서 \`run_sync("incremental")\`과 \`run_sync("full")\` 모두 **공식 서버 조회 전에** \`LIVE_ARCHIVE_INCREMENTAL_SYNC_DISABLED\`로 거부됨.

## 4. 회귀 검증 및 QA

- 격리시험 본체: \`scripts/audit_incremental_sync_isolation.py\`
- 격리 회귀시험: \`tests/test_incremental_sync_isolation.py\`
- 기존 통합 수집기: \`scripts/collect_integrated_minutes.py\`
- current vs initial shard 지원 전수 검사: \`scripts/audit_stage_c.py\`
- 격리시험 Actions: https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41371875579 — **PASS**
- 한 번만 생성하는 QA 원장: \`reports/incremental-sync-isolation-diagnostics.json\`
- 원장 검증·기존 전체 unittest·Stage C 전수 해시 QA·개발 브랜치 저장: https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41371942115 (성공 여부는 실행 완료 후 최종 확인)

## 5. 운영 승인 전 남은 3개 release blocker

1. **동일 ID의 공식 메타데이터/공개상태 변경 이력 보존**: 이전 원본 MD와 SHA-256, 이전 필드값, 이전 published/provisional 상태를 삭제하지 않는 revision ledger를 설계하고, 임시→정식 전환을 실제로 테스트.
2. **동일 ID의 본문 개정 이력 보존**: 기존 원본의 버전별 파일을 안전한 경로에 저장하고 현재본·과거본·변경 증빙의 1:1 관계를 검증. 공식 published 본문이 기존 ID를 유지하며 바뀌는 사례도 처리.
3. **비정상 프로세스 종료·전원장애에 대한 회복 전략**: 파일별 예외 롤백은 검증됐으나 kill -9/전원상실 등에서 여러 파일이 모두 한 시점으로 보이는 다중파일 원자성은 별도 설계·검증 필요. copy+rollback만으로 완전한 ACID 원자성을 주장할 수 없다.

그 밖에 공식 서버가 자주 연결 시간 초과를 일으켜, 증분수집의 실제 HTTP 재시도/부분성공 복구는 추후 **격리 환경·요청량 제한**으로 검증해야 한다.

## 6. 원본 보존·실행 차단 원칙

- \`feature/archive-foundation\`에서만 개발·검증. \`main\` 및 독립 저장소 \`wildkim11/cheongju-council-minutes\` 변경 없음.
- 기존 회의록 \`published=2,333\`, \`provisional=6\`, 전체 **2,339**의 원문·SHA는 변경하지 않음.
- 정식 운영 실행 금지: 기존 실제 프로젝트 루트에서는 \`run_sync\`의 두 모드가 코드 수준에서 차단돼 있음.
- CI 성공은 **격리한 synthetic fixture의 테스트 통과**, 운영 개시나 실제 회의록 전체 갱신 성공의 증거가 아니다.
- 릴리스 차단 해제는 원본 보존·버전이력·복구시험과 Stage C 2,339건 본문·해시·export 동기화가 모두 검증된 이후에만 판단한다.
