# cheongju-council-archive_total

청주시의회 공식자료 자동수집·보존·검증·데이터 처리 저장소입니다.

- 실제 수집 코드와 원장: [`feature/archive-foundation`](https://github.com/wildkim11/cheongju-council-archive_total/tree/feature/archive-foundation)
- 운영 설명: [자동수집 구조와 제한](https://github.com/wildkim11/cheongju-council-archive_total/blob/feature/archive-foundation/docs/AUTOMATIC_COLLECTION.md)
- 실행 결과: [GitHub Actions](https://github.com/wildkim11/cheongju-council-archive_total/actions/workflows/automatic-collection.yml)

`main`의 실행 진입점이 매일 오전 6시(한국시간)에 전체 자료군을 수집합니다. 매시간 가벼운 실패 상태 확인을 하고, 정상 자료군은 공식 사이트에 재접속하지 않습니다. 실패한 자료군만 하루 최대 3회 추가 재시도합니다. 실제 작업은 개발 브랜치의 원장을 사용하며 회의록·의안·의정활동·의원명부·위원회/연구단체·보도자료·문서첨부를 수집합니다. 검증된 후보만 원장에 반영하며 실패·재시도 상태도 기록합니다.

운영 완료 여부는 각 자료군의 실제 실행 기록으로 확인합니다. 일정 설정이나 코드 검사 통과만으로 전 자료 수집 완료를 뜻하지 않습니다. HTML은 이 저장소에서 처리한 자료를 받는 후속 열람·배포 도구이며 현재 작업의 우선 대상은 저장소 자동수집입니다.

## 원문 기반 가공

저장된 회의록의 발언·문단 좌표, 인물 연결 근거와 공통 활동역할 원장을 GitHub에서 생성·검증합니다. 공식 사이트를 추가로 조회하지 않는 독립 가공 작업이며, 수집 후보 반영 시에도 같은 가공 검증을 수행합니다.

- [가공 규칙과 한계](https://github.com/wildkim11/cheongju-council-archive_total/blob/feature/archive-foundation/docs/MEETING_PROCESSING.md)
- [최신 가공 검증 결과](https://github.com/wildkim11/cheongju-council-archive_total/blob/feature/archive-foundation/reports/processing-qa-latest.json)
- [가공 작업 실행](https://github.com/wildkim11/cheongju-council-archive_total/actions/workflows/process-archived-records.yml)

발언 구간을 질의·답변·성과로 자동 판정한 것은 아닙니다. 분석 분류와 남은 근거 보완은 후속 단계입니다.
