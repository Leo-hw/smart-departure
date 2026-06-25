# smart-departure

Google Calendar 일정과 지도 API를 기반으로 당일 알림 계획을 계산하고, Discord webhook, Telegram 또는 둘 다로 알림을 보내는 스케줄링 worker입니다.

## Requirements

- Python 3.11+
- 필수 환경변수
  - `GOOGLE_SERVICE_ACCOUNT_JSON`
  - `GOOGLE_CALENDAR_IDS`
  - `GOOGLE_MAPS_API_KEY`
  - 자동차 길찾기 사용 시: `KAKAO_REST_API_KEY`
  - `HOME_ADDRESS`
- 채널별 환경변수
  - Discord 사용 시: `DISCORD_WEBHOOK_URL`
  - Telegram 사용 시: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

## Notification Channels

`shared/config/settings.yaml`의 `notification.enabled_channels`로 활성 채널을 선택합니다.

```yaml
notification:
  enabled_channels:
    - discord
    - telegram
```

- `discord`만 넣으면 Discord webhook만 사용합니다.
- `telegram`만 넣으면 Telegram만 사용합니다.
- 둘 다 넣으면 두 채널 모두 전송합니다.

## Local Run

1. 가상환경을 생성하고 활성화합니다.
2. 의존성을 설치합니다.
3. 환경변수를 설정합니다.
4. 엔트리포인트를 실행합니다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account"}'
export GOOGLE_CALENDAR_IDS='primary'
export GOOGLE_MAPS_API_KEY='your-google-maps-key'
export KAKAO_REST_API_KEY='your-kakao-rest-api-key'
export DISCORD_WEBHOOK_URL='your-discord-webhook-url'
export HOME_ADDRESS='서울시 강남구 테헤란로 123'
python3 main.py
```

Telegram도 함께 쓰려면 아래를 추가합니다.

```bash
export TELEGRAM_BOT_TOKEN='your-telegram-bot-token'
export TELEGRAM_CHAT_ID='your-telegram-chat-id'
```

정상 실행 시 `settings.yaml`을 로드하고, 당일 계획 수와 현재 due alert 수, 채널 전송 시도 수를 출력합니다.

`.env` 파일에 같은 값을 넣어도 로컬 실행 시 자동으로 읽습니다. 다만 이미 export된 값이 있으면 그 값을 우선합니다.

## Scheduling

- 당일 일정 계획은 `.runtime/schedule_today.json`에 저장됩니다.
- 기본값 `schedule.snapshot_ttl_minutes: 0`에서는 매 실행 캘린더를 다시 조회하고 계획을 재계산합니다.
- TTL을 양수로 설정하면 같은 날짜의 신선한 스냅샷만 해당 시간 동안 재사용합니다.
- 준비 알림은 `schedule.prep_minutes`, 출발 알림은 이동 시간과 버퍼 기준으로 계산됩니다.
- 놓친 출발 알림은 기본적으로 `schedule.departure_catchup_minutes: 45`까지 catch-up합니다.

## Dedup

- 전송 성공한 알림은 `.runtime/sent_alerts.json`에 기록됩니다.
- 같은 알림 키는 다시 전송하지 않으며, 의도적으로 봉인한 준비 알림도 `skipped`로 기록합니다.
- 일정 시작 60분 후에는 해당 dedup 기록을 자동으로 정리합니다.

## Deployment

두 배포 방식 모두 같은 `main.py`를 실행합니다.

### Oracle Crontab

- 배포 가이드는 [deploy/oracle_crontab.md](./deploy/oracle_crontab.md)에 정리되어 있습니다.
- 권장 주기: `*/30 * * * *`

### GitHub Actions

- 워크플로우는 [.github/workflows/departure_check.yml](./.github/workflows/departure_check.yml)에 추가되어 있습니다.
- GitHub Secrets에 환경변수를 넣고 외부 5분 트리거 또는 수동 실행으로 사용할 수 있습니다.
- 예약 실행은 GitHub Actions의 부하에 따라 지연되거나 일부 tick이 누락될 수 있습니다.
- 정시성이 필요하면 [외부 트리거 가이드](./deploy/external_trigger_setup.md)에 따라 cron-job.org에서 `workflow_dispatch`를 5분마다 호출합니다.
- `.runtime/`은 Actions cache로 다음 실행에 복원되어 dedup 상태를 유지합니다.
