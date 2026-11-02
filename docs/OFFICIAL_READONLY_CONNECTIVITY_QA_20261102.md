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
