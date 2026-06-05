# T-010-report — 견고성 + 놓친 알림 catch-up

**완료일**: 2026-06-05  
**담당**: Codex

---

## AC 결과

| AC | 결과 | 비고 |
|----|------|------|
| Calendar timeout 및 3회 재시도 | ✅ | 기본 timeout 10초, 환경변수로 조정 가능 |
| 실패 시 Discord 오류 알림 | ✅ | 오류 알림은 dedup 없이 매번 시도 |
| GitHub Actions runtime 상태 보존 | ✅ | 실행별 롤링 cache key 적용 |
| 일정 시작 60분 후 dedup 만료 | ✅ | sent/skipped 모두 `event_start` 저장 |
| 정시/catch-up/만료 판정 | ✅ | 준비와 출발에 서로 다른 만료 시각 적용 |
| catch-up 늦음 표기 | ✅ | 원래 예정 시각과 평가 시각 표시 |
| 다중 준비 알림 중 최신만 발송 | ✅ | 이전 단계는 `skipped`로 봉인 |
| 단위 테스트 | ✅ | 전체 37개 테스트 통과 |

## 원래 기획과 달라진 점

- 향후 T-009 다단계 준비 알림을 수용하도록 prep 시각 조회를 별도 함수로 분리함

## 발생한 에러/이슈

- timeout 구현에 필요한 `google-auth-httplib2`를 명시 의존성으로 추가함

## 다음 작업자에게 전달할 주의사항

- T-009는 `ScheduledAlert`의 catch-up 분류와 최신 준비 단계 선택 흐름을 유지해야 함
- GitHub Actions cache는 즉시 삭제 가능한 영구 저장소가 아니므로 운영상 중요 상태는 별도 저장소가 필요할 수 있음
