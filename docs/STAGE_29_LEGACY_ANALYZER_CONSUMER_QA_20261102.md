# 29단계 — 기존 의정분석기 HTML 구조 및 연결 차단 검증 (2026-11-02)

## 결론

**보관 HTML 구조검사 PASS / 공식 아카이브 자동 연결 미승인.**

2026-09-27 생성본 CheongjuCouncilAnalyzer_MASTER_SOURCE_r10_2_INTEGRATED.html의 embedded JSON을 실제 추출해 읽기 전용으로 검사했다. 사용자 PC의 현재 최신 MASTER_SOURCE 작업 폴더에 접속한 것은 아니다.

## 검증 결과

| 항목 | 확인값 |
|---|---:|
| HTML 원본 크기 | 37,188,810바이트 |
| SHA-256 | 44087188c7fa390a4c063cb5d63ced0d8afc46ef643f589e34f18c7f90b98582 |
| embedded schema | cheongju-integrated-html-embedded-data/1.0 |
| 생성 시각 (UTC) | 2026-09-27T11:20:10.167441+00:00 |
| 전체 정규화 facts | 18,451 |
| 전체 member_fact_links | 13,748 |
| BILLS facts | 3,332 |
| BILLS 관련 member_fact_links | 10,920 |
| 의원 연결이 있는 BILLS | 861 |
| member_contexts가 있는 BILLS | 861 |
| BILLS 내 공식 internal_number | **0** |
| BILLS 내 proposer_type / proposer_type_list | **0** |
| BILLS 연결 내 proposer_role | **0** |
| BILLS 내 official_url | **0** |
| BILLS scope | cheongju-integrated (3,332) |
| BILLS 날짜 | 2014-07-01~2026-09-08 |

- 이 HTML의 fact_id=evnode-... 및 source_ref.source_item_id=bills-...는 구 분석기의 내부 식별자다. 새 아카이브의 공식 의안 내부번호와 동일하다고 판단할 증거가 없다.
- 의원 연결 10,920행은 검증된 대표·공동발의 역할과 동일하다는 근거가 없다. 이 값에 기관형 인명 44행이 포함됐다고 단정하지 않는다.
- 과거 분석기 의안 3,332건과 11월 공식 아카이브 의안 3,394건은 시점과 범위가 다르다. 차이 62건을 자동으로 누락/신규 판정하지 않는다.
- HTML의 cheongju-integrated와 새 아카이브의 cheongju_integrated는 별도의 범위 매핑 근거가 필요하다.

## 검사 코드와 재현

- scripts/audit_legacy_analyzer_html.py : 원본 HTML 읽기 전용 내장 JSON 감사, 결과는 표준 출력으로만 내보냄
- tests/test_audit_legacy_analyzer_html.py : 네트워크 없는 fixture 6건, 로컬 실행 6/6 PASS
- .github/workflows/audit-legacy-analyzer-html.yml : 읽기 전용 CI로 독립 확인 가능
- 실제 보관 HTML 검사: STRUCTURAL_PASS_CROSSWALK_NOT_VERIFIED
- GitHub Actions의 신규 실행 완료 여부는 **미확인**. 테스트 설정 배포를 CI 통과와 혼동하지 않는다.
- 로컬 파일·GitHub 아카이브 원본·사용자 PC 데이터는 수정하지 않았다.

## 30단계에 필요한 조건

1. 최신 사용자 PC MASTER_SOURCE 의안 원장의 원천 식별 필드와, 본 HTML의 source_item_id 및 새 공식 아카이브 internal_number 사이 crosswalk를 **공식 ID나 출처 원문**으로 검증한다.
2. 대수·기관·시점이 일치하는 의원 신원 대응표를 별도 생성한다. 동명이인 이름만으로 person_id를 결합하지 않는다.
3. 후보 관계는 EXACT_OFFICIAL_ID, SOURCE_DOCUMENT_MATCH_PENDING, UNMATCHED, CONFLICT로 구분해 미확정 승격을 차단한다.
4. 개인 발의 분석은 검증된 bill_proposers_member_only 11,377행만 활용하고 기관형 44행은 격리한다. 명단 미확인 7건은 추정하지 않는다.
5. 사용자 PC 원본 MASTER_SOURCE/GOLD/EVENT/P1~P7/기존 집계/체크포인트 및 새 아카이브 RAW를 덮어쓰지 않는다. crosswalk는 독립 파생 원장으로만 작성한다.
6. 확인된 현재 상태는 정식 회의록 2,339건, 2,342건은 격리 시연, main 미병합, 정기 자동수집 OFF다.

위 사실은 28단계의 아카이브 안전 입력검사와 별개다. **29단계는 기존 의정분석기 출력본 구조 확인이며 실제 최신 PC 분석기 연결 또는 배포가 아니다.**
