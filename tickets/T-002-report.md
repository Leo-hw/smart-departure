# T-002-report — Google Calendar 연동

**완료일**: 2026-04-15  
**담당**: Codex

---

## AC 결과

| AC | 결과 | 비고 |
|----|------|------|
| `core/calendar_service.py`의 `get_upcoming_events()` 구현 | ✅ | `list_upcoming_events()` 별칭도 유지 |
| 환경변수 `GOOGLE_SERVICE_ACCOUNT_JSON`, `GOOGLE_CALENDAR_IDS` 사용 | ✅ | 서비스 계정 JSON 파싱 및 복수 캘린더 지원 |
| `GOOGLE_CALENDAR_IDS`는 쉼표 구분 복수 캘린더 지원 | ✅ | 공백 제거 후 다중 ID 처리 |
| 반환 항목: `summary`, `location`, `start_time` (datetime, KST) | ✅ | `CalendarEvent` dataclass로 정규화 |
| `location`이 비어있는 일정은 결과에서 제외 | ✅ | 빈 문자열/공백 location 제외 |
| 현재 시각 기준 향후 `lookahead_hours` 이내 일정만 반환 | ✅ | API 조회 범위와 로컬 필터 둘 다 적용 |
| 단위 테스트: `tests/test_calendar_service.py` 작성 | ✅ | mock 기반으로 필터링, KST 변환, override 파싱 검증 |

---

## 원래 기획과 달라진 점

- 종일 일정은 `start_time`이 `dateTime`이 아니므로 반환 대상에서 제외함

---

## 발생한 에러/이슈

- 없음

---

## 다음 작업자에게 전달할 주의사항

- 유지할 것: `transport_override` 허용값은 `transit`, `driving`, `walking`만 처리해야 함
- 주의할 것: Google Calendar 의존성은 함수 내부에서 lazy import 하므로 테스트 환경에서도 import 단계가 깨지지 않음
- 제거 예정: 없음
