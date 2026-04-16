# CHANGELOG

## [미완료] Phase 1 MVP — 진행 중

### T-005 알림 채널 라우팅 완료
- `shared/config/runtime_config.py`로 설정 로더와 채널별 환경변수 검증 로직 분리
- `core/notifier.py`에 Discord webhook, Telegram, 다중 채널 라우팅과 공통 메시지 포맷 구현
- `main.py`를 실제 알림 흐름으로 연결하고, 활성 채널 기준으로 조건부 환경변수 검증 적용
- `tests/test_notifier.py`, `tests/test_runtime_config.py`를 추가하고 파이프라인 상태를 `T-006 READY`로 갱신

### T-004 출발 시각 계산 엔진 완료
- `core/departure_engine.py`에 출발 시각 계산, 이동 수단 선택, buffer 반영, alert window 판단 로직 추가
- `DepartureDecision` 구조와 `build_departure_decisions()`, `evaluate_departure_alert()` 구현
- `tests/test_departure_engine.py`로 default transport, override, alert filtering, 설정 오류 케이스 검증 추가
- 파이프라인 상태를 갱신해 다음 작업 `T-005`를 READY로 전환

### T-002, T-003 병렬 구현 완료
- `core/calendar_service.py`에 Google Calendar 서비스 계정 연동, 복수 캘린더 조회, KST 변환, `transport_override` 파싱 추가
- `core/maps_service.py`에 Google Directions API 조회, 6시간 TTL 캐시, fallback 추정값 반환 로직 추가
- `tests/test_calendar_service.py`, `tests/test_maps_service.py`로 Calendar/Maps 단위 테스트 추가
- 파이프라인 상태를 갱신해 다음 작업 `T-004`를 READY로 전환

### T-001 프로젝트 기반 세팅 완료
- Railway cron worker용 `main.py`, `Procfile`, `requirements.txt`, `.gitignore`, `README.md` 추가
- `core/`, `shared/config/`, `tests/` 기본 구조와 향후 티켓용 스텁 모듈 생성
- `settings.yaml` 로더와 환경변수 검증, `.runtime/` 초기화 로직 구현
- T-001 완료 처리 및 다음 작업(T-002, T-003) 상태를 READY로 갱신

### 프로젝트 초기 설계
- SPEC.md, CLAUDE.md, AGENTS.md, PIPELINE.md, ROADMAP.md 작성
- Phase 1 티켓 큐 구성 (T-001 ~ T-006)
