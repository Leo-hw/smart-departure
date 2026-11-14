# T-015 리포트 — Routes API 전환

## AC 결과
- ✅ Routes API `computeRoutes` 호출로 교체 (`core/maps_service.py`)
- ✅ 이동 수단 매핑, duration 문자열 파싱, 실패 시 캐시 → 30분 추정 유지
- ✅ `python -m unittest discover -s tests`: 50개 통과 (기존 48 + 신규 2, URL 검증 테스트는 요청 본문·헤더 검증으로 교체)
- ✅ begonia 폰에서 실제 키로 이동 시간 28/47/57분 확인. 2026-11-14 인계서에 실제 일정 `estimated=False` 기록

## 달라진 점
- 요청이 GET 쿼리 → POST JSON. API 키가 URL이 아닌 헤더로 가서 로그·프록시에 남을 위험이 줄었다.
- `departure_time=now` 파라미터는 없앰: Routes API는 출발 시각을 생략하면 현재 시각 기준.

## 주의
- Routes API는 경로가 없으면 `{}`를 돌려준다 → 추정값으로 처리.
- 한국에서 Google은 자동차·도보 경로를 제공하지 않는 경우가 있다. 자동차는 기존대로 카카오가 처리한다.
