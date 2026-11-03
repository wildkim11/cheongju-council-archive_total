# cheongju-council-archive_total

청주시의회 공식자료 자동수집·보존·검증·데이터 처리 저장소입니다.

- 실제 수집 코드와 원장: [`feature/archive-foundation`](https://github.com/wildkim11/cheongju-council-archive_total/tree/feature/archive-foundation)
- 운영 설명: [자동수집 구조와 제한](https://github.com/wildkim11/cheongju-council-archive_total/blob/feature/archive-foundation/docs/AUTOMATIC_COLLECTION.md)
- 실행 결과: [GitHub Actions](https://github.com/wildkim11/cheongju-council-archive_total/actions/workflows/automatic-collection.yml)

`main`의 실행 진입점이 3시간 간격(매 25분)에 macOS 작업을 시작합니다. 실제 작업은 개발 브랜치의 원장을 사용하며 회의록·의안·의정활동·의원명부·위원회/연구단체·보도자료·문서첨부를 순환 수집합니다. 검증된 후보만 원장에 반영하며 실패·재시도 상태도 기록합니다.

운영 완료 여부는 각 자료군의 실제 실행 기록으로 확인합니다. 일정 설정이나 코드 검사 통과만으로 전 자료 수집 완료를 뜻하지 않습니다. HTML은 이 저장소에서 처리한 자료를 받는 후속 열람·배포 도구이며 현재 작업의 우선 대상은 저장소 자동수집입니다.
