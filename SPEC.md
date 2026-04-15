# smart-departure — 프로젝트 명세서

> Google Calendar 일정 + 지도 API 기반으로 출발 시각을 계산하고, 텔레그램으로 "지금 출발해!" 알림을 보내는 자동화 봇

---

## 1. 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 프로젝트명 | smart-departure |
| 목적 | 캘린더 일정의 장소와 이동 시간을 분석해, 출발해야 할 시점에 텔레그램 알림 전송 |
| 실행 환경 | Railway (분 단위 cron) |
| 언어 | Python 3.11 |
| 외부 의존성 | Google Calendar API, Google Maps API, Telegram Bot API |

---

## 2. 핵심 플로우

```
[매 시간 실행]
  ↓
Google Calendar → 향후 N시간 이내 장소 있는 일정 조회
  ↓
Maps API → 집 → 목적지 이동 시간 계산
  ↓
출발 시각 = 일정 시작 - 이동 시간 - 여유 시간(buffer)
  ↓
현재 시각이 출발 시각 ±window 이내이면 → 텔레그램 알림 전송
```

---

## 3. 디렉토리 구조

```
smart-departure/
├── .github/
│   └── workflows/           # (참고용 — 실제 실행은 Railway)
├── core/
│   ├── calendar_service.py  # Google Calendar 일정 조회
│   ├── maps_service.py      # 이동 시간 계산 (transport별 API 라우팅)
│   ├── departure_engine.py  # 출발 시각 계산 + 알림 판단
│   └── notifier.py          # 텔레그램 알림 전송
├── shared/
│   └── config/
│       ├── settings.yaml    # 사용자 설정 (집 주소, 기본 이동 수단, buffer 등)
│       └── transport_rules.py  # 이동 수단별 API 라우팅 규칙
├── tests/
│   ├── test_calendar_service.py
│   ├── test_maps_service.py
│   └── test_departure_engine.py
├── main.py                  # 진입점
├── requirements.txt
├── SPEC.md
├── CLAUDE.md
├── AGENTS.md
├── PIPELINE.md
├── CHANGELOG.md
└── ROADMAP.md
```

---

## 4. 사용자 설정 (settings.yaml)

```yaml
user:
  home_address: "서울시 OO구 OO동 OO"  # 환경변수 HOME_ADDRESS로 오버라이드 가능
  default_transport: "transit"           # transit / driving / walking

transport:
  transit:
    api: "google"
    buffer_minutes: 10      # 도착 후 여유 시간
  driving:
    api: "kakao"
    buffer_minutes: 15
  walking:
    api: "google"
    buffer_minutes: 5

schedule:
  lookahead_hours: 3        # 향후 몇 시간 이내 일정을 체크할지
  alert_window_minutes: 10  # 출발 시각 ±N분 이내이면 알림 발송
  dedup_ttl_minutes: 60     # 같은 일정 중복 알림 방지 TTL
```

캘린더 일정 설명란 오버라이드 (선택):
```
transport: driving
```

---

## 5. 이동 수단별 API 전략

| 이동 수단 | API | 이유 |
|-----------|-----|------|
| transit (대중교통) | Google Maps | 한국 지하철/버스 기본 지원 |
| driving (자동차) | 카카오 Maps | 한국 도로 정확도 우수 |
| walking (도보) | Google Maps | 충분한 정확도 |

확장 가능: 향후 네이버 Maps 추가 가능하도록 `maps_service.py`는 provider 추상화

---

## 6. 텔레그램 알림 포맷

```
🚀 출발할 시간이에요!

📅 일정: 스터디 모임
📍 장소: 강남구 역삼동 OO카페
🕐 시작: 오후 3:00
🚌 이동: 대중교통 약 35분
⏰ 출발: 오후 2:15 (지금!)

서두르세요 👟
```

---

## 7. 환경변수

| 변수명 | 설명 |
|--------|------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Google 서비스 계정 JSON 전체 문자열 |
| `GOOGLE_CALENDAR_IDS` | 쉼표 구분 캘린더 ID 목록 |
| `GOOGLE_MAPS_API_KEY` | Google Maps API 키 |
| `KAKAO_REST_API_KEY` | 카카오 REST API 키 |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 알림 수신 채팅 ID |
| `HOME_ADDRESS` | 집 주소 (settings.yaml 오버라이드) |

---

## 8. 에러 처리

| 상황 | 처리 방식 |
|------|----------|
| Calendar API 실패 | 재시도 3회 후 텔레그램 에러 알림 |
| Maps API 실패 | fallback: 이전 캐시 값 사용, 없으면 기본값 30분으로 계산 후 알림에 "(이동 시간 추정)" 표기 |
| 장소 없는 일정 | 조용히 스킵 |
| 중복 알림 | `.runtime/sent_alerts.json`에 TTL 기반 dedup |
| 텔레그램 전송 실패 | stderr 기록 후 종료 코드 1 |

---

## 9. 구현 단계

### Phase 1 — MVP
- T-001: 프로젝트 기반 세팅 (Railway + 환경변수 + main.py 뼈대)
- T-002: Google Calendar 연동 (장소 있는 일정 조회)
- T-003: Google Maps 대중교통 이동 시간 계산
- T-004: 출발 시각 계산 + 알림 판단 엔진
- T-005: 텔레그램 알림 전송
- T-006: 중복 알림 방지 (dedup)

### Phase 2 — 이동 수단 확장
- T-007: 카카오 Maps 자동차 길찾기 연동
- T-008: settings.yaml 기반 이동 수단 설정 + 캘린더 오버라이드

### Phase 3 — 품질
- T-009: 단위 테스트
- T-010: Railway 배포 자동화 + 모니터링
