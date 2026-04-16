# T-005-report — 알림 채널 라우팅 + 전송

**완료일**: 2026-04-16  
**담당**: Codex

---

## AC 결과

| AC | 결과 | 비고 |
|----|------|------|
| `core/notifier.py`의 공용 전송 함수 구현 | ✅ | `send_notifications()` 공용 진입점 구현 |
| `settings.yaml`의 `notification.enabled_channels`로 활성 채널 선택 가능 | ✅ | 기본값은 `discord`로 설정 |
| `discord`, `telegram`, `둘 다` 구성 지원 | ✅ | 리스트 기반 채널 선택 구조 적용 |
| Discord는 `DISCORD_WEBHOOK_URL` 환경변수로 전송 | ✅ | webhook POST 구현 |
| Telegram은 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 환경변수로 전송 | ✅ | Bot API `sendMessage` POST 구현 |
| 활성 채널에 따라 `main.py` 환경변수 검증이 조건부로 동작 | ✅ | Discord만 활성 시 Telegram 변수 미요구 |
| 공통 알림 메시지 포맷 구현 | ✅ | Discord/Telegram 공용 텍스트 포맷 사용 |
| 채널 하나가 실패해도 다른 채널 전송은 계속 시도 | ✅ | 채널별 `NotificationDelivery` 결과 수집 |
| 단위 테스트: `tests/test_notifier.py` 작성 | ✅ | notifier 테스트와 runtime config 테스트 추가 |

---

## 원래 기획과 달라진 점

- 단일 텔레그램 전송 대신, 향후 채널 추가를 고려한 다중 채널 라우팅 구조로 확장함

---

## 발생한 에러/이슈

- 기존 YAML fallback 파서는 block list를 지원하지 않아 기본 설정의 `enabled_channels`는 inline list 형식으로 저장함

---

## 다음 작업자에게 전달할 주의사항

- 유지할 것: 새 알림 채널은 `enabled_channels` 리스트와 채널별 sender 함수만 추가하는 구조를 유지하는 편이 안전함
- 주의할 것: 현재 `main.py`는 알림 전송 실패 시 종료 코드 1을 반환하므로, T-006 dedup 추가 시에도 실패 처리와 중복 방지 로직을 섞지 않아야 함
- 제거 예정: 없음
