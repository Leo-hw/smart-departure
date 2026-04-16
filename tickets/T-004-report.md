# T-004-report — 출발 시각 계산 + 알림 판단 엔진

**완료일**: 2026-04-16  
**담당**: Codex

---

## AC 결과

| AC | 결과 | 비고 |
|----|------|------|
| `core/departure_engine.py`의 `evaluate_departure_alert()` 구현 | ✅ | alert 대상만 필터링해 반환 |
| 출발 시각 = `event.start_time - travel_time - buffer_minutes` | ✅ | `DepartureDecision.departure_time`에 반영 |
| 이동 수단 우선순위: `event.transport_override` > `settings.yaml`의 `default_transport` | ✅ | 이벤트 override가 있으면 우선 적용 |
| `settings.yaml`의 `transport.<mode>.buffer_minutes` 반영 | ✅ | mode별 buffer 계산 반영 |
| `settings.yaml`의 `schedule.alert_window_minutes` 반영 | ✅ | `departure_time ± window` 비교 구현 |
| 반환 결과에 `should_alert`, `departure_time`, `travel_minutes`, `buffer_minutes` 포함 | ✅ | `DepartureDecision` dataclass 제공 |
| 이동 시간이 추정값(`is_estimated=True`)이어도 계산/판단은 계속 수행 | ✅ | 추정 여부는 그대로 보존하고 계산 계속 수행 |
| 단위 테스트: `tests/test_departure_engine.py` 작성 | ✅ | 5개 케이스 검증 |

---

## 원래 기획과 달라진 점

- 엔진 내부 계산 결과 전체를 재사용할 수 있도록 `build_departure_decisions()`를 추가하고, `evaluate_departure_alert()`는 그 결과 중 알림 대상만 반환하도록 구성함

---

## 발생한 에러/이슈

- `tickets/T-004.md`가 저장소에 없어 구현 전에 티켓 파일을 먼저 보강함

---

## 다음 작업자에게 전달할 주의사항

- 유지할 것: dedup 판단은 아직 넣지 않았고, T-006 범위까지 엔진에서 중복 차단 로직을 섞지 않아야 함
- 주의할 것: `load_settings()`를 통해 `HOME_ADDRESS` 오버라이드가 반영된 설정을 사용하므로 직접 환경변수를 다시 읽지 않도록 유지하는 편이 안전함
- 제거 예정: 없음
