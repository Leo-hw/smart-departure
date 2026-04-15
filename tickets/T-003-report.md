# T-003-report — Google Maps 대중교통 이동 시간 계산

**완료일**: 2026-04-15  
**담당**: Codex

---

## AC 결과

| AC | 결과 | 비고 |
|----|------|------|
| `core/maps_service.py`의 `get_travel_time(origin, destination, transport_mode)` 구현 | ✅ | `TravelResult` dataclass 포함 |
| `transport_mode="transit"` 시 Google Maps Directions API 사용 | ✅ | MVP 범위에서 Google provider 유지 |
| 반환값: 이동 시간(분, int) | ✅ | `duration_minutes`로 분 단위 반환 |
| API 실패 시 fallback: `.runtime/travel_cache.json` 캐시 값 사용 | ✅ | TTL 6시간 캐시 조회 구현 |
| 캐시도 없으면 기본값 30분 반환 + `is_estimated=True` 플래그 | ✅ | 추정값 fallback 적용 |
| 캐시 저장: 동일 조합 결과 저장, TTL 6시간 | ✅ | `origin|destination|transport_mode` 키 사용 |
| 단위 테스트: `tests/test_maps_service.py` 작성 | ✅ | API 성공, 캐시 fallback, 기본값 fallback 검증 |

---

## 원래 기획과 달라진 점

- HTTP 호출은 `requests` 대신 표준 라이브러리 `urllib`로 구현했음. 런타임 동작은 동일함

---

## 발생한 에러/이슈

- 없음

---

## 다음 작업자에게 전달할 주의사항

- 유지할 것: `get_travel_time()`는 반드시 provider 선택 구조를 유지해야 함
- 주의할 것: `provider` 값은 현재 `google`이며, `driving -> kakao` 전환은 T-007 범위임
- 제거 예정: 없음
