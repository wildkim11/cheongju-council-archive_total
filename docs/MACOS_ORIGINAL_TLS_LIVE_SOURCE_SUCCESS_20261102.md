# macOS 공식 회의록 서버 실시간 조회 성공 — 기존 수집기 TLS 재현 QA (2026-11-02)

## 1. 검증 결론

**`PASS_LIMITED_LIVE_SOURCE_READ`: 공식 회의록 2건과 최상위 대수별 목록에 대한 읽기전용 실시간 조회 성공.**

최초 GitHub-hosted macOS read-only 진단에서 일반 Python `ssl.create_default_context()`만으로 조회한 `schSn=3999`는 `SSLV3_ALERT_HANDSHAKE_FAILURE`로 실패했다. 과거 **2,339건을 최초 수집한 원본 수집기**에서 사용하던 `collect_integrated_minutes.TLS` 컨텍스트 (인증서 검증 활성, TLS 최소 1.2, `set_ciphers("DEFAULT")`)를 그대로 사용한 이후 macOS에서 다음 조회가 성공했다.

- `schSn=3999`: **HTTP 200**, HTML **322,974바이트** 수신, 회의록 본문 추출 성공, 기존 저장본과 정규화 본문 SHA-256 **일치** (`2628560d876daa32a22f5d5bf0e55b580298d1199a21829aad3d951a52b119e6`).
- `schSn=4019`: **HTTP 200**, HTML **67,538바이트** 수신, 본문 추출 성공, 기존 저장본과 정규화 본문 SHA-256 **일치** (`bb96a51d169e43533f6c5388dd7ecf75d24e63bc9e177b698d630e455a4784c1`).
- 최상위 대수별 공식 트리 `SvcMntsTreeGnrtn.php` / `var10=SvcMntsTreeGnrtn`: **HTTP 200**, JSON **2,011바이트**, 루트 노드 **4개**, 공식 대수 1·2·3·4 모두 파싱 성공.

위 **3회 공식 조회**는 서로 다른 두 번의 macOS CI 작업에서 진행되었으며, 요청별 재시도는 없었다. 기존 저장된 2,339건의 원본 내용·인덱스·export는 전혀 갱신하지 않았다.

### 실행·기계검증 근거

| 검증 작업 | Actions 실행 기록 | 저장 원장 | 실시간 결과 |
|---|---|---|---|
| macOS Python 기본 TLS 방식 | https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41390168265 | `reports/official-macos-readonly-probe-20261102.json` | 첫 GET `3999` TLS handshake 실패 / HTTP 0 |
| macOS **원본 수집기 TLS 재현** | https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41390349243 | `reports/official-macos-original-tls-3999-20261102.json` | `3999` HTTP 200, 본문 SHA 일치 |
| macOS **원본 수집기 TLS 재현** 추가 | https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41390508185 | `reports/official-macos-original-tls-4019-tree-20261102.json` | `4019` HTTP 200 본문 SHA 일치, 대수별 목록 root HTTP 200·JSON 파싱 성공 |

## 2. 원인 해석 주의

- **사용한 TLS 설정이 다른 점은 실증됐다.** 원본 수집기에는 `TLS.set_ciphers("DEFAULT")`가 있지만 초기 소량 probe에는 이 설정이 없다.
- 그러나 각각 다른 CI 실행 시점·러너 인스턴스였으므로 **TLS 암호군 설정 차이만이 원인이라고 확정할 수는 없다**. 서버측 연결상태와 실행 IP도 시점에 따라 달랐을 수 있다.
- 이전 Ubuntu Actions/TLS-only 진단, ChatGPT Work 브라우저 조회 실패는 그 실행 환경에서의 유효한 실패 기록으로 남긴다. **모든 클라우드 환경이 차단됐다는 주장은 철회**한다. 적어도 macOS + 기존 수집기 TLS 환경에서는 공식 응답이 실제로 수신된다.
- SSL 오류명 `SSLV3_ALERT_HANDSHAKE_FAILURE`는 SSL 3.0 프로토콜 사용을 확정하지 않는다.
- 기존 `3999`는 `published`, `4019`는 `provisional`로 저장돼 있지만, **최상위 목록에는 개별 회의록 공개상태가 없어 두 ID의 실시간 공개상태 변화는 아직 검증하지 않았다.** 정확한 상태 확인에는 해당 대수의 해당 회기 분기까지 매우 제한적으로 조회해야 한다.

## 3. 데이터 무결성과 운영 정책

- 공식 사이트에 대해 **GET 2회, 루트 목록 조회용 POST 1회**, 모두 읽기전용. 전체 재귀 검색이나 전체 원문 재수집 없음.
- 전수 저장 원본 2,339건의 오프라인 Stage C 검증 PASS, 수집 전후 `archive`, `indexes`, `exports` 파일 변경 **0건**.
- 공식 서버에서 확인한 원문은 해시와 바이트 길이만 진단 원장에 보존, 전체 HTML이나 본문 텍스트를 신규 저장하지 않음.
- **실운영 `run_sync("incremental"/"full", ROOT)` 하드 잠금 유지**, 정기 자동수집 OFF, `main` 미변경, 별도 `wildkim11/cheongju-council-minutes` 저장소 미변경.
- 격리 QA 완료와 정식 무인수집 가동 승인을 구분한다. 본문 두 건 일치와 루트 조회 성공만으로 전체 회기 트리·신규 회의록·임시→정식 전환·전원장애 내구성까지 승인한 것은 아니다.

## 4. 다음 권장 작업

1. 기존에 실제로 통했던 `collect_integrated_minutes.TLS`를 소량 조회 스크립트의 기본 안전 설정에 반영하고, 클라우드 플랫폼·TLS 설정·성공률을 구분해 기록.
2. `4019`가 속하는 제4대·제106회 분기 1개에 한정해 **실시간 `var09` 공개상태**와 ID를 확인. 저장본 변경 후보만 출력하고 실제 반영 금지.
3. 이후 매우 작은 오프라인 복사본 격리환경에서 실제 목록 스냅샷과 저장본의 차이 검출 시험. 운영 원본은 승인 전까지 업데이트하지 않음.
4. 빈번한 재시도를 하거나 TLS 검증을 비활성화하지 않는다.

**판정: 접속 불가 문제는 macOS 기존 수집기 TLS로 일부 해결됨. 자동갱신 정식 운영은 여전히 미승인.**
