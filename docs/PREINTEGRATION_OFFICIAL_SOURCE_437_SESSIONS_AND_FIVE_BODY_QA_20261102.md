# 통합 전 청주시·청원군의회 공식 회의록 시스템 검증 및 437회기 규모 산정 — 2026-11-02

## 결론

**통합 전 청주시의회, 통합 전 청원군의회 모두 공식 전자회의록의 대수→회기→위원회→개별 회의록 원문에 읽기전용 접속 성공.** 두 시스템의 공식 원본은 각각 독립 `/minuteschj/`, `/minuteschw/` 경로에 존재한다. 공식 12개 대수의 하위 회기 목록을 직접 조회한 결과 **총 437회기**(구 청주시 226, 구 청원군 211)인 것을 확인했다.

실제 원문 5건(구 청주시 3건·구 청원군 2건)을 macOS에서 GET하고 **임시 기관별 저장소에 저장 후 SHA-256 대조 통과**. 임시 저장소는 삭제했다. **437은 회기 수이며 회의록 원문 건수가 아니다.** 전 회기별 위원회·개별 회의록의 총 원문 건수는 아직 확인되지 않았으며, 최초 전량 백필을 완료했다고 주장하지 않는다.

현재 기존 통합 청주시의회 원본 2,339건과 `main`, 기존 `indexes/`, `exports/`는 전혀 수정하지 않았다. 통합 전 회의록은 저장소 정식 원장에 아직 0건이며, 초기 수집은 파일·인덱스·공개상태 의미의 추가 검증 후에만 승인할 수 있다.

## A. 공식 진입점·목록 API·상세본문

| 기관 `council_scope` | 청주시의회 공식 검색 진입점 | 공식 대수·회기·위원회 트리 POST | 공식 상세본문 GET |
|---|---|---|---|
| `cheongju_old_city` | https://councilrec.cheongju.go.kr/content/cityMinutes/prevsession.html | `/minuteschj/svc/web/cms/mnts/SvcMntsTreeGnrtn.php` | `/minuteschj/svc/web/cms/mnts/SvcMntsViewer.php?schSn=<실제ID>` |
| `cheongwon_old_county` | https://councilrec.cheongju.go.kr/content/gunMinutes/prevsession.html | `/minuteschw/svc/web/cms/mnts/SvcMntsTreeGnrtn.php` | `/minuteschw/svc/web/cms/mnts/SvcMntsViewer.php?schSn=<실제ID>` |

두 HTML 페이지를 GET하여 200 수신. 각 페이지에서 `/minuteschj/`와 `/minuteschw/`를 사용하는 트리 JavaScript 경로를 확인. 공식 JavaScript `svc.mnts.tree.js` 및 `svc.mnts.tree.var.js` 각 2건에서 실제 GET·POST API 경로 확인. 공식 `jquery.treeview.async.svc.mnts.js`에서도 `var12`를 `schSn`에 넘기는 상세본문 링크 형식을 별도 실조회하여 확인했다. 미확인 추측 URL을 수집 근거로 사용하지 않았다.

공식 실제 데이터 요청은 기존 청주시의회 수집기에서 성공했던 인증서 검증 TLS 설정 사용(기본 CA·최소 TLS1.2·`DEFAULT` cipher), macOS GitHub Actions. 연결 실패 시 삭제나 보존 불가능으로 판단하지 않고 실패로 격리.

증거:
- `reports/official-preintegration-portals-readonly-20261102.json`: 공식 HTML 2건.
- `reports/official-preintegration-js-endpoints-readonly-20261102.json`: 트리 JS 4건의 공식 경로.
- `reports/official-preintegration-root-trees-readonly-20261102.json`: 두 기관의 독립 6개 대수 루트.
- `reports/official-preintegration-two-leaves-readonly-20261102.json`: 대수→회기→본회의→회의록 ID 실제 드릴다운.
- `reports/official-preintegration-viewer-js-readonly-20261102.json`: 상세 Viewer 링크의 공식 JS 근거.
- `reports/official-preintegration-two-real-bodies-readonly-20261102.json`: 각 기관 원문 1건 실조회/본문 해시.
- `reports/official-preintegration-12-terms-sessions-readonly-20261102.json`: 12대수 전체 공식 회기 수.
- `reports/official-preintegration-five-bodies-isolated-pilot-20261102.json`: 실자료 5건 임시 저장·SHA 왕복검증.

## B. 공식 대수·회기 재고 실측

| 기관 | 대수 | 기간 표시(공식 대수 루트 기준) | 공식 실조회 회기 수 | 회기 번호 최솟값~최댓값 |
|---|---:|---|---:|---|
| 구 청주시 | 4 | 1991~1995 | 44 | 104~147 |
| 구 청주시 | 5 | 1995~1998 | 27 | 148~174 |
| 구 청주시 | 6 | 1998~2002 | 38 | 175~212 |
| 구 청주시 | 7 | 2002~2006 | 40 | 213~252 |
| 구 청주시 | 8 | 2006~2010 | 41 | 253~293 |
| 구 청주시 | 9 | 2010~2014 | 36 | 294~329 |
| **구 청주시 소계** | **6개 대수** | **1991~2014** | **226** | — |
| 구 청원군 | 1 | 1991~1995 | 47 | 1~47 |
| 구 청원군 | 2 | 1995~1998 | 25 | 48~72 |
| 구 청원군 | 3 | 1998~2002 | 36 | 73~108 |
| 구 청원군 | 4 | 2002~2006 | 34 | 109~142 |
| 구 청원군 | 5 | 2006~2010 | 35 | 143~177 |
| 구 청원군 | 6 | 2010~2014 | 34 | 178~211 |
| **구 청원군 소계** | **6개 대수** | **1991~2014** | **211** | — |
| **합계** | **12개 대수** | — | **437개 회기** | — |

