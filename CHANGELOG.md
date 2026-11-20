# CHANGELOG

## 2026-11-20 T-013 공개 운영 검증 완료

- 사용자 제공 Discord 수신 기록 2건을 폰 전송 로그와 대조하고 공개 저장소의 로그·캐시 검증 결과를 반영해 T-013 완료 처리

## 2026-11-17 T-013 공개 운영 재검증 (진행 중)

- 공개 저장소의 Actions 캐시 0개, 과거 purge 이후 생성된 실행 기록만 존재함을 확인
- 폰 서비스의 알림 전송 성공 로그 2건과 민감정보 패턴 0건, 전체 테스트 68개 통과를 확인; Discord 실제 수신 확인은 대기

## 2026-11-15 T-018 대중교통 출발 시각 안정화

- 동일 일정·시각·장소·이동수단의 정상 Maps API 이동 시간은 증가하는 쪽만 반영해 출발 시각이 뒤로 밀리지 않게 함
- 캐시·추정값은 기준을 높이지 않고, 일정 시각·장소 변경 시 기준을 재설정
- 급증으로 계산된 출발 시각이 이미 45분 넘게 지났어도 일정 시작 전에는 긴급 출발 알림 후보로 유지
- 틱 사이 기준을 `schedule_today.json` 스냅샷 버전 3에 보존하고 68개 단위 테스트 통과
- 폰 자동 pull·활성 타이머·폰 전체 테스트 68개·마지막 서비스 실행 성공을 확인 (실알림 정책 효과는 추후 관찰)

## 2026-11-15 T-019 캘린더별 접근 실패 격리

- 캘린더별 403/404 접근 실패 시 해당 캘린더만 건너뛰고 나머지 일정 조회를 지속
- 모든 캘린더 접근 실패 또는 인증·할당량·네트워크 오류는 전체 실행 실패로 처리
- 경고 로그를 캘린더 순번과 HTTP 상태로 제한하고 63개 단위 테스트 통과

## 2026-11-15 T-009 occasion별 준비 단계 알림

- 다섯 준비 프로필과 제목 키워드·캘린더 설명의 `occasion:` 오버라이드 추가
- 준비 단계별 알림 시각·메시지·안정 dedup 키 적용; 출발 알림은 기존 형식 유지
- `schedule_today.json`에 occasion·단계·실제 alert key 저장, 구 스냅샷 버전 분리
- PyYAML 없는 환경의 간이 설정 파서에 단계 목록 지원, 59개 단위 테스트 통과

## 2026-11-15 T-017 폰 운영 검증

- 시험 일정에서 이동 시간이 변해도 준비·출발 알림이 각각 한 번만 전송되고 후속 실행에서는 dedup으로 걸러지는 것을 확인
- 카카오 대중교통 전환 후보에 동일 경로의 단계별 안내와 길찾기 링크 요구를 기록

## 2026-11-14 begonia 폰 운영 인계 및 T-017

- 폰 타이머를 운영 실행 경로로 문서화하고 GitHub Actions의 자동 `schedule`을 제거해 이중 실행 위험을 줄임
- 이동 시간 재계산과 무관하게 일정·시작 시각·알림 종류별 dedup 키를 고정하고, 향후 준비 단계 식별자 지원
- Routes API의 폰 실키·실제 일정 검증을 반영해 T-015 완료 처리
- GHA 중심 T-012·T-014는 대체 상태로 기록하고 T-009 차단 해제; 이동 시간 변동과 캘린더 일부 실패를 T-018·T-019로 등록
- T-016 카카오 대중교통 전환은 T-018 정책 결정 전까지 보류

## [미완료] Phase 1 MVP — 진행 중

### T-015 Google 이동 시간 Routes API 전환 구현 완료, 실키 검증 대기
- Directions API(Legacy) GET 호출을 Routes API `computeRoutes` POST로 교체(키는 헤더, FieldMask `routes.duration`)
- 이동 수단 매핑·duration 파싱 추가, 실패 시 캐시 → 30분 추정 동작 유지
- 단위 테스트 50개 통과

### 운영 점검
- 2026-08-17: GitHub Actions scheduled workflow inactivity 경고 대응을 위해 저장소 활동 기록 갱신

### T-014 외부 트리거 구현 준비 완료, 사용자 셋업 검증 대기
- GitHub `schedule:`을 매시간 백업 레이어로 낮추고 `workflow_dispatch`를 주 실행 경로로 유지
- cron-job.org에서 5분마다 `workflow_dispatch`를 호출하는 PAT 최소권한 셋업 가이드 추가
- 워크플로우 설정 회귀 테스트를 hourly backup schedule + manual trigger 기준으로 갱신

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
