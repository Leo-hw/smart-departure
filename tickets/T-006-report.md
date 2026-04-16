# T-006-report — 중복 알림 방지 (dedup)

**완료일**: 2026-04-16  
**담당**: Codex

---

## AC 결과

| AC | 결과 | 비고 |
|----|------|------|
| `.runtime/sent_alerts.json` 기반 dedup 구현 | ✅ | 이벤트 단위 sent 기록 저장 |
| `settings.yaml`의 `schedule.dedup_ttl_minutes` 반영 | ✅ | TTL 기반 필터 및 만료 정리 반영 |
| 동일 `event_id`는 TTL 이내 재전송하지 않음 | ✅ | `event_id` 기준 dedup 적용 |
| TTL이 지난 기록은 자동으로 만료 처리 | ✅ | 필터 시 prune 후 파일에 재저장 |
| 전송 성공한 일정만 dedup 기록으로 저장 | ✅ | 최소 한 채널 성공 시 sent 기록 |
| 알림 전송 실패한 일정은 dedup에 기록하지 않음 | ✅ | 전송 후 성공 이벤트만 저장 |
| `main.py` 실행 흐름에 dedup 필터 적용 | ✅ | dedup skip count 출력 포함 |
| 단위 테스트: `tests/test_dedup.py` 작성 | ✅ | dedup, TTL 만료, 성공 기록 테스트 추가 |

---

## 원래 기획과 달라진 점

- 로컬 실행 편의를 위해 `.env` 자동 로드를 함께 추가함. 이미 export된 환경변수는 덮어쓰지 않음

---

## 발생한 에러/이슈

- `tickets/T-006.md`가 저장소에 없어 구현 전에 티켓 파일을 먼저 보강함

---

## 다음 작업자에게 전달할 주의사항

- 유지할 것: dedup은 현재 이벤트 단위이며, 채널 단위 dedup으로 바꾸지 않는 편이 MVP 흐름에 맞음
- 주의할 것: 파이프라인 완료 기준은 코드상 T-006 완료만으로 끝나지 않고 Railway 실제 알림 수신 확인까지 필요함
- 제거 예정: 없음
