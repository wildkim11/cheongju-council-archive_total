# 2026-11-02 실제 신규 회의록 4024·4025 — 2,341건 전수 격리 증분수집 및 SIGKILL 복구 QA

## 결론

**PASS** — 공식 청주시의회 회의록 `schSn=4024,4025`의 현재 본문을 macOS에서 재조회해 과거 실시간 SHA-256과 동일함을 확인한 뒤, **기존 2,339건 전체의 바이트 동일 복사본**에만 두 건을 증분 추가했다.

격리 복사본은 **2,341건 전수 원본 SHA-256, 본문 정규화 SHA-256, 제1~4대 인덱스, 분석기 JSONL/manifest 모두 PASS**했다. 이어 별도의 원본 복사본에서 **트랜잭션 파일 2개 설치 후 SIGKILL 강제 종료**를 실행, 원복 저널이 복구하면서 **기존 2,339건 원본·인덱스·분석기 파일의 기존 바이트를 정확히 복원**함을 확인했다.

- **이 모든 성공은 임시 복사본 안에서의 성공이다.**
- 공식 실운영 저장소에 **신규 원문 4024·4025를 추가한 적 없음**. 현재 개발 브랜치의 보존 아카이브는 여전히 **2,339건**이고, `main` 및 별도 `wildkim11/cheongju-council-minutes` 저장소 불변.
- `run_sync("incremental"/"full", ROOT)` 하드 잠금 유지, 정기 수집 스케줄 OFF, 운영 활성화는 별도 승인 필요.

## 1. 공식 원문 2건 재조회 증거

기존 원본 수집기 `collect_integrated_minutes.TLS`의 검증된 TLS 설정 (`ssl.create_default_context`, TLS 최소 1.2, `set_ciphers("DEFAULT")`, 서버 인증서 검증)을 그대로 사용한 **GitHub-hosted macOS**에서 공식 상세페이지 두 건을 정확히 **1회씩** 조회했다. 재시도 0회.

| ID | 회의록 | 상태 | HTTP | 본문 SHA-256 (직전 확인 원장과 동일) |
|---|---|---|---:|---|
| 4024 | 제106회 도시건설위원회 제1호, 2026-10-14 | 임시 `N` | 200 | `818fa74efdb62b563d5ba4ce8c23a47e5c9811113e0b3e493f82fe3ee5b6545d` |
| 4025 | 제106회 의회운영위원회 제1호, 2026-10-12 | 임시 `N` | 200 | `56a6503293a26f9cec67d6170dfaa5fa93b0047cacbb5438c55fd192592f3eba` |

앞선 공식 제4대 목록 52건 조회 `reports/official-term4-new-meeting-id-discovery-20261102.json`, 공식 2026 연도별 목록의 두 신규 ID 확인 `reports/official-year2026-new-ids-presence-20261102.json`와 공식 본문 이전 해시 `reports/official-term4-new-meeting-body-check-20261102.json`가 모두 검사 전제조건으로 강제됐다. 실제 본문은 임시 COPY에만 전달됐고 **QA 보고서나 GitHub 커밋에는 전문 HTML·텍스트를 저장하지 않았다**.

## 2. 2,339→2,341 전량 복사본 검증 결과

| 검증 항목 | 결과 |
|---|---:|
| 기존 원본 총수 | **2,339** |
| 격리 복사본 현재 원본 총수 | **2,341** |
| 기존 원본 Markdown 바이트·SHA-256 불변 | **2,339/2,339** |
| 새 원본 4024·4025의 공식 본문 해시 일치 | **2/2** |
| 복사본 Markdown 파일 SHA-256 검사 | **2,341/2,341** |
| 정규화 본문 SHA-256 검사 | **2,341/2,341** |
| 1·2·3·4대 원본 수 | **663 / 771 / 855 / 52** |
| 정식 / 임시 회의록 | **2,333 / 8** |
| 분석기 `meetings.jsonl` 행수 | **2,341** |
| `manifest` 전체 분석기 export SHA 검사 | **24/24** |
| Stage C 검증 | **PASS, 오류 0, 경고 0** |
| 임시본 6건 저장본 그대로 본문 재생 | **6건** |
| 증분 수집기 mock body 요청 | 기존 임시 6 + 공식 재조회 신규 2 = **8건** |
| 원본 아카이브·`main` 변경 | **0건** |

