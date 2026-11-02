# 회의록 동일 ID 원본 버전 보존 및 강제 종료 복구 격리검증 (2026-11-02)

## 결론 — 오프라인 증분 검증 통과, 운영수집은 잠금 유지

기존 원본 **2,339건을 한 건도 수정하지 않고**, 동일 공식 회의록 ID의 공개상태 및 원문 수정 전후 양쪽을 함께 보존하는 **원문 버전 원장**, 재시작 가능한 **디스크 저널**, **SIGKILL 강제 종료 복구** 코드를 개발 브랜치에서 구현하고 검증했다.

단, 이는 **GitHub에 보관된 자료와 임시 복사본**에 대한 검증이다. 청주시의회 실시간 서버를 대상으로 한 정기 증분수집은 실시하지 않았으며, `main`에 반영하거나 운영 잠금을 해제하지 않았다.

## 1. 개선 기능과 실제 검증

| 테스트 및 기능 | 격리시험 결과 | 확인 범위 |
|---|---|---|
| 동일 ID의 `provisional → published` | PASS | 이전 Markdown 파일의 원래 바이트와 공개상태를 저장하고 최신본의 새 헤더·상태를 동기화 |
| 동일 ID 공식 본문 개정 | PASS | 이전 원문의 SHA-256 및 정확한 원래 파일 내용을 `_revisions` 경로에 불변 보존 |
| 세 차례 연속 버전 전환 및 본문 복귀 | PASS | 공개상태 전환·본문 수정·원문으로 복귀 시 전이 3건과 이전 원본 전부 보존 |
| 과거 원본 해시 및 이력 검산 | PASS | `audit_stage_c.py`가 이력 원장·원본 SHA·이전/다음 인덱스 연계를 검증 |
| 파일별 적용 중 일반 예외 | PASS | 저장 전 모든 파일의 백업과 신규 내용 확인 후 반영; 복사 실패 시 변경 전 바이트 전체 복구 |
| 별도 프로세스의 **SIGKILL** | PASS | (1) 저널 준비 직후, (2) 파일 일부 반영 직후, (3) 커밋 표식 기록 직후를 각각 강제 종료, 재시작 후 **롤백 또는 커밋 확정** |
| 손상된 백업으로 복구 시도 | PASS | 잘못된 백업을 사용해 자료를 덮어쓰지 않고 검증 오류로 중단 |
| 동시 수집기 경쟁 | PASS | 동일 임시 저장소의 `fcntl.flock` 비차단 lock이 두 번째 실행을 거부 |
| 악성 경로/상대경로 이탈 | PASS | 저널 경로 검증에서 절대경로·`..` 등 위험 경로 차단 |
| **실제 보존 자료 2,339건 전체 복사본** | PASS | 가상 회의록 1건만 추가, 기존 2,339건의 원본 해시 불변, 새 2,340행의 Stage C 인덱스/원문/분석기 해시 전수 검증 |
| 실제 개발 저장소 기본 수집명령 | **계속 차단** | 실제 ROOT에서 `full`·`incremental` 모두 공식 서버 접속 이전에 `LIVE_ARCHIVE_INCREMENTAL_SYNC_DISABLED` 예외 |

### 동일 ID 개정본의 보관 방식

현행 파일 `archive/meetings/cheongju_integrated/term-N/YYYY/minutes-XXXX.md`는 **현재 정식 상태**를 유지한다. 내용이나 발행 상태가 달라져 이전 MD가 교체되기 전 다음 자료를 함께 저장한다.

- 이전 MD의 정확한 원시 바이트: `archive/meetings/cheongju_integrated/_revisions/minutes-XXXX/<이전_파일_SHA256>.md`.
- 이력 원장: `indexes/integrated/meeting_revisions.json`.
- 원장 기록은 이전·다음 원천 인덱스 스냅샷, 원래/새로운 SHA-256, 이전 경로, 변경 필드, 기록 시각, 소스 ID를 모두 포함한다.
- 같은 원문 내용으로 되돌아오는 경우에도 새 전이 기록을 남기고 기존 해시 파일은 그대로 재사용한다. 공식 회의록의 회기/대수/파일 이름과 분리된 `_revisions` 경로는 일반 회의록 개수에 중복 반영되지 않는다.
- **서로 다른 source ID를 가진 provisional → published 대체**는 기존 `meeting_history.json`과 `superseded` 관계를 사용한다. **같은 ID의 공개상태·본문 개정**은 별도 `meeting_revisions.json`에서 관리한다.

### 저널 트랜잭션과 재시작 복구

`scripts/sync_transaction.py`는 임시 staging에 최신 `archive/indexes/reports/exports` 전체를 검증 완료한 뒤, 실제 변경된 파일들의 **이전 바이트·다음 바이트·SHA**를 먼저 저널 `.integrated-sync-journal`에 기록한다.

