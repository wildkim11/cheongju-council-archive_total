# 회의록 본문 소비 모듈

- `meeting_text_reader.js`: 고정 커밋의 대수별 gzip을 SHA/행수/회의록 출처·본문 해시로 검증한다. 전체 해제 자료를 보관하지 않고 선택 회의록만 반환한다.
- `meeting_text_updates.js`: GitHub에서 확정한 새 커밋의 catalog와 인덱스를 검증한다. 기존 ID 삭제나 대수·일자·공식URL 변경, 이전/분기된 버전은 자동 수용하지 않는다.
- `meeting_text_update_ui.js`: 기존 Stage47 앱 IIFE 내부의 본문 확장 뒤에 삽입한다. 별도 전역 페이지로 실행하는 파일이 아니다. 기존 release/state/render 및 본문 확장의 textRegistry/meetings47/bodyCache를 사용한다.

자료 확인은 사용자 버튼으로 실행한다. GitHub branch SHA를 먼저 고정한 다음 compare와 해당 커밋의 catalog/index를 읽는다. 확인과 적용을 분리하고, 새 HTML 저장 요청 준비에 실패하면 현 자료를 유지한다. 본문 로딩 중에는 갱신 적용을 막는다. 개인판에는 전체 회의목록 갱신을 적용하지 않는다.

본문 자료 버전은 의안·활동 분석자료 버전과 별도로 표시한다. SHA 검증은 자료 정합성 확인이며 발행자 전자서명이 아니다. 실제 브라우저의 CORS·파일선택·다운로드와 모바일 배치는 별도 검수가 필요하다.

Python unittest discovery에서 Node 기반 reader/update 회귀시험을 실행한다. 실제 Stage47 HTML 조립 및 DOM 시험은 프로젝트의 회의록 HTML 연결 재현 묶음에서 수행한다.

## 자료별 버전 표시와 HTML 동기화

`data_versions_ui.js`는 기존 Stage47 앱 IIFE의 기초집계 갱신 확장 뒤에 삽입한다.
회의록·기초집계·기존 의안/활동/관계망 묶음의 기준 버전을 구분하며, 기존 대조
진단을 현재 수집 상태로 오인하지 않도록 표시한다. 자료 배정이나 판정을 바꾸지 않는다.

```sh
python scripts/install_html_data_versions.py source.html prepared.html
```

설치기는 기존 JSON 데이터와 시작 지점을 유지하고 명시적 마커 사이만 재설치한다.
알 수 없는 시작 구조나 중복 마커는 추측해 수정하지 않는다.

수동 통합 검증: `tests/manual_stage47_sync_dom.cjs`에 검토 작업 폴더와 jsdom 경로를
인자로 준다. 작업 폴더는 `prepared/`의 마스터·의원 HTML, `assets/branch.json`,
구 버전별 compare 결과, 고정 커밋의 catalog/index/집계 묶음과 term-4 본문 묶음을
포함한다. jsdom 26.1.0을 사용한다. JSON 메타데이터는 GitHub에서 확인한 응답의
필요 필드이며 gzip/index는 해당 커밋에서 받은 원본 바이트다. 실행은 `updated/`에
저장 Blob의 HTML을 기록하고 다시 열어 검사한다. 이는 네이티브 브라우저의
CORS·다운로드 완료·실제 모바일 배치 검증을 대체하지 않는다.