**주의:** 격리 리허설에서 검증된 공식 실제 본문은 **두 신규 ID뿐**이다. 저장된 기존 임시 6건은 SHA-검사된 원본 Markdown 본문을 **모의 fetch 응답으로 재생**했고 공식 서버에 6건을 다시 요청했다고 주장하지 않는다. 1~3대 현재 공식 목록 및 기존 모든 회의록의 현재 본문 동일성을 검증한 것도 아니다.

## 3. 별도 복사본의 강제 종료·원복 시험

기존 원본 상태(2,339건)의 **두 번째 전체 복사본**을 준비하고, 첫 번째 리허설에서 완성된 2,341건 데이터의 신규 2개 Markdown, 인덱스, 전송 리포트, 분석기 JSONL/manifest 등 7개 파일을 트랜잭션 후보로 준비했다.

- 실제 `sync_transaction.publish_staged_snapshot` 저널을 만들고 **두 파일 설치 직후** 별도 자식 프로세스에 `SIGKILL` 주입.
- 저널이 **미완료**인 상태로 남은 것을 확인.
- `sync_transaction.recover_pending`은 `rolled_back_uncommitted` 처리.
- 추가된 두 파일이 원상복구되고 기존 **2,339건 모든 원본 SHA** 일치.
- 기존 인덱스, 분석기 `meetings.jsonl`, `manifest.json`의 기존 **정확한 바이트·SHA** 복구.
- 복구 후 Stage C 전체 무결성 `PASS`, 기존 회의록 **2,339건**.
- 네트워크 파일시스템, 물리적 전원 손실, 악의적 변조, 여러 호스트의 동시수정 시험은 **이번 범위 밖**.

두 임시 복사본은 작업 종료 시 제거했다. 별도 신규 회의록 원문 PDF/Markdown 파일을 실운영 저장소에 배포하지 않았다.

## 4. 실행·보고·코드

- 검증 Actions: https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41395286199
- 상세 기계검증 원장: `reports/official-real-two-new-2341-full-copy-rehearsal-20261102.json`
- 리허설 코드: `scripts/rehearse_real_two_new_2341_full_copy_macos.py`
- 오프라인 방어 회귀테스트: `tests/test_real_two_new_2341_isolated_rehearsal.py`
- 격리 복사본은 기존 `collect_integrated_minutes.run_sync("incremental", temp_root)`를 사용했고, `read_official_inventory`, `fetch`, `extract_minutes_body`는 명확하게 한정된 테스트 입력으로 대체했다.
- 검증 데이터는 **기존 공식 해시가 확인된 4024·4025 본문**, 공식 두 목록의 ID·상태 증빙과 기존 2,339건의 실보존 원본. 인위적 시험용 회의록을 공식 신규 원본으로 위장하지 않았다.
- 오프라인 유닛은 공식 증빙 해시 불일치, 신규 ID 무단 변경, macOS 외 실행을 차단함을 검증했다.

## 5. 다음 단계와 운영 승인 경계

이번 성공은 **정식 무인수집 가동의 핵심 기술 경로를 실증한 사례**다. 그러나 다음 사항은 운영 전에 별도 확인한다.

1. 정기 실행 주기·요청 상한·장애 재시도·지연에 따른 원문 공개상태 변화 감시 설계.
2. 기존 본문 변경, 임시→확정, 신규 ID 중복·누락이 동시에 발생하는 실제 누적 증분 시나리오의 회귀시험.
3. 변동이 감지되면 원본과 각 버전의 `content_sha256` 및 불변 이력을 보존하고, Stage C·analyzer export 원자성을 확인한다.
4. 운영 `run_sync` 잠금 해제 또는 스케줄 활성화는 **사용자 명시적 별도 승인** 뒤에만 수행. 자동 배포를 시험 성공과 동일시하지 않는다.

**최종 판정:** `PASS_TWO_REAL_NEW_SOURCE_BODIES_IN_2341_ISOLATED_COPY_AND_SIGKILL_ROLLBACK`; 운영 원본 현재 2,339건 유지.
