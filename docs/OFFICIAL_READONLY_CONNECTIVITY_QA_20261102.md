# 청주시의회 공식 회의록 서버 소량 읽기전용 검증 — 2026-11-02

## 1. 검증 결론

**`INCONCLUSIVE_SOURCE_UNAVAILABLE` — 클라우드 GitHub Actions 실행 환경에서 공식 회의록 서버의 TLS 연결에 실패했다.**

이 결과는 **청주시의회 공식 사이트 전체의 장애 확정, 기존 저장 회의록의 손상, 회의록의 최신 내용 변경을 뜻하지 않는다**. 클라우드 실행 환경의 접속 정책·방화벽·서버 측 허용목록·TLS 협상 등의 가능성을 현재 증거만으로 구분하지 못했다. 수집기의 실시간 목록 및 원문 파싱 품질도 아직 검증되지 않았다.

저장된 통합 회의록 2,339건, 원문 SHA, 원본·인덱스·분석기·버전 이력은 **변경하지 않았다**. 개발 브랜치 `feature/archive-foundation`에 검증용 코드·테스트·진단 원장만 작성했다. 실제 `main`과 독립 `wildkim11/cheongju-council-minutes`는 변경하지 않고 자동 수집도 OFF로 유지한다.

## 2. 첫 번째 시험: 공식 원문·트리 연결 (엄격한 한도)

- 실행 기록: https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41377991597
- 실행 코드: `scripts/probe_official_readonly_limited.py`
- 기계검증 원장: `reports/official-limited-readonly-probe-20261102.json`
- 허용 도메인: `councilrec.cheongju.go.kr`
- 상한: HTTP **최대 3회**, 요청당 **최대 12초**, 요청당 재시도 **0회**, 성공 후 최소 1초 간격, 응답당 최대 12MiB, 비정상 연결이면 즉시 전체 중단.
- 검사 계획: 저장본의 정식 회의록 `schSn=3999`와 임시본 `schSn=4019`에 대한 **GET** 두 건. 이 둘이 성공한 경우에만 공식 회기 트리 `SvcMntsTreeGnrtn.php`의 `var10=SvcMntsTreeGnrtn` **조회용 POST** 한 건. 그 이상 가지를 재귀 조회하지 않음.
- **실제 시도**: `GET ...SvcMntsViewer.php?schSn=3999` 1회만 시도.
- **결과**: HTTP 본문 수신 **0회**. HTTPS 연결 단계에서 `SSLError: [SSL: SSLV3_ALERT_HANDSHAKE_FAILURE]` 발생. 뒤의 GET 및 트리 조회는 시행하지 않음.
- 문구상 `SSLV3_ALERT_...`는 OpenSSL 오류 명칭이며 **서버가 SSL 3.0을 사용했다는 진단이 아니다**.
- `schSn=3999`의 저장본 상태는 `published`, `schSn=4019`의 저장본 상태는 `provisional`이지만, **이번 시험에서는 실시간 상태를 확인하지 못했다**. 현재 본문 해시가 저장본과 동일한지 여부도 미확인.

## 3. 두 번째 시험: 공식 도메인 두 곳의 TLS 연결 구분

- 실행 기록: https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41378195345
- 실행 코드: `scripts/diagnose_official_tls_path_readonly.py`
- 기계검증 원장: `reports/official-readonly-tls-diagnostic-20261102.json`
- `councilrec.cheongju.go.kr:443` 1회 TLS 접속 시도: **TimeoutError / timed out**
- `council.cheongju.go.kr:443` 1회 TLS 접속 시도: **TimeoutError / timed out**
- 총 **TLS 접속 시도 2회**, HTTP GET/POST **0회**, TLS 인증서 검증 무효화 **없음**, 보안 수준 강제 하향 **없음**, 각 시도 최대 8초.
- 결론: **GitHub Runner에서 두 도메인의 TLS 연결 성립을 확인하지 못함**. 다른 환경이나 일반 사용자 브라우저의 접속 가능성까지 부정하지 않음.

## 4. 공개 검색에서 확인되는 사항과 차이

검색 결과에서는 공식 청주시의회 회의록 홈페이지 `https://councilrec.cheongju.go.kr/`와 회기별 검색 `/content/minutes/session.html`이 존재하는 것으로 나타난다. 주 의회 홈페이지 `https://council.cheongju.go.kr/`에도 회의록 관련 공지가 검색된다.

