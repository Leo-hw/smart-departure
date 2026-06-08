# CHANGELOG

## [미완료] Phase 1 MVP — 진행 중

### T-013 public 로그/캐시 안전화 구현 완료, 검증 중
- 실행 로그에서 일정명·장소·원문 event ID를 제거하고 이벤트 식별자는 8자리 해시로 출력
- 예외 및 전송 실패 로그를 오류 타입·상태 코드 수준으로 제한해 민감한 메시지와 응답 본문 제거
- Actions cache를 해시 기반 `sent_alerts.json` 단일 파일로 축소하고 기존 평문 dedup 레코드 자동 마이그레이션 추가
- 과거 Actions workflow runs 560개와 caches 35개를 삭제하고 잔존 수량 0 확인

### T-012 GHA 실행 신뢰성 구현 완료, 운영 검증 중
- GitHub Actions 예약 실행을 5분 간격 요청으로 변경하고 pip 캐시와 concurrency 가드 추가
- 출발 catch-up 만료를 `departure_catchup_minutes` 설정으로 분리하고 기본값을 45분으로 확대
- 워크플로우 구성과 준비/출발 catch-up 경계를 검증하는 단위 테스트 추가

### T-011 당일 일정 스냅샷 staleness 핫픽스 완료
- 기본 설정에서 매 실행 Google Calendar를 재조회해 당일 중간에 추가된 일정이 다음 실행에 반영되도록 수정
- 스냅샷에 `built_at`을 저장하고 선택적 `snapshot_ttl_minutes` 내에서만 재사용하도록 변경
- 스케줄 재빌드 후에도 기존 `sent_alerts.json` dedup 상태가 유지되는 회귀 테스트 추가

### T-008, T-010 병렬 구현 완료
- 자동차 이동 시 카카오 주소 검색 및 길찾기 API를 사용하고, 실패 시 기존 캐시와 30분 추정값으로 fallback
- Google Calendar 호출에 10초 timeout과 3회 재시도를 적용하고 실행 실패 시 Discord 오류 알림 추가
- 놓친 준비/출발 알림의 catch-up 판정, 늦음 표기, 다중 준비 알림 봉인 및 `skipped` dedup 기록 구현
- GitHub Actions에서 `.runtime/`을 롤링 cache로 보존하고 dedup 만료 기준을 일정 시작 60분 후로 변경

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
