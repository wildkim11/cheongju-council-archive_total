# Stage A 인물 원천 기록 434 → 435 차이 규명 (2026-11-02)

## 결론
**최신 분석기 export의 인물 기록 435건/재임이력 435건은 맞다.** 초기 Stage A의 434건과 차이나는 정확히 1건은 **제4대 통합 청주시의회 공식 과거 명부에만 남은 최영중 의원 기록**이다. 해당 원천 기록의 프로필 코드 \`mcode=4200\`이다.

| 원천 범위 | 인물 기록 | 재임이력 |
|---|---:|---:|
| 현직 제4대 의원 명부 | 44 | 44 |
| 통합 청주시의회 제1~3대 | 123 | 123 |
| 통합 전 청주시의회 | 187 | 187 |
| 통합 전 청원군의회 | 80 | 80 |
| **최초 Stage A 기준 합계** | **434** | **434** |
| 제4대 과거 명부에만 존재하는 이력 | **1** | **1** |
| **최신 합계** | **435** | **435** |

### 1건 추가 원천
- 성명: **최영중**
- 범위: 통합 청주시의회 제4대
- 공식 프로필: https://council.cheongju.go.kr/include/memberProfile.html?daesu=4&mcode=4200
- 공식 과거 대수 명부: https://council.cheongju.go.kr/content/member/integrationCheongju.html
- 인물 원천 파일: \`archive/people/history/cheongju_integrated_term4_departed_people.json\`
- 재임이력 파일: \`archive/people/history/cheongju_integrated_term4_departed_tenures.json\`
- 보관된 시작·종료일: 2026-07-01, 2026-07-16. 이 날짜는 **아카이브의 원천 기록 값**이며, 이 보고서는 사퇴·자격상실 등의 사유를 별도로 검증하지 않는다.
- 아카이브 인물 ID: \`person-candidate-88e1f1872e64a4d5\`
- 동일 인물 자동 병합 여부: **\`candidate_unmerged\`** — 이름이 같다는 이유만으로 다른 대수·조직의 기록에 자동 통합하지 않음.
- 공식 원천사진 1장과 URL·SHA-256이 원천 파일에 기록돼 있음.

## 검증 방식
- \`scripts/audit_stage_a_people_count.py\`: 인물·재임 파일의 원천 범위별 행수, 435개 ID 고유성, 인물-재임 ID 일치, 각 수집 보고서의 행수, analyzer manifest의 \`people\`/\`tenures\` 435행을 **저장파일과 1:1 대조**한다.
- \`tests/test_stage_a_people_count.py\`: 434+1=435, 프로필 4200, 역사명부 전용 상태, 자동 병합 금지 및 원본 무수정 조건을 회귀 테스트.
- 실제 GitHub Actions 재검증: https://github.com/wildkim11/cheongju-council-archive_total/actions/runs/41367113137 — PASS, 오류 0.
- 기계 판독 가능한 JSON 검증서는 위 Actions의 \`stage-a-people-count-reconciliation\` artifact로 보존.

## 집계상 주의
**435는 ‘아카이브에서 보존하는 인물 원천 레코드 435행’이므로, 실제 서로 다른 개인 435명을 뜻하지 않는다.** 동일인이 다른 대수나 통합 전 기관에 속한 경우는 출처·신원 증빙에 따라 별도 연계해야 한다. 통합 전 청주·청원 원천도 같은 이름만으로 병합하지 않았다.

## 운영
- 이 검증에서는 인물 데이터·재임이력·사진·분석기 export를 **변경하지 않았다**.
- 후속은 동명이인·대수 간 동일인과 재임 구간이 공식 증빙으로 명확한 경우만 신원 연결 검증, 현재 아닌 의원의 과거 이력은 보존.
- \`main\` 병합과 정기 자동수집은 별도 승인 전까지 보류.