다만 **검색 엔진의 보관·색인 정보는 현재 서버가 이 실행 환경에 원문 HTML을 전달한다는 증명이 아니다**. 이번 조회용 공식 PHP 동적 페이지의 본문은 확보하지 못했다. 동적 회의록 `schSn=3999`에 대한 외부 웹 열기도 캐시 미스로 실패했다.

## 5. 안전성 및 검증 범위

- 공식 서버에 문서를 수정하거나 등록하는 요청 없음.
- 로그에 회의록 전문 HTML·본문 저장 없음. 기존 보존자료와 비교할 때만 SHA-256을 사용하도록 설계.
- 기존 2,339건 원문·해시 검증은 오프라인 Stage C로 통과. 이 사실을 **실시간 최신성 검증 성공**으로 바꾸어 표현하지 않음.
- 기존 `run_sync(full/incremental,ROOT)` 운영 하드 잠금 유지. 일정 자동 실행·무차별 재시도·`main` 변경 없음.
- 실시간 회의록 공개상태 변화, 신규 목록, 원문 변경, 공식 서버의 대수/연도 트리 차이 재탐색 결과는 **모두 확인 불가**.

## 6. 후속 검증 기준 (이 단계에서는 미실행)

1. 청주시의회 홈페이지에 접속 가능한 **승인된 다른 네트워크 환경**에서, 먼저 `schSn=3999` 한 건을 브라우저로 읽기전용 확인하고 공식 주소가 동일한지 검증.
2. 동일 ID `3999`(기존 published)와 `4019`(기존 provisional) 최대 2건의 본문 파싱·SHA 대조. 원문 상태가 달라진 경우 **즉시 저장·교체하지 말고 변경 후보로 별도 보고**.
3. 기본 접속이 안정적인 경우에만 회기 트리의 **최상위 루트 1회**, 이후 필요할 때 대수별 좁은 분기별로 확장. 재귀 전체 수집·자동 시간표는 별도 검증과 사용자 승인 이전까지 금지.
4. 특정 클라우드 IP의 차단인지, 실제 서버 측 TLS 설정 문제인지 지금 추론만으로 확정하지 않는다. 진단 과정에서 `verify=False`나 과거 약한 TLS로 보안 설정을 낮추지 않는다.

**운영 판정: `LIVE_SOURCE_VALIDATION_NOT_COMPLETED`, 원본 보존 및 자동수집 잠금 유지.**


## 7. 사용자 제공 ChatGPT Work 클라우드 브라우저 추가 검증 결과

**증거 구분: 사용자가 전달한 브라우저 실행 결과. 본 개발 세션이 동일 브라우저 내부 로그를 직접 검증한 것은 아님.**

- 대상 공식 상세페이지: `https://councilrec.cheongju.go.kr/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn=3999`.
- 브라우저가 해당 **URL까지 이동**한 것은 확인했지만, 공식 서버 본문을 표시하거나 읽어낸 것은 아님.
- 오류: `upstream connect error … connection timeout`. 한 차례 새로고침 후 동일한 타임아웃.
- 회의록 제목·일자·실시간 공개상태·본문 일부: **모두 확인 불가**. 현재 원문 SHA 비교나 정식본 여부 재확인에도 사용 불가.
- 사용자 설명상 저장자료는 수정하지 않음. 본 기록은 기존 GitHub Runner의 TLS 오류/시간 초과 검증과 **별개 환경의 관찰 결과**.
- 별도 출처 표시 원장: `reports/official-work-browser-readonly-3999-user-report-20261102.json`.

**종합 판단:** GitHub Actions 직접 연결, ChatGPT 웹 검색, ChatGPT Work 클라우드 브라우저 모두 **실시간 회의록 본문 확보에 실패**했다. 그렇다고 서버 전체 장애 또는 청주시의회 정책상 차단을 확정하는 증거는 아니다. 브라우저가 URL로 이동한 성공과 실제 HTML을 읽은 성공은 구분해야 한다.

**다음 실행 지점:** 기관에서 접속이 허용된 PC 및 네트워크에서 공식 홈페이지의 회의록 상세페이지 한 건 `schSn=3999`을 사람의 브라우저로 확인하고, 성공 시에만 수집 검증을 확장한다. 내부망 및 외부망 접속 정책을 준수한다. 연결에 실패하면 해당 환경의 시각·최소 오류유형만 남기고 무차별 재시도 금지. 운영 ROOT 수집 잠금과 스케줄 OFF는 유지한다.
