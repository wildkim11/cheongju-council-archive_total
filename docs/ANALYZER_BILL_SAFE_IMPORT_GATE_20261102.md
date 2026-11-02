# 의정분석기 의원발의 입력 안전 게이트 (2026-11-02)

## 목적·검증 범위

기관형 의안의 인명 표시 44행이 실제 의원 개인발의 실적으로 혼입되지 않도록 원천 아카이브에서 분석기로 넘어가는 입력 파일을 **읽기 전용으로 검증**한다.

- 원본 관계: 11,421행 (증거 및 호환성 보존)
- 의원발의 분석용: 11,377행 (안전 뷰)
- 기관형 관계: 44행, 5건 (역할 미확정 격리)
- 의원발의자 전원 명단 미확인: 7건 (1308, 1458, 2083, 2258, 2364, 2637, 3255)

이 수치는 2026-11-02 현재 보존 스냅샷 기준이며, 증분수집이나 새로운 발의 증빙의 반영 완료를 의미하지 않는다.

## 추가한 파일

- scripts/verify_analyzer_bill_import.py
- tests/test_verify_analyzer_bill_import.py
- .github/workflows/audit-analyzer-bill-safe-import.yml

## 안전 규칙

1. exports/analyzer/manifest.json의 스키마 및 'personal_proposer_statistics_dataset'이 정확히 'bill_proposers_member_only'인지 확인한다. 기존 'bill_proposers'로 대체할 수 없다.
2. bills, bill_proposers, bill_proposers_member_only, bill_proposers_institutional_type_quarantine 4개 데이터셋의 파일 경로, 행수, SHA-256을 검사한다.
3. 의원발의 판단은 의안의 proposer_type_list, proposer_type 두 원천 필드를 사용한다. 서로 모순이면 기관형/미확인 격리 쪽으로 판정한다.
4. 원본 관계를 같은 순서·같은 필드 값으로 안전뷰와 격리뷰로 분리한 결과가 저장된 뷰와 **완전히 일치해야만** 반환한다. 누락, 중복, 순서 변경, 기관형 인명 유입 모두 오류 처리한다.
5. 검증 실패 시 'UnsafeBillImport' 오류로 중단한다. 안전뷰가 없을 때 원본 관계를 자동으로 가져오는 동작은 없다.
6. 실제 의원별 발의 통계에서는 위 모듈의 'load_verified_personal_proposers' 반환값 또는 이와 동등한 검증 절차를 거친 11,377행 안전 뷰만 사용해야 한다.
7. 출처 근거 없는 7건의 공동발의자 이름을 합성하지 않는다. 안전뷰 사용이 곧 누락 7건의 명단 완성 또는 외부 분석기 연결 성공이라는 뜻은 아니다.

## 검증·운영

개발 브랜치에서 아래 명령을 실행하면 원본 파일을 수정하지 않고 검사한다.

    python -m unittest discover -s tests -p test_verify_analyzer_bill_import.py -v
    python scripts/verify_analyzer_bill_import.py

CI는 이 세 파일의 푸시 또는 수동 실행 시에만 작동하는 **읽기 전용 검사**다. 정기 수집기와 별개이며 수집·인덱스 갱신·분석기 서버 배포를 하지 않는다.

외부 구버전 의정분석기 실행본은 이 저장소에서 발견되지 않아, 실제 소비 코드가 현재 어느 JSONL 파일을 참조하는지 **아직 검증하지 못했다**. 향후 해당 프로젝트의 저장소/실행본을 확인하여 위 안전 로더에 실제로 연결하고, 의원별 집계 결과가 기관형 5건을 포함하지 않는지 통합 테스트해야 한다.

## 별도 원천자료 과제

- 의회사무국의 접수원안·발의 서명부를 통한 7건 전체 명단 확보 및 5건 인명관계 역할 확인은 여전히 미해결이다.
- 자료제출요구 초안: docs/BILL_SOURCE_RECORDS_REQUEST_20261102.md (미발송).
- 기존 원시 자료 및 기관형 관계 원본은 삭제·수정 금지.
- 2,342건은 격리 리허설 결과이며 정식 회의록 아카이브 2,339건과 구분.
- main 미병합, 무인 정기수집 및 운영 반영 비활성 상태 유지.
