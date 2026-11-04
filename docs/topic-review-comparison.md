# 주제분류 검토 대조

## 현재 단계

2026-11-04: AI 초안 40건·원문 근거 66구간 다음 단계로 검토 입력 검증·대조 기능 구현. 전체 Python 테스트 399개 통과. 실제 사람 검토 0건, 정확도·관심사 점수 산출 없음. 검토 화면은 아직 구현 전.

## 실행

```sh
python scripts/compare_topic_reviews.py
python scripts/compare_topic_reviews.py --reviews /path/to/human_reviews.jsonl
```

첫 명령은 입력 없는 상태를 명시적으로 기록한다. 두 번째 명령은 원문·코드북·검토 과제·AI 초안의 현재 스냅숏을 확인하고 제출된 검토를 대조한다. 보고서: `reports/topic-review-comparison-latest.json`. 자동 수집 또는 기존 주제 초안 보고서를 사람 검토 결과로 덮어쓰지 않는다. 현재 자동 실행에는 연결하지 않았으며 운영자가 명시적으로 실행한다.

## 입력 규칙

기존 `exports/topic-review/development_sample.jsonl.gz`의 해당 과제 필드를 유지하고 다음 필드를 사람이 작성한다.

- `case_id`, `activity_id`, `member_text_sha256`, `codebook_sha256`: 현재 과제의 값을 그대로 유지.
- `status`: `completed`, `review_origin`: `human`, `reviewer_id`: 공백 없는 식별자. 공개 저장소에는 개인 연락처·이메일 대신 가명 식별자 권장.
- `full_text_read`: 본문 전체를 읽은 경우에만 `true`.
- `review_method`: AI 초안을 보지 않고 판단한 `independent`, 또는 초안을 참고한 `ai_assisted`.
- `reviewed_at`: 검토 일시.
- `decision`: `coded`, `no_policy`, `ambiguous`; 정책 주제가 있으면 `coded`와 `topic_ids`를 작성.
- `rationale`: 판단 이유. `evidence_spans`: 각 주제마다 원문 문자 시작·끝 위치와 정확히 일치하는 인용문.
- `change_reason`: AI와 주제 집합 또는 판단이 다르면 수정 이유 필수.

원문·코드북·과제 불일치, 부정확한 인용, 미완료/자동 검토 선언, 같은 검토자·과제의 중복 제출은 보류한다. 중복은 첫 제출을 임의 채택하지 않고 모두 보류한다. 수정본은 명시적으로 정리한 제출 파일로 재실행하며 원본 제출 이력은 별도로 보존해야 한다.

## 해석의 한계

사람이라는 선언과 독립 검토 여부는 입력자의 자기보고이며 신원을 인증하거나 실제 독립성을 입증하는 기능이 아니다. AI와 사람의 일치는 정확도가 아니다. 여러 사람이 제출한 결과는 개별 비교로 남고 합의·다수결·최종 분류로 자동 승격하지 않는다. 골드 정답·학술 신뢰도·의원 점수 산출은 하지 않는다. 보류가 있으면 보고서의 `held`를 함께 확인한다.

## 다음 단계

- [x] AI 초안 40건 근거 보존
- [x] 사람 검토 입력 검증, 추가·삭제 주제와 수정 이유 대조
- [x] 원문·코드북·중복·AI 오인 방지 회귀검증
- [ ] 원문과 코드북을 보고 입력·저장할 수 있는 검토 화면
- [ ] 독립 검토 실제 확보 및 분류 경계 수정
- [ ] 별도 합의 절차와 평가 설계

## 공개 소개문 운영

사용자 요청에 따라 main 및 feature/archive-foundation의 README는 저장소명만 유지한다. About description은 null, homepage null, topics 빈 배열로 확인했다. 소개문을 자동 생성·추가하지 않는다. 공개 저장소의 파일과 과거 커밋은 여전히 검색될 수 있으며 설명 삭제는 검색 차단이 아니다.