**공식 표시 불일치 확인**: 구 청원군의회 제1대 최상위 대수 설명문에는 `제001회 ~ 제040회`가 표시되지만, **실제 해당 공식 대수 노드의 하위 회기 목록 POST 응답에는 제1~47회 47개**가 반환됐다. 상위 설명을 근거로 41~47회 기록을 누락하거나 하위 목록을 임의로 수정하지 않는다. 최초 전량수집 시 해당 회기 7개의 분기/원문 존재와 소속 확인을 별도 QA에서 요구한다.

## C. 두 기관의 실제 원문 5건 임시 수집

| 기관 | 기관 내부 ID | 회기·위원회 | 본문 글자 수 | 정규화 본문 SHA-256 |
|---|---:|---|---:|---|
| 구 청주시 | 4349 | 제329회 본회의 개회식 | 2,211 | `6d5a5451978275c67719550c13771b4c0c9b608732daa38fbae8d31610d39812` |
| 구 청주시 | 4354 | 제329회 본회의 제1차 | 22,959 | `be88a7a556904dcf7ebecb0e5761815b88742a7db04d38480c69bc52928b6590` |
| 구 청주시 | 4355 | 제329회 본회의 제2차 | 3,152 | `aa8009f8fbdd5b6a2eccf86bd6b863951590503764de66724b8b4c825ba905cd` |
| 구 청원군 | 3163 | 제211회 본회의 제1차 | 13,492 | `b7a3aaaf2f145e27bd9a9a281f2c4d2946c3713058e3ef3cae290738a8373d5f` |
| 구 청원군 | 2581 | 제211회 본회의 제2차 | 4,621 | `238b6064a2b51113cdd11afbbc179004354a4cc50d97fa51f599534a9db83e57` |

전부 공식 GET HTTP 200, 실제 본문 추출 완료. 이전에 각각 개별 GET으로 검증한 4355·2581의 SHA와 이번 재조회 SHA가 일치함도 확인했다. 실제 본문 HTML 또는 전문을 GitHub 개발 브랜치에 업로드하지 않고, 임시 디렉터리에만 원본 Markdown 파일 5개와 기관별 식별자·SHA를 생성·재읽기한 후 **삭제**했다.

CI 실증: https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41408694408

## D. 중요한 두 가지 데이터 보존 규칙

**첫째: 기관별 대수·ID는 절대 합치지 않는다.** 통합 전 구 청주시 제4~9대와 구 청원군 제1~6대는 독립 기관이다. 동일 숫자 `schSn`가 둘 이상의 기관에 등장해도 고유키는 `council_scope:minutes-<source_id>`로 별도 유지한다. 관련 코드: `scripts/legacy_minutes_scope_contract.py`, 회귀검증 `tests/test_legacy_minutes_scope_contract.py`. 기존 통합 시의회의 `cheongju_integrated`와도 기관 식별자를 혼동하지 않는다.

**둘째: 과거 목록의 `var09=N`을 자동으로 '임시본'이라고 확정하지 않는다.** 2014년 표본 5건 모두 목록의 원시 `N` 상태코드가 확인되었으나, 먼저 확인한 두 공식 본문에는 통합 이후 시스템에 등장하는 '임시회의록' 안내가 없었다. 구 의회 운영 당시 상태코드 의미/이관 규칙은 별도 공식 증빙이 필요하다. 현재 임시 수집 레코드는 `source_tree_publication_code=N`, `normalized_publication_status=null`, `source_publication_semantics_verified=false`, `eligible_for_public_analyzer=false`로 보존하며 자동 승격 금지.

## E. 후속 최초 전량수집 설계

초기 백필은 **12개 대수·437개 공식 회기**로 분리하고, 각 회기별 공식 위원회→개별 회의록 노드를 전부 수집해 그때부터 실제 회의록 수와 누락/중복/미확인 원장을 작성한다. 상위 대수 설명문과 하위 회기 목록 불일치는 별도 품질검증 항목으로 남긴다.

현행 macOS 단발 실증의 조회 한도와 리포트·정규화 알고리즘을 재사용하되, 실운영 원본에 바로 쓰지 않고, **기관·대수별 체크포인트/원본 버전과 SHA가 보존되는 격리 저장소**에 먼저 백필한다. 각 구간에 대해서만 본문 재조회→해시 일치→공식 URL→분석기 스키마 검증을 통과시키고, 실패한 회기는 재개 목록에 남긴다.

이후 두 기관의 원문 공개상태 의미, 시기별 소속/인물 동일성, 누락 회기와 원문 출처를 검증한 다음에만 정식 보존 아카이브나 변은영 기준판 통합 의정분석기에 반영한다. **통합 청주시의회 원본 2,339건 및 현재 운용 잠금은 유지.** 자동 스케줄·정식 원본 백필·`main` 반영은 아직 실행하지 않았다.

**현재 판정: `LEGACY_OFFICIAL_SOURCE_AND_BODY_EXTRACTABLE_BOTH_SCOPES`; `ALL_12_TERMS_437_SESSIONS_ENUMERATED`; `FIVE_REAL_BODIES_DISPOSABLE_STAGING_PASS`; `FULL_LEGACY_BACKFILL_NOT_YET_EXECUTED`.**
