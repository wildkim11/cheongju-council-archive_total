# 청주시의회 임시 회의록 6건 실시간 공개상태 및 비파괴 변경후보 판정 — 2026-11-02

## 1. 최종 판정

**공식 제4대 105·106회 해당 위원회 회의록 트리에서 기존 임시 회의록 6건 모두 현재도 `var09=N`으로 확인. 변경 후보 0건.**

이것은 **기존 `provisional` 6건만 대상으로 한 읽기전용 검증**이다. 자동수집 시스템이 전체 청주시의회 신규 회의록과 모든 수정 이력을 빠짐없이 찾았다고 주장하지 않는다.

- 공식 서버 호스트: `councilrec.cheongju.go.kr`
- 서버: 기존 수집기와 동일한 Python TLS 설정 (`ssl.create_default_context()`, 최소 TLS 1.2, `set_ciphers("DEFAULT")`, 서버 인증서 검증 유지)
- 실행 환경: GitHub Actions **macOS**
- 공식 데이터: 대수별 회의록 JSON 트리 `/minutes/svc/web/cms/mnts/SvcMntsTreeGnrtn.php`의 읽기전용 요청.
- 첫 검증 루트 2회(전체 대수 루트·제4대 직속 회기 목록), 둘째 제105/106회 위원회 목록 조회 2회, 마지막 **대상 위원회 4개 분기 조회 4회**. **총 8회**, 단계별 요청당 재시도 **0회**.
- 안전장치: 기존 `archive/`, `indexes/`, `exports/` 원본 수정 0건, 운영 `run_sync` 하드 잠금 유지, 자동 정기수집 OFF.

## 2. 공식 개별 ID 결과

| 기존 공식 `schSn` | 회기/위원회 | 기존 상태 | 공식 현재 `var09` | 현재 판정 |
|---|---|---|---|---|
| 4017 | 제105회 의회운영위원회 (`C101`) | provisional | `N` | provisional / 변경 없음 |
| 4018 | 제106회 본회의 (`A010`) | provisional | `N` | provisional / 변경 없음 |
| 4019 | 제106회 본회의 (`A010`) | provisional | `N` | provisional / 변경 없음 |
| 4020 | 제106회 농업정책위원회 (`C501`) | provisional | `N` | provisional / 변경 없음 |
| 4021 | 제106회 농업정책위원회 (`C501`) | provisional | `N` | provisional / 변경 없음 |
| 4022 | 제106회 복지교육위원회 (`C403`) | provisional | `N` | provisional / 변경 없음 |

공식 회의록 상세 URL 형식: `https://councilrec.cheongju.go.kr/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn=<ID>`.

모든 ID는 **공식 마지막 회의록 노드** (`var12`)와 공개상태 (`var09`)가 함께 확인됐으므로 단순히 임시본의 원문 내용이 동일하다는 간접 추정이 아니다.

## 3. 3단계 검증 증거

| 공식 서버 조회 단계 | 요청 | 결과 원장 | 실행 증명 |
|---|---:|---|---|
| 최상위 대수 루트 → 제4대 직속 회기 | 2 | `reports/official-term4-branch-discovery-20261102.json` | https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41391542744 |
| 제105·106회 위원회 목록 | 2 | `reports/official-term4-target-sessions-20261102.json` | https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41391710745 |
| 제105·106회 4개 대상 위원회와 임시 6건의 `var09` 대조 | 4 | `reports/official-six-provisional-status-20261102.json` | https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41391894216 |
| 공식 조회 원장 → 원본 상태 비교, 실제 데이터가 변경되었을 때만 검토 후보로 분리 | HTTP 0 | `reports/official-six-provisional-change-candidates-20261102.json` | https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41392066334 |

세 번째 작업의 공식 대상 위원회에는 원래 저장된 회의록 ID 외 새로 등장한 ID가 관찰되지 않았다. **하지만 이는 4개 위원회에 한정된 것이며 전체 최근 회의록 신규 여부 판정이 아니다.**

## 4. 판정과 안전처리 정책

- 현재 공식의 `var09=N`이므로 임시 6건을 유지한다. **정식본 승격·원문 덮어쓰기·재수집 없음.**
- 순수 오프라인 판정 스크립트 `scripts/evaluate_provisional_official_changes.py`: 6건 모두 같은 상태면 `NO_CONFIRMED_STATUS_CHANGE_IN_SIX_PROVISIONAL_SOURCES`, 검증된 변동이 있으면 `LIVE_STATUS_CHANGE_CANDIDATES_REQUIRING_BODY_VERIFICATION`.
- 별도 합성 단위시험에서 **가상의 `4019: N→Y`**를 주입하면 `review_candidates` 1건만 생성하고, `auto_apply=false`, 후속 공식 본문 재조회 및 불변 이력화 필요로 판정한다. 실제 `4019`가 정식으로 바뀌었다는 의미는 **전혀 아님**.
- 공식 ID 누락이나 알 수 없는 상태값은 상태 추정/삭제로 연결하지 않고 `unverified`로 격리한다.
- 실제 서비스에서 전체 자동 증분을 가동하려면 **정식 전체 공식 목록 교차조회/일관성 QA 및 추가 운영 승인**이 필요하다.
- 저장된 회의록 **2,339건** 무결성 QA 통과, 원본/인덱스/분석기 수정 **0건**, `main` 및 독립 `cheongju-council-minutes` 저장소 불변.

## 5. 후속 우선순위

1. 동일한 macOS/TLS 조건에서 **현재 대수별 회기 트리의 제한된 신규 목록 조회**와 기존 전체 목록 대비 신규 ID 후보 비교; 초기에는 공식 전체 원문 수집이나 운영원본 갱신을 하지 않는다.
2. 공식 목록에 새로운 상태/내용 변경 후보가 발견되면 격리된 복사본에서 원본 바이트·본문 SHA·이력·저널 복구를 검증한 후 승인 단계로 넘긴다.
3. 정기 자동수집을 켜는 것은 **별도 운영 승인**에 속하며 이번 읽기전용 검증 성공으로 자동 활성화하지 않는다.

**운영 판정: `SIX_LIVE_PROVISIONAL_STATUSES_VERIFIED_NO_CHANGES`; 실운영 자동 수집 잠금 유지.**