각 대상 파일은 임시파일 작성·fsync·`os.replace`로 적용한다. 적용 도중 실패하거나 프로세스가 SIGKILL을 당했다면 **미완료 저널은 이전 스냅샷으로 롤백**, 적용이 끝나 커밋 마커가 기록됐다면 **다음 스냅샷의 SHA가 정확한지 확인하고 확정**한다. 재시작 복구는 `recover_pending`이 공식 서버 요청에 앞서 실행된다.

정상적으로 해결된 저널은 **원자적으로 `.integrated-sync-resolved-* ` 이름으로 이동한 다음 삭제**하므로, 정리 도중 강제 종료되더라도 활성 저널의 불완전 삭제로 복구가 막힐 위험을 줄인다. 복구가 미완료된 저널이나 원본 SHA에 문제가 있으면 조용히 무시하지 않고 차단한다.

## 2. 기존 2,339건 전체 복사본 테스트

2026-11-02 GitHub Actions 실행:
https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41375525361 — **PASS**

- 초기 실제 저장자료 **2,339건** 원본/인덱스/분석기 무결성 검사: **PASS**.
- 임시 복사본에 가상 신규 회의록 1건을 추가하고 기존 **6건 provisional**은 저장된 원본에서 추출한 내용으로만 재확인. **네트워크 요청 0회**.
- 가상 인덱스 **2,340건**, 전체 파일 2,340건의 원문/해시 검사 **PASS**, 분석기 회의록 JSONL도 2,340행 일치.
- 원래 2,339건 전부의 SHA-256 **동일**.
- 가상 신규 회의록은 공식 아카이브/기존 브랜치에 추가하지 않았다.

## 3. 테스트·소스 및 CI

- `scripts/collect_integrated_minutes.py`: 동일 ID 이력 생성·하드 잠금·수집기 통합.
- `scripts/sync_transaction.py`: 디스크 저널, fsync·atomic replace, 복구·동시 실행 차단.
- `scripts/audit_stage_c.py`: 버전별 원본 SHA, 원장 연결 관계의 신규 검사.
- `scripts/audit_incremental_sync_isolation.py`: 신규·전환·개정·복귀·일반 오류의 임시 HTTP mock.
- `tests/test_sync_transaction_crash.py`: 실제 프로세스 SIGKILL / 손상 백업 / 락 충돌 / 경로 검증.
- `tests/test_incremental_sync_isolation.py` 및 `tests/test_integrated_minutes.py`: 증분회귀 테스트.
- 기존 2,339건 전체 검증: `scripts/rehearse_incremental_full_snapshot.py`.
- 전체 테스트 및 Stage C 무결성 실행: https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41375340219 — **PASS (당시 122개 테스트, 이후 SIGKILL로 시험 강화)**.
- SIGKILL 강화 이후 전체 회귀 성공: https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41375676225.

## 4. 아직 해제할 수 없는 운영 조건

1. **공식 서버 실시간 증분수집은 아직 미검증**. 서버 응답 지연 및 연도/대수 트리 실시간 접속 실패 이력이 있어 소량·읽기전용 접속 QA 후 별도 승인 필요.
2. **같은 ID의 날짜/대수 변경으로 파일 경로가 달라지는 경우는 차단**. 원본을 `_revisions`로 보존한 뒤 과거 정식 경로를 안전하게 정리하는 마이그레이션은 미구현이며 `SAME_ID_PATH_CHANGE_REQUIRES_VERSIONED_MIGRATION`으로 중단한다.
3. **실제 전원 차단·파일시스템 손상·네트워크 파일시스템·비협조적 외부 프로세스 동시 쓰기**에 대한 물리 환경 검증은 실시하지 않았다. 검증한 것은 POSIX 로컬 파일시스템과 SIGKILL 및 일반 프로세스 예외의 복구다. 복구용 저널의 디스크 영속성은 `fsync`·rename 규칙에 따라 설계했지만 하드웨어 전원차단을 직접 재현했다고 주장하지 않는다.
4. 운영 승인·`main` 병합·자동 스케줄은 **아직 보류**. 현재 코드의 실제 프로젝트 ROOT 수집 하드 잠금을 유지한다.
5. `.integrated-sync-draft-*` 또는 `.integrated-sync-resolved-*` 잔여 디렉터리가 강제 종료 시 남을 수 있다. 정식 원본과 분리된 점검 대상이며 검증 없이 임의 삭제하지 않는다.

## 5. 인수인계 결론

**동일 ID 공개상태/본문 원본 보존, SIGKILL 시 재시작 복구, 기존 2,339건 전체 복사본의 신규 1건 추가 시험을 통과했다.** 운영 활성화 자체는 별도 심사이며 사용자가 승인하기 전 정기 수집이나 프로덕션 원본 변경을 하지 않는다.

원칙: 아카이브는 **출처·원문·변경 이력**을 보존한다. 개인 의원 점수·의안 평가·순위는 별도 분석기로 넘기되 본 원천 수집기에서는 생성하지 않는다.
