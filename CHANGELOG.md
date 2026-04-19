# CHANGELOG

## [미완료] Phase 1 MVP — 진행 중

### T-007 스케줄링 재설계 완료
- `core/scheduler.py`에 당일 계획 생성, `.runtime/schedule_today.json` 저장, due alert 추출 로직 추가
- `main.py`를 스케줄 계획 재사용 구조로 전환하고 prep/departure 알림 흐름을 연결
- alert 단위 dedup 키를 지원하도록 `core/dedup.py`를 확장
- Oracle crontab 가이드와 GitHub Actions 워크플로우를 추가하고 README 배포 가이드를 갱신

### T-006 dedup 완료
- `core/dedup.py`에 `.runtime/sent_alerts.json` 기반 TTL dedup 필터와 성공 전송 기록 저장 로직 추가
- `main.py` 실행 흐름에 dedup 선필터와 성공 전송 후 sent 기록 반영 로직 추가
- `.env` 자동 로드를 추가해 로컬 환경변수 관리 흐름을 보강
- `tests/test_dedup.py`, `tests/test_runtime_env_loading.py`를 추가해 dedup TTL과 `.env` 로딩 동작 검증

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
